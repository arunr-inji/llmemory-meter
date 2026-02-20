#!/bin/bash
# Overnight Benchmark Runner
# Usage: ./run_overnight.sh [config_file]

# Load environment variables from .env file (for API keys, Telegram notifications, etc.)
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

set -euo pipefail

# Configuration
CONFIG_FILE="${1:-configs/industry-benchmarks.yml}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="logs"
LOG_FILE="${LOG_DIR}/benchmark_${TIMESTAMP}.log"
RESULTS_DIR="results"
RUN_MARKER=".run_marker_${TIMESTAMP}"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create directories
mkdir -p "$LOG_DIR" "$RESULTS_DIR"
touch "$RUN_MARKER"
trap 'rm -f "$RUN_MARKER"' EXIT

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  LLMemory Meter - Overnight Runner${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}📋 Config:${NC} $CONFIG_FILE"
echo -e "${GREEN}📁 Log:${NC} $LOG_FILE"
echo -e "${GREEN}🕐 Started:${NC} $(date)"
echo ""

# Check if required services are running (optional)
if command -v docker &> /dev/null; then
    if docker ps | grep -q qdrant; then
        echo -e "${GREEN}✓ Qdrant is running${NC}"
    else
        echo -e "${YELLOW}⚠ Qdrant not detected (may be required for mem0)${NC}"
    fi
fi

echo ""
echo -e "${BLUE}🚀 Starting benchmark...${NC}"
echo -e "${YELLOW}💤 You can now close this terminal or go to sleep${NC}"
echo -e "${YELLOW}📊 Results will be saved automatically${NC}"
echo ""

# Run benchmark with output to both terminal and log file
START_EPOCH=$(date +%s)
set +e
.venv/bin/python -m llmemory_meter.cli run --config "$CONFIG_FILE" 2>&1 | tee "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
set -e
END_EPOCH=$(date +%s)
DURATION_SECS=$((END_EPOCH - START_EPOCH))
DURATION_MIN=$((DURATION_SECS / 60))
DURATION_HR=$((DURATION_MIN / 60))
DURATION_REM_MIN=$((DURATION_MIN % 60))

echo ""
echo -e "${BLUE}========================================${NC}"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Benchmark completed successfully!${NC}"
else
    echo -e "${YELLOW}⚠️  Benchmark exited with code: $EXIT_CODE${NC}"
fi
echo -e "${GREEN}🕐 Finished:${NC} $(date)"
echo -e "${GREEN}📁 Log saved:${NC} $LOG_FILE"
echo ""

# Post-hoc accuracy evaluation (runs after benchmark, doesn't affect latency/token metrics)
if [ $EXIT_CODE -eq 0 ]; then
    RESULTS_FILE=$(grep 'output_file:' "$CONFIG_FILE" 2>/dev/null | awk '{print $2}' | head -1)
    if [ -n "$RESULTS_FILE" ] && [ -f "$RESULTS_FILE" ]; then
        EVAL_LOG="${LOG_DIR}/eval_${TIMESTAMP}.log"

        # LongMemEval evaluation
        if grep -q "LongMemEval" "$CONFIG_FILE" && grep -A1 "name: LongMemEval" "$CONFIG_FILE" | grep -q "enabled: true"; then
            echo -e "${BLUE}🧪 Running LongMemEval accuracy evaluation (GPT-4o judge)...${NC}"
            set +e
            .venv/bin/python -m llmemory_meter.cli evaluate \
                --benchmark LongMemEval --judge gpt-4o \
                --results "$RESULTS_FILE" --config "$CONFIG_FILE" 2>&1 | tee -a "$EVAL_LOG"
            EVAL_EXIT=$?
            set -e
            if [ $EVAL_EXIT -eq 0 ]; then
                echo -e "${GREEN}✅ LongMemEval evaluation complete${NC}"
            else
                echo -e "${YELLOW}⚠️  LongMemEval evaluation failed (exit: $EVAL_EXIT)${NC}"
            fi
        fi

        # MemBench evaluation
        if grep -q "MemBench" "$CONFIG_FILE" && grep -A1 "name: MemBench" "$CONFIG_FILE" | grep -q "enabled: true"; then
            echo -e "${BLUE}🧪 Running MemBench accuracy evaluation (LLM judge)...${NC}"
            set +e
            .venv/bin/python -m llmemory_meter.cli evaluate \
                --benchmark MemBench \
                --results "$RESULTS_FILE" --config "$CONFIG_FILE" 2>&1 | tee -a "$EVAL_LOG"
            EVAL_EXIT=$?
            set -e
            if [ $EVAL_EXIT -eq 0 ]; then
                echo -e "${GREEN}✅ MemBench evaluation complete${NC}"
            else
                echo -e "${YELLOW}⚠️  MemBench evaluation failed (exit: $EVAL_EXIT)${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}⚠️  Skipping evaluation: results file not found ($RESULTS_FILE)${NC}"
    fi
fi

# Move results to results directory with timestamp
shopt -s nullglob
for result_file in *_results.json; do
    # Skip files older than the run marker; equal timestamp is treated as this run.
    if [ "$result_file" -ot "$RUN_MARKER" ]; then
        continue
    fi
    base_name="${result_file%_results.json}"
    dest_file="${RESULTS_DIR}/${base_name}_${TIMESTAMP}.json"
    mv "$result_file" "$dest_file"
    echo -e "${GREEN}📊 Results moved:${NC} $dest_file"
done
shopt -u nullglob
# Print summary of results files
echo ""
echo -e "${BLUE}📋 Available Results:${NC}"
ls -lht "$RESULTS_DIR" | head -6

# Optional: Send notification (uncomment one that works for you)

# Option 1: macOS Notification (no setup needed, shows on your Mac)
# osascript -e 'display notification "Check results in logs/" with title "Benchmark Complete ✅"'

# Option 2: Slack Webhook (get URL from: https://api.slack.com/messaging/webhooks)
# SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
# curl -X POST -H 'Content-type: application/json' --data "{\"text\":\"✅ Benchmark complete! Log: $LOG_FILE\"}" "$SLACK_WEBHOOK"

# Option 3: Telegram Bot (easiest setup, works on phone!)
# Reads from env vars: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    echo "📱 Sending Telegram notification..."

    if [ $EXIT_CODE -eq 0 ]; then
        STATUS_EMOJI="✅"
        STATUS_TEXT="Completed Successfully"
    else
        STATUS_EMOJI="❌"
        STATUS_TEXT="Failed (exit code: $EXIT_CODE)"
    fi

    # Extract quick metrics from log
    SUMMARY=$(grep -A 20 "Overall Performance Metrics" "$LOG_FILE" 2>/dev/null | head -25 || echo "")
    TOOLS=$(grep -E "(🔧|Success Rate:)" "$LOG_FILE" 2>/dev/null | sed 's/^[[:space:]]*//' | head -10 || echo "No metrics available")

    # Extract evaluation results if eval log exists
    EVAL_RESULTS=""
    if [ -n "${EVAL_LOG:-}" ] && [ -f "${EVAL_LOG:-}" ]; then
        EVAL_RESULTS=$(grep -E "(Score|Accuracy|accuracy|score|judge|✅|❌)" "$EVAL_LOG" 2>/dev/null | sed 's/^[[:space:]]*//' | head -15 || echo "")
    fi

    TELEGRAM_MSG="${STATUS_EMOJI} Benchmark ${STATUS_TEXT}
━━━━━━━━━━━━━━━━━━━━
📋 Config: $(basename "$CONFIG_FILE")
⏱ Duration: ${DURATION_HR}h ${DURATION_REM_MIN}m
🕐 Finished: $(date '+%Y-%m-%d %H:%M')
📁 Log: $LOG_FILE

📊 Results:
${TOOLS}"

    if [ -n "$EVAL_RESULTS" ]; then
        TELEGRAM_MSG="${TELEGRAM_MSG}

🧪 Evaluation:
${EVAL_RESULTS}"
    fi

    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="$TELEGRAM_CHAT_ID" \
      -d parse_mode="HTML" \
      --data-urlencode "text=${TELEGRAM_MSG}" > /dev/null
    echo "📱 Telegram notification sent!"
else
    echo "⚠️  Telegram env vars not set (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing)"
fi

# Option 4: Discord Webhook (get URL from: Server Settings > Integrations > Webhooks)
# DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR/WEBHOOK/URL"
# curl -X POST -H 'Content-type: application/json' --data "{\"content\":\"✅ Benchmark complete! Log: $LOG_FILE\"}" "$DISCORD_WEBHOOK"

# Option 5: Email via SendGrid API (requires API key from sendgrid.com)
# SENDGRID_API_KEY="your_api_key_here"
# YOUR_EMAIL="your@email.com"
# curl -X POST https://api.sendgrid.com/v3/mail/send \
#   -H "Authorization: Bearer $SENDGRID_API_KEY" \
#   -H "Content-Type: application/json" \
#   -d "{\"personalizations\":[{\"to\":[{\"email\":\"$YOUR_EMAIL\"}]}],\"from\":{\"email\":\"benchmark@yourapp.com\"},\"subject\":\"Benchmark Complete\",\"content\":[{\"type\":\"text/plain\",\"value\":\"Benchmark finished at $(date). Log: $LOG_FILE\"}]}"

exit $EXIT_CODE
