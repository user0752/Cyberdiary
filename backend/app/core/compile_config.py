from pydantic import BaseModel, Field


class CompilationConfig(BaseModel):
    model: str = "deepseek/deepseek-chat"
    max_revisions: int = Field(default=3, ge=1, le=10)
    parallel_researchers: int = Field(default=3, ge=1, le=5)
    pass_threshold: float = Field(default=8.0, ge=0, le=10)
    fallback_model: str = "ollama/qwen2.5:7b"
    enable_human_review: bool = False
    embedding_model: str = ""
    incremental: bool = True


DEFAULT_CONFIG = CompilationConfig().model_dump()
