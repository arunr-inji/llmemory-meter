"""
OpenAI Memory Tool Implementation

Provides integration with OpenAI's memory capabilities.
"""

import asyncio
import time
from typing import Dict, Any, Optional

from .base import MemoryTool
from ..config import Config


class OpenAIMemoryTool(MemoryTool):
    """OpenAI Memory tool implementation with real API calls."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("openai_memory", config)
        self.api_key = Config.OPENAI_API_KEY
        if not self.api_key:
            print("⚠️  OPENAI_API_KEY not found - using mock implementation")
            self._use_mock = True
        else:
            self._use_mock = False
        
        if not self._use_mock:
            self._initialize_openai_client()
        
        # Simple in-memory storage for this demo (in production, use persistent storage)
        self.stored_memories = []
        self.conversation_history = []
    
    def _initialize_openai_client(self):
        """Initialize the OpenAI client."""
        try:
            import openai
            self.client = openai.AsyncOpenAI(api_key=self.api_key)
            self.model = self.config.get("model", "gpt-4o-mini")
            print("✅ OpenAI client initialized")
        except ImportError:
            print("⚠️  openai package not installed - using mock implementation")
            self._use_mock = True
        except Exception as e:
            print(f"⚠️  Failed to initialize OpenAI: {e} - using mock implementation")
            self._use_mock = True
    
    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store memory using OpenAI (simulated with in-memory storage)."""
        if self._use_mock:
            await asyncio.sleep(0.05)
            return f"[MOCK] Stored in OpenAI Memory: {content[:50]}..."
        
        try:
            # Store the memory with timestamp and metadata
            memory_entry = {
                "content": content,
                "timestamp": time.time(),
                "metadata": metadata or {}
            }
            self.stored_memories.append(memory_entry)
            
            # Use OpenAI to create a summary/embedding for better retrieval
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Create a concise summary of this information for memory storage:"},
                    {"role": "user", "content": content}
                ],
                max_tokens=100,
                temperature=0.1
            )
            
            summary = response.choices[0].message.content
            memory_entry["summary"] = summary
            
            return f"Stored in OpenAI Memory: {content[:50]}... (Summary: {summary[:30]}...)"
        except Exception as e:
            raise Exception(f"OpenAI store failed: {e}")
    
    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Retrieve memory using OpenAI."""
        if self._use_mock:
            await asyncio.sleep(0.1)
            return f"[MOCK] Retrieved from OpenAI Memory for query '{query}': [mock response]"
        
        try:
            if not self.stored_memories:
                return f"No memories stored yet for query: '{query}'"
            
            # Use OpenAI to find the most relevant memories
            memory_context = "\n".join([
                f"Memory {i+1}: {mem['content']}" 
                for i, mem in enumerate(self.stored_memories[-10:])  # Last 10 memories
            ])
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"Based on these stored memories, answer the query. Memories:\n{memory_context}"},
                    {"role": "user", "content": query}
                ],
                max_tokens=200,
                temperature=0.2
            )
            
            answer = response.choices[0].message.content
            
            return f"Retrieved from OpenAI Memory for '{query}': {answer}"
        except Exception as e:
            raise Exception(f"OpenAI retrieve failed: {e}")
    
    async def chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Chat with OpenAI memory context."""
        if self._use_mock:
            await asyncio.sleep(0.15)
            return f"[MOCK] OpenAI response to '{message}': [mock response with memory context]"
        
        try:
            # Build context from stored memories and conversation history
            context_messages = [
                {"role": "system", "content": "You are a helpful assistant with access to stored memories. Use the memories to provide contextual responses."}
            ]
            
            # Add memory context
            if self.stored_memories:
                memory_context = "Your memories: " + " | ".join([
                    mem['content'][:100] for mem in self.stored_memories[-5:]  # Last 5 memories
                ])
                context_messages.append({"role": "system", "content": memory_context})
            
            # Add recent conversation history
            context_messages.extend(self.conversation_history[-6:])  # Last 3 exchanges
            
            # Add current message
            context_messages.append({"role": "user", "content": message})
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=context_messages,
                max_tokens=300,
                temperature=0.3
            )
            
            answer = response.choices[0].message.content
            
            # Update conversation history
            self.conversation_history.extend([
                {"role": "user", "content": message},
                {"role": "assistant", "content": answer}
            ])
            
            return f"OpenAI Memory response: {answer}"
        except Exception as e:
            raise Exception(f"OpenAI chat failed: {e}")
