# backend/services/orchestrator.py
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from backend.core.llm.context_builder import build_context
from backend.core.llm.intent_parser import build_config_from_llm_output, translate_policy
from backend.core.llm.reasoning_chain import run_reasoning_chain
from backend.services.simulation_service import run_simulation_job

load_dotenv()


def get_calib_data():
    from backend.storage.storage import load_artifact

    return load_artifact("calibration") or {}


def orchestrate_user_request(user_text: str) -> dict:
    """
    The 3-Agent Orchestration Pipeline (Backend Phase)

    Agent 1 (Router/Parser): Classifies intent. If simulate, extracts parameters.
    Agent 2 (Simulator/Reasoner): Runs Monte Carlo and generates JSON briefing.
    """
    # ── AGENT 1: Intent Routing ──────────────────────────────────────────────
    messages = [
        {
            "role": "system",
            "content": (
                'You are an intent router. Classify the user text as either "simulate" '
                "(if they are proposing a workplace policy change that explicitly affects workload, headcount, pay, schedule, or stress) "
                'or "chat" (for greetings, general questions, OR irrelevant policies like "paint the walls blue" or "serve bananas"). '
                'Return JSON strictly in this format: {"intent": "simulate" | "chat", "chat_response": "If chat, your response here (if an irrelevant policy, explain what factors you CAN simulate), else null"}'
            ),
        },
        {"role": "user", "content": user_text},
    ]

    api_key = os.getenv("GROQ_API_KEY")

    try:
        if api_key:
            client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            intent_json = json.loads(response.choices[0].message.content)
        else:
            # Fallback to local
            local_client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
            response = local_client.chat.completions.create(
                model="llama3.1:8b",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            intent_json = json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[Orchestrator] Intent routing failed: {e}. Defaulting to simulation.")
        intent_json = {"intent": "simulate"}

    if intent_json.get("intent") == "chat":
        return {
            "type": "chat",
            "response": intent_json.get(
                "chat_response", "I'm ready to simulate policies. What would you like to test?"
            ),
        }

    # ── AGENT 1: Policy Parameter Extraction ─────────────────────────────────
    calib_data = get_calib_data()
    context = build_context(calib_data)

    print("[Orchestrator] Intent is simulate. Extracting parameters...")
    raw_llm_json = translate_policy(user_text, context)

    if raw_llm_json.get("unrecognized_intent"):
        return {
            "type": "chat",
            "response": "I cannot parse a valid workplace policy parameter change from this input. Please provide a clear HR, org structure, or compensation policy to simulate.",
        }

    config, justification = build_config_from_llm_output(raw_llm_json, calib_data, user_text)

    # Escape Hatch: Did the LLM confidently map this policy?
    if justification.get("mapping_confidence", "high").lower() == "low":
        return {
            "type": "chat",
            "response": "I see you're proposing a valid policy change, but I'm not confident about how it explicitly impacts workload, schedule, or stress parameters. Could you clarify how this policy would logically affect the day-to-day operations of the team?",
        }

    # ── AGENT 2: Simulation Engine ───────────────────────────────────────────
    print("[Orchestrator] Generating Monte Carlo simulation...")
    runs = 10
    sim_result = run_simulation_job(policy_name="custom", runs=runs, policy_config=config.__dict__)

    # inject the config into sim_result for the reasoning chain to consume
    sim_result["config"] = config.__dict__
    sim_result["summary"]["policy_name"] = "Custom Executive Policy"

    # ── AGENT 2: Analytical Reasoner ──────────────────────────────────────────
    print("[Orchestrator] Running Agent 2 Reasoning Chain...")
    briefing = run_reasoning_chain(sim_result, config.__dict__, user_text)

    return {
        "type": "simulation",
        "briefing": briefing,  # JSON to be sent to frontend Agent 3
        "sim_result": sim_result,  # Raw data for frontend charts
        "config": config.__dict__,
        "justification": justification,
    }
