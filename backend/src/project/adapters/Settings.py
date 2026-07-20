from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic.networks import AnyHttpUrl, IPvAnyAddress
from typing_extensions import Literal
from pydantic.types import PositiveInt
from pydantic import AliasChoices, Field
from dataclasses import dataclass


class ProjectSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class SecurityVariables(ProjectSettings):
    OPENAI_API_KEY: str
    MARITACA_API_KEY: str
    LANGCHAIN_API_KEY: str


class APIVariables(ProjectSettings):
    port: PositiveInt = Field(validation_alias=AliasChoices("api_port", "port"))
    host: AnyHttpUrl | IPvAnyAddress
    allowed_origins: list[AnyHttpUrl | Literal["*"]]
    allowed_methods: list[str]
    allowed_headers: list[str]


@dataclass
class Settings:
    api: APIVariables
    security: SecurityVariables

    @classmethod
    def load(cls):
        return Settings(api=APIVariables(), security=SecurityVariables())
