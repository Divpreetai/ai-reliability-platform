from typing import Dict, Any, List, Optional
from backend.app.engine.registry import BaseEvaluator, evaluator_registry
from backend.app.engine.evaluators.utils import call_llm_judge

class HallucinationEvaluator(BaseEvaluator):
    @property
    def name(self) -> str:
        return "hallucination"

    async def evaluate(
        self,
        input_prompt: str,
        generated_response: str,
        reference_context: Optional[str] = None,
        expected_output: Optional[str] = None,
        agent_trace: Optional[List[Dict[str, Any]]] = None,
        expected_tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        prompt = (
            f"Input Prompt: {input_prompt}\n"
            f"Reference Context: {reference_context or 'No context provided (Evaluate based on general facts).'}\n"
            f"Generated Response: {generated_response}\n\n"
            "Analyze the Generated Response for any fabricated facts, unsupported claims, or contradictions "
            "with respect to the Reference Context (or general truth if no context is provided).\n"
            "Score 1.0 if the response contains definite hallucinations (made-up facts, unsupported details, false details).\n"
            "Score 0.0 if the response is completely accurate, truthful, and free of any hallucinations.\n"
            "Score between 0.0 and 1.0 for partial hallucinations."
        )
        system_prompt = "You are an expert evaluator assessing Hallucinations. 0.0 is perfect (truthful, no hallucinations), 1.0 is worst (fabricated claims)."
        return await call_llm_judge(prompt, system_prompt)

# Register Hallucination Evaluator
evaluator_registry.register(HallucinationEvaluator())
