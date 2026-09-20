# Roles and permissions

## Owner

Full business administration, including purchase payables, supplier settlement history, reminders, owner financial dashboard data, stores, employees, inward, outward, diversion, POS, inventory, and reports.

## Manager

Operational dashboard, products, barcodes, inward receiving, godown scanning, inventory, outward transfers, diversion, employees view, operational reports, notifications, POS, and invoices. Manager navigation and APIs exclude owner purchase payments, vendor settlement data, finance reports, and the owner dashboard. Purchase payable endpoints additionally require the OWNER role at the backend.

## Employee

Mobile-first Scan & Bill, assigned-shop inventory, invoices, customers, and profile/settings. The backend derives the allowed shop from `assigned_store_id`; cross-shop inventory, invoice, barcode lookup, and billing attempts are rejected. Employees cannot change their assignment.

| Feature | Owner | Manager | Employee |
|---|---:|---:|---:|
| Inward / barcode / godown | Yes | Yes | No |
| Inventory / transfer / diversion | Yes | Yes | Own-shop receive/view only |
| POS and invoices | Yes | Yes | Assigned shop |
| Operational reports | Yes | Yes | Limited |
| Purchase payments and reminders | Yes | No | No |
