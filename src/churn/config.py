from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_path: str = "artifact/model.joblib"
    model_name: str | None = None
    model_alias: str = "champion"
    database_url: str | None = None
    log_level: str = "INFO"

    model_config = {"env_file": ".env"}


settings = Settings()