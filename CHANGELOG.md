# Changelog

## [Unreleased]

### Added

- **Multi-provider, multi-model accuracy evaluation**: Support for evaluating responses with multiple embedding models simultaneously from different providers (OpenAI, local sentence-transformers)
- **Debug flag for response prefixes**: Conditional `[tool_name]` prefixes in responses (debug: true for development, false for production benchmarks)
- **Enhanced configuration validation**: Early validation catches invalid accuracy providers, missing Mem0 vector_store, and other config errors with helpful error messages
- **Real-time error visibility**: Immediate console printing of step failures and timeouts with emoji indicators (❌ for failures, ⏱️ for timeouts)
- **Error summary reporting**: Post-benchmark summary showing total failures with guidance to detailed logs
- **Configuration Validation section** in README.md with examples
- **Error Handling and Debugging section** in README.md with common patterns
- **Chat operation limitation** documented in KNOWN_ISSUES.md (chat returns memory context, not LLM-generated responses)

### Changed

- **Removed Memory Stress Testing benchmark**: Empty suite consolidated into Technical Performance
- **Updated .gitignore**: Now excludes `results/` directory (already present in remote)
- **Accuracy configuration format**: Now requires `providers: {dict of lists}` format only (all config files updated)
- **All 6 memory tools updated**: Added conditional debug prefixes (mem0, openai_memory, memgpt, claude_memory, zep, baseline)
- **Removed backwards compatibility**: Old accuracy config format (`providers: [list]`) no longer supported; invalid formats now print clear error messages

### Fixed

- **Prevented silent failures**: Invalid accuracy provider configurations now caught at validation time
- **Mem0 SQLite threading prevention**: Early validation requires `vector_store` configuration
- **Improved accuracy evaluation**: First provider's first model becomes primary accuracy score, with all scores in `accuracy_by_provider`

### Documentation

- Updated README.md: Multi-provider accuracy, debug mode, configuration validation, error handling
- Updated configs/README.md: Debug flag documentation
- Updated docs/architecture.md: Accuracy evaluation flow, debug mode behavior
- Updated KNOWN_ISSUES.md: Chat operation limitations, Mem0 validation enhancements

---

## [0.1.1] - 2024-12-11

### Fixed

- **JSON Serialization**: WorkloadResult objects now properly serialize to structured JSON instead of string representations
- **MemGPT Context Accumulation**: Use unique agent per benchmark run to prevent token growth (was 3.4K→38K, now consistent ~3-5K)
- **Zep Knowledge Graph Accumulation**: Use unique user_id per run to prevent context growth (was 2KB→44KB, now consistent ~2KB)
- **Mem0 SQLite Threading**: Create new Memory() instances per operation for thread safety
- **Terminal Output**: Added ⚠️ icons to highlight tools with <100% success rates

### Changed

- **configs/comprehensive.yml**: Disabled Memory Stress Testing (too slow, 15-20min)
- **configs/\***: Removed hardcoded user_ids to enable automatic isolation
- **Zep token counting**: Now counts full response to reflect real LLM costs
- **All tools**: Accurate token tracking (extract from API or estimate with tiktoken)

### Added

- **KNOWN_ISSUES.md**: Comprehensive documentation of limitations and fixes
- **docs/PERFORMANCE_NOTES.md**: Detailed performance analysis and recommendations
- **configs/claude-only.yml**: Isolated testing configuration for Claude Memory
- **Zep hybrid API**: Automatic switching between thread.add_messages and graph.add based on message size

### Documentation

- Documented Claude's 97.2% success rate (3 failures in Memory Capacity Test)
- Explained MemGPT's high token usage (agentic architecture with reasoning)
- Noted Zep's 8-second delays (knowledge graph processing, can be async in production)

---

## [0.1.0] - 2024-12-10

### Added

- Initial release with 5 memory tools: Mem0, OpenAI Memory, Claude Memory, MemGPT/Letta, Zep
- 6 benchmark suites: Conversational AI, Long Context, Persona Consistency, Technical Performance, Memory Stress, Domain-Specific
- Comprehensive metrics: Latency, Token Usage, Success Rate
- YAML-based configuration system
- JSON result export

### Known Limitations

- Synthetic benchmarks (inspired by MSC/PersonaChat, not actual datasets)
- No accuracy/precision metrics yet (planned for v0.2.0)
- Claude Memory rate limiting under high volume
- MemGPT high token costs due to agentic architecture
