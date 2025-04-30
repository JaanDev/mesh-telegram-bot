from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy import Integer, String


class MyBase(DeclarativeBase):
    pass


class Users(MyBase):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String)
    student_id: Mapped[str] = mapped_column(String)
