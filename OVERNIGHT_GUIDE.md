# Running Benchmarks Overnight 😴

## Quick Start (3 steps)

### 1. Make script executable (one time only)

```bash
chmod +x run_overnight.sh
```

### 2. Start the benchmark

```bash
# Use nohup so it keeps running even if you close terminal/logout
nohup ./run_overnight.sh configs/comprehensive.yml &

# Alternative: use screen (allows you to reattach later)
screen -S benchmark
./run_overnight.sh configs/comprehensive.yml
# Press Ctrl+A then D to detach
```

### 3. Go to sleep! 💤

---

## Check Progress (While It's Running)

### See live output

```bash
tail -f logs/benchmark_*.log | grep -E "(→|✓|Progress)"
```

### Check if it's still running

```bash
ps aux | grep llmemory_meter
```

### Reattach to screen session

```bash
screen -r benchmark
```

---

## After You Wake Up ☕

### View results

```bash
# Latest log
ls -lt logs/ | head -1

# Latest results
ls -lt results/ | head -1

# Quick summary
tail -50 logs/benchmark_*.log
```

### Open results

```bash
# View in terminal
cat results/comprehensive_*.json | python3 -m json.tool | less

# Or use VSCode
code results/comprehensive_*.json
```

---

## Notification Setup (Optional)

### macOS Notification (Easiest)

Uncomment in `run_overnight.sh`:

```bash
osascript -e 'display notification "Check results in logs/" with title "Benchmark Complete ✅"'
```

No setup needed! Notification appears on your Mac.

### Telegram Notification (Recommended! 📱)

**Why Telegram**: Works on phone, reliable, super easy setup

**Setup (2 minutes):**

1. Open Telegram, search for `@BotFather`
2. Send: `/newbot`
3. Follow prompts, get your `BOT_TOKEN` (looks like: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
4. Search for your new bot and send it a message (anything, like "hi")
5. Visit: `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates` (replace `<BOT_TOKEN>`)
6. Find your `chat_id` in the JSON response (under `"chat":{"id": 12345678}`)
7. Add to `~/.zshrc` (env vars auto-load in script):

   ```bash
   export TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
   export TELEGRAM_CHAT_ID="12345678"
   ```

8. Reload: `source ~/.zshrc`

**That's it!** The script now auto-loads env vars from `~/.zshrc`.

**Test it:**

```bash
# Send test message
TELEGRAM_BOT_TOKEN="your_token"
TELEGRAM_CHAT_ID="your_chat_id"
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="$TELEGRAM_CHAT_ID" \
  -d text="Test: Notifications working! 🎉"
```

### Slack Notification

1. Go to: <https://api.slack.com/messaging/webhooks>
2. Create a webhook for your workspace
3. Copy the webhook URL
4. In `run_overnight.sh`, uncomment and update:

```bash
SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
curl -X POST -H 'Content-type: application/json' --data "{\"text\":\"✅ Benchmark complete!\"}" "$SLACK_WEBHOOK"
```

### Discord Notification

1. In Discord: Server Settings > Integrations > Webhooks > New Webhook
2. Copy webhook URL
3. In `run_overnight.sh`, uncomment and update:

```bash
DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR/WEBHOOK"
curl -X POST -H 'Content-type: application/json' --data "{\"content\":\"✅ Benchmark complete!\"}" "$DISCORD_WEBHOOK"
```

---

## Time Estimates

**Comprehensive Config (5 tools × 6 benchmarks):**

- **Conversational AI**: ~30 min
- **Long Context**: ~30 min
- **Persona Consistency**: ~15 min
- **Technical Performance**: ~2.5 hours ⏰ (50 stores per tool)
- **Memory Stress**: ~15 min
- **Domain-Specific**: ~20 min
**Total: ~4-5 hours**

---

## Troubleshooting

### Benchmark stopped overnight?

```bash
# Check exit code in log
tail -20 logs/benchmark_*.log

# Check for errors
grep -i "error\|failed\|timeout" logs/benchmark_*.log
```

### Out of disk space?

```bash
# Check disk usage
df -h

# Clean old logs (keep last 5)
ls -t logs/benchmark_*.log | tail -n +6 | xargs rm
```

### Process killed?

```bash
# Check system logs
grep -i "killed\|oom" /var/log/system.log
```

---

## Pro Tips 💡

1. **Test first**: Run with a small config to verify everything works

   ```bash
   ./run_overnight.sh configs/quick-test.yml
   ```

2. **Monitor resource usage**:

   ```bash
   top -pid $(pgrep -f llmemory_meter)
   ```

3. **Estimate completion time**:

   ```bash
   # Check progress in log
   grep "Progress:" logs/benchmark_*.log | tail -1
   ```

4. **Multiple runs**: Use different configs

   ```bash
   # Run 1: Just Zep
   nohup ./run_overnight.sh configs/zep-only.yml &

   # Run 2: Just mem0
   nohup ./run_overnight.sh configs/mem0-only.yml &
   ```

---

## What Gets Saved

```text
llmemory_meter/
├── logs/
│   └── benchmark_20241219_143022.log  # Full output
├── results/
│   └── comprehensive_20241219_143022.json  # Results with timestamp
└── comprehensive_results.json  # Latest results (overwritten)
```

All results are saved automatically! Just check the files when you wake up. ☕📊
