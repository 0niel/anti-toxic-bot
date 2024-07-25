import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Config(BaseSettings):
    PERSPECTIVE_API_KEY: str = os.getenv("PERSPECTIVE_API_KEY")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN")
    ADMIN_USERNAMES: list[str] = os.getenv("ADMIN_USERNAMES").split(",")


config = Config()
