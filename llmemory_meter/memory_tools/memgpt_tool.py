"""MemGPT/Letta memory tool implementation using Letta Python client."""

from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from llmemory_meter.memory_tools.base import MemoryTool
from llmemory_meter.config_parser import Config
from llmemory_meter.logging_utils import get_logger

logger = get_logger(__name__)


class MemGPTTool(MemoryTool):
    """MemGPT/Letta memory tool implementation using the Letta Python client."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("memgpt", config)
        
        # Require Letta API key
        if not Config.MEMGPT_API_KEY:
            raise ValueError("MEMGPT_API_KEY required for Letta Cloud")
        
        self._agent_id = None
        self._last_tokens = 0  # Track token usage from last API call
        
        # Create dedicated thread pool executor to avoid shared pool exhaustion
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="memgpt_")
        
        # Initialize Letta client
        self._initialize_letta_client()
    
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
            from llmemory_meter.config_parser import Config as EnvConfig
            
            # List existing agents
            agents = list(self.client.agents.list())
            
            # Find existing agent by name
            existing_agent = next((a for a in agents if a.name == agent_name), None)
            
            if existing_agent:
                self._agent_id = existing_agent.id
            else:
                # Create new agent with OpenAI credentials
                from llmemory_meter.config_parser import Config as EnvConfig
                
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
            logger.warning("Error in _setup_agent: %s", e)
            # Fallback: try to list and use first available agent
            try:
                agents = list(self.client.agents.list())
                if agents:
                    self._agent_id = agents[0].id
                    logger.warning("Using first available agent: %s", self._agent_id)
                else:
                    raise Exception(f"Could not set up Letta agent: {e}")
            except Exception as fallback_error:
                raise Exception(f"Could not set up Letta agent: {fallback_error}") from fallback_error

    def _agent_name(self) -> str:
        """Generate a short, unique agent name for the current instance."""
        return f"benchmark_agent_{self._session_id}"
    
    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store memory in Letta by sending a message to the agent."""
        try:
            # Run in executor to avoid blocking
            result = await self._run_in_executor(self._sync_send_message, content)
            
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
            result = await self._run_in_executor(self._sync_query_memory, query)
            
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
            result = await self._run_in_executor(self._sync_chat, message)
            
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
                    logger.error("Error deleting MemGPT agent: %s", e)
                    raise

            # Generate new user_id and agent for workload isolation
            self._reset_session()
            agent_name = self._agent_name()
            memgpt_config = self.config.get("memgpt_config") or {}
            self._setup_agent(agent_name, memgpt_config)
            
            return f"Memory cleared (new agent: {self._agent_id})"
        except Exception as e:
            return f"Error reinitializing MemGPT agent: {e}"
