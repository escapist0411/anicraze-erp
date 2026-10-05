# PHP migration API contract — reference inventory

Generated from **232 registered FastAPI method/path routes**. The machine-readable inventory is [php-migration-api-contract.json](php-migration-api-contract.json).

This is an inventory, **not PHP parity**. OpenAPI supplies declared request/response schemas, parameters, validation constraints, and status codes; registered dependency closures supply permission candidates. Service-level database operations, locking, exact transaction boundaries, error cases, and shop scoping remain `REVIEW_REQUIRED` per operation until manually traced and tested. Do not infer safety from a SALES allowlisted path alone.

The PHP API must retain `/api/v1`, the `{message,error:{code,request_id}}` error envelope, current success envelopes, bearer/refresh semantics, authorization and assigned-store checks. See [sales endpoint permission matrix](../output/sales-endpoint-permission-matrix.md) and Phase 3 tests for known security boundaries.

| Method | Path | Auth dependency values | SALES policy | Source | PHP status |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/anime` | all_permissions:anime.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:156` | NOT_IMPLEMENTED |
| POST | `/api/v1/anime` | all_permissions:anime.create | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:158` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/anime/{entity_id}` | all_permissions:anime.delete | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:164` | NOT_IMPLEMENTED |
| GET | `/api/v1/anime/{entity_id}` | all_permissions:anime.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:160` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/anime/{entity_id}` | all_permissions:anime.update | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:162` | NOT_IMPLEMENTED |
| GET | `/api/v1/attendance` | all_permissions:attendance.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:56` | NOT_IMPLEMENTED |
| POST | `/api/v1/attendance/check-in` | all_permissions:attendance.check_in | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:58` | NOT_IMPLEMENTED |
| POST | `/api/v1/attendance/check-out` | all_permissions:attendance.check_out | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:60` | NOT_IMPLEMENTED |
| POST | `/api/v1/attendance/manual` | all_permissions:attendance.manage | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:62` | NOT_IMPLEMENTED |
| GET | `/api/v1/attendance/summary` | all_permissions:attendance.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:54` | NOT_IMPLEMENTED |
| GET | `/api/v1/attendance/today` | all_permissions:attendance.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:52` | NOT_IMPLEMENTED |
| POST | `/api/v1/auth/change-password` | public/other — review | public_or_self_service | `backend/app/api/v1/auth.py:105` | NOT_IMPLEMENTED |
| POST | `/api/v1/auth/forgot-password` | public/other — review | public_or_self_service | `backend/app/api/v1/auth.py:80` | NOT_IMPLEMENTED |
| POST | `/api/v1/auth/login` | public/other — review | public_or_self_service | `backend/app/api/v1/auth.py:37` | NOT_IMPLEMENTED |
| POST | `/api/v1/auth/logout` | public/other — review | public_or_self_service | `backend/app/api/v1/auth.py:63` | NOT_IMPLEMENTED |
| POST | `/api/v1/auth/logout-all` | public/other — review | public_or_self_service | `backend/app/api/v1/auth.py:74` | NOT_IMPLEMENTED |
| GET | `/api/v1/auth/me` | public/other — review | public_or_self_service | `backend/app/api/v1/auth.py:122` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/auth/me` | public/other — review | public_or_self_service | `backend/app/api/v1/auth.py:127` | NOT_IMPLEMENTED |
| POST | `/api/v1/auth/refresh` | public/other — review | public_or_self_service | `backend/app/api/v1/auth.py:53` | NOT_IMPLEMENTED |
| POST | `/api/v1/auth/reset-password` | public/other — review | public_or_self_service | `backend/app/api/v1/auth.py:99` | NOT_IMPLEMENTED |
| GET | `/api/v1/auth/sessions` | public/other — review | public_or_self_service | `backend/app/api/v1/auth.py:137` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/auth/sessions/{session_id}` | public/other — review | public_or_self_service | `backend/app/api/v1/auth.py:143` | NOT_IMPLEMENTED |
| POST | `/api/v1/billing` | all_permissions:billing.create | allowed_route_only | `backend/app/api/v1/billing.py:47` | NOT_IMPLEMENTED |
| GET | `/api/v1/billing/analytics` | all_permissions:billing.read | allowed_route_only | `backend/app/api/v1/billing.py:82` | NOT_IMPLEMENTED |
| GET | `/api/v1/billing/barcode/{barcode}` | all_permissions:billing.read | allowed_route_only | `backend/app/api/v1/billing.py:31` | NOT_IMPLEMENTED |
| GET | `/api/v1/billing/products` | all_permissions:billing.read | allowed_route_only | `backend/app/api/v1/billing.py:38` | NOT_IMPLEMENTED |
| GET | `/api/v1/billing/reports/payments` | all_permissions:payments.read | denied_by_sales_allowlist | `backend/app/api/v1/billing.py:86` | NOT_IMPLEMENTED |
| GET | `/api/v1/billing/reports/returns` | all_permissions:billing.read | allowed_route_only | `backend/app/api/v1/billing.py:90` | NOT_IMPLEMENTED |
| GET | `/api/v1/billing/reports/sales` | all_permissions:billing.read | allowed_route_only | `backend/app/api/v1/billing.py:84` | NOT_IMPLEMENTED |
| GET | `/api/v1/billing/search` | all_permissions:billing.read | allowed_route_only | `backend/app/api/v1/billing.py:26` | NOT_IMPLEMENTED |
| GET | `/api/v1/brands` | all_permissions:brands.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:144` | NOT_IMPLEMENTED |
| POST | `/api/v1/brands` | all_permissions:brands.create | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:146` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/brands/{entity_id}` | all_permissions:brands.delete | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:152` | NOT_IMPLEMENTED |
| GET | `/api/v1/brands/{entity_id}` | all_permissions:brands.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:148` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/brands/{entity_id}` | all_permissions:brands.update | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:150` | NOT_IMPLEMENTED |
| GET | `/api/v1/cash-register` | all_permissions:billing.read | allowed_route_only | `backend/app/api/v1/billing.py:92` | NOT_IMPLEMENTED |
| GET | `/api/v1/categories` | all_permissions:categories.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:131` | NOT_IMPLEMENTED |
| POST | `/api/v1/categories` | all_permissions:categories.create | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:133` | NOT_IMPLEMENTED |
| GET | `/api/v1/categories/tree` | all_permissions:categories.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:114` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/categories/{entity_id}` | all_permissions:categories.delete | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:140` | NOT_IMPLEMENTED |
| GET | `/api/v1/categories/{entity_id}` | all_permissions:categories.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:136` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/categories/{entity_id}` | all_permissions:categories.update | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:138` | NOT_IMPLEMENTED |
| GET | `/api/v1/characters` | all_permissions:characters.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:168` | NOT_IMPLEMENTED |
| POST | `/api/v1/characters` | all_permissions:characters.create | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:170` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/characters/{entity_id}` | all_permissions:characters.delete | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:176` | NOT_IMPLEMENTED |
| GET | `/api/v1/characters/{entity_id}` | all_permissions:characters.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:172` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/characters/{entity_id}` | all_permissions:characters.update | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:174` | NOT_IMPLEMENTED |
| POST | `/api/v1/communications/whatsapp/send` | all_permissions:customer_communications.create | denied_by_sales_allowlist | `backend/app/api/v1/crm.py:133` | NOT_IMPLEMENTED |
| GET | `/api/v1/communications/whatsapp/settings` | all_permissions:customer_communications.read | denied_by_sales_allowlist | `backend/app/api/v1/crm.py:130` | NOT_IMPLEMENTED |
| GET | `/api/v1/communications/whatsapp/webhook` | public/other — review | denied_by_sales_allowlist | `backend/app/api/v1/crm.py:147` | NOT_IMPLEMENTED |
| POST | `/api/v1/communications/whatsapp/webhook` | public/other — review | denied_by_sales_allowlist | `backend/app/api/v1/crm.py:152` | NOT_IMPLEMENTED |
| POST | `/api/v1/communications/{id}/retry` | all_permissions:customer_communications.create | denied_by_sales_allowlist | `backend/app/api/v1/crm.py:136` | NOT_IMPLEMENTED |
| GET | `/api/v1/customer-refunds` | all_permissions:customer_refunds.read | denied_by_sales_allowlist | `backend/app/api/v1/crm.py:167` | NOT_IMPLEMENTED |
| GET | `/api/v1/customer-refunds/{id}/receipt` | all_permissions:customer_refunds.receipt | denied_by_sales_allowlist | `backend/app/api/v1/crm.py:169` | NOT_IMPLEMENTED |
| GET | `/api/v1/dashboard/owner` | any_permission:dashboard.owner,dashboard.read | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:44` | NOT_IMPLEMENTED |
| GET | `/api/v1/dashboard/{section}` | any_permission:dashboard.owner,dashboard.read | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:48` | NOT_IMPLEMENTED |
| GET | `/api/v1/departments` | all_permissions:departments.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:44` | NOT_IMPLEMENTED |
| POST | `/api/v1/departments` | all_permissions:departments.create | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:46` | NOT_IMPLEMENTED |
| GET | `/api/v1/designations` | all_permissions:designations.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:48` | NOT_IMPLEMENTED |
| POST | `/api/v1/designations` | all_permissions:designations.create | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:50` | NOT_IMPLEMENTED |
| GET | `/api/v1/employees` | all_permissions:employees.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:15` | NOT_IMPLEMENTED |
| POST | `/api/v1/employees` | all_permissions:employees.create | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:17` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/employees/{id}` | all_permissions:employees.delete | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:23` | NOT_IMPLEMENTED |
| GET | `/api/v1/employees/{id}` | all_permissions:employees.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:19` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/employees/{id}` | all_permissions:employees.update | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:21` | NOT_IMPLEMENTED |
| POST | `/api/v1/employees/{id}/assign-store` | all_permissions:employees.assign_store | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:29` | NOT_IMPLEMENTED |
| GET | `/api/v1/employees/{id}/attendance` | all_permissions:attendance.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:33` | NOT_IMPLEMENTED |
| GET | `/api/v1/employees/{id}/history` | all_permissions:employees.view_history | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:41` | NOT_IMPLEMENTED |
| GET | `/api/v1/employees/{id}/leave` | all_permissions:leave.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:35` | NOT_IMPLEMENTED |
| POST | `/api/v1/employees/{id}/link-user` | all_permissions:employees.link_user | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:27` | NOT_IMPLEMENTED |
| GET | `/api/v1/employees/{id}/payroll` | all_permissions:payroll.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:37` | NOT_IMPLEMENTED |
| GET | `/api/v1/employees/{id}/performance` | all_permissions:performance.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:39` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/employees/{id}/status` | all_permissions:employees.update_status | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:25` | NOT_IMPLEMENTED |
| GET | `/api/v1/expenses` | all_permissions:expenses.read | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:117` | NOT_IMPLEMENTED |
| POST | `/api/v1/expenses` | all_permissions:expenses.create | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:121` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/expenses/{id}` | all_permissions:expenses.delete | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:136` | NOT_IMPLEMENTED |
| GET | `/api/v1/expenses/{id}` | all_permissions:expenses.read | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:131` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/expenses/{id}` | all_permissions:expenses.update | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:124` | NOT_IMPLEMENTED |
| POST | `/api/v1/expenses/{id}/approve` | all_permissions:expenses.approve | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:142` | NOT_IMPLEMENTED |
| GET | `/api/v1/health` | public/other — review | public_or_self_service | `backend/app/api/v1/health.py:11` | NOT_IMPLEMENTED |
| GET | `/api/v1/holidays` | all_permissions:holidays.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:72` | NOT_IMPLEMENTED |
| GET | `/api/v1/hr/analytics/{report}` | all_permissions:hr.analytics | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:121` | NOT_IMPLEMENTED |
| GET | `/api/v1/hr/dashboard` | all_permissions:hr.analytics | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:119` | NOT_IMPLEMENTED |
| GET | `/api/v1/inventory` | all_permissions:inventory.read | allowed_route_only | `backend/app/api/v1/inventory.py:111` | NOT_IMPLEMENTED |
| POST | `/api/v1/inventory` | all_permissions:inventory.create | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:116` | NOT_IMPLEMENTED |
| GET | `/api/v1/inventory-alerts` | all_permissions:inventory.read | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:180` | NOT_IMPLEMENTED |
| GET | `/api/v1/inventory/analytics/summary` | all_permissions:inventory.analytics | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:100` | NOT_IMPLEMENTED |
| GET | `/api/v1/inventory/export` | all_permissions:reports.inventory.export | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:105` | NOT_IMPLEMENTED |
| GET | `/api/v1/inventory/ledger` | all_permissions:inventory.read | allowed_route_only | `backend/app/api/v1/inventory.py:95` | NOT_IMPLEMENTED |
| GET | `/api/v1/inventory/reports/stock` | all_permissions:inventory.analytics | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:102` | NOT_IMPLEMENTED |
| GET | `/api/v1/inventory/transactions` | all_permissions:inventory.read | allowed_route_only | `backend/app/api/v1/inventory.py:90` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/inventory/{id}` | all_permissions:inventory.delete | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:122` | NOT_IMPLEMENTED |
| GET | `/api/v1/inventory/{id}` | all_permissions:inventory.read | allowed_route_only | `backend/app/api/v1/inventory.py:118` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/inventory/{id}` | all_permissions:inventory.update | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:120` | NOT_IMPLEMENTED |
| POST | `/api/v1/inventory/{id}/damage` | all_permissions:inventory.adjust | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:129` | NOT_IMPLEMENTED |
| POST | `/api/v1/inventory/{id}/return` | all_permissions:inventory.update | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:131` | NOT_IMPLEMENTED |
| POST | `/api/v1/inventory/{id}/stock-in` | all_permissions:inventory.create | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:125` | NOT_IMPLEMENTED |
| POST | `/api/v1/inventory/{id}/stock-out` | all_permissions:inventory.adjust | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:127` | NOT_IMPLEMENTED |
| GET | `/api/v1/invoices` | all_permissions:billing.read | allowed_route_only | `backend/app/api/v1/billing.py:51` | NOT_IMPLEMENTED |
| GET | `/api/v1/invoices/{id}` | all_permissions:billing.read | allowed_route_only | `backend/app/api/v1/billing.py:53` | NOT_IMPLEMENTED |
| POST | `/api/v1/invoices/{id}/cancel` | all_permissions:billing.cancel | allowed_route_only | `backend/app/api/v1/billing.py:59` | NOT_IMPLEMENTED |
| GET | `/api/v1/invoices/{id}/communications` | all_permissions:customer_communications.read | denied_by_sales_allowlist | `backend/app/api/v1/crm.py:128` | NOT_IMPLEMENTED |
| GET | `/api/v1/invoices/{id}/history` | all_permissions:billing.read | allowed_route_only | `backend/app/api/v1/billing.py:98` | NOT_IMPLEMENTED |
| GET | `/api/v1/invoices/{id}/pdf` | all_permissions:billing.pdf | allowed_route_only | `backend/app/api/v1/billing.py:61` | NOT_IMPLEMENTED |
| GET | `/api/v1/leave/balances` | all_permissions:leave.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:78` | NOT_IMPLEMENTED |
| GET | `/api/v1/leave/requests` | all_permissions:leave.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:80` | NOT_IMPLEMENTED |
| POST | `/api/v1/leave/requests` | all_permissions:leave.create | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:82` | NOT_IMPLEMENTED |
| POST | `/api/v1/leave/requests/{id}/approve` | all_permissions:leave.approve | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:87` | NOT_IMPLEMENTED |
| POST | `/api/v1/leave/requests/{id}/reject` | all_permissions:leave.reject | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:89` | NOT_IMPLEMENTED |
| POST | `/api/v1/leave/requests/{id}/submit` | all_permissions:leave.submit | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:85` | NOT_IMPLEMENTED |
| GET | `/api/v1/leave/types` | all_permissions:leave.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:74` | NOT_IMPLEMENTED |
| POST | `/api/v1/leave/types` | all_permissions:leave.manage_types | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:76` | NOT_IMPLEMENTED |
| GET | `/api/v1/notifications` | any_permission:dashboard.owner,dashboard.read | denied_by_sales_allowlist | `backend/app/api/v1/notifications.py:16` | NOT_IMPLEMENTED |
| POST | `/api/v1/notifications/mark-all-read` | any_permission:dashboard.owner,dashboard.read | denied_by_sales_allowlist | `backend/app/api/v1/notifications.py:24` | NOT_IMPLEMENTED |
| GET | `/api/v1/notifications/summary` | any_permission:dashboard.owner,dashboard.read | denied_by_sales_allowlist | `backend/app/api/v1/notifications.py:19` | NOT_IMPLEMENTED |
| POST | `/api/v1/notifications/{id}/read` | any_permission:dashboard.owner,dashboard.read | denied_by_sales_allowlist | `backend/app/api/v1/notifications.py:22` | NOT_IMPLEMENTED |
| GET | `/api/v1/payments` | all_permissions:payments.read | denied_by_sales_allowlist | `backend/app/api/v1/billing.py:70` | NOT_IMPLEMENTED |
| GET | `/api/v1/payroll/payslips` | all_permissions:payroll.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:105` | NOT_IMPLEMENTED |
| GET | `/api/v1/payroll/payslips/{id}/pdf` | all_permissions:payroll.payslip | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:107` | NOT_IMPLEMENTED |
| GET | `/api/v1/payroll/periods` | all_permissions:payroll.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:91` | NOT_IMPLEMENTED |
| POST | `/api/v1/payroll/periods` | all_permissions:payroll.create_run | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:93` | NOT_IMPLEMENTED |
| GET | `/api/v1/payroll/runs` | all_permissions:payroll.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:95` | NOT_IMPLEMENTED |
| POST | `/api/v1/payroll/runs` | all_permissions:payroll.create_run | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:97` | NOT_IMPLEMENTED |
| POST | `/api/v1/payroll/runs/{id}/approve` | all_permissions:payroll.approve | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:101` | NOT_IMPLEMENTED |
| POST | `/api/v1/payroll/runs/{id}/calculate` | all_permissions:payroll.calculate | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:99` | NOT_IMPLEMENTED |
| POST | `/api/v1/payroll/runs/{id}/finalize` | all_permissions:payroll.finalize | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:103` | NOT_IMPLEMENTED |
| GET | `/api/v1/performance/reviews` | all_permissions:performance.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:115` | NOT_IMPLEMENTED |
| POST | `/api/v1/performance/reviews` | all_permissions:performance.create | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:117` | NOT_IMPLEMENTED |
| GET | `/api/v1/permissions` | all_permissions:permissions.read | denied_by_sales_allowlist | `backend/app/api/v1/management.py:124` | NOT_IMPLEMENTED |
| POST | `/api/v1/permissions` | all_permissions:permissions.create | denied_by_sales_allowlist | `backend/app/api/v1/management.py:126` | NOT_IMPLEMENTED |
| GET | `/api/v1/permissions/grouped` | all_permissions:permissions.read | denied_by_sales_allowlist | `backend/app/api/v1/management.py:121` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/permissions/{permission_id}` | all_permissions:permissions.delete | denied_by_sales_allowlist | `backend/app/api/v1/management.py:132` | NOT_IMPLEMENTED |
| GET | `/api/v1/permissions/{permission_id}` | all_permissions:permissions.read | denied_by_sales_allowlist | `backend/app/api/v1/management.py:128` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/permissions/{permission_id}` | all_permissions:permissions.update | denied_by_sales_allowlist | `backend/app/api/v1/management.py:130` | NOT_IMPLEMENTED |
| GET | `/api/v1/products` | all_permissions:products.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:56` | NOT_IMPLEMENTED |
| POST | `/api/v1/products` | all_permissions:products.create | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:62` | NOT_IMPLEMENTED |
| GET | `/api/v1/products/export` | all_permissions:products.export | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:47` | NOT_IMPLEMENTED |
| POST | `/api/v1/products/import` | all_permissions:products.import | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:42` | NOT_IMPLEMENTED |
| GET | `/api/v1/products/search/barcode/{barcode}` | all_permissions:products.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:28` | NOT_IMPLEMENTED |
| GET | `/api/v1/products/search/sku/{sku}` | all_permissions:products.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:35` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/products/{product_id}` | all_permissions:products.delete | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:77` | NOT_IMPLEMENTED |
| GET | `/api/v1/products/{product_id}` | all_permissions:products.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:67` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/products/{product_id}` | all_permissions:products.update | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:72` | NOT_IMPLEMENTED |
| GET | `/api/v1/products/{product_id}/barcode` | all_permissions:products.read | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:99` | NOT_IMPLEMENTED |
| POST | `/api/v1/products/{product_id}/barcode` | all_permissions:products.manage_barcode | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:94` | NOT_IMPLEMENTED |
| GET | `/api/v1/products/{product_id}/history` | all_permissions:products.read_history | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:108` | NOT_IMPLEMENTED |
| POST | `/api/v1/products/{product_id}/images` | all_permissions:products.manage_images | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:86` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/products/{product_id}/images/{image_id}` | all_permissions:products.manage_images | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:90` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/products/{product_id}/status` | all_permissions:products.update_status | denied_by_sales_allowlist | `backend/app/api/v1/catalog.py:81` | NOT_IMPLEMENTED |
| GET | `/api/v1/purchase-payables` | require_owner:review | denied_by_sales_allowlist | `backend/app/api/v1/payables.py:13` | NOT_IMPLEMENTED |
| POST | `/api/v1/purchase-payables` | require_owner:review | denied_by_sales_allowlist | `backend/app/api/v1/payables.py:15` | NOT_IMPLEMENTED |
| POST | `/api/v1/purchase-payables/reconcile-reminders` | require_owner:review | denied_by_sales_allowlist | `backend/app/api/v1/payables.py:19` | NOT_IMPLEMENTED |
| GET | `/api/v1/purchase-payables/summary` | require_owner:review | denied_by_sales_allowlist | `backend/app/api/v1/payables.py:17` | NOT_IMPLEMENTED |
| GET | `/api/v1/purchase-payables/{payable_id}` | require_owner:review | denied_by_sales_allowlist | `backend/app/api/v1/payables.py:21` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/purchase-payables/{payable_id}` | require_owner:review | denied_by_sales_allowlist | `backend/app/api/v1/payables.py:23` | NOT_IMPLEMENTED |
| POST | `/api/v1/purchase-payables/{payable_id}/payments` | require_owner:review | denied_by_sales_allowlist | `backend/app/api/v1/payables.py:25` | NOT_IMPLEMENTED |
| POST | `/api/v1/purchase-payables/{payable_id}/reminders` | require_owner:review | denied_by_sales_allowlist | `backend/app/api/v1/payables.py:27` | NOT_IMPLEMENTED |
| POST | `/api/v1/purchase-payables/{payable_id}/reminders/{reminder_id}/dismiss` | require_owner:review | denied_by_sales_allowlist | `backend/app/api/v1/payables.py:29` | NOT_IMPLEMENTED |
| GET | `/api/v1/refunds` | all_permissions:payments.read | denied_by_sales_allowlist | `backend/app/api/v1/billing.py:78` | NOT_IMPLEMENTED |
| GET | `/api/v1/report-schedules` | all_permissions:reports.schedules.read | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:150` | NOT_IMPLEMENTED |
| POST | `/api/v1/report-schedules` | all_permissions:reports.schedules.create | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:152` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/report-schedules/{id}` | all_permissions:reports.schedules.delete | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:194` | NOT_IMPLEMENTED |
| GET | `/api/v1/report-schedules/{id}` | all_permissions:reports.schedules.read | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:183` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/report-schedules/{id}` | all_permissions:reports.schedules.update | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:188` | NOT_IMPLEMENTED |
| POST | `/api/v1/report-schedules/{id}/run-now` | all_permissions:reports.schedules.run | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:154` | NOT_IMPLEMENTED |
| GET | `/api/v1/reports/export` | any_permission:reports.finance.export,reports.inventory.export,reports.sales.export | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:92` | NOT_IMPLEMENTED |
| POST | `/api/v1/reports/export` | any_permission:reports.finance.export,reports.inventory.export,reports.sales.export | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:90` | NOT_IMPLEMENTED |
| GET | `/api/v1/reports/export-history` | any_permission:reports.finance.export,reports.inventory.export,reports.sales.export | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:58` | NOT_IMPLEMENTED |
| GET | `/api/v1/reports/history/{id}/download` | any_permission:reports.finance.read,reports.schedules.read | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:176` | NOT_IMPLEMENTED |
| GET | `/api/v1/reports/targets` | all_permissions:reports.targets.read | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:95` | NOT_IMPLEMENTED |
| POST | `/api/v1/reports/targets` | all_permissions:reports.targets.manage | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:99` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/reports/targets/{id}` | all_permissions:reports.targets.manage | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:107` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/reports/targets/{id}` | all_permissions:reports.targets.manage | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:101` | NOT_IMPLEMENTED |
| GET | `/api/v1/reports/weekly-business-summary` | any_permission:dashboard.owner,dashboard.read,reports.finance.read,reports.inventory.read,reports.sales.read | denied_by_sales_allowlist | `backend/app/api/v1/reports.py:54` | NOT_IMPLEMENTED |
| GET | `/api/v1/reports/{domain}/{report}` | any_permission:dashboard.owner,dashboard.read,reports.finance.read,reports.inventory.read,reports.sales.read | allowed_route_only | `backend/app/api/v1/reports.py:113` | NOT_IMPLEMENTED |
| GET | `/api/v1/returns` | all_permissions:billing.read | allowed_route_only | `backend/app/api/v1/billing.py:74` | NOT_IMPLEMENTED |
| POST | `/api/v1/returns` | all_permissions:billing.return | allowed_route_only | `backend/app/api/v1/billing.py:76` | NOT_IMPLEMENTED |
| GET | `/api/v1/roles` | all_permissions:roles.read | denied_by_sales_allowlist | `backend/app/api/v1/management.py:99` | NOT_IMPLEMENTED |
| POST | `/api/v1/roles` | all_permissions:roles.create | denied_by_sales_allowlist | `backend/app/api/v1/management.py:101` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/roles/{role_id}` | all_permissions:roles.delete | denied_by_sales_allowlist | `backend/app/api/v1/management.py:110` | NOT_IMPLEMENTED |
| GET | `/api/v1/roles/{role_id}` | all_permissions:roles.read | denied_by_sales_allowlist | `backend/app/api/v1/management.py:103` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/roles/{role_id}` | all_permissions:roles.update | denied_by_sales_allowlist | `backend/app/api/v1/management.py:108` | NOT_IMPLEMENTED |
| POST | `/api/v1/roles/{role_id}/permissions` | all_permissions:roles.assign_permissions | denied_by_sales_allowlist | `backend/app/api/v1/management.py:112` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/roles/{role_id}/permissions/{permission_id}` | all_permissions:roles.assign_permissions | denied_by_sales_allowlist | `backend/app/api/v1/management.py:114` | NOT_IMPLEMENTED |
| GET | `/api/v1/roles/{role_id}/users` | all_permissions:roles.read | denied_by_sales_allowlist | `backend/app/api/v1/management.py:116` | NOT_IMPLEMENTED |
| GET | `/api/v1/sales-returns` | all_permissions:sales_returns.read | denied_by_sales_allowlist | `backend/app/api/v1/crm.py:162` | NOT_IMPLEMENTED |
| POST | `/api/v1/sales-returns` | all_permissions:sales_returns.create | denied_by_sales_allowlist | `backend/app/api/v1/crm.py:164` | NOT_IMPLEMENTED |
| GET | `/api/v1/shifts` | all_permissions:shifts.read | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:64` | NOT_IMPLEMENTED |
| POST | `/api/v1/shifts` | all_permissions:shifts.create | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:66` | NOT_IMPLEMENTED |
| POST | `/api/v1/shifts/assignments` | all_permissions:shifts.assign | denied_by_sales_allowlist | `backend/app/api/v1/hr.py:68` | NOT_IMPLEMENTED |
| GET | `/api/v1/stock-adjustments` | all_permissions:inventory.read | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:166` | NOT_IMPLEMENTED |
| POST | `/api/v1/stock-adjustments` | all_permissions:inventory.adjust | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:170` | NOT_IMPLEMENTED |
| GET | `/api/v1/stock-receipt-suppliers` | all_permissions:inventory.create | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:53` | NOT_IMPLEMENTED |
| GET | `/api/v1/stock-receipts` | all_permissions:inventory.create | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:51` | NOT_IMPLEMENTED |
| POST | `/api/v1/stock-receipts` | all_permissions:inventory.create | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:57` | NOT_IMPLEMENTED |
| POST | `/api/v1/stock-receipts/import-pdf` | all_permissions:inventory.create | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:68` | NOT_IMPLEMENTED |
| GET | `/api/v1/stock-receipts/{id}` | all_permissions:inventory.create | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:59` | NOT_IMPLEMENTED |
| POST | `/api/v1/stock-receipts/{id}/cancel` | all_permissions:inventory.create | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:65` | NOT_IMPLEMENTED |
| POST | `/api/v1/stock-receipts/{id}/finalize` | all_permissions:inventory.create | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:63` | NOT_IMPLEMENTED |
| POST | `/api/v1/stock-receipts/{id}/scan` | all_permissions:inventory.create | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:61` | NOT_IMPLEMENTED |
| GET | `/api/v1/stock-reservations` | all_permissions:inventory.read | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:172` | NOT_IMPLEMENTED |
| POST | `/api/v1/stock-reservations` | all_permissions:inventory.adjust | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:176` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/stock-reservations/{id}` | all_permissions:inventory.adjust | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:178` | NOT_IMPLEMENTED |
| GET | `/api/v1/stock-transfers` | all_permissions:inventory.read | allowed_route_only | `backend/app/api/v1/inventory.py:134` | NOT_IMPLEMENTED |
| POST | `/api/v1/stock-transfers` | all_permissions:inventory.transfer | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:136` | NOT_IMPLEMENTED |
| POST | `/api/v1/stock-transfers/direct` | all_permissions:inventory.transfer | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:138` | NOT_IMPLEMENTED |
| GET | `/api/v1/stock-transfers/{id}` | all_permissions:inventory.read | allowed_route_only | `backend/app/api/v1/inventory.py:140` | NOT_IMPLEMENTED |
| POST | `/api/v1/stock-transfers/{id}/pick` | all_permissions:inventory.transfer | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:147` | NOT_IMPLEMENTED |
| GET | `/api/v1/stock-transfers/{id}/receipt` | all_permissions:inventory.read | allowed_route_only | `backend/app/api/v1/inventory.py:151` | NOT_IMPLEMENTED |
| POST | `/api/v1/stock-transfers/{id}/receive` | all_permissions:inventory.read | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:149` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/stock-transfers/{id}/status` | all_permissions:inventory.transfer | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:145` | NOT_IMPLEMENTED |
| GET | `/api/v1/stores` | all_permissions:inventory.read | allowed_route_only | `backend/app/api/v1/inventory.py:30` | NOT_IMPLEMENTED |
| POST | `/api/v1/stores` | require_owner:review | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:35` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/stores/{id}` | require_owner:review | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:37` | NOT_IMPLEMENTED |
| GET | `/api/v1/users` | all_permissions:users.read | denied_by_sales_allowlist | `backend/app/api/v1/management.py:24` | NOT_IMPLEMENTED |
| POST | `/api/v1/users` | all_permissions:users.create | denied_by_sales_allowlist | `backend/app/api/v1/management.py:30` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/users/{user_id}` | all_permissions:users.delete | denied_by_sales_allowlist | `backend/app/api/v1/management.py:45` | NOT_IMPLEMENTED |
| GET | `/api/v1/users/{user_id}` | all_permissions:users.read | denied_by_sales_allowlist | `backend/app/api/v1/management.py:35` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/users/{user_id}` | all_permissions:users.update | denied_by_sales_allowlist | `backend/app/api/v1/management.py:40` | NOT_IMPLEMENTED |
| GET | `/api/v1/users/{user_id}/audit-logs` | all_permissions:users.read | denied_by_sales_allowlist | `backend/app/api/v1/management.py:95` | NOT_IMPLEMENTED |
| POST | `/api/v1/users/{user_id}/permissions` | all_permissions:users.assign_permissions | denied_by_sales_allowlist | `backend/app/api/v1/management.py:65` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/users/{user_id}/permissions/{permission_id}` | all_permissions:users.assign_permissions | denied_by_sales_allowlist | `backend/app/api/v1/management.py:70` | NOT_IMPLEMENTED |
| POST | `/api/v1/users/{user_id}/reset-password` | all_permissions:users.reset_password | denied_by_sales_allowlist | `backend/app/api/v1/management.py:75` | NOT_IMPLEMENTED |
| POST | `/api/v1/users/{user_id}/revoke-sessions` | all_permissions:users.manage_sessions | denied_by_sales_allowlist | `backend/app/api/v1/management.py:90` | NOT_IMPLEMENTED |
| POST | `/api/v1/users/{user_id}/roles` | all_permissions:users.assign_roles | denied_by_sales_allowlist | `backend/app/api/v1/management.py:55` | NOT_IMPLEMENTED |
| DELETE | `/api/v1/users/{user_id}/roles/{role_id}` | all_permissions:users.assign_roles | denied_by_sales_allowlist | `backend/app/api/v1/management.py:60` | NOT_IMPLEMENTED |
| GET | `/api/v1/users/{user_id}/sessions` | all_permissions:users.manage_sessions | denied_by_sales_allowlist | `backend/app/api/v1/management.py:85` | NOT_IMPLEMENTED |
| PATCH | `/api/v1/users/{user_id}/status` | all_permissions:users.manage_status | denied_by_sales_allowlist | `backend/app/api/v1/management.py:50` | NOT_IMPLEMENTED |
| POST | `/api/v1/users/{user_id}/unlock` | all_permissions:users.manage_status | denied_by_sales_allowlist | `backend/app/api/v1/management.py:80` | NOT_IMPLEMENTED |
| GET | `/api/v1/warehouses` | all_permissions:inventory.read | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:44` | NOT_IMPLEMENTED |
| POST | `/api/v1/warehouses` | require_owner:review | denied_by_sales_allowlist | `backend/app/api/v1/inventory.py:48` | NOT_IMPLEMENTED |
| GET | `/health` | public/other — review | public_or_self_service | `backend/app/main.py:29` | NOT_IMPLEMENTED |
