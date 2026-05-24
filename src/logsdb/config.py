from __future__ import annotations
from pathlib import Path
import tomllib
from pydantic import BaseModel
import sqlalchemy as sa
from .core import Database


class BaseConfig(BaseModel):
    model_config = {"extra": "forbid"}


class DatabaseDetails(BaseConfig):
    database: str
    username: str
    password: str


class Features(BaseConfig):
    apache_access: bool = False
    authfail: bool = False
    maillog: bool = False


class DailyReportCfg(BaseConfig):
    recipient: str
    mailbox: Path
    logs_dir: Path


class Config(BaseConfig):
    database: DatabaseDetails
    features: Features
    dailyreport: DailyReportCfg

    @classmethod
    def from_toml_file(cls, fpath: Path) -> Config:
        with fpath.open("rb") as fp:
            data = tomllib.load(fp)
        return cls.model_validate(data)

    def connect_to_database(self) -> Database:
        url = sa.engine.URL.create(
            drivername="postgresql",
            host="localhost",
            database=self.database.database,
            username=self.database.username,
            password=self.database.password,
        )
        return Database.connect(url)
