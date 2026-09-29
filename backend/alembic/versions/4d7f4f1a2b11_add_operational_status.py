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
    with op.batch_alter_table("leads",schema=None) as batch:
        batch.add_column(sa.Column("operational_status",sa.String(length=20),nullable=False,server_default="new"))
        batch.create_check_constraint("ck_leads_operational_status","operational_status IN ('new','contacted','converted','closed')")
def downgrade():
    with op.batch_alter_table("leads",schema=None) as batch:
        batch.drop_constraint("ck_leads_operational_status",type_="check")
        batch.drop_column("operational_status")
