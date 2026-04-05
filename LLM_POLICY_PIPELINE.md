# LLM Policy Translation Pipeline

This document outlines the end-to-end architecture for safely translating raw natural language user inputs into deterministic, stable simulation parameters.

The core philosophy of this pipeline is **Multiplier-Based Translation**: LLMs are terrible at guessing absolute mathematical constants for complex systems, but excel at determining relative semantic magnitude (e.g., "This policy makes things 5x worse than normal"). By abstracting away the underlying `calibration.json` absolute numbers, the LLM prompt never has to change across different datasets.

---

## Stage 1: User Input
Accept raw, unstructured text.
*Example: "4 day work week", "we're doing layoffs next quarter", "give everyone flexible hours".*

---

## Stage 2: Intent Disambiguation & Locking
**Objective:** Prevent silent failures by forcing the LLM to clarify ambiguous inputs before any math is calculated.

> [!CAUTION]
> **Disambiguation Paralysis Risk**
> LLMs will ask annoying pedantic questions if left unconstrained. You must strictly define what matters.

**Prompt constraint:** 
"Only ask for clarification if the input is ambiguous regarding these specific axes:
1. **Pay compensation** (e.g. same pay vs pay cut)
2. **Output expectations** (e.g. compressed hours vs reduced quotas)
3. **Duration** (e.g. temporary freeze vs permanent policy)
DO NOT ask about scheduling specifics, legal constraints, or implementation details."

*Outcome: A "locked" intent string.*

---

## Stage 3: Load Calibration Anchors
Extract only the essential bounds from the background dataset's `calibration.json`. **Do not dump the entire JSON into the prompt**, as the noise will degrade the LLM's reasoning.

```python
anchors = {
    "behavior_stress_gain_rate": calib["behavior_stress_gain_rate"],  # e.g., 0.01
    "motivation_recovery_rate":  calib["motivation_recovery_rate"],   # e.g., 0.0079
    "shockwave_stress_factor":   calib["shockwave_stress_factor"],    # e.g., 0.2489
    "annual_attrition_rate":     calib["annual_attrition_rate"],      # e.g., 0.1612
    "avg_burnout_limit":         calib["avg_burnout_limit"],          # e.g., 0.5783
}
```

---

## Stage 4: LLM Translation via Multipliers & CoT
This is the core translation prompt. 

> [!IMPORTANT]
> **Chain-of-Thought JSON Construction**
> The `_justification` field MUST be the first key in the JSON object. LLMs generate tokens sequentially. Forcing the LLM to write out its justification logic first serves as internal Chain-of-Thought (CoT), resulting in far more reliable multipliers below it.

**System Prompt Structure:**

* **Section A (Semantics):** Define multipliers based on the injected anchors.
  * *`stress_gain_rate`*: 0.5x = calm/remote, 1.0x = baseline, 5.0x = mass overload.
  * *`motivation_decay_rate`*: 0.5x = highly rewarding, 1.0x = baseline, 8.0x = active layoff survivors.
* **Section B (Few-Shot):** Provide existing policies as examples.
  * *"Company doing 15% layoffs" -> stress_gain_rate = 5.5x, layoff_ratio = 0.15*
* **Section C (Strict JSON Schema):**
  ```json
  {
    "_justification": {
      "overall_logic": "Compressing the work week without changing output means the workload density increases, but the extra day off provides significant schedule relief...",
      "workload_multiplier": "same output compressed \u2192 1.0x, no change",
      "stress_gain_rate": "0.8x baseline \u2014 schedule relief reduces accumulation"
    },
    "workload_multiplier": 1.0,
    "stress_gain_rate": 0.8,
    "motivation_decay_rate": 0.6,
    "shock_factor": 0.0,
    "hiring_active": true,
    "layoff_ratio": 0.0,
    "duration_months": 12,
    "overtime_bonus": 0.0,
    "wlb_boost": 0.4
  }
  ```

---

## Stage 5: Pydantic Validation & Clamping
Convert the multipliers into absolute floats used by the engine, applying dataset-specific clamps.

```python
PARAM_BOUNDS = {
    "workload_multiplier":   (0.5, 1.6),
    "stress_gain_rate":      (0.4 * calib["behavior_stress_gain_rate"],
                              9.0 * calib["behavior_stress_gain_rate"]),
    # ...
}
```

> [!WARNING]
> **Global Severity Verification**
> Before handoff, the validation layer must check for compounding extremes. If the LLM generates a config where *mutually compounding* variables (e.g. stress, shock, and motivation decay) are all pushed to their absolute maximum limits, it will instantly crash the simulated company. Reject and retry the prompt if `global_severity_score > MAX_THRESHOLD`.

---

## Stage 6: The Trust Layer (Human-in-the-Loop)
Present the translated parameters and the generated `_justification` fields to the user for a final sign-off.

> [!NOTE]
> **Handling Clamped Values Gracefully**
> If Stage 5 clamped a value (e.g. the LLM hallucinated `15.0x` but Pydantic clamped it to `9.0x`), the UI **must** inform the user. 
> *Incorrect UX:* Showing the user a justification tailored for 15.0x while silently running 9.0x.
> *Correct UX:* Append a system note to the justification: `"[System note: Value clamped to maximum 9.0x for engine runtime stability against burnout cascade.]"`

---

## Stages 7 & 8: Simulation Handoff
Hand over the `SimulationConfig` to `run_simulation()` and `behavior_engine.py`. The LLM has zero involvement past this point, ensuring deterministic and secure execution loops.
