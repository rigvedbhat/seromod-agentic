from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    discord_token: str = os.getenv("DISCORD_TOKEN", "").strip()
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o").strip()
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1").strip()
    data_dir: str = os.getenv("SEROMOD_DATA_DIR", "data/guilds").strip()


config = Config()
