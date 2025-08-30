#!/bin/bash

echo "🌐 AgentQL Universal Web Automation - Works on ANY Website!"
echo "============================================================"

# Check if URL is provided
if [ -z "$1" ]; then
    echo "Usage: ./run_universal_test.sh <target_url> [persona_file]"
    echo ""
    echo "Examples:"
    echo "  ./run_universal_test.sh https://amazon.com"
    echo "  ./run_universal_test.sh https://nike.com"
    echo "  ./run_universal_test.sh https://airbnb.com"
    echo "  ./run_universal_test.sh https://booking.com example_data/personas/json/boulder_mom.json"
    exit 1
fi

TARGET_URL="$1"
PERSONA_FILE="${2:-example_data/personas/json/bruvi_coffee_shopper.json}"

echo "Target URL: $TARGET_URL"
echo "Persona: $PERSONA_FILE"
echo ""

# Activate virtual environment
source simulated_web_agent_env/bin/activate

# Run universal automation - works on ANY website!
simulated_web_agent_env/bin/python -m simulated_web_agent.main \
    --persona "$PERSONA_FILE" \
    --output "output/universal_$(date +%Y%m%d_%H%M%S)" \
    --max-steps 25 \
    --llm-provider openai \
    --target-url "$TARGET_URL"

echo ""
echo "✅ Universal automation completed!"
echo "This demonstrates how AgentQL can work on ANY website without manual recipes!" 