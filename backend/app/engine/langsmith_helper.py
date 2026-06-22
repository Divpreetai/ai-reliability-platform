import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models import EvaluationRun, EvaluationResult, MetricScore, Dataset, TestCase

logger = logging.getLogger(__name__)

# Active LangSmith Client placeholder
_ls_client = None

def get_langsmith_client():
    global _ls_client
    if _ls_client is not None:
        return _ls_client

    api_key = settings.LANGCHAIN_API_KEY
    tracing_enabled = settings.LANGCHAIN_TRACING_V2.lower() == "true"

    if not api_key or api_key == "your-langsmith-api-key-here" or not tracing_enabled:
        logger.debug("LangSmith tracing is disabled or API key is missing. Skipping integration.")
        return None

    try:
        from langsmith import Client
        _ls_client = Client(api_key=api_key)
        logger.info("LangSmith client successfully initialized.")
        return _ls_client
    except Exception as e:
        logger.warning(f"Failed to initialize LangSmith client: {str(e)}")
        return None


def sync_dataset_to_langsmith(dataset_id: str, db: Session) -> Optional[str]:
    """
    Syncs a local Dataset and its TestCases to LangSmith.
    Returns the LangSmith Dataset URL or ID if successful, otherwise None.
    """
    client = get_langsmith_client()
    if not client:
        return None

    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        logger.error(f"Dataset {dataset_id} not found in database.")
        return None

    try:
        # Check if dataset already exists in LangSmith
        ls_dataset = None
        try:
            ls_dataset = client.read_dataset(dataset_name=dataset.name)
            logger.info(f"LangSmith dataset '{dataset.name}' found. Syncing examples...")
        except Exception:
            # If read fails, create a new one
            ls_dataset = client.create_dataset(
                dataset_name=dataset.name,
                description=dataset.description or f"Synced from AgentEval category: {dataset.category}"
            )
            logger.info(f"Created new LangSmith dataset: '{dataset.name}'")

        if not ls_dataset:
            return None

        # Fetch local test cases
        test_cases = db.query(TestCase).filter(TestCase.dataset_id == dataset.id).all()
        
        # Fetch existing examples in LangSmith dataset to avoid duplicates
        existing_examples = client.list_examples(dataset_id=ls_dataset.id)
        existing_prompts = {ex.inputs.get("input") for ex in existing_examples if ex.inputs}

        # Upload new test cases
        new_count = 0
        for tc in test_cases:
            if tc.input_prompt in existing_prompts:
                continue
            
            client.create_example(
                inputs={
                    "input": tc.input_prompt,
                    "context": tc.reference_context or ""
                },
                outputs={
                    "output": tc.expected_output or ""
                },
                dataset_id=ls_dataset.id
            )
            new_count += 1

        logger.info(f"Synced {new_count} new test case examples to LangSmith dataset '{dataset.name}' (ID: {ls_dataset.id})")
        return str(ls_dataset.id)

    except Exception as e:
        logger.error(f"Failed to sync dataset {dataset_id} to LangSmith: {str(e)}")
        return None


def log_run_to_langsmith(run_id: str, db: Session):
    """
    Logs an EvaluationRun, its Results, and MetricScores as Feedback to LangSmith.
    """
    client = get_langsmith_client()
    if not client:
        return

    run = db.query(EvaluationRun).filter(EvaluationRun.id == run_id).first()
    if not run:
        logger.error(f"EvaluationRun {run_id} not found in database.")
        return

    # First ensure the dataset is synced so runs can link or reference it if needed
    sync_dataset_to_langsmith(run.dataset_id, db)

    try:
        logger.info(f"Logging run '{run.name}' to LangSmith project: {settings.LANGCHAIN_PROJECT}")

        results = db.query(EvaluationResult).filter(EvaluationResult.run_id == run.id).all()
        for res in results:
            # Skip if missing prompt or response
            if not res.test_case:
                res.test_case = db.query(TestCase).filter(TestCase.id == res.test_case_id).first()
            
            input_prompt = res.test_case.input_prompt if res.test_case else "N/A"
            ref_context = res.test_case.reference_context if res.test_case else ""
            
            # Estimate start and end times based on latency_ms
            latency_seconds = res.latency_ms / 1000.0
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(seconds=max(0.1, latency_seconds))

            # Log execution as a run in LangSmith
            ls_run = client.create_run(
                name=f"AgentEval_{run.name}",
                run_type="chain",
                inputs={
                    "input": input_prompt,
                    "context": ref_context
                },
                outputs={
                    "output": res.generated_response or ""
                },
                project_name=settings.LANGCHAIN_PROJECT,
                start_time=start_time,
                end_time=end_time,
                extra={
                    "metadata": {
                        "model": run.model_name,
                        "latency_ms": res.latency_ms,
                        "prompt_tokens": res.prompt_tokens,
                        "completion_tokens": res.completion_tokens,
                        "cost_usd": res.estimated_cost,
                        "evaluation_run_id": run.id,
                        "test_case_id": res.test_case_id
                    }
                }
            )

            # Log each metric score as feedback on this LangSmith run
            for score in res.metric_scores:
                client.create_feedback(
                    run_id=ls_run.id,
                    key=score.metric_type,
                    score=score.score,
                    comment=score.explanation
                )

        logger.info(f"EvaluationRun {run.name} successfully exported to LangSmith.")

    except Exception as e:
        logger.error(f"Error logging run {run_id} to LangSmith: {str(e)}")
