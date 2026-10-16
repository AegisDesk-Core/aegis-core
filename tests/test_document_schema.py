from app.db.schema import build_schema_sql


def test_document_status_migration_drops_legacy_check_before_status_update():
    schema_sql = build_schema_sql()

    drop_constraint = schema_sql.index(
        "ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_status_check;"
    )
    migrate_status = schema_sql.index(
        "UPDATE documents SET status = 'ready' WHERE status = 'completed';"
    )
    add_constraint = schema_sql.index(
        "ADD CONSTRAINT documents_status_check"
    )

    assert drop_constraint < migrate_status < add_constraint
