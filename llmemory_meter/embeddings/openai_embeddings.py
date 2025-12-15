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
        
        # Validate inputs - OpenAI API rejects empty strings, None, or non-strings
        validated_texts = []
        for i, text in enumerate(texts):
            if text is None:
                print(f"⚠️  WARNING: OpenAI embeddings received None at index {i}")
                validated_texts.append("[empty]")  # Use placeholder text
            elif not isinstance(text, str):
                print(f"⚠️  WARNING: OpenAI embeddings received non-string at index {i}: {type(text)}")
                validated_texts.append(str(text) if text else "[empty]")
            elif not text.strip():
                print(f"⚠️  WARNING: OpenAI embeddings received empty/whitespace string at index {i}")
                validated_texts.append("[empty]")  # Use placeholder text
            else:
                validated_texts.append(text)
        
        try:
            response = self.client.embeddings.create(
                input=validated_texts,
                model=self.model
            )
            
            # Sort by index to ensure correct order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [d.embedding for d in sorted_data]
        except Exception as e:
            print(f"\n❌ OpenAI API Error Details:")
            print(f"   Error: {e}")
            print(f"   Input type: {type(validated_texts)}")
            print(f"   Input length: {len(validated_texts)}")
            print(f"   First 3 inputs:")
            for i, text in enumerate(validated_texts[:3]):
                print(f"      [{i}] type={type(text)}, len={len(text) if text else 0}, preview='{str(text)[:50]}'")
            raise

