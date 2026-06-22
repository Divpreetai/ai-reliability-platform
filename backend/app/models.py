import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    category = Column(String, default="General") # e.g. Finance, Healthcare, Legal
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    test_cases = relationship("TestCase", back_populates="dataset", cascade="all, delete-orphan")
    runs = relationship("EvaluationRun", back_populates="dataset", cascade="all, delete-orphan")


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(String, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    input_prompt = Column(Text, nullable=False)
    reference_context = Column(Text, nullable=True) # Used for RAG evals
    expected_output = Column(Text, nullable=True)  # Ground truth
    expected_tools = Column(JSON, nullable=True)    # For agent tool selection tests e.g. ["calculator", "search"]
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dataset = relationship("Dataset", back_populates="test_cases")
    results = relationship("EvaluationResult", back_populates="test_case", cascade="all, delete-orphan")


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    version = Column(Integer, default=1)
    template_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    runs = relationship("EvaluationRun", back_populates="prompt_template")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(String, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    prompt_template_id = Column(String, ForeignKey("prompt_templates.id", ondelete="SET NULL"), nullable=True)
    name = Column(String, nullable=False)
    model_name = Column(String, nullable=False) # e.g. gpt-4o, claude-3-5-sonnet, gemini-1.5-flash, ollama/llama3
    status = Column(String, default="PENDING")   # PENDING, RUNNING, COMPLETED, FAILED
    total_cost = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dataset = relationship("Dataset", back_populates="runs")
    prompt_template = relationship("PromptTemplate", back_populates="runs")
    results = relationship("EvaluationResult", back_populates="run", cascade="all, delete-orphan")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    test_case_id = Column(String, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    generated_response = Column(Text, nullable=True)
    latency_ms = Column(Float, default=0.0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    agent_trace = Column(JSON, nullable=True) # Store actual agent steps (tools called)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    run = relationship("EvaluationRun", back_populates="results")
    test_case = relationship("TestCase", back_populates="results")
    metric_scores = relationship("MetricScore", back_populates="result", cascade="all, delete-orphan")


class MetricScore(Base):
    __tablename__ = "metric_scores"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    result_id = Column(String, ForeignKey("evaluation_results.id", ondelete="CASCADE"), nullable=False)
    metric_type = Column(String, nullable=False) # e.g. hallucination, RAG precision, safety, etc.
    score = Column(Float, nullable=False)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    result = relationship("EvaluationResult", back_populates="metric_scores")
