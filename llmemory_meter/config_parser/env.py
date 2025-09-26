"""Configuration management for LLMemoryMeter."""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration class for LLMemoryMeter."""
    
    # API Keys
    MEM0_API_KEY: Optional[str] = os.getenv("MEM0_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    ZEP_API_KEY: Optional[str] = os.getenv("ZEP_API_KEY")
    LANGCHAIN_API_KEY: Optional[str] = os.getenv("LANGCHAIN_API_KEY")
    
    # Performance settings
    DEFAULT_TIMEOUT: int = int(os.getenv("DEFAULT_TIMEOUT", "30"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Memory tool settings
    SUPPORTED_TOOLS = ["mem0", "openai_memory"]
    
    @classmethod
    def validate_api_keys(cls) -> dict:
        """Validate which API keys are available."""
        available_keys = {}
        
        if cls.MEM0_API_KEY:
            available_keys["mem0"] = True
        if cls.OPENAI_API_KEY:
            available_keys["openai_memory"] = True
            
        return available_keys
    
    @classmethod
    def get_available_tools(cls) -> list:
        """Get list of tools that can be used based on available API keys."""
        available_keys = cls.validate_api_keys()
        available_tools = []
        
        if available_keys.get("mem0"):
            available_tools.append("mem0")
        if available_keys.get("openai_memory"):
            available_tools.append("openai_memory")
            
        return available_tools
