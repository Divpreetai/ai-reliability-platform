from typing import Dict, Any, List, Optional
from backend.app.engine.registry import BaseEvaluator, evaluator_registry
from backend.app.engine.evaluators.utils import call_llm_judge

class ContextPrecisionEvaluator(BaseEvaluator):
    @property
    def name(self) -> str:
        return "rag_context_precision"

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
            return {"score": 1.0, "explanation": "No reference context provided; skipped precision evaluation."}
        
        prompt = (
            f"Query: {input_prompt}\n"
            f"Retrieved Context: {reference_context}\n\n"
            "Evaluate if the retrieved context contains relevant information to answer the query, "
            "and if the most useful parts of the context are presented first. "
            "Give a score between 0.0 (completely irrelevant context) and 1.0 (highly precise and relevant context)."
        )
        system_prompt = "You are an expert evaluator assessing RAG Context Precision (whether retrieved documents match the query's informational needs)."
        return await call_llm_judge(prompt, system_prompt)


class ContextRecallEvaluator(BaseEvaluator):
    @property
    def name(self) -> str:
        return "rag_context_recall"

    async def evaluate(
        self,
        input_prompt: str,
        generated_response: str,
        reference_context: Optional[str] = None,
        expected_output: Optional[str] = None,
        agent_trace: Optional[List[Dict[str, Any]]] = None,
        expected_tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if not reference_context or not expected_output:
            return {"score": 1.0, "explanation": "Missing reference context or expected ground truth output; skipped recall evaluation."}
        
        prompt = (
            f"Expected Ground Truth Output: {expected_output}\n"
            f"Retrieved Context: {reference_context}\n\n"
            "Analyze if all the facts and details in the Expected Ground Truth Output are present in the Retrieved Context. "
            "Score 1.0 if all details are present in the context, and 0.0 if none of the ground truth facts are represented. "
            "Provide a decimal score between 0.0 and 1.0 indicating the fraction of ground truth facts that are recallable."
        )
        system_prompt = "You are an expert evaluator assessing RAG Context Recall (whether all facts in the ground truth are present in the context)."
        return await call_llm_judge(prompt, system_prompt)


class FaithfulnessEvaluator(BaseEvaluator):
    @property
    def name(self) -> str:
        return "rag_faithfulness"

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
            return {"score": 1.0, "explanation": "No reference context provided; skipped faithfulness evaluation."}
        
        prompt = (
            f"Retrieved Context: {reference_context}\n"
            f"Generated Response: {generated_response}\n\n"
            "Identify all claims or facts stated in the Generated Response. Check if each claim is directly supported "
            "by or inferred from the Retrieved Context. Deduct score for statements that cannot be verified by the context. "
            "Score 1.0 if the response is completely faithful and contains zero unverified claims. Score 0.0 if the response "
            "is entirely fabricated or unsupported by the context."
        )
        system_prompt = "You are an expert evaluator assessing RAG Faithfulness (whether the generated response is strictly grounded in the context)."
        return await call_llm_judge(prompt, system_prompt)


class AnswerRelevancyEvaluator(BaseEvaluator):
    @property
    def name(self) -> str:
        return "rag_answer_relevancy"

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
            f"Query/Prompt: {input_prompt}\n"
            f"Generated Response: {generated_response}\n\n"
            "Evaluate if the Generated Response directly answers the user's query. Deduct score if the response "
            "contains redundant info, goes off-topic, or fails to address the prompt fully. "
            "Score from 0.0 (completely irrelevant response) to 1.0 (highly relevant, focused, and direct answer)."
        )
        system_prompt = "You are an expert evaluator assessing Answer Relevancy (how well the output matches the query's intent, ignoring correctness/truth)."
        return await call_llm_judge(prompt, system_prompt)


# Register all RAG evaluators
evaluator_registry.register(ContextPrecisionEvaluator())
evaluator_registry.register(ContextRecallEvaluator())
evaluator_registry.register(FaithfulnessEvaluator())
evaluator_registry.register(AnswerRelevancyEvaluator())
