<p align="center"><img src="docs/assets/banner.png" alt="ANICRAZE ERP banner" width="100%"></p>

# ANICRAZE ERP

Production retail ERP for an anime-merchandise business: one central warehouse, eight selling locations, and a barcode-led path from purchase to sale.

**Production deployment: live on Hostinger** · [Live Production ERP](https://erp.anicraze.com) · [Production API](https://api.anicraze.com/api/v1) · [API health](https://api.anicraze.com/api/v1/health)

## Overview

ANICRAZE ERP connects product management, warehouse intake, shop inventory, point-of-sale billing, supplier payables, and owner reporting. The active production application uses a React frontend and a PHP/MariaDB API hosted on Hostinger. The older FastAPI/PostgreSQL code remains in this repository as a reference; it is not the production backend.

## Business workflow

```text
Product → Inward Stock → Barcode / Label → Scan to Godown
        → Central Warehouse Inventory → Direct Transfer to Shop
        → Shop Inventory → POS → Billing / Invoice
        → Stock Update → Analytics / Finance
```

Receiving a purchase creates a pending receipt; it does **not** immediately increase warehouse stock. Barcode verification and confirmation complete the godown intake. A direct, multi-product warehouse-to-shop transfer updates the relevant location inventories. The POS bills against the employee's assigned shop and records the resulting stock movement.

Supplier settlement is a separate flow:

```text
Supplier → Inward Purchase → Payable → Partial / Final Payment
         → Outstanding Balance
```

Supplier selection is optional for ordinary stock receiving; a supplier is required when a payable is created. Owner-only payment records and balances are kept separate from shop billing.

## Current modules

| Area | Production scope |
|---|---|
| Product Master & Barcode Centre | Product catalogue, categories, prices, import, unique Code 128 identifiers, and 50 × 25 mm labels |
| Inward Stock & Godown | Multi-product receipts, barcode scanning, confirmation into the single central warehouse, and stock ledger |
| Inventory & Transfers | Location-scoped inventory, corrections, direct warehouse-to-shop transfers, and staff/owner transfer PDFs |
| Shop POS & Sales | Shop-scoped barcode lookup, billing, payment methods, sales records, and invoice PDFs |
| Suppliers & Payments | Supplier records, purchase payables, partial/final settlements, balances, and reminders |
| Reports & Finance | Operational reports, exports, sales analytics, owner finance summaries, and shop-wise gross-profit views |
| Stores & Employees | Eight selling locations, assigned-shop employee accounts, and role-based access |
| Notifications | In-app operational stock notifications |

The active ERP does not calculate GST. Official WhatsApp invoice delivery is **not active** in production. A warehouse desktop application and multi-warehouse mode are future work, not current capabilities.

## Architecture and technology

```text
Owner / Manager / Employee browser
                │
                ▼
React 19 + TypeScript + Vite frontend  (erp.anicraze.com)
                │  HTTPS /api/v1
                ▼
PHP 8.3 API                              (api.anicraze.com)
                │
                ▼
MariaDB — one central warehouse and eight selling locations
```

The frontend uses Tailwind CSS v4, shadcn/ui, React Router, TanStack Query, Axios, Framer Motion, Recharts, and ZXing barcode scanning. The backend uses PHP 8.3, PDO/MariaDB, JWT-based sessions, and server-generated PDFs. Frontend and API are deployed on Hostinger; migrations `001`–`012` are applied to the production MariaDB database.

The repository also contains `backend/` (the earlier FastAPI/PostgreSQL reference), but the Hostinger runtime does not depend on FastAPI, Render, Neon, or Netlify.

## Access and security

| Role | Principal access |
|---|---|
| Owner | Company-wide operations, stores, suppliers, purchase payments, finance, and reports |
| Manager | Operational catalogue, inward stock, inventory, transfers, POS, and operational reports; no owner settlement or finance access |
| Employee / Sales | Assigned-shop POS, products, invoices, and relevant notifications |

The API enforces role permissions and assigned-shop scoping server-side, including document access; hiding a button in the UI is not treated as authorization. Authentication includes access/refresh sessions, refresh rotation, and account lockout. Operational records and stock movements are maintained in MariaDB. Do not place environment files, credentials, private documents, or database backups in a public web root or commit them to Git.

## Repository layout

```text
frontend/        React ERP and production static build
hostinger-api/   Active PHP API, MariaDB migrations, tests, and private document services
public-website/  Public-site static build source
backend/         Earlier FastAPI/PostgreSQL reference implementation
docs/            Architecture, workflow, migration, and operational documentation
database/        Reference data and schema material
```

## Local development

The production API and database are **not** a development sandbox. Use an isolated local MariaDB database and private, Git-ignored configuration. Review the safeguards in `hostinger-api/database/migrate.php` and the provisioning scripts before running them; never point local tests or seeds at production.

For the frontend:

```bash
cd frontend
npm ci
cp .env.example .env
# Set VITE_API_URL to your local PHP API, including /api/v1.
npm run dev
```

The PHP API requires PHP 8.3+, Composer dependencies, and the extensions declared in [`hostinger-api/composer.json`](hostinger-api/composer.json). Its HTTP entry point is `hostinger-api/public/index.php`; keep `src/`, `vendor/`, private configuration, and storage outside the served directory. The frontend can be checked with `npm run build` and `npm run check:hostinger-parity`. Do not put secrets in `VITE_` variables: they are bundled into public JavaScript.

## Documentation

- [Role and access overview](docs/roles-and-permissions.md)
- [Stock receiving and godown workflow](docs/simple-stock-flow.md)
- [Active frontend/API route inventory](docs/hostinger-active-api-surface.md)
- [PHP migration business rules](docs/php-migration-business-rules.md)

Some older phase/demo documents describe the retained FastAPI reference and should not be read as the current production deployment instructions.

<!--
## Screenshots

Screenshots will be added only after approved, real application captures are available in docs/screenshots/.
-->

## Roadmap

- [x] Product Master and barcode labels
- [x] Single central warehouse, inward receiving, and Scan to Godown
- [x] Direct multi-product warehouse-to-shop transfers and transfer PDFs
- [x] Shop-scoped POS, sales, and invoice PDFs
- [x] Supplier payables and partial/final payment tracking
- [x] Owner/Manager/Employee role boundaries and shop isolation
- [x] Operational notifications and current reports/finance views
- [x] Hostinger production deployment (React, PHP API, MariaDB; migrations `001`–`012`)
- [ ] Official WhatsApp invoice delivery activation
- [ ] Warehouse desktop application
- [ ] Multi-warehouse mode

## License

**All rights reserved.** This is proprietary client software. Unauthorized copying, redistribution, or commercial use is prohibited. No open-source license is granted.
