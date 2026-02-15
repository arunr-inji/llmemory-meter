"""
Command Line Interface for LLMemoryMeter

Provides a simple CLI to run benchmarks using YAML configuration.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from llmemory_meter.config_parser import ConfigManager
from llmemory_meter.comparator import MemoryComparator
from llmemory_meter.hybrid_evaluator import HybridEvaluator


async def run_benchmarks(config_file: str = None, verbose: bool = False):
    """Run benchmarks using configuration file."""
    
    print("🧠 LLMemoryMeter - AI Memory System Benchmarking")
    print("=" * 60)
    
    # Load configuration
    print(f"\n📋 Loading configuration...")
    if config_file:
        print(f"   Config file: {config_file}")
    else:
        print(f"   Using default config: {ConfigManager.get_default_config_file()}")
    
    try:
        config = ConfigManager.load_config(config_file)
    except Exception as e:
        print(f"\n❌ Failed to load configuration: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False
    
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
        comparator = MemoryComparator(config)
        
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
                        avg_accuracy = tool_metrics.get('avg_accuracy')
                        
                        # Build output string
                        status_icon = "✅" if success_rate == 100.0 else "⚠️"
                        output = f"   {status_icon} {tool_name}: {success_rate:.1f}% success, {avg_latency:.0f}ms avg"
                        
                        # Add accuracy if available
                        if avg_accuracy is not None:
                            # Show accuracy as percentage (0.0-1.0 → 0-100%)
                            output += f", {avg_accuracy*100:.1f}% accuracy"
                        
                        print(output)
                
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
            # Aggregate all workload results across all benchmarks for overall metrics
            from llmemory_meter.metrics import MetricsCalculator
            from llmemory_meter.workload import WorkloadResult, StepResult
            from collections import defaultdict
            from datetime import datetime

            all_workload_results = defaultdict(list)  # tool_name -> list of WorkloadResults

            for benchmark_name, benchmark_results in all_results.items():
                if "standard_results" in benchmark_results:
                    workload_results_dict = benchmark_results["standard_results"].get("workload_results", {})
                    # workload_results_dict is: {"Workload Name": {"tool1": result_dict, "tool2": result_dict}}
                    for workload_name, tools_dict in workload_results_dict.items():
                        if isinstance(tools_dict, dict):
                            for tool_name, result_dict in tools_dict.items():
                                # Reconstruct WorkloadResult from serialized dict
                                if isinstance(result_dict, dict) and 'tool_name' in result_dict:
                                    # Reconstruct StepResult objects
                                    step_results = []
                                    for step_dict in result_dict.get('step_results', []):
                                        step_result = StepResult(
                                            step_index=step_dict['step_index'],
                                            action=step_dict['action'],
                                            response=step_dict['response'],
                                            latency_ms=step_dict['latency_ms'],
                                            tokens_used=step_dict.get('tokens_used'),
                                            input_tokens=step_dict.get('input_tokens'),
                                            output_tokens=step_dict.get('output_tokens'),
                                            model=step_dict.get('model'),
                                            success=step_dict['success'],
                                            error_message=step_dict.get('error_message'),
                                            metadata=step_dict.get('metadata'),
                                            accuracy=step_dict.get('accuracy'),
                                            accuracy_by_provider=step_dict.get('accuracy_by_provider')
                                        )
                                        step_results.append(step_result)

                                    # Reconstruct WorkloadResult object
                                    workload_result = WorkloadResult(
                                        tool_name=result_dict['tool_name'],
                                        workload_name=result_dict['workload_name'],
                                        step_results=step_results,
                                        total_latency_ms=result_dict['total_latency_ms'],
                                        total_tokens_used=result_dict['total_tokens_used'],
                                        success_rate=result_dict['success_rate'],
                                        timestamp=datetime.fromisoformat(result_dict['timestamp'])
                                    )
                                    all_workload_results[tool_name].append(workload_result)

            # Calculate overall metrics across all benchmarks
            summary_results = {}
            if all_workload_results:
                overall_metrics = {}
                for tool_name, results_list in all_workload_results.items():
                    if results_list:
                        try:
                            metrics = MetricsCalculator.calculate_metrics(results_list, config=comparator.config)
                            overall_metrics[tool_name] = metrics
                        except Exception as e:
                            print(f"Warning: Error calculating overall metrics for {tool_name}: {e}")

                if overall_metrics:
                    summary_results["overall_metrics"] = {
                        name: metrics.to_dict() for name, metrics in overall_metrics.items()
                    }

                    # Generate accuracy comparison across all benchmarks
                    if config.metrics.accuracy:
                        provider_comparison = comparator._generate_provider_comparison(all_workload_results)
                        if provider_comparison:
                            summary_results["accuracy_comparison"] = provider_comparison

            if summary_results:
                comparator.print_summary(summary_results)
        
        # Print error summary if any steps failed
        total_failures = 0
        for benchmark_name, suite_results in all_results.items():
            # Skip benchmarks that had errors during execution
            if isinstance(suite_results, dict) and "error" in suite_results:
                continue
            
            # Check standard_results structure
            if isinstance(suite_results, dict) and "standard_results" in suite_results:
                workload_results_dict = suite_results["standard_results"].get("workload_results", {})
                for workload_name, tools_dict in workload_results_dict.items():
                    if isinstance(tools_dict, dict):
                        for tool_name, tool_results in tools_dict.items():
                            if hasattr(tool_results, 'step_results'):
                                failed_steps = [sr for sr in tool_results.step_results if not sr.success]
                                total_failures += len(failed_steps)
        
        if total_failures > 0:
            print(f"\n⚠️  {total_failures} step(s) failed during benchmark execution.")
            print(f"   See detailed errors above and in the JSON results file.")
        
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
    config_file = args.output or ConfigManager.get_default_config_file()
    
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


def evaluate_command(args):
    """Run hybrid evaluation using official benchmark scripts."""
    results_path = Path(args.results or "benchmark_results.json")
    if not results_path.exists():
        print(f"❌ Results file not found: {results_path}")
        return False

    benchmark_name = args.benchmark
    judge = args.judge
    config = ConfigManager.load_config(args.config) if args.config else None
    benchmark_config = None
    if config:
        benchmark_config = ConfigManager.get_benchmark_config(config, benchmark_name)

    with results_path.open("r", encoding="utf-8") as f:
        results_data = json.load(f)

    all_benchmarks = results_data.get("results", {})
    benchmark_results = all_benchmarks.get(benchmark_name)
    if not benchmark_results:
        for name in all_benchmarks.keys():
            if name.lower() == benchmark_name.lower():
                benchmark_name = name
                benchmark_results = all_benchmarks[name]
                break
    if not benchmark_results:
        print(f"❌ Benchmark '{benchmark_name}' not found in results file.")
        return False

    workload_results = benchmark_results.get("standard_results", {}).get("workload_results")
    if not workload_results:
        print(f"❌ No workload results found for benchmark '{benchmark_name}'.")
        return False

    tools = sorted({tool for data in workload_results.values() for tool in data.keys()})
    if not tools:
        print(f"❌ No tools found for benchmark '{benchmark_name}'.")
        return False

    evaluator = HybridEvaluator()
    evaluations = []

    if benchmark_name.lower() == "longmemeval":
        config_subset = None
        if benchmark_config and benchmark_config.settings:
            config_subset = benchmark_config.settings.get("subset")
        subset = args.subset or config_subset or "S"
        for tool_name in tools:
            evaluations.append(
                evaluator.evaluate_longmemeval(
                    tool_name=tool_name,
                    workload_results=workload_results,
                    subset=subset,
                    judge_model=judge,
                )
            )
    elif benchmark_name.lower() == "membench":
        eval_script = Path(args.eval_script) if args.eval_script else None
        for tool_name in tools:
            evaluations.append(
                evaluator.evaluate_membench(
                    tool_name=tool_name,
                    workload_results=workload_results,
                    eval_script=eval_script,
                )
            )
    else:
        print(f"❌ Hybrid evaluation not supported for benchmark '{benchmark_name}'.")
        return False

    print("\n📊 Hybrid Evaluation Results:")
    for result in evaluations:
        if result.error:
            print(f"  • {result.tool_name}: error - {result.error}")
            continue
        if benchmark_name.lower() == "membench" and result.judge_model == "deterministic_canary":
            print(f"  • {result.tool_name}: deterministic canary completed (diagnostic only; not publication accuracy)")
            continue
        if result.accuracy is not None:
            print(f"  • {result.tool_name}: {result.accuracy*100:.2f}% accuracy")
        else:
            print(f"  • {result.tool_name}: evaluation complete (see logs)")

    return True


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="LLMemoryMeter - AI Memory System Benchmarking Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  llmemory run                          # Run with default config (industry-benchmarks.yml)
  llmemory run --config longmemeval-only.yml  # LongMemEval-only run
  llmemory run --config my_config.yml  # Run with custom config
  llmemory create-config                # Create default config file
  llmemory create-config --output custom.yml # Create custom config file

Environment Variables:
  LLMEMORY_DEFAULT_CONFIG=configs/industry-benchmarks.yml  # Change default config
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

    # Evaluate command
    evaluate_parser = subparsers.add_parser('evaluate', help='Run hybrid benchmark evaluation')
    evaluate_parser.add_argument('--benchmark', '-b', required=True, help='Benchmark name (LongMemEval, MemBench)')
    evaluate_parser.add_argument('--judge', default='gpt-4o', help='Judge model (LongMemEval only)')
    evaluate_parser.add_argument('--results', '-r', help='Results JSON file path')
    evaluate_parser.add_argument('--config', '-c', help='Config file (for benchmark settings)')
    evaluate_parser.add_argument('--subset', help='LongMemEval subset (S, M, oracle)')
    evaluate_parser.add_argument('--eval-script', help='MemBench eval script path')
    
    args = parser.parse_args()
    
    if args.command == 'run':
        success = asyncio.run(run_benchmarks(args.config, args.verbose))
        sys.exit(0 if success else 1)
    
    elif args.command == 'create-config':
        success = create_config_command(args)
        sys.exit(0 if success else 1)

    elif args.command == 'evaluate':
        success = evaluate_command(args)
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
