def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Computes estimated cost of an execution in USD.
    Pricing per 1M tokens.
    """
    name = model_name.lower()
    
    # Model pricing tables per 1,000,000 tokens (input, output)
    pricing_table = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    }

    # Local Ollama models are free
    if "ollama" in name or "local" in name:
        return 0.0

    # Match provider pattern
    for model_key, rates in pricing_table.items():
        if model_key in name:
            in_cost = (prompt_tokens / 1_000_000.0) * rates["input"]
            out_cost = (completion_tokens / 1_000_000.0) * rates["output"]
            return in_cost + out_cost

    # Default fallback to approximate low-cost models (gpt-4o-mini rates)
    in_cost = (prompt_tokens / 1_000_000.0) * 0.15
    out_cost = (completion_tokens / 1_000_000.0) * 0.60
    return in_cost + out_cost
