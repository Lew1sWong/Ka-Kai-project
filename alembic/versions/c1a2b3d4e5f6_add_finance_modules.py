"""add finance modules: roles, audit log, hypotheses, portfolios, knowledge base

Revision ID: c1a2b3d4e5f6
Revises: 7f6d1e4d8b2a
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "7f6d1e4d8b2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Permission & Log System ------------------------------------------
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="analyst"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # --- Investment-Hypothesis Management (Module B) ----------------------
    op.create_table(
        "hypotheses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("hero_id", sa.Integer(), sa.ForeignKey("heroes.id"), nullable=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("core_assumptions", sa.JSON(), nullable=True),
        sa.Column("validation_metrics", sa.JSON(), nullable=True),
        sa.Column("falsification_conditions", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("conviction", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_hypotheses_user_id", "hypotheses", ["user_id"])
    op.create_index("ix_hypotheses_ticker", "hypotheses", ["ticker"])

    op.create_table(
        "hypothesis_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hypothesis_id", sa.Integer(), sa.ForeignKey("hypotheses.id"), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_hypothesis_events_hypothesis_id", "hypothesis_events", ["hypothesis_id"])

    # --- Portfolio Risk-Assistance (Module C) -----------------------------
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_portfolios_user_id", "portfolios", ["user_id"])

    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("shares", sa.Float(), nullable=True),
        sa.Column("sector", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_holdings_portfolio_id", "holdings", ["portfolio_id"])
    op.create_index("ix_holdings_ticker", "holdings", ["ticker"])

    # --- Research Hub + Knowledge Base (Module D) -------------------------
    op.create_table(
        "kb_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_kb_documents_user_id", "kb_documents", ["user_id"])

    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("kb_documents.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_kb_chunks_document_id", "kb_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_table("kb_chunks")
    op.drop_table("kb_documents")
    op.drop_table("holdings")
    op.drop_table("portfolios")
    op.drop_table("hypothesis_events")
    op.drop_table("hypotheses")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_column("users", "role")
