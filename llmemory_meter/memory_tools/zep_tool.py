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
            
            task_id = None
            episode_uuid = None
            message_uuid = None
            
            if len(content) < MAX_MESSAGE_LENGTH:
                # Short message - use thread.add_messages
                message = Message(
                    role="user",
                    content=content
                )
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.thread.add_messages(
                        thread_id=self.session_id,
                        messages=[message]
                    )
                )
                print(f"🔍 DEBUG - thread.add_messages result: {result}")
                print(f"   Has task_id: {hasattr(result, 'task_id')}, value: {getattr(result, 'task_id', None)}")
                print(f"   Has message_uuids: {hasattr(result, 'message_uuids')}, value: {getattr(result, 'message_uuids', None)}")
                
                # Get message_uuids for polling (task_id is None for single messages)
                if hasattr(result, 'message_uuids') and result.message_uuids:
                    # Use the first message UUID to poll  
                    message_uuid = result.message_uuids[0]
                    print(f"✅ Will poll using message_uuid: {message_uuid}")
                else:
                    print(f"⚠️ No message_uuids in response!")
            else:
                # Long content - use graph.add (no size limit)
                message_data = self._truncate_for_graph(f"User: {content}")
                episode = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.graph.add(
                        user_id=self.user_id,
                        type="message",
                        data=message_data
                    )
                )
                print(f"🔍 DEBUG - graph.add result: {episode}")
                print(f"   Type: {type(episode)}")
                print(f"   Has uuid_: {hasattr(episode, 'uuid_')}")
                if hasattr(episode, 'uuid_'):
                    print(f"   uuid_ value: {episode.uuid_}")
                
                # Get episode UUID for polling
                if hasattr(episode, 'uuid_') and episode.uuid_:
                    episode_uuid = episode.uuid_
                    print(f"✅ Captured episode_uuid: {episode_uuid}")

            # IMPORTANT: Poll for Zep to finish processing the message
            # Zep processes messages asynchronously (typically 5-10 seconds per message)
            # Poll until processing completes (max 30 seconds timeout)
            await self._wait_for_processing(task_id, episode_uuid, timeout=30, message_uuid=message_uuid)

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
            # Use graph search for better fact retrieval
            graph_search_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.graph.search(
                    user_id=self.user_id,
                    query=query,
                    limit=5
                )
            )
            
            # Extract facts from graph search results
            if graph_search_response and hasattr(graph_search_response, 'edges') and graph_search_response.edges:
                facts = []
                for edge in graph_search_response.edges[:5]:
                    if hasattr(edge, 'fact') and edge.fact:
                        facts.append(edge.fact)
                
                if facts:
                    response = f"Retrieved from Zep: {'; '.join(facts)}"
                    input_tokens = self._estimate_tokens(query)
                    output_tokens = self._estimate_tokens(response)
                    self._last_tokens = input_tokens + output_tokens
                    return response
            
            # Fallback to thread context if graph search returns nothing
            context_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.thread.get_user_context(
                    thread_id=self.session_id
                )
            )

            # Extract context from response
            if context_response:
                # PREFER facts over context (context often has metadata, facts have actual memories)
                if hasattr(context_response, 'facts') and context_response.facts:
                    relevant_memories = [fact.fact for fact in context_response.facts[:5]]
                    if relevant_memories:
                        response = f"Retrieved from Zep: {'; '.join(relevant_memories)}"
                        # Count full context for tokens (users pay for entire context Zep returns)
                        full_context = context_response.context if hasattr(context_response, 'context') else response
                        input_tokens = self._estimate_tokens(query)
                        output_tokens = self._estimate_tokens(full_context)
                        self._last_tokens = input_tokens + output_tokens
                        return response
                
                # Fallback to context if facts not available
                if hasattr(context_response, 'context') and context_response.context:
                    context_text = context_response.context
                    # Extract just the facts for cleaner responses (better for accuracy)
                    facts = self._extract_facts_from_context(context_text)
                    response = f"Retrieved from Zep: {facts}"
                    # Count full original response for tokens
                    input_tokens = self._estimate_tokens(query)
                    output_tokens = self._estimate_tokens(context_text)
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

    def _extract_facts_from_context(self, context_text: str) -> str:
        """Extract just the facts from Zep's verbose context format.
        
        Zep returns context with template headers like:
        'FACTS and ENTITIES represent relevant context...'
        
        This method extracts just the actual facts for cleaner responses.
        """
        if not context_text:
            return ""
        
        # Split by lines and filter out template/header lines
        lines = context_text.split('\n')
        facts = []
        
        for line in lines:
            line = line.strip()
            # Skip empty lines, headers, XML tags, and formatting lines
            if not line:
                continue
            if line.startswith('#'):
                continue
            if line.startswith('<') and line.endswith('>'):
                continue  # Skip XML tags like <FACTS>, </FACTS>, <ENTITIES>
            if 'FACTS and ENTITIES' in line:
                continue
            if 'represent relevant context' in line:
                continue
            if 'format:' in line:
                continue
            if 'Date range:' in line and line.endswith('-'):
                continue
            if line == '-' or line == '|':
                continue  # Skip separator lines
            
            # This is likely an actual fact
            facts.append(line)
        
        return '; '.join(facts) if facts else context_text
    
    async def _wait_for_processing(self, task_id: Optional[str], episode_uuid: Optional[str], timeout: int = 30, message_uuid: Optional[str] = None):
        """Poll Zep until graph processing completes and facts are searchable.
        
        Args:
            task_id: Task ID from thread.add_messages (for batch processing)
            episode_uuid: Episode UUID from graph.add (for single episode)
            timeout: Maximum seconds to wait (default 30)
        """
        print(f"🔍 DEBUG - Polling started: task_id={task_id}, episode_uuid={episode_uuid}, message_uuid={message_uuid}")
        
        if not task_id and not episode_uuid and not message_uuid:
            # No polling info available, use fallback wait
            print(f"⚠️ No task_id, episode_uuid, or message_uuid - using fallback 8s wait")
            await asyncio.sleep(8)
            return
        
        start_time = time.time()
        
        try:
            # Option C: For single messages, skip broken polling and use fixed wait
            FIXED_WAIT_SINGLE_MESSAGE = 15  # Fixed wait for single messages
            
            if message_uuid:
                print(f"⏱️ Using fixed {FIXED_WAIT_SINGLE_MESSAGE}s wait for single message (Option C)")
                print(f"   Reason: 'processed' field unreliable for thread.add_messages()")
                await asyncio.sleep(FIXED_WAIT_SINGLE_MESSAGE)
                elapsed = FIXED_WAIT_SINGLE_MESSAGE
            else:
                # Phase 1: Poll for task_id or episode_uuid (these work reliably)
                print(f"🔍 Phase 1: Polling for processing completion...")
                poll_count = 0
                while (time.time() - start_time) < timeout:
                    poll_count += 1
                    
                    if task_id:
                        # Poll task status for thread.add_messages_batch
                        task = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self.client.task.get(task_id=task_id)
                        )
                        print(f"  Poll {poll_count}: Task status = {getattr(task, 'status', 'N/A')}")
                        if hasattr(task, 'status'):
                            if task.status == "completed":
                                print(f"✅ Phase 1 complete after {poll_count} polls ({time.time() - start_time:.1f}s)")
                                break
                            elif task.status == "failed":
                                print(f"⚠️ Zep task failed: {getattr(task, 'error', 'Unknown error')}")
                                return
                    
                    elif episode_uuid:
                        # Poll episode status for graph.add
                        episode = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self.client.graph.episode.get(uuid_=episode_uuid)
                        )
                        processed = getattr(episode, 'processed', False)
                        print(f"  Poll {poll_count}: Episode processed = {processed}")
                        if hasattr(episode, 'processed') and episode.processed:
                            print(f"✅ Phase 1 complete after {poll_count} polls ({time.time() - start_time:.1f}s)")
                            break
                    
                    # Wait 1 second before next poll
                    await asyncio.sleep(1)
                
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    print(f"⚠️ Phase 1 timeout reached ({timeout}s)")
            
            # Phase 2: Wait for facts to be searchable (indexing delay)
            # Even after "processing complete", search index needs time to update
            # Poll graph search until we get results or timeout
            remaining_timeout = max(10, timeout - elapsed)  # At least 10s for Phase 2
            indexing_start = time.time()
            
            print(f"🔍 Phase 2: Verifying facts are searchable (timeout: {remaining_timeout:.1f}s)...")
            index_poll_count = 0
            
            while (time.time() - indexing_start) < remaining_timeout:
                index_poll_count += 1
                try:
                    # Do a simple graph search to check if facts are available
                    search_result = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.client.graph.search(
                            user_id=self.user_id,
                            query="user",  # Generic query to check for any facts
                            limit=1
                        )
                    )
                    edge_count = len(search_result.edges) if (search_result and hasattr(search_result, 'edges') and search_result.edges) else 0
                    print(f"  Index poll {index_poll_count}: Found {edge_count} edges")
                    
                    if search_result and hasattr(search_result, 'edges') and search_result.edges:
                        # Facts are now searchable!
                        print(f"✅ Phase 2 complete after {index_poll_count} polls ({time.time() - indexing_start:.1f}s)")
                        print(f"✅ Total wait time: {time.time() - start_time:.1f}s")
                        return
                except Exception as e:
                    print(f"  Index poll {index_poll_count}: Error - {type(e).__name__}: {str(e)[:50]}")
                
                await asyncio.sleep(1)
            
            # Indexing timeout - continue anyway
            print(f"⚠️ Phase 2 timeout after {index_poll_count} polls ({time.time() - indexing_start:.1f}s)")
            print(f"⚠️ Total wait time: {time.time() - start_time:.1f}s")
            if (time.time() - start_time) >= timeout:
                print(f"⚠️ Overall Zep timeout reached ({timeout}s)")
            
        except Exception as e:
            # Polling failed, fall back to static wait
            print(f"⚠️ Zep polling error: {type(e).__name__}: {str(e)[:200]}")
            import traceback
            traceback.print_exc()
            print(f"Falling back to 8s wait")
            await asyncio.sleep(8)
    
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
        """Clear memory by creating a new user and thread (workload isolation).
        
        Zep stores knowledge graph at USER level, so we create a new user for each workload
        to ensure complete isolation without the complexity of deleting/recreating threads.
        """
        try:
            # Generate new user_id for workload isolation
            self.user_id = f"benchmark_user_{int(time.time() * 1000)}"
            self.session_id = f"zep_{int(time.time())}"
            
            # Ensure new user exists
            self._ensure_user_exists()
            
            # Create new thread
            self._ensure_thread_exists()
            
            return f"Memory cleared (new user: {self.user_id})"
        except Exception as e:
            return f"Error reinitializing Zep: {e}"

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