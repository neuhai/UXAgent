#!/bin/bash

echo "🚀 AgentQL Universal Web Automation Test"
echo "========================================"

# Activate virtual environment
source simulated_web_agent_env/bin/activate

# Test on Bruvi.com with AgentQL (no manual recipes needed!)
simulated_web_agent_env/bin/python -m simulated_web_agent.main \
    --persona example_data/personas/json/bruvi_coffee_shopper.json \
    --output output/agentql_bruvi_test \
    --max-steps 20 \
    --llm-provider openai \
    --target-url "https://bruvi.com"

echo ""
echo "✅ AgentQL test completed!"
echo "Check output/agentql_bruvi_test/ for results" 