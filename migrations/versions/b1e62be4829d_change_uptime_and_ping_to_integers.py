"""Change uptime and ping to integers

Revision ID: b1e62be4829d
Revises: 
Create Date: 2024-12-21 03:35:00.145453

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1e62be4829d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('vpn_servers', schema=None) as batch_op:
        batch_op.alter_column('uptime',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.Integer(),
               existing_nullable=True)
        batch_op.alter_column('ping',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.Integer(),
               existing_nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('vpn_servers', schema=None) as batch_op:
        batch_op.alter_column('ping',
               existing_type=sa.Integer(),
               type_=sa.VARCHAR(length=50),
               existing_nullable=True)
        batch_op.alter_column('uptime',
               existing_type=sa.Integer(),
               type_=sa.VARCHAR(length=50),
               existing_nullable=True)

    # ### end Alembic commands ###
