from typing import Dict, Any, List, Optional
from backend.app.engine.registry import BaseEvaluator, evaluator_registry
from backend.app.engine.evaluators.utils import call_llm_judge

class GroundingEvaluator(BaseEvaluator):
    @property
    def name(self) -> str:
        return "grounding_check"

    async def evaluate(
        self,
        input_prompt: str,
        generated_response: str,
        reference_context: Optional[str] = None,
        expected_output: Optional[str] = None,
        agent_trace: Optional[List[Dict[str, Any]]] = None,
        expected_tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if not reference_context:
            return {"score": 1.0, "explanation": "No reference context provided; response is considered grounded by default."}

        prompt = (
            f"Reference Context: {reference_context}\n"
            f"Generated Output: {generated_response}\n\n"
            "Analyze whether the claims and assertions in the Generated Output are supported by the Reference Context. "
            "Score 1.0 if the output is completely grounded and does not contain outside assumptions. "
            "Score 0.0 if the output completely ignores the context or contradicts it. "
            "Provide a score between 0.0 and 1.0 representing the ratio of grounded statements."
        )
        system_prompt = "You are an expert evaluator checking Grounding (whether the LLM output stays strictly within the boundaries of the reference document)."
        return await call_llm_judge(prompt, system_prompt)

# Register Grounding Evaluator
evaluator_registry.register(GroundingEvaluator())
