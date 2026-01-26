"""MemGPT/Letta memory tool implementation using Letta Python client."""

from typing import Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
from llmemory_meter.memory_tools.base import MemoryTool
from llmemory_meter.config_parser.env import Config
from llmemory_meter.pricing import split_tokens



class MemGPTTool(MemoryTool):
    """MemGPT/Letta memory tool implementation using the Letta Python client."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("memgpt", config)
        
        # Require Letta API key
        if not Config.MEMGPT_API_KEY:
            raise ValueError("MEMGPT_API_KEY required for Letta Cloud")
        
        self._agent_id = None
        self._last_tokens = 0  # Track token usage from last API call
        self._last_input_tokens = 0
        self._last_output_tokens = 0
        self.model = self.config.get("model", "gpt-4o-mini")
        
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
                # Create new agent with OpenAI credentials
                from llmemory_meter.config_parser.env import Config as EnvConfig
                
                # Build LLM config with OpenAI API key
                llm_config = {
                    "model": self.config.get("model", "gpt-4o-mini"),
                    "model_endpoint_type": "openai",
                    "model_endpoint": "https://api.openai.com/v1"
                }
                
                # Add OpenAI API key if available
                if EnvConfig.OPENAI_API_KEY:
                    llm_config["model_endpoint_api_key"] = EnvConfig.OPENAI_API_KEY
                
                new_agent = self.client.agents.create(
                    name=agent_name,
                    memory_blocks=[],
                    llm_config=llm_config
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

    def _agent_name(self) -> str:
        """Generate a short, unique agent name for the current instance."""
        return f"benchmark_agent_{self._session_id}"
    
    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store memory in Letta by sending a message to the agent."""
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
            response = self.client.agents.messages.create(
                agent_id=self._agent_id,
                messages=[{
                    "role": "user",
                    "content": f"Please remember this information: {content}"
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
            raise Exception(f"Letta API error in store: {e}")
    
    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Retrieve memory from Letta by querying the agent."""
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, self._sync_query_memory, query)
            
            # Extract response text from messages
            if hasattr(result, 'messages') and result.messages:
                # Get assistant messages
                assistant_msgs = [msg for msg in result.messages 
                                if hasattr(msg, 'message_type') and 
                                'assistant' in msg.message_type.lower()]
                if assistant_msgs and hasattr(assistant_msgs[-1], 'content'):
                    response_text = assistant_msgs[-1].content
                    if self.debug:
                        return f"[memgpt] Retrieved: {response_text}"
                    else:
                        return response_text
            
            return f"Retrieved from Letta for query: {query}"
        except Exception as e:
            raise Exception(f"Error retrieving memory: {e}")
    
    def _sync_query_memory(self, query: str):
        """Synchronous wrapper for Letta memory querying."""
        try:
            # Ask agent to recall information
            response = self.client.agents.messages.create(
                agent_id=self._agent_id,
                messages=[{
                    "role": "user",
                    "content": f"What do you remember about: {query}?"
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
                self._set_last_usage(self._estimate_tokens(query))
            
            return response
                
        except Exception as e:
            # Fallback: estimate tokens from query
            self._set_last_usage(self._estimate_tokens(query))
            raise Exception(f"Letta API error in retrieve: {e}")
    
    async def chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Chat with Letta agent using its memory context."""
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
