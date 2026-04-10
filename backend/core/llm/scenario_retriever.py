# backend/core/llm/scenario_retriever.py
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from backend.core.llm.extended_scenarios import EXTENDED_SCENARIOS

class ScenarioRetriever:
    def __init__(self):
        # We initialized the corpus queries when the class is loaded
        self.scenarios = EXTENDED_SCENARIOS
        self.queries = [s["query"] for s in self.scenarios]
        
        # Initialize and fit TF-IDF vectorizer
        # We use standard English stop words to filter out noise
        self.vectorizer = TfidfVectorizer(stop_words='english')
        
        # If there are no scenarios, we don't fit
        if self.queries:
            self.tfidf_matrix = self.vectorizer.fit_transform(self.queries)
        else:
            self.tfidf_matrix = None

    def get_top_k_scenarios(self, user_text: str, k: int = 2) -> str:
        """
        Calculates cosine similarity between user_text and all scenarios.
        Returns the top `k` scenarios formatted as a string block.
        """
        if self.tfidf_matrix is None or not self.queries:
            return ""

        # Transform user input into the TF-IDF space
        user_vec = self.vectorizer.transform([user_text])
        
        # Compute similarities
        similarities = cosine_similarity(user_vec, self.tfidf_matrix).flatten()
        
        # Get the indices of the top k highest similarity scores
        # argsort() returns ascending, so we reverse it with [::-1]
        top_k_indices = similarities.argsort()[-(k):][::-1]
        
        # Build the resulting text
        result_text = ""
        for idx in top_k_indices:
            # Optionally we could filter by a minimum similarity threshold,
            # but returning *something* structurally similar is always helpful.
            if similarities[idx] > 0.0: 
                result_text += self.scenarios[idx]["content"] + "\n\n"
            else:
                # If there's 0 overlap, maybe just pick a fallback or nothing.
                # Returning the top match regardless provides safety.
                pass
                
        # If no similarity (complete orthogonal query), it will just return empty or 0 threshold skip
        # We will guarantee at least one element just to show format if needed.
        if not result_text.strip() and k > 0 and len(self.scenarios) > 0:
             result_text = self.scenarios[0]["content"] + "\n\n"

        return result_text.strip()
