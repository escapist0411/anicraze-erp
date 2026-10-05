"""Export PostgreSQL ORM schema facts for manual MariaDB migration design."""

import json
from pathlib import Path

from app.database.base import Base
from app.models import auth, billing, catalog, crm, hr, inventory, notifications, payables, procurement, reports  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "php-migration-schema-inventory.json"


def main() -> None:
    tables = []
    for table in sorted(Base.metadata.tables.values(), key=lambda table: table.name):
        columns = []
        for column in table.columns:
            columns.append({
                "name": column.name,
                "postgres_type": str(column.type),
                "nullable": column.nullable,
                "primary_key": column.primary_key,
                "unique": bool(column.unique),
                "foreign_keys": [str(key.target_fullname) for key in column.foreign_keys],
                "mysql_mapping_status": "MANUAL_REVIEW_REQUIRED",
            })
        tables.append({
            "name": table.name,
            "columns": columns,
            "indexes": [{"name": index.name, "columns": [col.name for col in index.columns],
                         "unique": index.unique, "dialect_options": str(index.dialect_options)}
                        for index in table.indexes],
            "constraints": [str(constraint) for constraint in table.constraints],
            "migration_status": "NOT_IMPLEMENTED",
        })
    payload = {"source": "SQLAlchemy metadata at local HEAD", "tables": tables,
               "table_count": len(tables),
               "column_count": sum(len(item["columns"]) for item in tables),
               "foreign_key_count": sum(len(col["foreign_keys"]) for item in tables for col in item["columns"]),
               "warning": "Inventory only; do not mechanically execute as MySQL DDL. Review types, constraints, indexes, defaults, FKs, collations and locking manually."}
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"tables={payload['table_count']} columns={payload['column_count']} foreign_keys={payload['foreign_key_count']}")


if __name__ == "__main__":
    main()
