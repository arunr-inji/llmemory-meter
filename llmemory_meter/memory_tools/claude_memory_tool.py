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
            self.model = claude_config.get("model", "claude-3-5-haiku-20241022")
            self.max_tokens = claude_config.get("max_tokens", 1000)
            self.temperature = claude_config.get("temperature", 0.2)
            
            # Memory storage (simple in-memory for now, Claude handles persistence)
            self._conversation_history = []
            self._last_tokens = 0  # Track token usage from last API call
            
        except ImportError:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")
        except Exception as e:
            raise Exception(f"Failed to initialize Claude: {e}")
    
    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store memory by adding to conversation context."""
        try:
            # Add to conversation history (Claude API doesn't support metadata in messages)
            memory_entry = {
                "role": "user",
                "content": f"Please remember this information: {content}"
            }
            
            # Store metadata separately if needed (not in the message structure)
            if metadata:
                # Could store metadata separately, but Claude API messages don't support it
                pass
            
            self._conversation_history.append(memory_entry)
            
            # Send to Claude to acknowledge storage
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "user", 
                        "content": f"I want you to remember this: {content}. Just acknowledge that you'll remember it."
                    }
                ]
            )
            
            # Track token usage (Claude API format)
            if hasattr(response, 'usage'):
                self._last_tokens = response.usage.input_tokens + response.usage.output_tokens
            else:
                self._last_tokens = 0
            
            return f"Stored in Claude Memory: {content}"
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
            
            # Track token usage
            if hasattr(response, 'usage'):
                self._last_tokens = response.usage.input_tokens + response.usage.output_tokens
            else:
                self._last_tokens = 0
            
            if response.content and len(response.content) > 0:
                response_text = response.content[0].text
                return f"Retrieved from Claude Memory for '{query}': {response_text}"
            
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
            
            # Track token usage
            if hasattr(response, 'usage'):
                self._last_tokens = response.usage.input_tokens + response.usage.output_tokens
            else:
                self._last_tokens = 0
            
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
                
                return f"Claude Memory chat response to '{message}': {response_text}"
            
            return f"Claude Memory chat response to '{message}': [No response received]"
        except Exception as e:
            raise Exception(f"Claude Memory chat failed: {e}")
    
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
                tokens_used=self._last_tokens,  # Use tracked tokens
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
