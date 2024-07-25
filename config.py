from typing import Any, List, Optional, Tuple, Type
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource
from pydantic import Field, validator
from pydantic.fields import FieldInfo


class MyCustomSource(EnvSettingsSource):
    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        if field_name == "ADMIN_USERNAMES" and value:
            return value.split(",")
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Config(BaseSettings):
    PERSPECTIVE_API_KEY: str
    TELEGRAM_BOT_TOKEN: str
    ADMIN_USERNAMES: Optional[List[str]] = Field(default=None)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (MyCustomSource(settings_cls),)


config = Config()
