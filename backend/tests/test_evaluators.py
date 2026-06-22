import pytest
from backend.app.engine.registry import evaluator_registry
from backend.app.engine.evaluators.cost_tracker import calculate_cost

def test_evaluator_registry_registration():
    # Verify that standard evaluators are auto-registered
    all_evaluators = evaluator_registry.get_all()
    assert len(all_evaluators) > 0
    
    # Check for specific evaluator names
    hallucination_eval = evaluator_registry.get("hallucination")
    assert hallucination_eval is not None
    assert hallucination_eval.name == "hallucination"
    
    grounding_eval = evaluator_registry.get("grounding_check")
    assert grounding_eval is not None

    toxicity_eval = evaluator_registry.get("safety_toxicity")
    assert toxicity_eval is not None


def test_cost_calculation():
    # Test free local models
    assert calculate_cost("ollama/llama3", 100, 200) == 0.0
    assert calculate_cost("local-mistral", 50, 50) == 0.0

    # Test GPT pricing
    gpt4o_cost = calculate_cost("gpt-4o", 1000000, 1000000)
    assert gpt4o_cost == 5.00 + 15.00  # $5/M input, $15/M output

    gpt_mini_cost = calculate_cost("gpt-4o-mini", 1000000, 1000000)
    assert gpt_mini_cost == 0.15 + 0.60  # $0.15/M input, $0.60/M output

    # Test Claude pricing
    claude_cost = calculate_cost("claude-3-5-sonnet", 1000000, 1000000)
    assert claude_cost == 3.00 + 15.00  # $3/M input, $15/M output
