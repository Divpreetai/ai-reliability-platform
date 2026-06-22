import asyncio
import time
import uuid
import logging
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional

from backend.app.celery_app import celery_app
from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.models import EvaluationRun, EvaluationResult, MetricScore, TestCase, PromptTemplate
from backend.app.engine.registry import evaluator_registry
from backend.app.engine.evaluators.cost_tracker import calculate_cost

# Ensure all evaluators are registered
import backend.app.engine.evaluators

logger = logging.getLogger(__name__)

# ==========================================
# Multi-Model LLM API Callers
# ==========================================
async def call_model_api(
    model_name: str, 
    system_prompt: str, 
    user_prompt: str,
    expected_tools: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Invokes the requested LLM model and returns:
    - text: generated response
    - latency_ms: duration
    - prompt_tokens: count
    - completion_tokens: count
    - agent_trace: list of steps (simulated for agentic test cases)
    """
    start_time = time.time()
    
    # ----------------------------------------------------
    # MOCK FALLBACK (If API keys are missing)
    # ----------------------------------------------------
    openai_missing = not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your-openai-api-key-here"
    anthropic_missing = not settings.ANTHROPIC_API_KEY or settings.ANTHROPIC_API_KEY == "your-anthropic-api-key-here"
    gemini_missing = not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your-gemini-api-key-here"

    # Normalize name
    model_lower = model_name.lower()
    
    # Simple simulated agent trace if tools are expected
    simulated_agent_trace = None
    if expected_tools:
        simulated_agent_trace = []
        for i, tool in enumerate(expected_tools):
            simulated_agent_trace.append({
                "type": "thought",
                "step": i * 2 + 1,
                "content": f"I need to call the '{tool}' tool to fetch details relevant to the prompt."
            })
            simulated_agent_trace.append({
                "type": "tool_call",
                "step": i * 2 + 2,
                "tool_name": tool,
                "tool_input": {"query": user_prompt[:30]},
                "tool_output": f"Simulated output from {tool} tool execution."
            })

    # Execute actual calls or fall back to mock
    try:
        if "gpt" in model_lower:
            if openai_missing:
                await asyncio.sleep(1.0) # simulate network latency
                mock_text = f"[MOCKED OpenAI {model_name}] Here is the response to your prompt: '{user_prompt}'. All systems operational."
                return {
                    "text": mock_text,
                    "latency_ms": (time.time() - start_time) * 1000,
                    "prompt_tokens": 40,
                    "completion_tokens": 35,
                    "agent_trace": simulated_agent_trace
                }
            
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )
            return {
                "text": resp.choices[0].message.content,
                "latency_ms": (time.time() - start_time) * 1000,
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "agent_trace": simulated_agent_trace
            }

        elif "claude" in model_lower:
            if anthropic_missing:
                await asyncio.sleep(1.5)
                mock_text = f"[MOCKED Anthropic Claude] I have processed your instruction: '{user_prompt}'. The analysis is complete."
                return {
                    "text": mock_text,
                    "latency_ms": (time.time() - start_time) * 1000,
                    "prompt_tokens": 50,
                    "completion_tokens": 45,
                    "agent_trace": simulated_agent_trace
                }
                
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            resp = await client.messages.create(
                model=model_name,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            # Estimate tokens roughly
            prompt_toks = resp.usage.input_tokens
            comp_toks = resp.usage.output_tokens
            return {
                "text": resp.content[0].text,
                "latency_ms": (time.time() - start_time) * 1000,
                "prompt_tokens": prompt_toks,
                "completion_tokens": comp_toks,
                "agent_trace": simulated_agent_trace
            }

        elif "gemini" in model_lower:
            if gemini_missing:
                await asyncio.sleep(0.8)
                mock_text = f"[MOCKED Gemini] Summarizing user request: '{user_prompt}'. Grounding verify: Positive."
                return {
                    "text": mock_text,
                    "latency_ms": (time.time() - start_time) * 1000,
                    "prompt_tokens": 30,
                    "completion_tokens": 25,
                    "agent_trace": simulated_agent_trace
                }
                
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            # Convert system prompt + user prompt for Gemini
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_prompt if system_prompt else None
            )
            # generate content
            response = await asyncio.to_thread(model.generate_content, user_prompt)
            # Estimate tokens roughly (Gemini SDK has count_tokens call, let's estimate to avoid double API trip)
            txt = response.text
            prompt_toks = len(user_prompt.split()) * 2
            comp_toks = len(txt.split()) * 2
            return {
                "text": txt,
                "latency_ms": (time.time() - start_time) * 1000,
                "prompt_tokens": prompt_toks,
                "completion_tokens": comp_toks,
                "agent_trace": simulated_agent_trace
            }

        elif "ollama" in model_lower:
            # Try calling local Ollama instance
            async with httpx.AsyncClient() as client:
                # model_name could be like ollama/llama3
                clean_model = model_name.split("/")[-1] if "/" in model_name else model_name
                try:
                    payload = {
                        "model": clean_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "stream": False
                    }
                    resp = await client.post(
                        f"{settings.OLLAMA_HOST}/api/chat", 
                        json=payload, 
                        timeout=30.0
                    )
                    data = resp.json()
                    txt = data["message"]["content"]
                    prompt_toks = data.get("prompt_eval_count", len(user_prompt.split()) * 2)
                    comp_toks = data.get("eval_count", len(txt.split()) * 2)
                    return {
                        "text": txt,
                        "latency_ms": (time.time() - start_time) * 1000,
                        "prompt_tokens": prompt_toks,
                        "completion_tokens": comp_toks,
                        "agent_trace": simulated_agent_trace
                    }
                except Exception as ollama_err:
                    logger.warning(f"Ollama local connection failed, mocking: {str(ollama_err)}")
                    await asyncio.sleep(0.5)
                    return {
                        "text": f"[MOCKED Local Ollama {clean_model}] Response to: {user_prompt}",
                        "latency_ms": 500,
                        "prompt_tokens": 20,
                        "completion_tokens": 15,
                        "agent_trace": simulated_agent_trace
                    }

        else:
            # Catch-all model mock fallback
            await asyncio.sleep(1.0)
            return {
                "text": f"[Mocked Generic Model {model_name}] Received: {user_prompt}",
                "latency_ms": 1000,
                "prompt_tokens": 25,
                "completion_tokens": 20,
                "agent_trace": simulated_agent_trace
            }

    except Exception as api_err:
        logger.error(f"Error calling model API {model_name}: {str(api_err)}")
        return {
            "text": f"Error calling model API: {str(api_err)}",
            "latency_ms": (time.time() - start_time) * 1000,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "agent_trace": simulated_agent_trace
        }

# ==========================================
# Celery Execution Task
# ==========================================
@celery_app.task(name="backend.app.engine.runner.run_evaluation_job")
def run_evaluation_job(run_id: str):
    """
    Celery task that executes an evaluation run in the background.
    """
    logger.info(f"Starting Celery background job for EvaluationRun={run_id}")
    
    # Run async function in a synchronous context
    asyncio.run(execute_eval_run(run_id))


async def execute_eval_run(run_id: str):
    db = SessionLocal()
    try:
        run = db.query(EvaluationRun).filter(EvaluationRun.id == run_id).first()
        if not run:
            logger.error(f"EvaluationRun={run_id} not found in database.")
            return

        run.status = "RUNNING"
        db.commit()

        # Load test cases in dataset
        test_cases = db.query(TestCase).filter(TestCase.dataset_id == run.dataset_id).all()
        if not test_cases:
            logger.warning(f"No test cases found in Dataset={run.dataset_id}")
            run.status = "COMPLETED"
            db.commit()
            return

        # Fetch optional prompt template
        sys_prompt = "You are a helpful and accurate assistant."
        if run.prompt_template_id:
            pt = db.query(PromptTemplate).filter(PromptTemplate.id == run.prompt_template_id).first()
            if pt:
                sys_prompt = pt.template_text

        total_run_cost = 0.0

        for tc in test_cases:
            try:
                # Format final user prompt (simple placeholder substitution if present, e.g. {input_prompt})
                # If template references context, inject it
                user_prompt = tc.input_prompt
                
                # Execute model call
                logger.info(f"Evaluating model={run.model_name} on TestCase={tc.id}")
                resp_data = await call_model_api(
                    model_name=run.model_name,
                    system_prompt=sys_prompt,
                    user_prompt=user_prompt,
                    expected_tools=tc.expected_tools
                )
                
                # Save initial result details
                cost = calculate_cost(
                    model_name=run.model_name,
                    prompt_tokens=resp_data["prompt_tokens"],
                    completion_tokens=resp_data["completion_tokens"]
                )
                total_run_cost += cost

                result = EvaluationResult(
                    id=str(uuid.uuid4()),
                    run_id=run.id,
                    test_case_id=tc.id,
                    generated_response=resp_data["text"],
                    latency_ms=resp_data["latency_ms"],
                    prompt_tokens=resp_data["prompt_tokens"],
                    completion_tokens=resp_data["completion_tokens"],
                    estimated_cost=cost,
                    agent_trace=resp_data["agent_trace"]
                )
                db.add(result)
                db.flush() # populated result.id

                # Trigger registry evaluators concurrently
                eval_tasks = []
                evaluators = evaluator_registry.get_all()
                
                for evaluator in evaluators:
                    # Decide if evaluator should run
                    # For agent evaluators: only run if agent_trace/expected_tools is present or if it's agentic
                    # For RAG evaluators: only run if reference_context is present or if it's RAG-specific
                    # Safety and response quality scoring runs always
                    is_agent_metric = evaluator.name.startswith("agent")
                    is_rag_metric = evaluator.name.startswith("rag") or evaluator.name == "grounding_check"
                    
                    if is_agent_metric and not tc.expected_tools:
                        continue # Skip agent metrics for non-agentic cases
                    if is_rag_metric and not tc.reference_context:
                        continue # Skip RAG metrics if no context is provided
                        
                    task = evaluator.evaluate(
                        input_prompt=user_prompt,
                        generated_response=resp_data["text"],
                        reference_context=tc.reference_context,
                        expected_output=tc.expected_output,
                        agent_trace=resp_data["agent_trace"],
                        expected_tools=tc.expected_tools
                    )
                    eval_tasks.append((evaluator.name, task))

                if eval_tasks:
                    names = [name for name, _ in eval_tasks]
                    futures = [task for _, task in eval_tasks]
                    scores = await asyncio.gather(*futures)

                    for name, res in zip(names, scores):
                        ms = MetricScore(
                            id=str(uuid.uuid4()),
                            result_id=result.id,
                            metric_type=name,
                            score=res.get("score", 0.0),
                            explanation=res.get("explanation", "")
                        )
                        db.add(ms)

            except Exception as case_err:
                logger.error(f"Error evaluating test case {tc.id}: {str(case_err)}")
                # Create a failed result record
                result = EvaluationResult(
                    run_id=run.id,
                    test_case_id=tc.id,
                    generated_response=f"Failed execution: {str(case_err)}",
                    latency_ms=0.0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    estimated_cost=0.0
                )
                db.add(result)

        run.status = "COMPLETED"
        run.total_cost = total_run_cost
        db.commit()
        logger.info(f"EvaluationRun={run.id} completed successfully. Total cost: ${total_run_cost:.5f}")

        # Sync results to LangSmith if configured
        try:
            from backend.app.engine.langsmith_helper import log_run_to_langsmith
            log_run_to_langsmith(run.id, db)
        except Exception as ls_err:
            logger.warning(f"Failed to log run to LangSmith: {str(ls_err)}")


    except Exception as run_err:
        logger.error(f"Critical error executing run {run_id}: {str(run_err)}")
        db.rollback()
        try:
            run = db.query(EvaluationRun).filter(EvaluationRun.id == run_id).first()
            if run:
                run.status = "FAILED"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
