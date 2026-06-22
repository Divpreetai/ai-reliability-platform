from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime

# ==========================================
# Dataset Schemas
# ==========================================
class DatasetBase(BaseModel):
    name: str
    category: str = "General"
    description: Optional[str] = None

class DatasetCreate(DatasetBase):
    pass

class DatasetResponse(DatasetBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime

# ==========================================
# Test Case Schemas
# ==========================================
class TestCaseBase(BaseModel):
    input_prompt: str
    reference_context: Optional[str] = None
    expected_output: Optional[str] = None
    expected_tools: Optional[List[str]] = None

class TestCaseCreate(TestCaseBase):
    pass

class TestCaseResponse(TestCaseBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dataset_id: str
    created_at: datetime

# ==========================================
# Prompt Template Schemas
# ==========================================
class PromptTemplateBase(BaseModel):
    name: str
    template_text: str

class PromptTemplateCreate(PromptTemplateBase):
    pass

class PromptTemplateResponse(PromptTemplateBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    version: int
    created_at: datetime

# ==========================================
# Metric Score Schemas
# ==========================================
class MetricScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    metric_type: str
    score: float
    explanation: Optional[str] = None

# ==========================================
# Evaluation Result Schemas
# ==========================================
class EvaluationResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    run_id: str
    test_case_id: str
    generated_response: Optional[str] = None
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float
    agent_trace: Optional[List[Dict[str, Any]]] = None # Expected to hold tool selection details
    metric_scores: List[MetricScoreResponse] = []
    created_at: datetime
    test_case: Optional[TestCaseResponse] = None

# ==========================================
# Evaluation Run Schemas
# ==========================================
class EvaluationRunCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dataset_id: str
    prompt_template_id: Optional[str] = None
    name: str
    model_name: str # e.g. gpt-4o, claude-3-5-sonnet, gemini-1.5-flash, ollama/llama3

class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)
    id: str
    dataset_id: str
    prompt_template_id: Optional[str] = None
    name: str
    model_name: str
    status: str
    total_cost: float
    created_at: datetime
    results: List[EvaluationResultResponse] = []

# ==========================================
# Quick Check / Instant Evaluator
# ==========================================
class QuickCheckRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    input_prompt: str
    generated_response: Optional[str] = None
    model_name: Optional[str] = None
    system_prompt: Optional[str] = None
    reference_context: Optional[str] = None
    expected_output: Optional[str] = None
    agent_trace: Optional[List[Dict[str, Any]]] = None
    expected_tools: Optional[List[str]] = None

class QuickCheckResponse(BaseModel):
    generated_response: str
    latency_ms: float = 0.0
    estimated_cost: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    agent_trace: Optional[List[Dict[str, Any]]] = None
    scores: Dict[str, MetricScoreResponse]

# ==========================================
# Leaderboard & Rankings
# ==========================================
class ModelLeaderboardEntry(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_name: str
    avg_score: float
    avg_latency_ms: float
    total_cost: float
    run_count: int

class PromptLeaderboardEntry(BaseModel):
    prompt_name: str
    prompt_version: int
    avg_score: float
    avg_latency_ms: float
    run_count: int

class DatasetLeaderboardEntry(BaseModel):
    dataset_name: str
    category: str
    pass_rate: float # Percentage of tests scoring above threshold
    run_count: int
