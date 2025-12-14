"""Local sentence-transformers embeddings provider."""

from typing import List
from llmemory_meter.embeddings import EmbeddingProvider


class LocalEmbeddings(EmbeddingProvider):
    """Local embeddings provider using sentence-transformers.
    
    Cost: $0 (runs locally, no API calls)
    Privacy: Data never leaves your machine
    """
    
    def __init__(self, model: str = "all-mpnet-base-v2"):
        """Initialize local embeddings provider.
        
        Args:
            model: Sentence-transformers model name
                - all-mpnet-base-v2 (default, best quality, 768 dims, 420M params)
                - all-MiniLM-L6-v2 (fastest, 384 dims, 22M params)
                - all-MiniLM-L12-v2 (balanced, 384 dims, 33M params)
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers package not installed. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model = SentenceTransformer(model)
        self.model_name = model
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        embedding = self.model.encode([text], show_progress_bar=False)
        return embedding[0].tolist()
    
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts in a single batch.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        embeddings = self.model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        
        return embeddings.tolist()

