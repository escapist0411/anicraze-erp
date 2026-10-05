# PostgreSQL → Hostinger MariaDB schema translation plan

The [source schema inventory](php-migration-schema-inventory.json) records **104 ORM tables, 1,567 columns and 347 foreign keys**. It is not executable DDL. Each table needs a reviewed, deterministic MariaDB migration and a parity test against the FastAPI model before any production import. No Hostinger or local MariaDB schema has been created yet.

| PostgreSQL feature | Required MariaDB decision/test |
| --- | --- |
| UUID primary/foreign keys | Choose `BINARY(16)` with a single canonical byte-order codec, or `CHAR(36)` for simpler interoperability. Make every referencing column identical. Test round trips and indexes. |
| `TIMESTAMPTZ` | Store UTC in `DATETIME(6)` and convert only at API/presentation boundaries. Test timezone and daylight-saving cases. |
| `NUMERIC` money | Preserve exact precision/scale in `DECIMAL`; use decimal string arithmetic in PHP or database expressions, never floats. |
| `JSON`/`JSONB` | Use MariaDB-compatible JSON storage with explicit validation and serialization tests; do not rely on PostgreSQL JSON operators. |
| PostgreSQL enums | Use stable `VARCHAR` values plus application/DB validation; do not accidentally change wire values. |
| Partial/expression indexes | Re-express with generated columns or application-enforced invariants plus unique indexes where necessary; verify query plans and case-insensitive uniqueness. |
| Sequences and `RETURNING` | Replace with a locked counter row or other transaction-safe allocator for invoice/SKU numbers; confirm no duplicate under concurrency. |
| `ON CONFLICT` | Use a reviewed MariaDB upsert only where mutating an existing row is approved; production master import must fail on unexpected differences. |
| Row/advisory locks | Translate `FOR UPDATE` within explicit InnoDB transactions; standardize lock ordering. Use unique idempotency keys as a second line of defense. |
| FK/delete behavior | Preserve `RESTRICT`, `CASCADE`, `SET NULL`, orphan rules and soft-delete semantics. Use InnoDB and `utf8mb4`. |

Hostinger documents its Web/Cloud database engine as **MariaDB**, though hPanel labels it “MySQL.” Exact engine/version, collation, account-specific limits and SQL mode must be verified in the purchased plan before declaring compatibility. [Hostinger DBMS guide](https://www.hostinger.com/support/1583226-which-database-management-system-is-used-at-hostinger/), [plan limits](https://www.hostinger.com/support/6976044-parameters-and-limits-of-hosting-plans-in-hostinger/).

Migration acceptance order: reviewed DDL for all 104 tables → empty local MariaDB migration → FK/index/constraint audit → approved master/account import → second-run idempotency → concurrency/negative-stock and document tests → dump/restore drill. The local MySQL 9.7 executable is **not** a substitute for the exact Hostinger MariaDB version.
