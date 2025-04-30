from sqlalchemy.engine import create_engine
from sqlalchemy.orm.session import sessionmaker

from .database import *

engine = create_engine('sqlite:///database.db')

sessions = sessionmaker(engine)