import os
import json
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import ClassVar


load_dotenv()


class Settings(BaseSettings):
    APP_NAME: str = "Financial Analysis Platform"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    headers_str: ClassVar[str] = os.getenv("HEADERS", "{}")
    headers: dict = json.loads(headers_str)

    YFINANCE_TIMEOUT: int = int(os.getenv("YFINANCE_TIMEOUT", "5"))

    class Config:
        env_file = ".env"

settings = Settings()
