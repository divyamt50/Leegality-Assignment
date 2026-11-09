from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.orm import sessionmaker, declarative_base

engine = create_engine("sqlite:///./routes.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

class Node(Base):
    __tablename__ = "nodes"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

class Edge(Base):
    __tablename__ = "edges"
    id = Column(Integer, primary_key=True)
    source = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    latency = Column(Float, nullable=False)

class RouteHistory(Base):
    __tablename__ = "route_history"
    id = Column(Integer, primary_key=True)
    source = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    total_latency = Column(Float, nullable=False)
    path = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()