"""
Mem0 Memory Tool Implementation

Provides integration with Mem0 AI memory system.
"""

import asyncio
from typing import Dict, Any, Optional

from llmemory_meter.memory_tools.base import MemoryTool
from llmemory_meter.config_parser import Config


class Mem0Tool(MemoryTool):
    """Mem0 memory tool implementation with real API calls."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("mem0", config)
        
        # Require API keys
        if not Config.MEM0_API_KEY:
            raise ValueError("MEM0_API_KEY not found in environment variables")
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY required for Mem0 (underlying LLM)")
        
        self.api_key = Config.MEM0_API_KEY
        self._user_id = self.config.get("user_id", "benchmark_user")
        
        # Get LLM provider from config (default to openai)
        self.llm_provider = self.config.get("llm_provider", "openai")
        
        # Validate required API key for the chosen LLM provider
        if self.llm_provider == "openai" and not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY required for Mem0 with OpenAI LLM")
        elif self.llm_provider == "gemini":
            if not Config.GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY required for Mem0 with Gemini LLM")
            if not Config.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY also required for embeddings (even with Gemini LLM)")
        
        self._initialize_mem0_client()
    
    def _initialize_mem0_client(self):
        """Initialize the Mem0 client with proper configuration."""
        try:
            from mem0 import Memory
            
            # Get LLM configuration from settings
            llm_config = self.config.get("llm_config", {})
            
            # Configure LLM based on provider
            if self.llm_provider == "gemini":
                llm_provider_config = {
                    "provider": "gemini",
                    "config": {
                        "model": llm_config.get("model", "gemini-2.0-flash-001"),
                        "temperature": llm_config.get("temperature", 0.2),
                        "max_tokens": llm_config.get("max_tokens", 2000),
                        "top_p": llm_config.get("top_p", 1.0),
                        "api_key": Config.GOOGLE_API_KEY
                    }
                }
            else:  # default to openai
                llm_provider_config = {
                    "provider": "openai",
                    "config": {
                        "model": llm_config.get("model", "gpt-4o-mini"),
                        "temperature": llm_config.get("temperature", 0.2),
                        "max_tokens": llm_config.get("max_tokens", 1500),
                        "api_key": Config.OPENAI_API_KEY
                    }
                }
            
            # Build the complete Mem0 configuration
            self.mem0_config = {
                "llm": llm_provider_config,
                "embedder": {
                    "provider": "openai",
                    "config": {
                        "model": "text-embedding-3-small",
                        "api_key": Config.OPENAI_API_KEY
                    }
                }
            }
            
            # Add vector store configuration if provided
            vector_store_config = self.config.get("vector_store")
            if vector_store_config:
                if vector_store_config.get("provider") == "qdrant":
                    self.mem0_config["vector_store"] = {
                        "provider": "qdrant",
                        "config": {
                            "collection_name": vector_store_config.get("collection_name", "llmemory_benchmarks"),
                            "host": vector_store_config.get("host", "localhost"),
                            "port": vector_store_config.get("port", 6333),
                        }
                    }
            
            # Initialize Mem0 with the complete configuration
            try:
                self.memory = Memory.from_config(self.mem0_config)
                # Mem0 initialized successfully
            except Exception as e:
                raise Exception(f"Failed to initialize Mem0: {e}")
            
        except ImportError:
            raise ImportError("mem0ai package not installed. Install with: pip install mem0ai")
        except Exception as e:
            raise Exception(f"Failed to initialize Mem0: {e}")
    
    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store memory in Mem0."""
        try:
            # Run in a thread-safe manner by using run_in_executor
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._sync_add, content, metadata)
            memory_id = result.get('id', 'unknown') if isinstance(result, dict) else str(result)
            return f"Stored in Mem0 (ID: {memory_id}): {content[:50]}..."
        except Exception as e:
            raise Exception(f"Mem0 store failed: {e}")
    
    def _sync_add(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Synchronous wrapper for Mem0 add operation with fresh instance."""
        # Create a new Mem0 instance for this thread to avoid SQLite conflicts
        from mem0 import Memory
        fresh_memory = Memory.from_config(self.mem0_config)
        return fresh_memory.add(content, user_id=self._user_id, metadata=metadata)
    
    def _sync_search(self, query: str, metadata: Optional[Dict[str, Any]] = None):
        """Synchronous wrapper for Mem0 search operation with fresh instance."""
        # Create a new Mem0 instance for this thread to avoid SQLite conflicts
        from mem0 import Memory
        fresh_memory = Memory.from_config(self.mem0_config)
        return fresh_memory.search(query, user_id=self._user_id, limit=3)
    
    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Retrieve memory from Mem0."""
        try:
            # Run in a thread-safe manner by using run_in_executor
            import asyncio
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, self._sync_search, query, metadata)

            # Handle different response formats
            if isinstance(results, dict):
                results = results.get('results', [])

            if results and hasattr(results, '__iter__'):
                memories = []
                # Safely iterate through results
                for result in list(results)[:3]:
                    if isinstance(result, dict):
                        memory_text = result.get('memory', result.get('text', 'No content'))
                        score = result.get('score', 0)
                        memories.append(f"[Score: {score:.3f}] {memory_text}")

                if memories:
                    return f"Retrieved from Mem0 for '{query}': " + " | ".join(memories)

            return f"No memories found in Mem0 for query: '{query}'"
        except Exception as e:
            raise Exception(f"Mem0 retrieve failed: {e}")
    
    async def chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Chat with Mem0 memory context."""
        try:
            # Use thread-safe search
            import asyncio
            loop = asyncio.get_event_loop()
            search_results = await loop.run_in_executor(None, self._sync_search, message, metadata)
            
            # Handle different response formats
            memories = []
            if isinstance(search_results, dict) and 'results' in search_results:
                memories = search_results['results'][:3]  # Take top 3
            elif isinstance(search_results, list):
                memories = search_results[:3]
            
            context = ""
            if memories:
                memory_texts = []
                for mem in memories:
                    if isinstance(mem, dict):
                        memory_text = mem.get('memory', mem.get('text', str(mem)))
                        memory_texts.append(memory_text)
                context = "Relevant memories: " + " | ".join(memory_texts)
            
            return f"Mem0 chat response to '{message}' (with {len(memories)} memories): Based on your memories, I can help you with this request. {context[:200]}..."
        except Exception as e:
            raise Exception(f"Mem0 chat failed: {e}")
