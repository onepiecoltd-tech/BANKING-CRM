"""
Application configuration and settings.
"""
import os
from typing import Literal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings."""

    # LLM Configuration
    llm_backend: Literal["gemini", "ollama", "nvidia"] = "ollama"
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    nvidia_api_key: str = ""
    nvidia_model: str = "meta/llama-3.1-70b-instruct"

    # CRM Configuration
    crm_backend: Literal["sqlite", "hubspot"] = "sqlite"
    database_url: str = "sqlite:///./banking_crm.db"
    hubspot_developer_key: str = ""

    # Outreach Configuration
    sender_backend: Literal["mock", "twilio", "whatsapp-web"] = "mock"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_whatsapp_content_sid: str = ""  # Content API template SID for rich messages
    whatsapp_service_url: str = "http://localhost:3001"  # WhatsApp Web JS service
    whatsapp_sandbox: bool = True                         # True = all msgs → sandbox number
    whatsapp_sandbox_number: str = "+917838146286"        # default sandbox recipient

    # Application Configuration
    debug: bool = False
    port: int = 8000
    streamlit_port: int = 8501

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
