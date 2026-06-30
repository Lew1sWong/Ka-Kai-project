"""add email verification fields

Revision ID: 7f6d1e4d8b2a
Revises: bcae4008639a
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f6d1e4d8b2a"
down_revision: Union[str, Sequence[str], None] = "bcae4008639a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_verified", sa.Boolean(), nullable=True))
    op.add_column("users", sa.Column("verification_token_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("verification_token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("verification_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE users
            SET is_verified = TRUE,
                verified_at = COALESCE(verified_at, created_at)
            """
        )
    )

    op.alter_column("users", "is_verified", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "verified_at")
    op.drop_column("users", "verification_sent_at")
    op.drop_column("users", "verification_token_expires_at")
    op.drop_column("users", "verification_token_hash")
    op.drop_column("users", "is_verified")
