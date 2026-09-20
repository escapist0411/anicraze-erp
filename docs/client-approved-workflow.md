# Client-approved ANICRAZE workflow

ANICRAZE operates one client-facing warehouse: **ANICRAZE Central Warehouse**. All purchased stock follows Product Master → Receive Stock → Barcode Centre → Scan to Godown → Confirm Stock Entry. Creating a receipt does not change inventory; exact scan completion and final confirmation create the existing ledger-backed purchase movements.

Selling locations are configurable records, not hard-coded branches. Permanent shops and temporary events both support employee assignment, transfers, POS, invoices, inventory, and reporting. The provisional configured names are Chinchwad, Westend, Civil Metro, Swargate Metro, Kalyani Metro, Shivaji Metro, Event 1, and Event 2. Addresses intentionally remain blank until the client confirms them.

Outward stock uses the existing pick, pack, dispatch, receive, and discrepancy lifecycle. Divert Stock uses the same transfer service for warehouse-to-shop, shop-to-shop, and shop-to-warehouse paths; it never edits quantities directly.
