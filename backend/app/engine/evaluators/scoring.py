from typing import Dict, Any, List, Optional
from backend.app.engine.registry import BaseEvaluator, evaluator_registry
from backend.app.engine.evaluators.utils import call_llm_judge

class ResponseQualityEvaluator(BaseEvaluator):
    @property
    def name(self) -> str:
        return "response_score"

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
            f"Expected Response (Ground Truth): {expected_output or 'Not provided'}\n"
            f"Actual Generated Response: {generated_response}\n\n"
            "Compare the Generated Response with the Expected Response (ground truth) and the user's intent. "
            "Evaluate its correctness, helpfulness, and detail level. "
            "Assign an integer score from 1.0 (completely incorrect or empty) to 5.0 (perfect, accurate, and comprehensive)."
        )
        system_prompt = "You are an expert evaluator grading Response Quality on a scale of 1.0 (worst) to 5.0 (best)."
        return await call_llm_judge(prompt, system_prompt)

# Register Response Quality Evaluator
evaluator_registry.register(ResponseQualityEvaluator())
