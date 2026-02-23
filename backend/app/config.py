from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 火山方舟 Seedance
    ark_api_key: str = ""
    ark_seedance_endpoint_id: str = ""

    # LLM (seed-doubao 2.0 via Ark / OpenAI-compatible)
    ark_llm_api_key: str = ""
    ark_llm_endpoint_id: str = ""
    ark_llm_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

    openai_api_key: str = ""
    doubao_api_key: str = ""

    # Infrastructure
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/video_agent"
    redis_url: str = "redis://localhost:6379/0"

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    upload_dir: str = "./uploads"
    output_dir: str = "./outputs"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
