from __future__ import annotations
from configparser import ConfigParser
from pathlib import Path
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
    def from_ini_file(cls, inifile: Path) -> Config:
        cfg = ConfigParser()
        with inifile.open() as fp:
            cfg.read_file(fp)
        return cls.model_validate(
            {k: dict(v) for k, v in cfg.items() if k != "DEFAULT"}
        )

    def connect_to_database(self) -> Database:
        url = sa.engine.URL.create(
            drivername="postgresql",
            host="localhost",
            database=self.database.database,
            username=self.database.username,
            password=self.database.password,
        )
        return Database.connect(url)
