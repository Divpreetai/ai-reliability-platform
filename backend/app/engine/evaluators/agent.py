from typing import Dict, Any, List, Optional
from backend.app.engine.registry import BaseEvaluator, evaluator_registry
from backend.app.engine.evaluators.utils import call_llm_judge

class AgentToolSelectionEvaluator(BaseEvaluator):
    @property
    def name(self) -> str:
        return "agent_tool_selection"

    async def evaluate(
        self,
        input_prompt: str,
        generated_response: str,
        reference_context: Optional[str] = None,
        expected_output: Optional[str] = None,
        agent_trace: Optional[List[Dict[str, Any]]] = None,
        expected_tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if not expected_tools:
            return {"score": 1.0, "explanation": "No expected tools specified; skipped selection check."}
        if not agent_trace:
            return {"score": 0.0, "explanation": "Expected tools but agent trace is empty or missing."}

        # Extract tools called in trace
        tools_called = []
        for step in agent_trace:
            if isinstance(step, dict) and step.get("type") == "tool_call" and step.get("tool_name"):
                tools_called.append(step["tool_name"])

        # Check overlap
        expected_set = set(expected_tools)
        called_set = set(tools_called)
        
        if not expected_set:
            return {"score": 1.0, "explanation": "No specific tools were expected."}
            
        intersection = expected_set.intersection(called_set)
        score = len(intersection) / len(expected_set)
        
        explanation = f"Expected tools: {list(expected_set)}. Tools called: {list(called_set)}. Match rate: {score * 100:.1f}%."
        return {"score": score, "explanation": explanation}


class AgentToolCorrectnessEvaluator(BaseEvaluator):
    @property
    def name(self) -> str:
        return "agent_tool_correctness"

    async def evaluate(
        self,
        input_prompt: str,
        generated_response: str,
        reference_context: Optional[str] = None,
        expected_output: Optional[str] = None,
        agent_trace: Optional[List[Dict[str, Any]]] = None,
        expected_tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if not agent_trace:
            return {"score": 1.0, "explanation": "No agent trace provided to check tool correctness."}

        prompt = (
            f"User Prompt: {input_prompt}\n"
            f"Agent Traces/Steps: {agent_trace}\n\n"
            "Evaluate if the tool inputs and parameters passed in the tool_calls are correct and logical. "
            "Did the agent pass incorrect/hallucinated parameters, or use a tool incorrectly? "
            "Score 1.0 if all tools were called with appropriate, high-quality inputs. "
            "Score 0.0 if there are critical errors in tool inputs or arguments."
        )
        system_prompt = "You are an expert evaluator assessing Agent Tool Correctness (whether tool inputs are correct and relevant)."
        return await call_llm_judge(prompt, system_prompt)


class AgentLoopDetectionEvaluator(BaseEvaluator):
    @property
    def name(self) -> str:
        return "agent_loop_detection"

    async def evaluate(
        self,
        input_prompt: str,
        generated_response: str,
        reference_context: Optional[str] = None,
        expected_output: Optional[str] = None,
        agent_trace: Optional[List[Dict[str, Any]]] = None,
        expected_tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if not agent_trace:
            return {"score": 0.0, "explanation": "No agent trace provided; no loop detected."}

        # Look for identical tool calls with identical inputs
        seen_calls = {}
        loop_detected = False
        loop_details = ""
        
        for step in agent_trace:
            if isinstance(step, dict) and step.get("type") == "tool_call":
                tool = step.get("tool_name")
                tool_input = str(step.get("tool_input"))
                call_key = f"{tool}({tool_input})"
                
                seen_calls[call_key] = seen_calls.get(call_key, 0) + 1
                if seen_calls[call_key] >= 3:
                    loop_detected = True
                    loop_details = f"Tool call {call_key} was repeated {seen_calls[call_key]} times."
                    break

        if loop_detected:
            return {
                "score": 1.0, # 1.0 indicates a loop WAS detected (failure)
                "explanation": f"Jail/Loop detected! Agent is spinning in a repetitive tool call cycle: {loop_details}"
            }
        else:
            return {
                "score": 0.0, # 0.0 indicates no loop (success)
                "explanation": "No infinite loop or repetitive cycles detected in the agent trace."
            }


class AgentTaskCompletionEvaluator(BaseEvaluator):
    @property
    def name(self) -> str:
        return "agent_task_completion"

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
            f"User Goal: {input_prompt}\n"
            f"Expected Outcome (Ground Truth): {expected_output or 'Not specified'}\n"
            f"Final Agent Answer: {generated_response}\n\n"
            "Assess if the agent successfully completed the task. "
            "Check if the final answer contains the requested information and matches the expected outcome (if provided). "
            "Score from 0.0 (failed to solve the user's request) to 1.0 (fully accomplished user prompt)."
        )
        system_prompt = "You are an expert evaluator assessing Agent Task Completion (whether the final agent response answers and solves the prompt)."
        return await call_llm_judge(prompt, system_prompt)


# Register agent evaluators
evaluator_registry.register(AgentToolSelectionEvaluator())
evaluator_registry.register(AgentToolCorrectnessEvaluator())
evaluator_registry.register(AgentLoopDetectionEvaluator())
evaluator_registry.register(AgentTaskCompletionEvaluator())
