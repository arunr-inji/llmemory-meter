# Performance Notes and Considerations

## Token Usage Characteristics

### MemGPT/Letta: Context-Heavy Architecture

**Token Range**: 3,000 - 5,000 tokens per query (with isolated agents)

**Why So High?**
MemGPT is an **agentic memory system** that includes:
- Internal reasoning and planning
- Function call overhead
- Extended context maintenance
- Multi-step processing

**Cost Implications**:
```
Per 1,000 queries (at 4K tokens avg):
- With GPT-4o-mini ($0.15/$0.60 per 1M): ~$1.50
- With GPT-4 ($2.50/$10 per 1M):        ~$25
```

**Best For**: 
- Research and prototyping
- Complex reasoning tasks
- Applications where quality > cost

**Avoid For**:
- High-volume production (cost scales linearly)
- Cost-sensitive applications
- Simple memory retrieval

---

### Zep: Knowledge Graph Processing

**Measured Latency**: ~6.3s average (includes processing delays)

**Architecture**:
- Stores messages in thread (instant)
- Processes into knowledge graph (async, ~8s)
- Extracts facts, entities, episodes

**Real API Latency**: ~0.3-1.5s (without processing delays)

**Design Decision**: We include 8-second delays to ensure graph processing completes before next operation. This is **intentional** for benchmark consistency.

**Production Recommendation**:
- Use async processing (don't block on graph updates)
- Actual user-facing latency can be ~1-2s
- Graph enrichment happens in background

---

### Mem0: Token Efficiency Champion

**Token Range**: 41 tokens per query average

**Why So Low?**
- Lightweight API responses
- Minimal context wrapping
- Efficient vector similarity search
- No heavy formatting overhead

**Cost**: ~$0.10 per 1,000 queries (negligible)

**Trade-off**: Slower overall latency (4.4s avg) due to vector DB operations

---

### OpenAI Memory: Best Balanced Performance

**Metrics**:
- **Latency**: 1.6s (fastest)
- **Tokens**: 375 (reasonable)
- **Reliability**: 100%

**Sweet Spot**: Fast enough for real-time, efficient enough for scale

---

### Claude Memory: Fast but Token-Heavy

**Metrics**:
- **Latency**: 2.0s (2nd fastest)
- **Tokens**: 3,617 (9.6x more than OpenAI)
- **Reliability**: 97.2% overall (rate limiting under stress)

**Best For**: Real-time applications with moderate volume

**Limitations**: 
- Higher token costs than OpenAI
- Rate limiting issues with >20 rapid operations

---

## Benchmark-Specific Notes

### Memory Stress Testing (55 operations)

**Speed Rankings** (store operations):
1. OpenAI: 1.1s ⚡ (9x faster than Mem0)
2. Claude: 1.4s
3. Zep: 7.4s (includes graph delays)
4. MemGPT: 7.8s
5. Mem0: 9.1s 🐌

**Key Insight**: Tool performance diverges significantly under load. OpenAI dominates for bulk operations.

---

## Fair Comparison Considerations

### Token Counting Methodology

We count **full tokens as they would be billed in production**:

1. **OpenAI, Claude, MemGPT**: Extract from API `usage` field (exact)
2. **Mem0**: Estimate using tiktoken (no API exposure)
3. **Zep**: Count full context returned (reflects LLM cost when used)

**Why count Zep's full context?**
- In production, users pass Zep context to LLM (GPT-4, Claude)
- LLM bills for entire context including Zep's verbose formatting
- ~500-600 tokens per retrieve reflects **real cost**, not Zep API cost

### Latency Measurement

- **Includes**: Full round-trip time (network + processing)
- **Zep**: Includes 8s graph delays (can be async in production)
- **All tools**: Affected by network conditions
- **Measured**: From localhost (network latency minimal)

---

## Recommendations by Use Case

| Priority | Best Tool | Runner-Up | Notes |
|----------|-----------|-----------|-------|
| **Speed** | OpenAI (1.6s) | Claude (2.0s) | Real-time ready |
| **Cost** | Mem0 (41 tokens) | OpenAI (375 tokens) | 9x cheaper |
| **Reliability** | Mem0/OpenAI/MemGPT/Zep | Claude | All 100% except Claude under stress |
| **Bulk Ops** | OpenAI (1.1s stores) | Claude | Avoid Mem0 (9.1s) |
| **Self-Hosted** | Mem0 or Zep | - | Open source friendly |

---

*For detailed issue tracking, see [KNOWN_ISSUES.md](../KNOWN_ISSUES.md)*

