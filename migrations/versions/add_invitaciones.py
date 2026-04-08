"""add invitaciones table

Revision ID: a1bdc3d4e5f6
Revises: 002b52b19601
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

from migrations.versions.b442c9cd1813_core_inicial_tenants_users_roles_ import branch_labels, depends_on

# revision identifiers
revision = 'a1b2c3d4e5f6'
down_revision = '002b52b19601'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'invitaciones',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', sa.UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('email', sa.String(255), nullable=False, index=True),
        sa.Column('nombre', sa.String(128), nullable=True),
        sa.Column('token', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('estado', sa.String(16), nullable=False, server_default='pendiente'),
        sa.Column('invitado_por_id', sa.UUID(as_uuid=True),
                  sa.ForeignKey('tenant_members.id'), nullable=False),
        sa.Column('identity_id', sa.UUID(as_uuid=True),
                  sa.ForeignKey('identities.id'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('creatad_at', sa.DateTime(timezone=True),
                  default=datetime.now(timezone.utc), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    )

def downgrade():
    op.drop_table('invitaciones')