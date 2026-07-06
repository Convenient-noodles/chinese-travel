"""
知识库统一数据模型
三表合一：attractions + hotels + foods → knowledge_items
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Float, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, default="attraction"
    )  # attraction / hotel / food
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True, default="")
    description: Mapped[str] = mapped_column(Text, nullable=True, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="published")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<KnowledgeItem({self.item_type}) {self.name}>"
