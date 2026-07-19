from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All config lives here, driven by env vars / .env file.
    Nothing else in the codebase should read os.environ directly.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM backend switch ---
    # "ollama" -> local dev / CPU testing, talks to the Ollama HTTP API
    # "vllm"   -> AMD pod, OpenAI-compatible endpoint from `vllm serve`
    llm_backend: str = "ollama"

    ollama_base_url: str = "http://ollama:11434"
    ollama_small_model: str = "qwen2.5:3b"
    ollama_large_model: str = "qwen2.5:7b"

    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_api_key: str = "not-needed"
    vllm_small_model: str = "Qwen/Qwen2.5-3B-Instruct"
    vllm_large_model: str = "Qwen/Qwen2.5-14B-Instruct"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://ara:ara_dev_pw@postgres:5432/ara_db"

    # --- Redis ---
    redis_url: str = "redis://redis:6379/0"

    # --- Agent execution ---
    # "sequential" or "concurrent" — this is the benchmark toggle.
    # Exposed via API so the frontend can flip it live during a demo.
    default_execution_mode: str = "sequential"

    # --- Tools ---
    web_search_enabled: bool = True
    code_exec_enabled: bool = True

    # --- Misc ---
    app_env: str = "dev"
    log_level: str = "INFO"


settings = Settings()
