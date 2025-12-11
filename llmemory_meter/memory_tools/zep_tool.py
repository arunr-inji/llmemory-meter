"""
Zep Memory Tool Implementation

Implements the MemoryTool interface for Zep memory system.
Provides long-term memory capabilities for AI assistants.
"""

import os
from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime

try:
    from zep_cloud.client import Zep
    from zep_cloud.types import Message
    ZEP_AVAILABLE = True
except ImportError:
    ZEP_AVAILABLE = False
    Zep = None
    Message = None

from llmemory_meter.memory_tools.base import MemoryTool
from llmemory_meter.workload import WorkloadStep, StepResult
import time

# Try to import tiktoken for better token estimation
try:
    import tiktoken
    _has_tiktoken = True
except ImportError:
    _has_tiktoken = False


class ZepTool(MemoryTool):
    """Zep memory tool implementation."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("zep", config)

        if not ZEP_AVAILABLE:
            raise ImportError(
                "Zep Cloud SDK not found. Install with: pip install zep-cloud"
            )

        # Get configuration
        self.api_key = config.get("api_key") or os.getenv("ZEP_API_KEY")

        if not self.api_key:
            raise ValueError("ZEP_API_KEY is required in config or environment variables")

        # Initialize client
        self.client = Zep(
            api_key=self.api_key
        )

        # Session management
        # Use unique user_id per instance to avoid knowledge graph accumulation
        # Zep's graph.add() stores at USER level, not thread level
        default_user = f"benchmark_user_{int(time.time() * 1000)}"
        self.user_id = config.get("user_id", default_user)
        self.session_id = config.get("session_id", self._session_id)
        
        # Token tracking
        self._last_tokens = 0

        # Initialize user and thread
        self._ensure_user_exists()
        self._ensure_thread_exists()
        print("✅ Zep client initialized")

    def _truncate_for_graph(self, text: str, limit: int = 9000) -> str:
        """Truncate text to stay within graph.add 10k char limit (leave buffer)."""
        if not text:
            return ""
        return text[:limit]

    def _ensure_user_exists(self):
        """Ensure user exists in Zep."""
        try:
            # Try to get user, create if doesn't exist
            try:
                self.client.user.get(user_id=self.user_id)
                print(f"✅ Zep user '{self.user_id}' found")
            except Exception as e:
                # User doesn't exist or users are managed automatically in Zep Cloud
                print(f"ℹ️ Zep user creation: users are auto-managed in Zep Cloud")
        except Exception as e:
            # Continue without user creation
            print(f"⚠️ Could not verify Zep user: {type(e).__name__}: {str(e)[:80]}")

    def _ensure_thread_exists(self):
        """Ensure thread exists for the current session."""
        try:
            # First, try to add the user (Zep Cloud manages users automatically)
            try:
                self.client.user.add(
                    user_id=self.user_id,
                    first_name="Test",
                    last_name="User",
                    email=f"{self.user_id}@test.com"
                )
                print(f"✅ Zep user '{self.user_id}' created")
            except Exception as user_err:
                # User might already exist
                print(f"ℹ️ Zep user: {type(user_err).__name__} (user may already exist)")
            
            # Now create thread
            self.client.thread.create(
                thread_id=self.session_id,
                user_id=self.user_id
            )
            print(f"✅ Zep thread '{self.session_id}' created")
        except Exception as e:
            # Thread might already exist
            error_msg = str(e)[:200]
            print(f"ℹ️ Zep thread creation: {type(e).__name__}: {error_msg}")
            # Don't fail - thread creation might fail if it already exists, continue anyway

    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store information in Zep memory."""
        try:
            # Zep has 2500 char limit for thread.add_messages
            # Use graph.add for longer content
            MAX_MESSAGE_LENGTH = 2400  # Leave some buffer
            
            if len(content) < MAX_MESSAGE_LENGTH:
                # Short message - use thread.add_messages
                message = Message(
                    role="user",
                    content=content
                )
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.thread.add_messages(
                        thread_id=self.session_id,
                        messages=[message]
                    )
                )
            else:
                # Long content - use graph.add (no size limit)
                message_data = self._truncate_for_graph(f"User: {content}")
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.graph.add(
                        user_id=self.user_id,
                        type="message",
                        data=message_data
                    )
                )

            # IMPORTANT: Wait for Zep to process the message and build knowledge graph
            # Zep processes messages asynchronously (5-10 seconds per message)
            # Without this delay, retrieve operations will return empty results
            await asyncio.sleep(8)  # Wait 8 seconds for graph processing

            response = f"Successfully stored memory: {content[:50]}..."
            
            # Estimate tokens: input (content) + output (processing + response)
            input_tokens = self._estimate_tokens(content)
            output_tokens = self._estimate_tokens(response) + int(input_tokens * 0.3)  # Zep processing overhead
            self._last_tokens = input_tokens + output_tokens
            
            return response

        except Exception as e:
            # Log the actual error with full details
            error_type = type(e).__name__
            print(f"❌ Zep store error: {error_type}")
            print(f"   Error: {str(e)[:500]}")
            if hasattr(e, 'body'):
                print(f"   Body: {e.body}")
            if hasattr(e, 'status_code'):
                print(f"   Status: {e.status_code}")
            raise Exception(f"Zep API error in store: {error_type}: {str(e)[:200]}")

    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Retrieve information from Zep memory."""
        try:
            # Get user context from thread (relevant memories)
            context_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.thread.get_user_context(
                    thread_id=self.session_id
                )
            )

            # Extract context from response
            if context_response:
                # Try to get context string
                if hasattr(context_response, 'context') and context_response.context:
                    context_text = context_response.context
                    response = f"Retrieved from Zep: {context_text}"
                    # Count full response: This reflects real cost when passed to an LLM
                    # Users pay for the entire context Zep returns (including formatting)
                    input_tokens = self._estimate_tokens(query)
                    output_tokens = self._estimate_tokens(response)
                    self._last_tokens = input_tokens + output_tokens
                    return response
                
                # Fallback to facts if context not available
                if hasattr(context_response, 'facts') and context_response.facts:
                    relevant_memories = [fact.fact for fact in context_response.facts[:3]]
                    if relevant_memories:
                        response = f"Retrieved from Zep: {'; '.join(relevant_memories)}"
                        input_tokens = self._estimate_tokens(query)
                        output_tokens = self._estimate_tokens(response)
                        self._last_tokens = input_tokens + output_tokens
                        return response

            # Estimate tokens even if no memories found
            response = "No relevant memories found in Zep."
            input_tokens = self._estimate_tokens(query)
            output_tokens = self._estimate_tokens(response)
            self._last_tokens = input_tokens + output_tokens
            return response

        except Exception as e:
            # Log the actual error with full details
            error_type = type(e).__name__
            error_str = str(e)
            
            # For NotFoundError, it's expected if thread is new - return empty result instead of raising
            if "NotFoundError" in error_type or "404" in error_str:
                print(f"ℹ️ Zep retrieve: Thread not found (thread may be too new)")
                response = "No relevant memories found in Zep (thread is new)."
                input_tokens = self._estimate_tokens(query)
                output_tokens = self._estimate_tokens(response)
                self._last_tokens = input_tokens + output_tokens
                return response
            
            print(f"❌ Zep retrieve error: {error_type}")
            print(f"   Error: {error_str[:500]}")
            if hasattr(e, 'body'):
                print(f"   Body: {e.body}")
            if hasattr(e, 'status_code'):
                print(f"   Status: {e.status_code}")
            raise Exception(f"Zep API error in retrieve: {error_type}: {error_str[:200]}")

    async def chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Have a conversation using Zep memory context."""
        try:
            # First, retrieve relevant context
            context = await self.retrieve_memory(message, metadata)

            # Zep has 2500 char limit for thread.add_messages
            # Use graph.add for longer content
            MAX_MESSAGE_LENGTH = 2400  # Leave some buffer
            
            # Add user message
            if len(message) < MAX_MESSAGE_LENGTH:
                # Short message - use thread.add_messages to maintain thread structure
                user_message = Message(
                    role="user",
                    content=message
                )
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.thread.add_messages(
                        thread_id=self.session_id,
                        messages=[user_message]
                    )
                )
            else:
                # Long message - use graph.add (no size limit)
                message_data = self._truncate_for_graph(f"User: {message}")
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.graph.add(
                        user_id=self.user_id,
                        type="message",
                        data=message_data
                    )
                )
                # Wait for graph processing when using graph.add
                await asyncio.sleep(8)

            # For this implementation, we'll return context-aware response
            # In a real implementation, you'd integrate with an LLM here
            response = f"Based on context: {context}. Responding to: {message}"

            # Count tokens realistically:
            # - Input: message + context (what gets passed to LLM)
            # - Output: reasonable response length (NOT including context again)
            #   In real apps, LLM generates ~same length as input message
            input_text = message + " " + context
            input_tokens = self._estimate_tokens(input_text)
            output_tokens = self._estimate_tokens(message) * 2  # Typical response is 1-2x input length
            self._last_tokens = input_tokens + output_tokens

            # Store assistant response
            if len(response) < MAX_MESSAGE_LENGTH:
                # Short response - use thread.add_messages
                assistant_message = Message(
                    role="assistant",
                    content=response
                )
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.thread.add_messages(
                        thread_id=self.session_id,
                        messages=[assistant_message]
                    )
                )
            else:
                # Long response - use graph.add (no size limit)
                response_data = self._truncate_for_graph(f"Assistant: {response}")
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.graph.add(
                        user_id=self.user_id,
                        type="message",
                        data=response_data
                    )
                )
                # Wait for graph processing when using graph.add
                await asyncio.sleep(8)

            return response

        except Exception as e:
            # Log the actual error with full details
            error_type = type(e).__name__
            error_str = str(e)
            error_repr = repr(e)
            
            print(f"❌ Zep chat error: {error_type}")
            print(f"   Error string: {error_str[:500]}")
            print(f"   Error repr: {error_repr[:500]}")
            
            # Try to extract body/status if available
            if hasattr(e, 'body'):
                print(f"   Error body: {e.body}")
            if hasattr(e, 'status_code'):
                print(f"   Status code: {e.status_code}")
            if hasattr(e, 'message'):
                print(f"   Message: {e.message}")
            
            raise Exception(f"Zep API error in chat: {error_type}: {error_str[:200]}")

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count using tiktoken if available, fallback to heuristic."""
        if not text:
            return 0
        if _has_tiktoken:
            try:
                encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer
                return len(encoding.encode(text))
            except:
                pass
        # Fallback: rough estimate (1 token ≈ 4 characters)
        return len(text) // 4

    async def execute_step(self, step: WorkloadStep, step_index: int) -> StepResult:
        """Execute a single workload step and measure performance."""
        start_time = time.time()
        self._last_tokens = 0  # Reset before each call
        
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
                tokens_used=self._last_tokens,
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
                success=False,
                error_message=str(e)
            )

    async def clear_memory(self, session_id: Optional[str] = None) -> str:
        """Clear memory for a session."""
        target_session = session_id or self.session_id
        try:
            # In v3, use thread.delete instead of memory.delete
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.thread.delete(thread_id=target_session)
            )
            return f"Cleared memory for thread: {target_session}"
        except Exception as e:
            return f"Error clearing Zep thread: {e}"

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics for the current session."""
        try:
            # In v3, use thread.get instead of memory.get to get thread messages
            thread_info = self.client.thread.get(thread_id=self.session_id)
            if thread_info:
                return {
                    "session_id": self.session_id,
                    "message_count": len(thread_info.messages) if hasattr(thread_info, 'messages') else 0,
                    "has_summary": hasattr(thread_info, 'summary') and thread_info.summary is not None,
                    "last_updated": datetime.now().isoformat()
                }
        except:
            pass

        return {
            "session_id": self.session_id,
            "message_count": 0,
            "has_summary": False,
            "last_updated": datetime.now().isoformat()
        }