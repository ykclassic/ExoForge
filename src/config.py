import yaml
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class TradingConfig(BaseModel):
    max_open_positions: int = Field(gt=0)
    daily_loss_limit_usd: float = Field(gt=0.0)
    max_drawdown_pct: float = Field(gt=0.0, le=100.0)
    default_risk_per_trade_pct: float = Field(gt=0.0, le=100.0)

class BotConfig(BaseModel):
    trading: TradingConfig
    symbols: list[str]
    intervals: list[str]

    @field_validator("symbols")
    def validate_symbols(cls, v):
        if not v:
            raise ValueError("At least one trading symbol must be provided.")
        return v

class EnvironmentConfig(BaseSettings):
    GATEIO_API_KEY: str
    GATEIO_API_SECRET: str
    SUPABASE_DB_URL: str
    DISCORD_WEBHOOK_URL: str
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

def load_yaml_config(filepath: str = "config/config.yaml") -> BotConfig:
    """Loads and validates the YAML configuration."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found at {filepath}")
    
    with open(path, "r") as file:
        data = yaml.safe_load(file)
        
    return BotConfig(**data)

def get_settings() -> tuple[EnvironmentConfig, BotConfig]:
    """Retrieves all validated settings."""
    env_settings = EnvironmentConfig()
    yaml_settings = load_yaml_config()
    return env_settings, yaml_settings
