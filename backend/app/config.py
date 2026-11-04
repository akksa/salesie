from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
PLACEHOLDER = "CHANGE_ME"
MIN_OWNER_PASSWORD_LENGTH = 16


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str
    test_database_url: str | None = None
    meta_app_secret: SecretStr
    meta_verify_token: SecretStr
    owner_username: str = "owner"
    owner_password: SecretStr
    simulator_enabled: bool = False
    api_docs_enabled: bool = False
    max_body_bytes: int = 1_000_000

    # Sales agent. "mock" is a deterministic stand-in used until Meta Model API credits are available.
    agent_enabled: bool = True
    # "muse" = any OpenAI-compatible chat endpoint serving a Meta model: Meta Model API by default,
    # or Baseten's Muse Spark Open (LLM_BASE_URL=https://inference.baseten.co/v1,
    # LLM_MODEL=meta-models/muse-spark-open).
    llm_provider: Literal["mock", "muse"] = "mock"
    model_api_key: SecretStr | None = None
    llm_base_url: str = "https://api.meta.ai/v1"
    llm_model: str = "muse-spark-1.3"
    llm_timeout_seconds: float = 60.0

    # Instagram sending. Without a token, replies are recorded in Salesie but not sent to Meta.
    instagram_access_token: SecretStr | None = None
    instagram_graph_url: str = "https://graph.instagram.com/v23.0"
    # Facebook Page: Messenger replies and private replies to Page comments, with a Page access token.
    facebook_page_access_token: SecretStr | None = None
    facebook_graph_url: str = "https://graph.facebook.com/v26.0"

    # Where shoppers open payment links (this server's public URL).
    public_base_url: str = "http://localhost:8000"
    # The built-in checkout takes no money. With live Instagram sending, real shoppers could "pay" for free
    # and get a receipt, so that combination must be switched on deliberately (e.g. for a supervised demo).
    allow_test_checkout_with_live_instagram: bool = False

    # Agent load limits: concurrent turns stay well below the DB pool; a shopper over the daily budget is
    # handed to the owner instead of costing more model calls.
    agent_max_concurrent_turns: int = 4
    agent_turns_per_contact_per_day: int = 40

    @field_validator("meta_app_secret", "meta_verify_token", "owner_password")
    @classmethod
    def reject_placeholder(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if not secret or secret == PLACEHOLDER:
            raise ValueError("must be set to a real value (see backend/.env.example)")
        return value

    @field_validator("owner_password")
    @classmethod
    def require_strong_password(cls, value: SecretStr) -> SecretStr:
        # The dashboard is public; a long random password is what makes online guessing hopeless.
        if len(value.get_secret_value()) < MIN_OWNER_PASSWORD_LENGTH:
            raise ValueError(f"must be at least {MIN_OWNER_PASSWORD_LENGTH} characters")
        return value

    @field_validator("model_api_key", "instagram_access_token", "facebook_page_access_token", mode="before")
    @classmethod
    def empty_means_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def require_muse_key(self) -> Self:
        if self.llm_provider == "muse" and not self.model_api_key:
            raise ValueError("MODEL_API_KEY is required when LLM_PROVIDER=muse")
        return self

    @model_validator(mode="after")
    def guard_live_sending(self) -> Self:
        if self.instagram_access_token is None and self.facebook_page_access_token is None:
            return self
        if not self.allow_test_checkout_with_live_instagram:
            raise ValueError(
                "A Meta access token is set but payments use the test checkout (no money is taken). "
                "Set ALLOW_TEST_CHECKOUT_WITH_LIVE_INSTAGRAM=true only for a supervised demo."
            )
        if not self.public_base_url.startswith("https://"):
            raise ValueError(
                "PUBLIC_BASE_URL must be https:// when messaging real Instagram or Facebook users"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]  # values come from env/.env
