"""Environment-backed application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    openai_api_key: str = ""
    openai_model: str = "gpt-5.4"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536
    chunk_max_characters: int = 3_600
    chunk_overlap_characters: int = 450
    openai_discovery_max_output_tokens: int = 4_000
    openai_discovery_max_tool_calls: int = 6
    openai_discovery_input_budget_tokens: int = 60_000
    openai_brief_max_output_tokens: int = 6_000
    openai_content_max_output_tokens: int = 10_000
    openai_review_max_output_tokens: int = 6_000
    openai_agent_max_output_tokens: int = 2_000
    openai_agent_max_model_calls: int = 6
    openai_agent_recursion_limit: int = 40

    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "gtm-content-eval"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    openai_input_cost_per_million: float = 2.50
    openai_output_cost_per_million: float = 15.00
    openai_embedding_cost_per_million: float = 0.02
    openai_web_search_cost_per_call: float = 0.01

    pinecone_api_key: str = ""
    pinecone_index_name: str = "ai-week-in-review"
    pinecone_namespace: str = "ai-week-in-review"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    evaluation_runs_path: str = "data/evals/runs"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance for the current process."""
    return Settings()
