"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent / ".env")


class Config:
    """Central configuration. All settings come from environment variables."""

    # WeChat Work
    CORP_ID: str = os.getenv("CORP_ID", "")
    CORP_SECRET: str = os.getenv("CORP_SECRET", "")
    TOKEN: str = os.getenv("TOKEN", "")
    ENCODING_AES_KEY: str = os.getenv("ENCODING_AES_KEY", "")
    AGENT_ID: str = os.getenv("AGENT_ID", "")

    # GLM API
    GLM_API_KEY: str = os.getenv("GLM_API_KEY", "")
    GLM_API_BASE: str = os.getenv(
        "GLM_API_BASE", "https://api.z.ai/api/coding/paas/v4/"
    )
    GLM_MODEL: str = os.getenv("GLM_MODEL", "glm-4.5-flash")

    # Server
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8080"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # Message mode
    MESSAGE_MODE: str = os.getenv("MESSAGE_MODE", "kf")
    KF_OPEN_KFID: str = os.getenv("KF_OPEN_KFID", "")

    # Required fields validation
    _REQUIRED = ("CORP_ID", "CORP_SECRET", "TOKEN", "ENCODING_AES_KEY", "GLM_API_KEY")

    def __init__(self) -> None:
        missing = [f for f in self._REQUIRED if not getattr(self, f)]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Copy .env.example to .env and fill in the values."
            )
