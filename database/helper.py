from typing import Optional

import sqlalchemy
from sqlalchemy.engine import Engine
from sqlalchemy.future import select
from sqlalchemy.orm import Session

from database import models


class VotesDatabase:

    def __init__(self, echo: bool = False):
        self.engine = sqlalchemy.create_engine("sqlite:///data/database.db", echo=echo, future=True)
        self.engine: Engine

        models.Base.metadata.create_all(self.engine)

    def create_session(self) -> Session:
        return Session(self.engine)

    @staticmethod
    def get_or_create(session: Session, model: models.Base, **kwargs):
        instance = session.query(model).filter_by(**kwargs).first()
        if instance:
            return instance
        else:
            instance = model(**kwargs)
            session.add(instance)
            return instance
