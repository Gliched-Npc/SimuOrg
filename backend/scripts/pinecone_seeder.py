import os
import sys

from dotenv import load_dotenv

# Add project root to sys.path to allow importing backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from pinecone import Pinecone

from backend.core.llm.extended_scenarios import EXTENDED_SCENARIOS


def main():
    load_dotenv()

    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME", "simuorg-scenarios")

    if not api_key:
        print("ERROR: PINECONE_API_KEY environment variable not set.")
        return

    print(f"Connecting to Pinecone and index '{index_name}'...")
    pc = Pinecone(api_key=api_key)

    try:
        index = pc.Index(index_name)
    except Exception as e:
        print(f"ERROR: Could not find index '{index_name}'. Did you create it? {e}")
        return

    print(f"Loaded {len(EXTENDED_SCENARIOS)} scenarios to process.")

    # We will upload in batches of 96 (Pinecone inference recommendation)
    batch_size = 90
    for i in range(0, len(EXTENDED_SCENARIOS), batch_size):
        batch = EXTENDED_SCENARIOS[i : i + batch_size]
        print(f"Processing batch {i//batch_size + 1}...")

        # Prepare inputs for the embedding model
        inputs = [scenario["query"] for scenario in batch]

        try:
            # Generate embeddings using Pinecone Serverless Inference
            embedding_results = pc.inference.embed(
                model="llama-text-embed-v2",
                inputs=inputs,
                parameters={"input_type": "passage", "truncate": "END"},
            )
        except Exception as e:
            print(f"ERROR: Failed to generate embeddings. Check your API key. {e}")
            return

        vectors = []
        for j, record in enumerate(embedding_results):
            # The API returns a 'values' attribute on each embedding block
            scenario = batch[j]
            vector_data = {
                "id": f"scenario_{i + j}",
                "values": record.values,
                "metadata": {"query": scenario["query"], "content": scenario["content"]},
            }
            vectors.append(vector_data)

        # Upsert the vectors to the index
        print(f"Upserting {len(vectors)} vectors to Pinecone...")
        index.upsert(vectors=vectors)

    print("Database seeding completed successfully!")


if __name__ == "__main__":
    main()
