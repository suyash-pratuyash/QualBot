"""Add operational lead status.
Revision ID: 4d7f4f1a2b11
Revises: cf9f780915ed
"""
from alembic import op
import sqlalchemy as sa
revision="4d7f4f1a2b11"
down_revision="cf9f780915ed"
branch_labels=None
depends_on=None
def upgrade():
    op.add_column("leads",sa.Column("operational_status",sa.String(length=20),nullable=False,server_default="new"))
    op.create_check_constraint("ck_leads_operational_status","leads","operational_status IN ('new','contacted','converted','closed')")
    op.alter_column("leads","operational_status",server_default=None)
def downgrade():
    op.drop_constraint("ck_leads_operational_status","leads",type_="check")
    op.drop_column("leads","operational_status")
