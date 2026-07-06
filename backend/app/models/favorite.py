"""
用户收藏数据模型
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class UserFavorite(Base):
    __tablename__ = "user_favorites"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'attraction' | 'hotel' | 'food'
    item_id: Mapped[str] = mapped_column(
        String(36), nullable=False
    )
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 关系
    user = relationship("User", back_populates="favorites")

    # 唯一约束：同一用户不能重复收藏同一项
    __table_args__ = (
        UniqueConstraint("user_id", "item_type", "item_id", name="uq_user_favorite"),
    )

    def __repr__(self) -> str:
        return f"<UserFavorite(user_id={self.user_id}, type={self.item_type}, item_id={self.item_id})>"
