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
    workloads: Optional[List[str]] = None  # Specific workload names to run (None = all)


@dataclass
class MetricsConfig:
    """Configuration for metrics collection."""
    latency: bool = True
    success_rate: bool = True
    token_usage: bool = True
    accuracy: bool = False  # Future feature
    memory_quality: bool = False  # Future feature
    cost_analysis: bool = False


@dataclass
class LLMemoryMeterConfig:
    """Main configuration for LLMemoryMeter."""
    memory_tools: List[MemoryToolConfig]
    benchmarks: List[BenchmarkConfig]
    metrics: MetricsConfig
    output: Dict[str, Any]
    general: Dict[str, Any]
    accuracy: Optional[Dict[str, Any]] = None  # Accuracy evaluation configuration
    pricing: Optional[Dict[str, Any]] = None  # Optional pricing overrides


class ConfigManager:
    """Manages YAML configuration for LLMemoryMeter."""
    
    @classmethod
    def get_default_config_file(cls) -> str:
        """Get default config file from environment or fallback to starter.yml."""
        import os
        return os.getenv("LLMEMORY_DEFAULT_CONFIG", "configs/starter.yml")
    
    # Set default config file
    DEFAULT_CONFIG_FILE = "configs/starter.yml"  # Will be overridden by get_default_config_file() when called
    
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
                ),
                MemoryToolConfig(
                    name="zep",
                    enabled=True,
                    api_key_env="ZEP_API_KEY",
                    settings={
                        "api_url": "https://api.getzep.com"
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
                memory_quality=False,
                cost_analysis=False
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
    def resolve_config_path(config_file: str) -> str:
        """Resolve config file path, checking configs/ folder if needed."""
        import os
        
        # If it's already a full path that exists, use it
        if os.path.exists(config_file):
            return config_file
        
        # If it doesn't have configs/ prefix, try adding it
        if not config_file.startswith("configs/"):
            configs_path = f"configs/{config_file}"
            if os.path.exists(configs_path):
                return configs_path
        
        # Return original path (will fail later with clear error)
        return config_file
    
    @staticmethod
    def load_config(file_path: str = None) -> LLMemoryMeterConfig:
        """Load configuration from YAML file."""
        if file_path is None:
            file_path = ConfigManager.get_default_config_file()
        else:
            # Resolve the path to check configs/ folder
            file_path = ConfigManager.resolve_config_path(file_path)
        
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
            raise Exception(f"Failed to load configuration from {file_path}: {e}")
    
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
        
        # Get accuracy configuration
        accuracy_config = config_dict.get('accuracy', None)
        pricing_config = config_dict.get('pricing', None)
        
        return LLMemoryMeterConfig(
            memory_tools=memory_tools,
            benchmarks=benchmarks,
            metrics=metrics,
            output=config_dict.get('output', {}),
            general=config_dict.get('general', {}),
            accuracy=accuracy_config,
            pricing=pricing_config
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
        
        # Validate accuracy configuration if accuracy metric is enabled
        metrics = config.metrics
        if metrics.get('accuracy', False):
            accuracy_config = config.accuracy
            if not accuracy_config:
                issues.append(
                    "metrics.accuracy is enabled but 'accuracy' section is missing.\n"
                    "Add to your config:\n\n"
                    "  accuracy:\n"
                    "    providers:\n"
                    "      openai:\n"
                    "        - text-embedding-3-small"
                )
            elif not accuracy_config.get("providers"):
                issues.append(
                    "metrics.accuracy is enabled but 'accuracy.providers' is missing.\n"
                    "Recommended configuration:\n\n"
                    "  accuracy:\n"
                    "    providers:\n"
                    "      openai:\n"
                    "        - text-embedding-3-small"
                )
            else:
                providers = accuracy_config.get("providers", {})
                if not isinstance(providers, dict):
                    issues.append(
                        "accuracy.providers must be a dictionary.\n"
                        "Format:\n"
                        "  providers:\n"
                        "    openai: [model1, model2]\n"
                        "    local: [model1, model2]"
                    )
                else:
                    for provider, models in providers.items():
                        if provider not in ["openai", "local"]:
                            issues.append(
                                f"Invalid accuracy provider: '{provider}'.\n"
                                f"Supported providers: 'openai', 'local'"
                            )
                        if not isinstance(models, list) or not models:
                            issues.append(
                                f"accuracy.providers.{provider} must be a non-empty list of model names"
                            )
                        else:
                            for model in models:
                                if not isinstance(model, str) or not model.strip():
                                    issues.append(
                                        f"Invalid model in accuracy.providers.{provider}: must be non-empty string"
                                    )
        
        # Validate Mem0 vector_store configuration (to avoid SQLite threading issues)
        for tool in enabled_tools:
            if tool.name == "mem0":
                if not tool.settings or "vector_store" not in tool.settings:
                    issues.append(
                        "Mem0 requires 'vector_store' configuration to avoid threading issues.\n"
                        "Add to your config file under mem0 settings:\n\n"
                        "  settings:\n"
                        "    vector_store:\n"
                        "      provider: qdrant\n"
                        "      host: localhost\n"
                        "      port: 6333\n"
                        "      collection_name: llmemory_benchmarks\n\n"
                        "Note: Without this, Mem0 uses local SQLite which causes threading errors."
                    )
        
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

    @staticmethod
    def get_benchmark_config(config: LLMemoryMeterConfig, benchmark_name: str) -> Optional[BenchmarkConfig]:
        """Get configuration for specific benchmark."""
        for benchmark in config.benchmarks:
            if benchmark.name == benchmark_name:
                return benchmark
        return None
