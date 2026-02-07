from sqlmodel import create_engine
from app.core.config import settings

engine = create_engine(settings.db_url, echo=False)
