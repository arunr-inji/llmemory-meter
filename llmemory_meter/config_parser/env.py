"""Configuration management for LLMemoryMeter."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Find .env file starting from this module's directory and going up
try:
    # Start from this file's directory and go up to find .env
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent  # Go up two levels to project root
    env_file = project_root / ".env"
    
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
    else:
        # Try to find .env by searching upwards
        load_dotenv(verbose=False)
except (PermissionError, FileNotFoundError, OSError):
    # If .env file can't be loaded, continue with system environment variables
    pass


class Config:
    """Configuration class for LLMemoryMeter."""
    
    # API Keys
    MEM0_API_KEY: Optional[str] = os.getenv("MEM0_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    
    # MEMGPT_API_KEY: Special handling for base64 keys ending with =
    # load_dotenv() has a bug that truncates values ending with = even with quotes
    # Workaround: manually parse from .env file
    _memgpt_key = os.getenv("MEMGPT_API_KEY")
    if _memgpt_key and len(_memgpt_key) < 107:  # Expected length is 107
        # Try to read directly from .env file
        try:
            current_dir = Path(__file__).resolve().parent
            project_root = current_dir.parent.parent
            env_file = project_root / ".env"
            if env_file.exists():
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.startswith('MEMGPT_API_KEY'):
                            # Extract value after =, remove quotes and whitespace
                            _memgpt_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                            break
        except:
            pass
    MEMGPT_API_KEY: Optional[str] = _memgpt_key
    
    ZEP_API_KEY: Optional[str] = os.getenv("ZEP_API_KEY")
    LANGCHAIN_API_KEY: Optional[str] = os.getenv("LANGCHAIN_API_KEY")
    
    # Performance settings
    DEFAULT_TIMEOUT: int = int(os.getenv("DEFAULT_TIMEOUT", "30"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Memory tool settings
    SUPPORTED_TOOLS = ["mem0", "openai_memory", "memgpt", "claude_memory"]
    
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

        # Baseline tools don't require API keys and are always available
        available_tools.append("baseline")
        available_tools.append("full_context")

        return available_tools
