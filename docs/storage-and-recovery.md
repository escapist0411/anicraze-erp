# ANICRAZE file storage and recovery

This describes the local implementation prepared in Phase 3; it is **not** an external storage deployment or a completed restore drill.

## File inventory and classification

| File type | Classification | Location/behavior |
| --- | --- | --- |
| Final sales invoice PDFs | **Business record** | Private `documents/invoices`; invoice record stores its path. Preserve exact issued copy. |
| Weekly owner report PDFs | **Business record** | Private `documents/reports`; export-history download requires authenticated owner/report access and matching generator. |
| Payslip PDFs | **Business record** | Private `documents/payslips`; served only through payroll permission. |
| Product images | **Business asset** | `public/uploads/products`; uploaded originals must be backed up. Never place secrets or private documents there. |
| Barcode SVGs | **Regeneratable** | `public/uploads/barcodes`; stable product barcode in PostgreSQL is authoritative. Restoration may regenerate the SVG **without changing the value**. |
| Transfer PDFs, on-demand report PDF/CSV/XLS, legacy procurement PDFs | **Regeneratable/temporary** | Generated on request from database state; transport is authenticated where applicable. Historic exact copies must be retained separately if business policy requires them. Legacy procurement router is not mounted. |
| Inward PDF preview uploads | **Temporary** | Read in memory and parsed; no durable copy is made. |

## Configuration

- `STORAGE_BACKEND=local` is for development/test only. It keeps public assets under `backend/uploads` and private documents under `backend/generated`. Both are Git-ignored.
- Production **fails startup** in local mode. Set `STORAGE_BACKEND=volume` and absolute `STORAGE_ROOT` pointing to an actually mounted durable, backed-up filesystem. The app uses `<root>/public/uploads` and `<root>/private/documents`. The application cannot prove the host mounted a persistent volume; the operator must verify that separately before cutover.
- `/uploads` is constrained to catalog image extensions and barcode SVGs. Private documents are never under that static mount. Invoice PDF retrieval checks invoice store authorization **before** reading the file; report retrieval is owner/creator-scoped. Resolved private file paths must be inside the configured document kind. No arbitrary path from a database field is served.
- Do not put `.env`, credentials, private keys, customer documents or invoice PDFs in the public asset tree. Use least-privilege filesystem ownership and storage backups. No S3/Hostinger credentials are provided or assumed.

## Backup and restore procedure for a future authorized cutover

1. Freeze or account for writes, record application commit/image, migration revision, and storage configuration. Verify the exact database identity.
2. Take a PostgreSQL custom-format backup and checksum; independently back up **both** public product uploads and private document tree with permissions/metadata. Encrypt and store backups in an approved off-host location. The prior local demo dump is not a substitute for a fresh cutover backup.
3. Verify `pg_restore --list` and restore the DB into an isolated database; restore files to a separately mounted test root. Check count, checksums, ownership and representative invoices/payslips/report downloads under correct roles. A database-only restore leaves document paths broken.
4. Rehearse Alembic on the restored clone and verify `current_database()` and `alembic_version` before any production migration. Do not run demo reset, seed, or barcode repair scripts.
5. For rollback, restore a matching database **and** file snapshot or use a tested forward-compatible path. Never point an old image at a newer schema blindly. Preserve the existing Netlify/Render/Neon stack through an agreed rollback window.

Existing demo file paths may still point to old ephemeral locations. Moving those records to a new storage root requires an explicitly planned copy/reconciliation step; this phase did not copy live files or alter Neon paths.
