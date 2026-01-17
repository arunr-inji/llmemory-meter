"""Accuracy evaluator using semantic similarity."""

from typing import List, Optional
import numpy as np


class AccuracyEvaluator:
    """Evaluates accuracy using semantic similarity between responses and ground truth.
    
    Uses cosine similarity between embeddings to measure how close a response is
    to the expected answer. Supports multiple embedding providers (OpenAI, local).
    """
    
    def __init__(self, provider: str = "openai", model: Optional[str] = None):
        """Initialize accuracy evaluator with an embedding provider.
        
        Args:
            provider: Embedding provider to use ("openai" or "local")
            model: Optional model name (uses provider default if not specified)
                - OpenAI: "text-embedding-3-small" (default), "text-embedding-3-large"
                - Local: "all-mpnet-base-v2" (default), "all-MiniLM-L6-v2", etc.
        
        Raises:
            ValueError: If provider is not supported
        """
        if provider == "openai":
            from llmemory_meter.embeddings.openai_embeddings import OpenAIEmbeddings
            self.embedder = OpenAIEmbeddings(model or "text-embedding-3-small")
        elif provider == "local":
            from llmemory_meter.embeddings.local_embeddings import LocalEmbeddings
            self.embedder = LocalEmbeddings(model or "all-mpnet-base-v2")
        else:
            raise ValueError(f"Unknown embedding provider: {provider}. Use 'openai' or 'local'.")
        
        self.provider = provider
    
    def evaluate_single(self, response: str, ground_truth: str) -> float:
        """Evaluate accuracy for a single response.
        
        Args:
            response: The tool's response
            ground_truth: The expected answer
            
        Returns:
            Cosine similarity score between 0.0 and 1.0
            Returns None if no ground truth (store steps)
            Returns 0.0 if empty response with ground truth (failure)
        """
        # Skip if no ground truth (store steps don't have expected answers)
        if not ground_truth or not ground_truth.strip():
            return None
        
        # Empty response when answer is expected = FAILURE
        if not response or not response.strip():
            return 0.0
        
        # Get embeddings
        embeddings = self.embedder.get_embeddings_batch([response, ground_truth])
        
        # Calculate cosine similarity
        return self._cosine_similarity(embeddings[0], embeddings[1])
    
    def evaluate_batch(self, 
                      responses: List[str], 
                      ground_truths: List[str]) -> List[Optional[float]]:
        """Evaluate accuracy for a batch of responses (efficient).
        
        This is much more efficient than calling evaluate_single() multiple times
        because it batches all embedding API calls.
        
        Args:
            responses: List of tool responses
            ground_truths: List of expected answers (can contain None values)
            
        Returns:
            List of accuracy scores (None for steps without ground truth)
        """
        if len(responses) != len(ground_truths):
            raise ValueError("responses and ground_truths must have same length")
        
        # Filter out steps without ground truth
        valid_indices = []
        valid_texts = []
        
        # Initialize scores with None (for steps without ground truth)
        scores = [None] * len(responses)
        
        for i, (response, gt) in enumerate(zip(responses, ground_truths)):
            # Only evaluate steps with ground truth (retrieve/chat steps)
            if gt is not None and gt.strip():
                # Empty response when answer is expected = FAILURE (score 0.0)
                if not response or not response.strip():
                    print(f"⚠️  WARNING: Step {i} has empty response but has ground truth!")
                    print(f"   Ground truth: '{gt[:50]}...'")
                    print(f"   Response: '{response}'")
                    print(f"   Scoring as 0.0 (failure to retrieve/respond)")
                    scores[i] = 0.0  # Failure score instead of None
                    continue
                
                valid_indices.append(i)
                valid_texts.extend([response, gt])
        
        # If no valid pairs to embed, return scores (with 0.0 for empty responses)
        if not valid_texts:
            return scores
        
        # Batch embed everything at once (efficient!)
        embeddings = self.embedder.get_embeddings_batch(valid_texts)
        
        # Calculate similarities for non-empty responses
        for j, idx in enumerate(valid_indices):
            response_emb = embeddings[j * 2]
            gt_emb = embeddings[j * 2 + 1]
            similarity = self._cosine_similarity(response_emb, gt_emb)
            scores[idx] = similarity
        
        return scores
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First embedding vector
            vec2: Second embedding vector
            
        Returns:
            Cosine similarity between 0.0 (completely different) and 1.0 (identical)
        """
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        
        # Avoid division by zero
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0

        return float(dot_product / (norm_v1 * norm_v2))


class ExactMatchEvaluator:
    """Evaluates accuracy using exact/partial string matching.

    Complements AccuracyEvaluator for tasks requiring precise answers
    (codes, numbers, key-value pairs) where embedding similarity is too loose.
    """

    def __init__(self, match_type: str = "exact"):
        """Initialize with match type.

        Args:
            match_type: One of "exact", "exact_case_insensitive", "contains", "regex"

        Raises:
            ValueError: If match_type is not supported
        """
        valid_types = ["exact", "exact_case_insensitive", "contains", "regex"]
        if match_type not in valid_types:
            raise ValueError(f"match_type must be one of {valid_types}, got: {match_type}")
        self.match_type = match_type

    def evaluate_single(self, response: str, ground_truth: str,
                       match_type: Optional[str] = None) -> Optional[float]:
        """Evaluate accuracy for a single response.

        Args:
            response: The tool's response
            ground_truth: The expected answer
            match_type: Override instance match_type for this evaluation

        Returns:
            Binary score: 1.0 (match) or 0.0 (no match)
            Returns None if no ground truth (store steps)
        """
        # Handle missing ground truth (store steps)
        if not ground_truth or not ground_truth.strip():
            return None

        # Handle empty response
        if not response or not response.strip():
            return 0.0

        # Determine which match type to use
        match_type = match_type or self.match_type

        # Route to appropriate match function
        if match_type == "exact":
            matched = self._exact_match(response, ground_truth)
        elif match_type == "exact_case_insensitive":
            matched = self._exact_case_insensitive_match(response, ground_truth)
        elif match_type == "contains":
            matched = self._contains_match(response, ground_truth)
        elif match_type == "regex":
            matched = self._regex_match(response, ground_truth)
        else:
            raise ValueError(f"Unknown match_type: {match_type}")

        return 1.0 if matched else 0.0

    def evaluate_batch(self, responses: List[str], ground_truths: List[str],
                      match_types: Optional[List[str]] = None) -> List[Optional[float]]:
        """Evaluate accuracy for a batch of responses.

        Note: Unlike embedding evaluation, exact matching doesn't benefit from batching
        since there are no API calls to optimize. This method exists for API consistency
        with AccuracyEvaluator.

        Args:
            responses: List of tool responses
            ground_truths: List of expected answers
            match_types: Optional per-response match type overrides

        Returns:
            List of binary scores (None for steps without ground truth)
        """
        if match_types is None:
            match_types = [None] * len(responses)

        results = []
        for response, ground_truth, match_type in zip(responses, ground_truths, match_types):
            score = self.evaluate_single(response, ground_truth, match_type)
            results.append(score)

        return results

    def _exact_match(self, response: str, ground_truth: str) -> bool:
        """Case-sensitive exact match after stripping whitespace."""
        return response.strip() == ground_truth.strip()

    def _exact_case_insensitive_match(self, response: str, ground_truth: str) -> bool:
        """Case-insensitive exact match after stripping whitespace."""
        return response.strip().lower() == ground_truth.strip().lower()

    def _contains_match(self, response: str, ground_truth: str) -> bool:
        """Check if ground_truth substring appears in response (case-insensitive)."""
        return ground_truth.strip().lower() in response.strip().lower()

    def _regex_match(self, response: str, pattern: str) -> bool:
        """Check if response matches regex pattern.

        Includes timeout protection against ReDoS attacks.
        """
        import re
        import signal

        try:
            # Compile pattern
            compiled = re.compile(pattern.strip())

            # Set timeout (1 second)
            def timeout_handler(_signum, _frame):
                raise TimeoutError("Regex matching timeout")

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(1)

            try:
                match = compiled.search(response.strip()) is not None
            finally:
                signal.alarm(0)  # Cancel timeout

            return match

        except re.error as e:
            print(f"Warning: Invalid regex pattern '{pattern}': {e}")
            return False
        except TimeoutError:
            print(f"Warning: Regex matching timeout for pattern '{pattern}'")
            return False
        except Exception as e:
            print(f"Warning: Regex matching failed: {e}")
            return False

