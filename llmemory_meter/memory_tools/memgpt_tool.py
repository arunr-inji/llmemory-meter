"""MemGPT/Letta memory tool implementation using Letta Python client."""

from typing import Dict, Any, Optional
import asyncio
import time
import random
from concurrent.futures import ThreadPoolExecutor
from llmemory_meter.memory_tools.base import MemoryTool
from llmemory_meter.config_parser.env import Config

# Try to import tiktoken for token estimation
try:
    import tiktoken
    _has_tiktoken = True
except ImportError:
    _has_tiktoken = False


class MemGPTTool(MemoryTool):
    """MemGPT/Letta memory tool implementation using the Letta Python client."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("memgpt", config)
        
        # Require Letta API key
        if not Config.MEMGPT_API_KEY:
            raise ValueError("MEMGPT_API_KEY required for Letta Cloud")
        
        # Generate unique user_id for each benchmark run to prevent context accumulation
        # If user_id is provided in config, use it; otherwise generate unique one
        if self.config.get("user_id"):
            self._user_id = self.config.get("user_id")
        else:
            self._user_id = f"benchmark_user_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        
        self._agent_id = None
        self._last_tokens = 0  # Track token usage from last API call
        
        # Create dedicated thread pool executor to avoid shared pool exhaustion
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="memgpt_")
        
        # Initialize Letta client
        self._initialize_letta_client()
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count if API doesn't provide it."""
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
    
    def _initialize_letta_client(self):
        """Initialize Letta client and set up agent."""
        try:
            from letta_client import Letta
            
            # Initialize client
            self.client = Letta(api_key=Config.MEMGPT_API_KEY)
            
            # Set up or find existing agent
            memgpt_config = self.config.get("memgpt_config") or {}
            # Always generate unique agent name to prevent reusing agents from previous runs
            if memgpt_config.get("agent_name"):
                agent_name = memgpt_config.get("agent_name")
            else:
                # Use timestamp + random for uniqueness to prevent context accumulation
                agent_name = f"benchmark_agent_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
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
    
    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store memory in Letta by sending a message to the agent."""
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, self._sync_send_message, content)
            
            return f"Stored in Letta: {content}"
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
                self._last_tokens = usage.total_tokens
            else:
                # Fallback: estimate tokens
                self._last_tokens = self._estimate_tokens(content)
            
            return response
                
        except Exception as e:
            # Fallback: estimate tokens from content
            self._last_tokens = self._estimate_tokens(content)
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
                    return f"Retrieved from Letta: {response_text}"  # No truncation
            
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
                self._last_tokens = usage.total_tokens
            else:
                # Fallback: estimate tokens
                self._last_tokens = self._estimate_tokens(query)
            
            return response
                
        except Exception as e:
            # Fallback: estimate tokens from query
            self._last_tokens = self._estimate_tokens(query)
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
                        return last_msg.content
                    elif hasattr(last_msg, 'text'):
                        return last_msg.text
            
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
                self._last_tokens = usage.total_tokens
            else:
                # Fallback: estimate tokens
                self._last_tokens = self._estimate_tokens(message)
            
            return response
                
        except Exception as e:
            # Fallback: estimate tokens from message
            self._last_tokens = self._estimate_tokens(message)
            raise Exception(f"Letta API error in chat: {e}")
    
    async def execute_step(self, step, step_index: int):
        """Override to track token usage from API responses."""
        from llmemory_meter.workload import StepResult
        import time
        
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
                success=True,
                tokens_used=self._last_tokens
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
                tokens_used=self._last_tokens
            )
    
    async def clear_memory(self, session_id: Optional[str] = None) -> str:
        """Clear memory by creating a new agent (workload isolation).
        
        MemGPT stores conversation history in agent context, so we create a new agent
        for each workload to ensure complete isolation.
        """
        try:
            # Generate new user_id and agent for workload isolation
            self._user_id = f"benchmark_user_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
            agent_name = f"benchmark_agent_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
            
            # Create new agent
            memgpt_config = self.config.get("memgpt_config") or {}
            self._setup_agent(agent_name, memgpt_config)
            
            return f"Memory cleared (new agent: {agent_name})"
        except Exception as e:
            return f"Error reinitializing MemGPT agent: {e}"
