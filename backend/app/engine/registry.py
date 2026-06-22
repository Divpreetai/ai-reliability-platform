from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseEvaluator(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """The identifier for the metric (e.g. 'hallucination', 'rag_faithfulness')."""
        pass

    @abstractmethod
    async def evaluate(
        self,
        input_prompt: str,
        generated_response: str,
        reference_context: Optional[str] = None,
        expected_output: Optional[str] = None,
        agent_trace: Optional[List[Dict[str, Any]]] = None,
        expected_tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Executes the evaluation.
        Should return a dictionary with:
        - "score": float (typically 0.0 to 1.0, or 1.0 to 5.0 for scoring)
        - "explanation": str (justification for the score)
        """
        pass

class EvaluatorRegistry:
    def __init__(self):
        self._registry: Dict[str, BaseEvaluator] = {}

    def register(self, evaluator: BaseEvaluator):
        self._registry[evaluator.name] = evaluator

    def get(self, name: str) -> Optional[BaseEvaluator]:
        return self._registry.get(name)

    def get_all(self) -> List[BaseEvaluator]:
        return list(self._registry.values())

evaluator_registry = EvaluatorRegistry()
