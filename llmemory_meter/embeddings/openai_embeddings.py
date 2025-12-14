"""OpenAI embeddings provider."""

from typing import List
from llmemory_meter.embeddings import EmbeddingProvider


class OpenAIEmbeddings(EmbeddingProvider):
    """OpenAI embeddings provider using text-embedding-3-small by default.
    
    Cost: ~$0.00002 per 1K tokens (~$0.02 per 1K queries)
    """
    
    def __init__(self, model: str = "text-embedding-3-small"):
        """Initialize OpenAI embeddings provider.
        
        Args:
            model: OpenAI embedding model name
                - text-embedding-3-small (default, best price/performance)
                - text-embedding-3-large (highest quality)
                - text-embedding-ada-002 (legacy)
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Install with: pip install openai"
            )
        
        self.client = OpenAI()
        self.model = model
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        response = self.client.embeddings.create(
            input=[text],
            model=self.model
        )
        return response.data[0].embedding
    
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts in a single batch.
        
        This is much more efficient than calling get_embedding() multiple times.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        response = self.client.embeddings.create(
            input=texts,
            model=self.model
        )
        
        # Sort by index to ensure correct order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [d.embedding for d in sorted_data]

