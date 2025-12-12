"""
Cost calculator for LLM API calls.
Provides pricing information for different models and calculates costs.
"""

# Model pricing in USD per 1M tokens
# Last updated: 2024-12-05
# Source: Official pricing pages of each provider
MODEL_PRICING = {
    # OpenAI models
    "openai/gpt-4o-mini": {
        "input": 0.15,        # $0.15 per 1M input tokens
        "output": 0.60,       # $0.60 per 1M output tokens
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
    },
    "openai/gpt-5": {
        "input": 15.00,       # $15 per 1M input tokens
        "output": 60.00,      # $60 per 1M output tokens
    },
    "gpt-5": {
        "input": 15.00,
        "output": 60.00,
    },
    "openai/gpt-5-mini": {
        "input": 0.15,
        "output": 0.60,
    },
    "gpt-5-mini": {
        "input": 0.15,
        "output": 0.60,
    },
    # Anthropic Claude models
    "claude-sonnet-4-20250514": {
        "input": 3.00,        # $3 per 1M input tokens
        "output": 15.00,      # $15 per 1M output tokens
    },
    "claude-sonnet-4": {
        "input": 3.00,
        "output": 15.00,
    },
    "bedrock/global.anthropic.claude-sonnet-4-5-20250929-v1:0": {
        "input": 3.00,
        "output": 15.00,
    },
    "bedrock/claude-sonnet-4": {
        "input": 3.00,
        "output": 15.00,
    },
    # AWS Bedrock Claude models
    "bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0": {
        "input": 0.80,        # $0.80 per 1M input tokens
        "output": 4.00,       # $4 per 1M output tokens
    },
    "claude-haiku-4-5": {
        "input": 0.80,
        "output": 4.00,
    },
    # Embedding models
    "openai/text-embedding-3-small": {
        "input": 0.02,        # $0.02 per 1M tokens
        "output": 0.00,       # No output tokens for embeddings
    },
    "text-embedding-3-small": {
        "input": 0.02,
        "output": 0.00,
    },
    "bedrock/cohere.embed-english-v3": {
        "input": 0.10,
        "output": 0.00,
    },
}


def get_pricing(model_name: str) -> dict:
    """
    Get pricing information for a model.

    Args:
        model_name: Name of the model

    Returns:
        Dictionary with 'input' and 'output' keys containing prices per 1M tokens
    """
    # Try exact match first
    if model_name in MODEL_PRICING:
        return MODEL_PRICING[model_name]

    # Try to find partial match (e.g., "gpt-4o-mini" in "openai/gpt-4o-mini")
    for model_key in MODEL_PRICING:
        if model_name in model_key or model_key in model_name:
            return MODEL_PRICING[model_key]

    # Default pricing (fallback)
    print(f"Warning: Pricing not found for model '{model_name}', using default pricing")
    return {"input": 1.00, "output": 1.00}


def calculate_cost(model_name: str, usage: dict) -> float:
    """
    Calculate the cost of an API call.

    Args:
        model_name: Name of the model used
        usage: Dictionary with 'prompt_tokens' and 'completion_tokens'

    Returns:
        Cost in USD
    """
    if not usage:
        return 0.0

    pricing = get_pricing(model_name)
    prompt_tokens = usage.get('prompt_tokens', 0)
    completion_tokens = usage.get('completion_tokens', 0)

    # Calculate cost: tokens * (price per 1M tokens) / 1,000,000
    input_cost = prompt_tokens * pricing['input'] / 1_000_000
    output_cost = completion_tokens * pricing['output'] / 1_000_000

    return input_cost + output_cost


def format_cost(cost: float) -> str:
    """Format cost as a string with appropriate precision."""
    if cost < 0.001:
        return f"${cost:.6f}"
    elif cost < 0.01:
        return f"${cost:.5f}"
    else:
        return f"${cost:.4f}"
