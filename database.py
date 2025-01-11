from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import databases

# データベースURL
DATABASE_URL = "sqlite:///./chat_history.db"

# databases インスタンスの作成
database = databases.Database(DATABASE_URL)

# SQLAlchemy設定
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100))  # チャットのタイトル
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    messages = relationship("ChatMessage", back_populates="chat")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"))
    role = Column(String(50))  # "user" または "assistant"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    chat = relationship("Chat", back_populates="messages")

# データベースのテーブルを作成
Base.metadata.create_all(bind=engine)

# データベース接続のセッションを取得する関数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
