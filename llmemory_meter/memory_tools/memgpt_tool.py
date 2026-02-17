"""MemGPT/Letta memory tool implementation using Letta Python client."""

from typing import Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
from llmemory_meter.memory_tools.base import MemoryTool
from llmemory_meter.config_parser.env import Config
from llmemory_meter.pricing import split_tokens



class MemGPTTool(MemoryTool):
    """MemGPT/Letta memory tool implementation using the Letta Python client."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, debug: bool = False,
                 tool_name: str = "memgpt_memory_blocks"):
        super().__init__(tool_name, config, debug)
        
        # Require Letta API key
        if not Config.MEMGPT_API_KEY:
            raise ValueError("MEMGPT_API_KEY required for Letta Cloud")
        
        self._agent_id = None
        self._fatal_error: Optional[str] = None
        self._last_tokens = 0  # Track token usage from last API call
        self._last_input_tokens = 0
        self._last_output_tokens = 0
        self.model = self.config.get("model", "gpt-4o-mini")
        self.memory_mode = self.config.get("memory_mode", "default")
        
        # Create dedicated thread pool executor to avoid shared pool exhaustion
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="memgpt_")
        
        # Initialize Letta client
        self._initialize_letta_client()
    
    def _set_last_usage(
        self,
        total_tokens: Optional[int],
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
    ) -> None:
        """Store token usage details with a fallback split."""
        if total_tokens is None:
            total_tokens = 0

        if input_tokens is None and output_tokens is None:
            input_tokens, output_tokens = split_tokens(total_tokens)
        else:
            if input_tokens is None and output_tokens is not None:
                input_tokens = max(total_tokens - output_tokens, 0)
            if output_tokens is None and input_tokens is not None:
                output_tokens = max(total_tokens - input_tokens, 0)

        self._last_input_tokens = input_tokens or 0
        self._last_output_tokens = output_tokens or 0
        self._last_tokens = total_tokens or (self._last_input_tokens + self._last_output_tokens)

    def _extract_usage_tokens(self, usage) -> Dict[str, Optional[int]]:
        """Normalize usage token fields across providers."""
        input_tokens = getattr(usage, "input_tokens", None)
        if input_tokens is None:
            input_tokens = getattr(usage, "prompt_tokens", None)

        output_tokens = getattr(usage, "output_tokens", None)
        if output_tokens is None:
            output_tokens = getattr(usage, "completion_tokens", None)

        total_tokens = getattr(usage, "total_tokens", None)
        return {
            "total_tokens": total_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
    
    def _initialize_letta_client(self):
        """Initialize Letta client and set up agent."""
        try:
            from letta_client import Letta
            
            # Initialize client
            self.client = Letta(api_key=Config.MEMGPT_API_KEY)
            
            # Set up or find existing agent
            memgpt_config = self.config.get("memgpt_config") or {}
            agent_name = self._agent_name()
            self._setup_agent(agent_name, memgpt_config)
                
        except Exception as e:
            raise Exception(f"Failed to initialize Letta: {e}")
    
    def _setup_agent(self, agent_name: str, memgpt_config: Dict[str, Any]):
        """Set up or find Letta agent."""
        try:
            from llmemory_meter.config_parser.env import Config as EnvConfig
            
            # List existing agents
            agents = list(self.client.agents.list())
            
            # Find existing agent by name
            existing_agent = next((a for a in agents if a.name == agent_name), None)
            
            if existing_agent:
                self._agent_id = existing_agent.id
            else:
                # Create new agent using modern Letta API (BYOK via platform)
                model_name = self.config.get("model", "gpt-4o-mini")
                # Ensure model uses provider/model format for BYOK routing
                if "/" not in model_name:
                    model_name = f"openai/{model_name}"
                
                memory_blocks = self._build_memory_blocks()
                
                new_agent = self.client.agents.create(
                    name=agent_name,
                    model=model_name,
                    context_window_limit=128000,  # gpt-4o-mini / gpt-4o
                    memory_blocks=memory_blocks,
                    include_base_tools=True,
                    tools=["archival_memory_insert", "archival_memory_search"],
                    compaction_settings={
                        "model": "openai/gpt-4o-mini",
                    },
                )
                self._agent_id = new_agent.id
                
        except Exception as e:
            print(f"⚠️ Error in _setup_agent: {e}")
            # Fallback: try to list and use first available agent
            try:
                agents = list(self.client.agents.list())
                if agents:
                    self._agent_id = agents[0].id
                    print(f"Warning: Using first available agent: {self._agent_id}")
                else:
                    raise Exception(f"Could not set up Letta agent: {e}")
            except:
                raise Exception(f"Could not set up Letta agent: {e}")

    def _build_memory_blocks(self):
        """Build memory_blocks config based on memory_mode setting."""
        if self.memory_mode == "archival":
            # Small human block forces facts into archival storage
            return [
                {
                    "label": "human",
                    "value": "",
                    "description": (
                        "Brief summary only (keep under 200 chars). "
                        "Do NOT store facts here."
                    ),
                    "limit": 200,
                },
                {
                    "label": "persona",
                    "value": (
                        "I am a memory assistant. When the user shares information, "
                        "I extract EACH individual fact and store it as a SEPARATE "
                        "archival_memory_insert call. For example, if the user says "
                        "\"I graduated with a Business Administration degree from NYU in 2015\", "
                        "I make THREE separate archival inserts: "
                        "1) \"User graduated with a Business Administration degree\" "
                        "2) \"User attended NYU\" "
                        "3) \"User graduated in 2015\". "
                        "NEVER summarize multiple facts into one insert. "
                        "ALWAYS use archival_memory_insert for EVERY fact."
                    ),
                    "description": (
                        "Operating instructions. You extract and store individual facts "
                        "in archival memory so they can be searched and retrieved accurately."
                    ),
                    "limit": 1000,
                },
            ]
        else:
            # Default: Letta native config (no limit = 20K default)
            return [
                {
                    "label": "human",
                    "value": "",
                    "description": (
                        "Stores key facts and details about the person you are "
                        "conversing with. Update this block whenever you learn "
                        "new information about them."
                    ),
                },
                {
                    "label": "persona",
                    "value": (
                        "I am a memory assistant. I proactively store important "
                        "facts and details using my memory tools, and recall them "
                        "accurately when asked."
                    ),
                    "description": (
                        "Stores details about your current persona. You are a "
                        "memory-focused assistant that prioritizes remembering "
                        "and recalling information accurately."
                    ),
                },
            ]

    def _agent_name(self) -> str:
        """Generate a short, unique agent name for the current instance."""
        return f"benchmark_agent_{self._session_id}"
    
    def _build_store_prompt(self, content: str) -> str:
        """Build the store prompt based on memory mode."""
        if self.memory_mode == "archival":
            return (
                "Extract EVERY individual fact from the following conversation "
                "and store EACH fact as a SEPARATE archival_memory_insert. "
                "Do NOT summarize. Do NOT combine facts. One fact per insert.\n\n"
                f"{content}"
            )
        return f"Please remember this information: {content}"

    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store memory in Letta by sending a message to the agent."""
        if self._fatal_error:
            raise Exception(self._fatal_error)
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, self._sync_send_message, content)
            
            if self.debug:
                return f"[memgpt] Stored: {content}"
            else:
                return content
        except Exception as e:
            raise Exception(f"Error storing memory: {e}")
    
    def _sync_send_message(self, content: str):
        """Synchronous wrapper for Letta message sending."""
        try:
            # Send message to agent
            prompt = self._build_store_prompt(content)
            response = self.client.agents.messages.create(
                agent_id=self._agent_id,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Extract token usage
            if hasattr(response, 'usage'):
                usage = response.usage
                tokens = self._extract_usage_tokens(usage)
                self._set_last_usage(
                    tokens["total_tokens"],
                    input_tokens=tokens["input_tokens"],
                    output_tokens=tokens["output_tokens"],
                )
            else:
                # Fallback: estimate tokens
                self._set_last_usage(self._estimate_tokens(content))
            
            return response
                
        except Exception as e:
            # Fallback: estimate tokens from content
            self._set_last_usage(self._estimate_tokens(content))
            details = str(e)
            if "agents-limit-exceeded" in details or "limit for agents" in details:
                self._fatal_error = (
                    "Letta API rate limited by agent plan/quota (agents-limit-exceeded). "
                    "Delete unused agents or upgrade plan."
                )
                raise Exception(f"Letta API error in store: {self._fatal_error}")
            raise Exception(f"Letta API error in store: {e}")
    
    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Retrieve memory from Letta via SDK: read core blocks + search archival."""
        if self._fatal_error:
            raise Exception(self._fatal_error)
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor, self._sync_query_memory, query
            )
            if self.debug:
                return f"[memgpt] Retrieved: {result}"
            return result
        except Exception as e:
            raise Exception(f"Error retrieving memory: {e}")

    def _sync_query_memory(self, query: str):
        """Read core memory blocks and search archival passages via SDK."""
        parts = []

        # 1. Read core memory block (curated summary the agent maintains)
        try:
            human_block = self.client.agents.blocks.retrieve(
                agent_id=self._agent_id, block_label="human"
            )
            if human_block and human_block.value and human_block.value.strip():
                parts.append(human_block.value.strip())
        except Exception as e:
            print(f"Warning: Failed to retrieve human block for agent {self._agent_id}: {e}", flush=True)

        # 2. Search archival passages (semantic search over stored details)
        try:
            search_resp = self.client.agents.passages.search(
                agent_id=self._agent_id,
                query=query,
                top_k=3,
            )
            if hasattr(search_resp, 'results') and search_resp.results:
                for passage in search_resp.results:
                    text = getattr(passage, 'text', '') or getattr(passage, 'content', '')
                    if text and text.strip():
                        parts.append(text.strip())
        except Exception as e:
            print(f"Warning: Failed to search archival passages for agent {self._agent_id}: {e}", flush=True)

        # 3. Build response and estimate tokens (no LLM call during retrieval)
        response_text = " | ".join(parts) if parts else f"No memories found for: {query}"
        input_tokens = self._estimate_tokens(query)
        output_tokens = self._estimate_tokens(response_text)
        self._set_last_usage(
            input_tokens + output_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return response_text
    
    async def chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Chat with Letta agent using its memory context."""
        if self._fatal_error:
            raise Exception(self._fatal_error)
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, self._sync_chat, message)
            
            # Extract response from result
            if hasattr(result, 'messages') and result.messages:
                # Get assistant messages
                assistant_msgs = [msg for msg in result.messages 
                                if hasattr(msg, 'message_type') and 
                                'assistant' in msg.message_type.lower()]
                
                # Extract content from last assistant message
                if assistant_msgs:
                    last_msg = assistant_msgs[-1]
                    # Check for 'content' field (Letta uses 'content', not 'text')
                    if hasattr(last_msg, 'content'):
                        response_text = last_msg.content
                    elif hasattr(last_msg, 'text'):
                        response_text = last_msg.text
                    else:
                        response_text = "Received response from Letta agent."
                    
                    if self.debug:
                        return f"[memgpt] Response: {response_text}"
                    else:
                        return response_text
            
            # Fallback if no assistant messages
            if self.debug:
                return "[memgpt] Received response from Letta agent."
            else:
                return "Received response from Letta agent."
        except Exception as e:
            raise Exception(f"Error in chat: {e}")
    
    def _sync_chat(self, message: str):
        """Synchronous wrapper for Letta chat."""
        try:
            # Chat with agent
            response = self.client.agents.messages.create(
                agent_id=self._agent_id,
                messages=[{
                    "role": "user",
                    "content": message
                }]
            )
            
            # Extract token usage
            if hasattr(response, 'usage'):
                usage = response.usage
                tokens = self._extract_usage_tokens(usage)
                self._set_last_usage(
                    tokens["total_tokens"],
                    input_tokens=tokens["input_tokens"],
                    output_tokens=tokens["output_tokens"],
                )
            else:
                # Fallback: estimate tokens
                self._set_last_usage(self._estimate_tokens(message))
            
            return response
                
        except Exception as e:
            # Fallback: estimate tokens from message
            self._set_last_usage(self._estimate_tokens(message))
            details = str(e)
            if "agents-limit-exceeded" in details or "limit for agents" in details:
                self._fatal_error = (
                    "Letta API rate limited by agent plan/quota (agents-limit-exceeded). "
                    "Delete unused agents or upgrade plan."
                )
                raise Exception(f"Letta API error in chat: {self._fatal_error}")
            raise Exception(f"Letta API error in chat: {e}")
    
    async def execute_step(self, step, step_index: int):
        """Override to track token usage from API responses."""
        from llmemory_meter.workload import StepResult
        import time
        
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
                success=True,
                tokens_used=self._last_tokens,
                input_tokens=self._last_input_tokens,
                output_tokens=self._last_output_tokens,
                model=self.model
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return StepResult(
                step_index=step_index,
                action=step.action,
                response=f"Error: {str(e)}",
                latency_ms=latency_ms,
                success=False,
                error_message=str(e),
                tokens_used=self._last_tokens,
                input_tokens=self._last_input_tokens,
                output_tokens=self._last_output_tokens,
                model=self.model
            )
    
    async def clear_memory(self, session_id: Optional[str] = None) -> str:
        """Clear memory by creating a new agent (workload isolation).
        
        MemGPT stores conversation history in agent context, so we create a new agent
        for each workload to ensure complete isolation.
        """
        try:
            # Delete the current agent to avoid context accumulation.
            if self._agent_id:
                try:
                    self.client.agents.delete(self._agent_id)
                except Exception as e:
                    # Fail loudly if we cannot delete the agent to avoid stale context.
                    print(f"⚠️ Error deleting MemGPT agent: {e}")
                    raise

            # Generate new user_id and agent for workload isolation
            self._reset_session()
            agent_name = self._agent_name()
            memgpt_config = self.config.get("memgpt_config") or {}
            self._setup_agent(agent_name, memgpt_config)
            
            return f"Memory cleared (new agent: {self._agent_id})"
        except Exception as e:
            return f"Error reinitializing MemGPT agent: {e}"
