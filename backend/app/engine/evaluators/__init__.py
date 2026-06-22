# Auto-import all evaluators to register them with the central registry
from backend.app.engine.evaluators import (
    rag,
    grounding,
    hallucination,
    safety,
    agent,
    scoring
)
