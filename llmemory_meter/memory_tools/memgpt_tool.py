"""MemGPT memory tool implementation."""

from typing import Dict, Any, Optional
import asyncio
from llmemory_meter.memory_tools.base import MemoryTool
from llmemory_meter.config_parser.env import Config


class MemGPTTool(MemoryTool):
    """MemGPT memory tool implementation with real API calls."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("memgpt", config)
        
        # Require OpenAI API key for MemGPT LLM
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY required for MemGPT")
        
        self.api_key = Config.OPENAI_API_KEY
        self._user_id = self.config.get("user_id", "benchmark_user")
        self._agent_id = None
        
        # Initialize MemGPT client
        self._initialize_memgpt_client()
    
    def _initialize_memgpt_client(self):
        """Initialize the MemGPT client with proper configuration."""
        try:
            # Import MemGPT (will need to be installed)
            import memgpt
            from memgpt.client.client import RESTClient
            
            # Get MemGPT configuration
            memgpt_config = self.config.get("memgpt_config", {})
            
            # Initialize MemGPT client
            # Note: This assumes MemGPT server is running locally
            base_url = memgpt_config.get("base_url", "http://localhost:8283")
            
            self.client = RESTClient(base_url=base_url)
            
            # Create or get agent
            agent_name = memgpt_config.get("agent_name", f"benchmark_agent_{self._user_id}")
            
            try:
                # Try to get existing agent
                agents = self.client.list_agents()
                existing_agent = next((a for a in agents if a.name == agent_name), None)
                
                if existing_agent:
                    self._agent_id = existing_agent.id
                else:
                    # Create new agent
                    agent_config = {
                        "name": agent_name,
                        "preset": memgpt_config.get("preset", "memgpt_chat"),
                        "persona": memgpt_config.get("persona", "I am a helpful AI assistant with persistent memory."),
                        "human": memgpt_config.get("human", "The user is conducting memory benchmarks.")
                    }
                    
                    agent = self.client.create_agent(**agent_config)
                    self._agent_id = agent.id
                    
            except Exception as e:
                raise Exception(f"Failed to initialize MemGPT agent: {e}")
                
        except ImportError:
            raise ImportError("MemGPT package not installed. Install with: pip install pymemgpt")
        except Exception as e:
            raise Exception(f"Failed to initialize MemGPT: {e}")
    
    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store memory in MemGPT by sending a message to the agent."""
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._sync_send_message, content)
            
            return f"Stored in MemGPT: {content[:50]}..."
        except Exception as e:
            raise Exception(f"MemGPT store failed: {e}")
    
    def _sync_send_message(self, content: str):
        """Synchronous wrapper for MemGPT message sending."""
        # Send message to agent (this stores it in MemGPT's memory system)
        response = self.client.send_message(
            agent_id=self._agent_id,
            message=f"Please remember this information: {content}",
            role="user"
        )
        return response
    
    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Retrieve memory from MemGPT by asking the agent."""
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._sync_query_memory, query)
            
            # Extract the assistant's response
            if result and hasattr(result, 'messages'):
                assistant_messages = [msg for msg in result.messages if msg.role == 'assistant']
                if assistant_messages:
                    response_text = assistant_messages[-1].text
                    return f"Retrieved from MemGPT for '{query}': {response_text[:200]}..."
            
            return f"No relevant memories found in MemGPT for query: '{query}'"
        except Exception as e:
            raise Exception(f"MemGPT retrieve failed: {e}")
    
    def _sync_query_memory(self, query: str):
        """Synchronous wrapper for MemGPT memory querying."""
        # Ask agent to recall information
        response = self.client.send_message(
            agent_id=self._agent_id,
            message=f"What do you remember about: {query}?",
            role="user"
        )
        return response
    
    async def chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Chat with MemGPT agent using its memory context."""
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._sync_chat, message)
            
            # Extract the assistant's response
            if result and hasattr(result, 'messages'):
                assistant_messages = [msg for msg in result.messages if msg.role == 'assistant']
                if assistant_messages:
                    response_text = assistant_messages[-1].text
                    return f"MemGPT chat response to '{message}': {response_text[:200]}..."
            
            return f"MemGPT chat response to '{message}': [No response received]"
        except Exception as e:
            raise Exception(f"MemGPT chat failed: {e}")
    
    def _sync_chat(self, message: str):
        """Synchronous wrapper for MemGPT chat."""
        response = self.client.send_message(
            agent_id=self._agent_id,
            message=message,
            role="user"
        )
        return response
