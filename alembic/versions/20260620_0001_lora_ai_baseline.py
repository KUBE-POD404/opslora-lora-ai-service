from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260620_0001"
down_revision = None
branch_labels = None
depends_on = None


def _tenant_columns() -> list[sa.Column]:
    return [
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=255)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON()),
        *_tenant_columns(),
    )
    op.create_index("ix_ai_conversations_organization_id", "ai_conversations", ["organization_id"])
    op.create_index("ix_ai_conversations_status", "ai_conversations", ["status"])

    op.create_table(
        "ai_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("ai_conversations.id"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=64)),
        sa.Column("model", sa.String(length=128)),
        sa.Column("citations_json", sa.JSON()),
        sa.Column("token_count", sa.Integer()),
        *_tenant_columns(),
    )
    op.create_index("ix_ai_messages_conversation_id", "ai_messages", ["conversation_id"])
    op.create_index("ix_ai_messages_organization_id", "ai_messages", ["organization_id"])

    op.create_table(
        "ai_knowledge_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_uri", sa.String(length=1024)),
        sa.Column("visibility_scope", sa.String(length=64), nullable=False),
        sa.Column("retention_policy", sa.String(length=128)),
        sa.Column("status", sa.String(length=32), nullable=False),
        *_tenant_columns(),
    )
    op.create_index("ix_ai_knowledge_sources_organization_id", "ai_knowledge_sources", ["organization_id"])
    op.create_index("ix_ai_knowledge_sources_status", "ai_knowledge_sources", ["status"])

    op.create_table(
        "ai_knowledge_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_id", sa.String(length=36), sa.ForeignKey("ai_knowledge_sources.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("vector_id", sa.String(length=128)),
        sa.Column("metadata_json", sa.JSON()),
        *_tenant_columns(),
    )
    op.create_index("ix_ai_knowledge_chunks_source_id", "ai_knowledge_chunks", ["source_id"])
    op.create_index("ix_ai_knowledge_chunks_organization_id", "ai_knowledge_chunks", ["organization_id"])
    op.create_index("ix_ai_knowledge_chunks_vector_id", "ai_knowledge_chunks", ["vector_id"])

    for table_name, extra_columns in {
        "ai_tool_calls": [
            sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("ai_conversations.id")),
            sa.Column("tool_name", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("request_metadata_json", sa.JSON()),
            sa.Column("response_metadata_json", sa.JSON()),
        ],
        "ai_audit_events": [
            sa.Column("event_type", sa.String(length=128), nullable=False),
            sa.Column("event_metadata_json", sa.JSON()),
        ],
        "ai_usage_events": [
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("model", sa.String(length=128)),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cost_micros", sa.Integer(), nullable=False, server_default="0"),
        ],
    }.items():
        op.create_table(table_name, sa.Column("id", sa.String(length=36), primary_key=True), *extra_columns, *_tenant_columns())
        op.create_index(f"ix_{table_name}_organization_id", table_name, ["organization_id"])


def downgrade() -> None:
    for table_name in [
        "ai_usage_events",
        "ai_audit_events",
        "ai_tool_calls",
        "ai_knowledge_chunks",
        "ai_knowledge_sources",
        "ai_messages",
        "ai_conversations",
    ]:
        op.drop_table(table_name)
