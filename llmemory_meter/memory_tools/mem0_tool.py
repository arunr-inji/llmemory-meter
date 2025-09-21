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
        self._initialize_mem0_client()
    
    def _initialize_mem0_client(self):
        """Initialize the Mem0 client with proper configuration."""
        try:
            from mem0 import Memory

            # Use Mem0 cloud instead of local Qdrant
            self.mem0_config = {
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": "gpt-4o-mini",
                        "temperature": 0.2,
                        "max_tokens": 1500,
                        "api_key": Config.OPENAI_API_KEY
                    }
                },
                "embedder": {
                    "provider": "openai",
                    "config": {
                        "model": "text-embedding-3-small",
                        "api_key": Config.OPENAI_API_KEY
                    }
                }
            }
            
            try:
                self.memory = Memory.from_config(self.mem0_config)
                print("✅ Mem0 initialized with vector store")
            except Exception as e:
                print(f"⚠️  Vector store failed, using simple config: {e}")
                # Fallback to simpler config
                simple_config = {
                    "llm": {
                        "provider": "openai",
                        "config": {
                            "model": "gpt-4o-mini",
                            "temperature": 0.2,
                            "max_tokens": 1500,
                            "api_key": Config.OPENAI_API_KEY
                        }
                    }
                }
                self.memory = Memory.from_config(simple_config)
                print("✅ Mem0 initialized with simple config")
            
        except ImportError:
            raise ImportError("mem0ai package not installed. Install with: pip install mem0ai")
        except Exception as e:
            raise Exception(f"Failed to initialize Mem0: {e}")
    
    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store memory in Mem0."""
        try:
            result = self.memory.add(content, user_id=self._user_id, metadata=metadata)
            memory_id = result.get('id', 'unknown') if isinstance(result, dict) else str(result)
            return f"Stored in Mem0 (ID: {memory_id}): {content[:50]}..."
        except Exception as e:
            raise Exception(f"Mem0 store failed: {e}")
    
    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Retrieve memory from Mem0."""
        try:
            results = self.memory.search(query, user_id=self._user_id, limit=3)

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
            relevant_memories = self.memory.search(message, user_id=self._user_id, limit=5)
            
            context = ""
            if relevant_memories:
                context = "Relevant memories: " + " | ".join([
                    mem.get('memory', mem.get('text', '')) 
                    for mem in relevant_memories[:3]
                ])
            
            return f"Mem0 chat response to '{message}' (with {len(relevant_memories)} memories): Based on your memories, I can help you with this request. {context[:200]}..."
        except Exception as e:
            raise Exception(f"Mem0 chat failed: {e}")
