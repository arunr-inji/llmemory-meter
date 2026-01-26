"""
OpenAI Memory Tool Implementation

Provides integration with OpenAI's memory capabilities.
"""

import asyncio
import time
from typing import Dict, Any, Optional

from llmemory_meter.memory_tools.base import MemoryTool
from llmemory_meter.config_parser import Config


class OpenAIMemoryTool(MemoryTool):
    """OpenAI Memory tool implementation with real API calls."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, debug: bool = False):
        super().__init__("openai_memory", config, debug)
        
        # Require API key
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.api_key = Config.OPENAI_API_KEY
        self._initialize_openai_client()
        
        # Simple in-memory storage for this demo (in production, use persistent storage)
        self.stored_memories = []
        self.conversation_history = []
        self._last_tokens = 0  # Track token usage from last API call
        self._last_input_tokens = 0
        self._last_output_tokens = 0

    def _set_last_usage(self, usage) -> None:
        """Store token usage details from an OpenAI response."""
        if not usage:
            self._last_tokens = 0
            self._last_input_tokens = 0
            self._last_output_tokens = 0
            return

        input_tokens = getattr(usage, "prompt_tokens", None)
        if input_tokens is None:
            input_tokens = getattr(usage, "input_tokens", None)

        output_tokens = getattr(usage, "completion_tokens", None)
        if output_tokens is None:
            output_tokens = getattr(usage, "output_tokens", None)

        total_tokens = getattr(usage, "total_tokens", None)
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        self._last_input_tokens = input_tokens or 0
        self._last_output_tokens = output_tokens or 0
        self._last_tokens = total_tokens or (self._last_input_tokens + self._last_output_tokens)
    
    def _initialize_openai_client(self):
        """Initialize the OpenAI client."""
        try:
            import openai
            self.client = openai.AsyncOpenAI(api_key=self.api_key)
            self.model = self.config.get("model", "gpt-4o-mini")
            print("✅ OpenAI client initialized")
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")
        except Exception as e:
            raise Exception(f"Failed to initialize OpenAI: {e}")
    
    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store memory using OpenAI (simulated with in-memory storage)."""
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
            
            # Track token usage
            self._set_last_usage(response.usage)
            
            if self.debug:
                return f"[openai_memory] Stored: {content} (Summary: {summary})"
            else:
                return content
        except Exception as e:
            raise Exception(f"OpenAI store failed: {e}")
    
    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Retrieve memory using OpenAI."""
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
            
            # Track token usage
            self._set_last_usage(response.usage)
            
            if self.debug:
                return f"[openai_memory] Retrieved for '{query}': {answer}"
            else:
                return answer
        except Exception as e:
            raise Exception(f"OpenAI retrieve failed: {e}")
    
    async def chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Chat with OpenAI memory context."""
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
            
            # Track token usage
            self._set_last_usage(response.usage)
            
            # Update conversation history
            self.conversation_history.extend([
                {"role": "user", "content": message},
                {"role": "assistant", "content": answer}
            ])
            
            if self.debug:
                return f"[openai_memory] Response: {answer}"
            else:
                return answer
        except Exception as e:
            raise Exception(f"OpenAI chat failed: {e}")
    
    async def execute_step(self, step, step_index: int):
        """Override to track token usage from API responses."""
        from llmemory_meter.workload import StepResult
        
        start_time = time.time()
        self._last_tokens = 0  # Reset before each call
        self._last_input_tokens = 0
        self._last_output_tokens = 0
        
        try:
            if step.action == "store":
                response = await self.store_memory(step.content, step.metadata)
            elif step.action == "retrieve":
                response = await self.retrieve_memory(step.content, step.metadata)
            elif step.action == "chat":
                response = await self.chat(step.content, step.metadata)
            else:
                raise ValueError(f"Unknown action: {step.action}")
            
            latency_ms = (time.time() - start_time) * 1000
            
            return StepResult(
                step_index=step_index,
                action=step.action,
                response=response,
                latency_ms=latency_ms,
                tokens_used=self._last_tokens,  # Use tracked tokens
                input_tokens=self._last_input_tokens,
                output_tokens=self._last_output_tokens,
                model=self.model,
                success=True
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return StepResult(
                step_index=step_index,
                action=step.action,
                response="",
                latency_ms=latency_ms,
                tokens_used=0,
                input_tokens=0,
                output_tokens=0,
                model=self.model,
                success=False,
                error_message=str(e)
            )
    
    async def clear_memory(self, session_id: Optional[str] = None) -> str:
        """Clear memory by resetting storage (workload isolation)."""
        try:
            self.stored_memories = []
            self.conversation_history = []
            return "Memory cleared (storage reset)"
        except Exception as e:
            return f"Error clearing OpenAI Memory: {e}"
