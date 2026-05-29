"""
Connected Tenant models for SaaS multi-tenancy.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base_model import Base, TimestampMixin, UUIDMixin
from app.db.types import JSONType


class ConnectedTenant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "connected_tenants"

    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, unique=True)
    tenant_name: Mapped[str] = mapped_column(String(255), nullable=True)
    
    app_registration_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    app_client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    service_principal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    encrypted_client_secret: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    secret_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    secret_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deployment_status: Mapped[str] = mapped_column(String(50), default="not_started", nullable=False)
    admin_consent_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    deployment_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    
    consent_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    consent_granted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consent_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    granted_permissions: Mapped[dict | list | None] = mapped_column(JSONType, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    
    last_assessment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
