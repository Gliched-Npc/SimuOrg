# backend/core/llm/scenario_retriever.py
import os
from pinecone import Pinecone
from backend.core.llm.extended_scenarios import EXTENDED_SCENARIOS

class ScenarioRetriever:
    def __init__(self):
        self.api_key = os.getenv("PINECONE_API_KEY")
        self.index_name = os.getenv("PINECONE_INDEX_NAME", "simuorg-scenarios")
        
        if self.api_key:
            self.pc = Pinecone(api_key=self.api_key)
            self.index = self.pc.Index(self.index_name)
        else:
            print("WARNING: PINECONE_API_KEY not found. RAG will fallback to static examples.")
            self.pc = None
            self.index = None

    def get_top_k_scenarios(self, user_text: str, k: int = 2) -> str:
        """
        Calculates semantic similarity between user_text and all scenarios via Pinecone.
        Returns the top `k` scenarios formatted as a string block.
        """
        # Fallback if unconfigured
        if not self.pc or not self.index:
            return EXTENDED_SCENARIOS[0]["content"] + "\n\n"

        try:
            # 1. Generate the semantic dense vector for the user query
            embedding = self.pc.inference.embed(
                model="llama-text-embed-v2",
                inputs=[user_text],
                parameters={"input_type": "query"}
            )
            query_vector = embedding[0].values
            
            # 2. Search Pinecone
            response = self.index.query(
                vector=query_vector,
                top_k=k,
                include_metadata=True
            )
            
            result_text = ""
            for match in response.matches:
                # Minimum threshold check can go here if needed, Pinecone scores range up to 1.0
                if "content" in match.metadata:
                    result_text += match.metadata["content"] + "\n\n"
                    
            if not result_text.strip():
                 result_text = EXTENDED_SCENARIOS[0]["content"] + "\n\n"
                 
            return result_text.strip()

        except Exception as e:
            print(f"ERROR: Pinecone RAG query failed: {e}")
            # Fallback guarantee to ensure pipeline doesn't break
            return EXTENDED_SCENARIOS[0]["content"]

