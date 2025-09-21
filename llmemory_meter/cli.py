"""
Command Line Interface for LLMemoryMeter

Provides a simple CLI to run benchmarks using YAML configuration.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from llmemory_meter.config_parser import ConfigManager
from llmemory_meter.comparator import MemoryComparator


async def run_benchmarks(config_file: str = None, verbose: bool = False):
    """Run benchmarks using configuration file."""
    
    print("🧠 LLMemoryMeter - AI Memory System Benchmarking")
    print("=" * 60)
    
    # Load configuration
    print(f"\n📋 Loading configuration...")
    if config_file:
        print(f"   Config file: {config_file}")
    else:
        print(f"   Using default config: {ConfigManager.DEFAULT_CONFIG_FILE}")
    
    config = ConfigManager.load_config(config_file)
    
    # Validate configuration
    print("\n🔍 Validating configuration...")
    issues = ConfigManager.validate_config(config)
    if issues:
        print("❌ Configuration issues found:")
        for issue in issues:
            print(f"   • {issue}")
        
        if any("Missing API key" in issue for issue in issues):
            print("\n💡 Setup instructions:")
            print("   1. Copy .env.example to .env")
            print("   2. Add your API keys to .env file")
            print("   3. Run the command again")
        
        return False
    
    print("✅ Configuration valid")
    
    # Show what will be tested
    enabled_tools = ConfigManager.get_enabled_tools(config)
    enabled_benchmarks = ConfigManager.get_enabled_benchmarks(config)
    
    print(f"\n🔧 Memory Tools to test: {len(enabled_tools)}")
    for tool in enabled_tools:
        tool_config = ConfigManager.get_tool_config(config, tool)
        model = tool_config.model if tool_config and tool_config.model else "default"
        print(f"   • {tool} ({model})")
    
    print(f"\n📊 Benchmarks to run: {len(enabled_benchmarks)}")
    for benchmark in enabled_benchmarks:
        print(f"   • {benchmark}")
    
    # Initialize comparator with config
    print(f"\n🚀 Initializing memory tools...")
    try:
        comparator = MemoryComparator()
        
        # Run benchmarks
        print(f"\n🧪 Running benchmarks...")
        all_results = {}
        
        for benchmark_name in enabled_benchmarks:
            print(f"\n--- Running: {benchmark_name} ---")
            
            try:
                results = await comparator.run_benchmark_suite(benchmark_name, enabled_tools)
                all_results[benchmark_name] = results
                
                # Show quick results
                if "standard_results" in results and "overall_metrics" in results["standard_results"]:
                    metrics = results["standard_results"]["overall_metrics"]
                    for tool_name, tool_metrics in metrics.items():
                        success_rate = tool_metrics.get('success_rate', 0)
                        avg_latency = tool_metrics.get('avg_latency_ms', 0)
                        print(f"   {tool_name}: {success_rate:.1f}% success, {avg_latency:.0f}ms avg")
                
            except Exception as e:
                print(f"   ❌ Failed: {e}")
                if verbose:
                    import traceback
                    traceback.print_exc()
                all_results[benchmark_name] = {"error": str(e)}
        
        # Generate final report
        print(f"\n📈 Generating final report...")
        
        # Save results if configured
        if config.output.get('save_results', True):
            output_file = config.output.get('output_file', 'benchmark_results.json')
            
            # Save detailed results
            final_results = {
                "config": {
                    "tools": enabled_tools,
                    "benchmarks": enabled_benchmarks,
                    "metrics": config.metrics.__dict__
                },
                "results": all_results
            }
            
            comparator.save_results(final_results, output_file)
            print(f"💾 Results saved to: {output_file}")
        
        # Print summary if configured
        if config.output.get('print_summary', True):
            # Create summary from all results
            summary_results = {}
            for benchmark_name, benchmark_results in all_results.items():
                if "standard_results" in benchmark_results:
                    summary_results.update(benchmark_results["standard_results"])
            
            if summary_results:
                comparator.print_summary(summary_results)
        
        print(f"\n✅ Benchmarking complete!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during benchmarking: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def create_config_command(args):
    """Create default configuration file."""
    config_file = args.output or ConfigManager.DEFAULT_CONFIG_FILE
    
    if Path(config_file).exists() and not args.force:
        print(f"❌ Config file {config_file} already exists. Use --force to overwrite.")
        return False
    
    try:
        created_file = ConfigManager.save_default_config(config_file)
        print(f"✅ Created configuration file: {created_file}")
        print(f"\n📝 Next steps:")
        print(f"   1. Edit {created_file} to customize your benchmarks")
        print(f"   2. Set up your API keys in .env file")
        print(f"   3. Run: llmemory-meter run --config {created_file}")
        return True
    except Exception as e:
        print(f"❌ Error creating config: {e}")
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="LLMemoryMeter - AI Memory System Benchmarking Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  llmemory run                                # Run with default config
  llmemory run --config my_config.yml        # Run with custom config
  llmemory run --config configs/example.yml  # Run with example config
  llmemory create-config                      # Create default config file
  llmemory create-config --output custom.yml # Create custom config file
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run benchmarks')
    run_parser.add_argument('--config', '-c', help='Configuration file path')
    run_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    # Create config command
    config_parser = subparsers.add_parser('create-config', help='Create default configuration file')
    config_parser.add_argument('--output', '-o', help='Output file path')
    config_parser.add_argument('--force', '-f', action='store_true', help='Overwrite existing file')
    
    args = parser.parse_args()
    
    if args.command == 'run':
        success = asyncio.run(run_benchmarks(args.config, args.verbose))
        sys.exit(0 if success else 1)
    
    elif args.command == 'create-config':
        success = create_config_command(args)
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
