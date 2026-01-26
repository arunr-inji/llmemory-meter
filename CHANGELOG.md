# Changelog

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
