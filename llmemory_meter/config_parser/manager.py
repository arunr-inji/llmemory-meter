"""
Configuration Management for LLMemoryMeter

Handles YAML-based configuration for memory tools, benchmarks, and metrics.
"""

import os
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
from llmemory_meter.config_parser.env import Config as EnvConfig


@dataclass
class MemoryToolConfig:
    """Configuration for a single memory tool."""
    name: str
    enabled: bool = True
    api_key_env: Optional[str] = None
    model: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark execution."""
    name: str
    enabled: bool = True
    settings: Optional[Dict[str, Any]] = None


@dataclass
class MetricsConfig:
    """Configuration for metrics collection."""
    latency: bool = True
    success_rate: bool = True
    token_usage: bool = True
    accuracy: bool = False  # Future feature
    memory_quality: bool = False  # Future feature


@dataclass
class LLMemoryMeterConfig:
    """Main configuration for LLMemoryMeter."""
    memory_tools: List[MemoryToolConfig]
    benchmarks: List[BenchmarkConfig]
    metrics: MetricsConfig
    output: Dict[str, Any]
    general: Dict[str, Any]


class ConfigManager:
    """Manages YAML configuration for LLMemoryMeter."""
    
    DEFAULT_CONFIG_FILE = "configs/default.yml"
    
    @staticmethod
    def create_default_config() -> LLMemoryMeterConfig:
        """Create default configuration."""
        return LLMemoryMeterConfig(
            memory_tools=[
                MemoryToolConfig(
                    name="mem0",
                    enabled=True,
                    api_key_env="MEM0_API_KEY",
                    model="gpt-4o-mini",
                    settings={
                        "user_id": "benchmark_user",
                        "llm_provider": "openai",
                        "llm_api_key_env": "OPENAI_API_KEY",
                        "vector_store": {
                            "provider": "qdrant",
                            "host": "localhost",
                            "port": 6333,
                            "collection_name": "test"
                        }
                    }
                ),
                MemoryToolConfig(
                    name="openai_memory",
                    enabled=True,
                    api_key_env="OPENAI_API_KEY",
                    model="gpt-4o-mini",
                    settings={
                        "temperature": 0.3,
                        "max_tokens": 300
                    }
                )
            ],
            benchmarks=[
                BenchmarkConfig(name="Conversational AI Memory", enabled=True),
                BenchmarkConfig(name="Long Context Memory", enabled=True),
                BenchmarkConfig(name="Persona Consistency", enabled=False),
                BenchmarkConfig(name="Technical Performance", enabled=False),
                BenchmarkConfig(name="Memory Stress Testing", enabled=False),
                BenchmarkConfig(name="Domain-Specific Applications", enabled=False)
            ],
            metrics=MetricsConfig(
                latency=True,
                success_rate=True,
                token_usage=True,
                accuracy=False,
                memory_quality=False
            ),
            output={
                "save_results": True,
                "output_file": "benchmark_results.json",
                "print_summary": True,
                "detailed_logs": False
            },
            general={
                "timeout": 30,
                "max_retries": 3,
                "concurrent_tools": True,
                "debug": False
            }
        )
    
    @staticmethod
    def save_default_config(file_path: str = None) -> str:
        """Save default configuration to YAML file."""
        if file_path is None:
            file_path = ConfigManager.DEFAULT_CONFIG_FILE
        
        config = ConfigManager.create_default_config()
        config_dict = asdict(config)
        
        with open(file_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2, sort_keys=False)
        
        return file_path
    
    @staticmethod
    def load_config(file_path: str = None) -> LLMemoryMeterConfig:
        """Load configuration from YAML file."""
        if file_path is None:
            file_path = ConfigManager.DEFAULT_CONFIG_FILE
        
        # Create default config if file doesn't exist
        if not os.path.exists(file_path):
            print(f"⚠️  Config file {file_path} not found. Creating default config...")
            ConfigManager.save_default_config(file_path)
            print(f"✅ Created default config: {file_path}")
        
        try:
            with open(file_path, 'r') as f:
                config_dict = yaml.safe_load(f)
            
            # Convert dict to dataclass
            return ConfigManager._dict_to_config(config_dict)
        
        except Exception as e:
            print(f"❌ Error loading config from {file_path}: {e}")
            print("🔧 Using default configuration instead")
            return ConfigManager.create_default_config()
    
    @staticmethod
    def _dict_to_config(config_dict: Dict[str, Any]) -> LLMemoryMeterConfig:
        """Convert dictionary to LLMemoryMeterConfig."""
        # Convert memory tools
        memory_tools = []
        for tool_dict in config_dict.get('memory_tools', []):
            memory_tools.append(MemoryToolConfig(**tool_dict))
        
        # Convert benchmarks
        benchmarks = []
        for bench_dict in config_dict.get('benchmarks', []):
            benchmarks.append(BenchmarkConfig(**bench_dict))
        
        # Convert metrics
        metrics_dict = config_dict.get('metrics', {})
        metrics = MetricsConfig(**metrics_dict)
        
        return LLMemoryMeterConfig(
            memory_tools=memory_tools,
            benchmarks=benchmarks,
            metrics=metrics,
            output=config_dict.get('output', {}),
            general=config_dict.get('general', {})
        )
    
    @staticmethod
    def validate_config(config: LLMemoryMeterConfig) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        # Check if any tools are enabled
        enabled_tools = [tool for tool in config.memory_tools if tool.enabled]
        if not enabled_tools:
            issues.append("No memory tools are enabled")
        
        # Check API keys for enabled tools
        for tool in enabled_tools:
            if tool.api_key_env:
                api_key = os.getenv(tool.api_key_env)
                if not api_key:
                    issues.append(f"Missing API key: {tool.api_key_env} for tool '{tool.name}'")
            
            # Check additional API keys (e.g., OpenAI for Mem0)
            if tool.name == "mem0" and tool.settings:
                llm_key_env = tool.settings.get("llm_api_key_env")
                if llm_key_env:
                    llm_key = os.getenv(llm_key_env)
                    if not llm_key:
                        issues.append(f"Missing LLM API key: {llm_key_env} for Mem0")
        
        # Check if any benchmarks are enabled
        enabled_benchmarks = [bench for bench in config.benchmarks if bench.enabled]
        if not enabled_benchmarks:
            issues.append("No benchmarks are enabled")
        
        # Check output directory
        output_file = config.output.get('output_file')
        if output_file:
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                issues.append(f"Output directory does not exist: {output_dir}")
        
        return issues
    
    @staticmethod
    def get_enabled_tools(config: LLMemoryMeterConfig) -> List[str]:
        """Get list of enabled tool names."""
        return [tool.name for tool in config.memory_tools if tool.enabled]
    
    @staticmethod
    def get_enabled_benchmarks(config: LLMemoryMeterConfig) -> List[str]:
        """Get list of enabled benchmark names."""
        return [bench.name for bench in config.benchmarks if bench.enabled]
    
    @staticmethod
    def get_tool_config(config: LLMemoryMeterConfig, tool_name: str) -> Optional[MemoryToolConfig]:
        """Get configuration for specific tool."""
        for tool in config.memory_tools:
            if tool.name == tool_name:
                return tool
        return None
