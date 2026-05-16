from __future__ import annotations

from datetime import date  # noqa: TC003
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .mobile_type import MobileType

if TYPE_CHECKING:
    from .user import User


class MobileNumber(UUIDAuditBase):
    """Verified mobile numbers linked to user accounts."""

    __tablename__ = "mobile_number"
    __table_args__ = {"comment": "Verified mobile numbers linked to user accounts"}
    __pii_columns__ = {"number", "country_code"}

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_account.id", ondelete="cascade"), nullable=False)
    number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    country_code: Mapped[str] = mapped_column(String(5), nullable=False)
    type: Mapped[MobileType] = mapped_column(String(20), default=MobileType.PERSONAL, nullable=False)
    verified_via: Mapped[str] = mapped_column(String(20), nullable=False)
    is_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    verified_at: Mapped[date | None] = mapped_column(nullable=True, default=None)

    # ORM Relationships
    user: Mapped[User] = relationship(back_populates="mobile_numbers", lazy="selectin")
