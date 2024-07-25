import os
from dotenv import load_dotenv
from pydantic import BaseSettings, validator

load_dotenv()


class Config(BaseSettings):
    PERSPECTIVE_API_KEY: str
    TELEGRAM_BOT_TOKEN: str
    ADMIN_USERNAMES: list[str]

    @validator("ADMIN_USERNAMES", pre=True, each_item=True)
    def split_admin_usernames(cls, value):
        if isinstance(value, str):
            return value.split(",")
        return value


config = Config()
