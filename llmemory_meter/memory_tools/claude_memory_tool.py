"""Claude Memory API tool implementation."""

from typing import Dict, Any, Optional
import asyncio
from llmemory_meter.memory_tools.base import MemoryTool
from llmemory_meter.config_parser.env import Config


class ClaudeMemoryTool(MemoryTool):
    """Claude Memory API tool implementation with real API calls."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("claude_memory", config)
        
        # Require Anthropic API key
        if not Config.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY required for Claude Memory")
        
        self.api_key = Config.ANTHROPIC_API_KEY
        self._user_id = self.config.get("user_id", "benchmark_user")
        
        # Initialize Claude client
        self._initialize_claude_client()
    
    def _initialize_claude_client(self):
        """Initialize the Claude client with proper configuration."""
        try:
            import anthropic
            
            # Get Claude configuration
            claude_config = self.config.get("claude_config", {})
            
            # Initialize Anthropic client
            self.client = anthropic.AsyncAnthropic(
                api_key=self.api_key
            )
            
            # Model configuration
            self.model = claude_config.get("model", "claude-3-5-sonnet-20241022")
            self.max_tokens = claude_config.get("max_tokens", 1000)
            self.temperature = claude_config.get("temperature", 0.2)
            
            # Memory storage (simple in-memory for now, Claude handles persistence)
            self._conversation_history = []
            
        except ImportError:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")
        except Exception as e:
            raise Exception(f"Failed to initialize Claude: {e}")
    
    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store memory by adding to conversation context."""
        try:
            # Add to conversation history
            memory_entry = {
                "role": "user",
                "content": f"Please remember this information: {content}"
            }
            
            if metadata:
                memory_entry["metadata"] = metadata
            
            self._conversation_history.append(memory_entry)
            
            # Send to Claude to acknowledge storage
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=100,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "user", 
                        "content": f"I want you to remember this: {content}. Just acknowledge that you'll remember it."
                    }
                ]
            )
            
            return f"Stored in Claude Memory: {content[:50]}..."
        except Exception as e:
            raise Exception(f"Claude Memory store failed: {e}")
    
    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Retrieve memory from Claude by asking about stored information."""
        try:
            # Build context from conversation history
            context_messages = self._conversation_history.copy()
            context_messages.append({
                "role": "user",
                "content": f"Based on what I've told you to remember, what do you know about: {query}?"
            })
            
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=context_messages
            )
            
            if response.content and len(response.content) > 0:
                response_text = response.content[0].text
                return f"Retrieved from Claude Memory for '{query}': {response_text[:200]}..."
            
            return f"No relevant memories found in Claude Memory for query: '{query}'"
        except Exception as e:
            raise Exception(f"Claude Memory retrieve failed: {e}")
    
    async def chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Chat with Claude using memory context."""
        try:
            # Build full conversation context
            context_messages = self._conversation_history.copy()
            context_messages.append({
                "role": "user",
                "content": message
            })
            
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=context_messages
            )
            
            if response.content and len(response.content) > 0:
                response_text = response.content[0].text
                
                # Add response to conversation history
                self._conversation_history.append({
                    "role": "user",
                    "content": message
                })
                self._conversation_history.append({
                    "role": "assistant", 
                    "content": response_text
                })
                
                return f"Claude Memory chat response to '{message}': {response_text[:200]}..."
            
            return f"Claude Memory chat response to '{message}': [No response received]"
        except Exception as e:
            raise Exception(f"Claude Memory chat failed: {e}")
