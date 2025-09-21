# Adding New Memory Tools

## Quick Start

1. **Copy template**: `cp template_tool.py your_tool.py`
2. **Implement 3 methods**: `store_memory`, `retrieve_memory`, `chat`
3. **Add to exports**: Update `__init__.py`
4. **Add to comparator**: Update `../comparator.py`
5. **Add API key**: Update `../config.py`

## Implementation Template

```python
class YourTool(MemoryTool):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("your_tool", config)
        # Your initialization
    
    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        # Store logic
        return f"Stored: {content[:50]}..."
    
    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        # Retrieve logic
        return f"Retrieved for '{query}': [response]"
    
    async def chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        # Chat logic
        return f"Response to '{message}': [response]"
```

## Required Updates

**1. `__init__.py`**:
```python
from .your_tool import YourTool
__all__ = [..., "YourTool"]
```

**2. `../comparator.py`**:
```python
if tool_name == "your_tool":
    return YourTool(self.config.get("your_tool", {}))
```

**3. `../config.py`**:
```python
YOUR_TOOL_API_KEY: Optional[str] = os.getenv("YOUR_TOOL_API_KEY")
```

That's it! Your tool will work with all benchmarks.
