from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./sundai_iap.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from sqlalchemy import Column, Integer, String, JSON, DateTime
from datetime import datetime

# ... existing imports ...

Base = declarative_base()

class FeedbackMemory(Base):
    __tablename__ = "feedback_memory"
    
    id = Column(Integer, primary_key=True, index=True)
    original_content = Column(String)
    feedback_text = Column(String)
    embedding = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
