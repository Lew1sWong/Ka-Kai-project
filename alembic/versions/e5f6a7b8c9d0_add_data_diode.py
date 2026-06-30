"""add data-diode staging table (one-way transfer mechanism)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-30 00:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "diode_packets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("classification", sa.String(length=32), nullable=False, server_default="public"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="staged"),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("kb_documents.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transferred_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_diode_packets_user_id", "diode_packets", ["user_id"])
    op.create_index("ix_diode_packets_source", "diode_packets", ["source"])
    op.create_index("ix_diode_packets_content_hash", "diode_packets", ["content_hash"])
    op.create_index("ix_diode_packets_status", "diode_packets", ["status"])


def downgrade() -> None:
    op.drop_table("diode_packets")
