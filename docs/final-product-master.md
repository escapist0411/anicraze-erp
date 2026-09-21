# Final ANICRAZE Product Master

The authoritative product source is `backend/data/anicraze_final_product_master.csv`. It contains the 160 products approved in the client's WhatsApp catalogue. Prices are stored exactly as supplied, in INR, without added tax, markup, discount, or rounding.

## Structure

- Products: 160
- Categories: Action Figures, Figure Sets, Qposket Figures, Keychains, Card & Party Games, Novelty / Collectibles, Anime Weapons / Props
- Series: Naruto, Demon Slayer, One Piece, Dragon Ball Z, Jujutsu Kaisen, Marvel / DC / Movies, Character Sets, Princess / Superhero, Generic Types, Games, Novelty Items, Naruto / General
- Neutral priced variants: 11 product rows across Luffy Sitting, Goku Standing, Gojo Standing, Deadpool, and Pokemon Set of 6

Every CSV row is one sellable product. Identity is the normalized combination of series, base product name, and variant. Where the client supplied different prices for the same visible name, the importer stores `Variant 1`, `Variant 2`, or `Variant 3` in `edition` and appends it to the displayed name so POS operators cannot confuse the items.

Keychains are limited to Rubber Keychain (₹100), Metal Keychain (₹100), and Keyboard Keychain (₹200) under Generic Types. The 11 Princess / Superhero Qposket products are all ₹400.

## Data and history safety

The replacement never truncates or deletes business tables. All 19 earlier product records were changed to `ARCHIVED` and soft-deleted; 15 of them have ledger, invoice, or transfer history and remain addressable through their foreign keys. Their obsolete variants and images are also soft-deleted. Old sample category/series records remain stored for historical relationships but are inactive and hidden from active master lists.

New catalog rows do not create inventory records, barcodes, images, brands, suppliers, or statutory classifications. Required numeric fields use the existing unconfigured defaults (`purchase_price=0` and `reorder_level=0`); these values mean “not configured,” not a commercial assertion. Inventory remains zero until receiving or another real stock workflow creates it. SKUs are allocated exclusively through the existing PostgreSQL `product_sku_sequence` workflow.

## Import

From `backend`:

```bash
PYTHONPATH=. .venv/bin/python -m app.scripts.import_final_catalog --dry-run
PYTHONPATH=. .venv/bin/python -m app.scripts.import_final_catalog
```

The importer takes a PostgreSQL transaction lock and upserts by a deterministic SHA-256 import reference derived from series + product + variant. Re-running it updates 160 rows and creates zero rows. The former `app.scripts.seed_catalog` command is retained only as a compatibility wrapper for this importer; it no longer contains a competing demo list.

## PostgreSQL validation — 5 September 2026

- Active products: 160
- Active categories: 7
- Active series: 12
- Category counts: Action Figures 122; Figure Sets 6; Qposket Figures 11; Keychains 3; Card & Party Games 12; Novelty / Collectibles 3; Anime Weapons / Props 3
- Series counts: Naruto 20; Demon Slayer 34; One Piece 19; Dragon Ball Z 20; Jujutsu Kaisen 14; Marvel / DC / Movies 15; Character Sets 6; Princess / Superhero 11; Generic Types 3; Games 12; Novelty Items 3; Naruto / General 3
- Missing/non-positive prices: 0
- Duplicate identity groups: 0
- Neutral variant rows: 11
- Generated barcodes: 0
- Final products with inventory rows: 0
- Old demo products still active: 0
- Archived/soft-deleted products: 19
- Archived products with confirmed ledger/invoice/transfer history: 15
- Second importer run: 0 created, 160 updated, active count remained 160

The live owner API returned 160 products, 7 categories, and 12 series. Search returned all three Luffy Sitting prices (₹400, ₹600, ₹800), product detail exposed the edition, and employee credentials successfully searched Naruto Rasengan at ₹800. Billing availability intentionally depends on real received stock; none was fabricated for this validation.
