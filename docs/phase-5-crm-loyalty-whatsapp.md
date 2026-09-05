# Phase 5 — CRM, Loyalty and WhatsApp Invoice Automation

## Reused domains

Phase 5 keeps the existing `Customer`, `CustomerProfile`, address, note, tag, segment, loyalty account/transaction, membership tier/history, store-credit, invoice, return/refund and `CustomerCommunication` domains. Billing already invokes `CustomerCRMIntegration`, which updates authoritative lifetime values and awards loyalty points using the active `LoyaltyConfig` and membership multiplier. Invoice-based EARN lookup makes that processing idempotent.

Production CRM routes are shared at `/{role}/customers` and `/{role}/customers/:id`, subject to existing permissions. The list, KPIs, purchase history, loyalty ledger, membership, returns/refunds, store-credit balance, internal notes and communication timeline use live APIs. Mobile cards and desktop tables share the same components. Production CRM routes do not import the old mock datasets.

## Customer identity and privacy

Indian mobile numbers are canonicalized to country-code digits (`91XXXXXXXXXX`); lookup also recognizes legacy 10-digit rows so `+91XXXXXXXXXX` and `XXXXXXXXXX` cannot create separate customers. UI lists mask mobile numbers. Backend CRM/POS schemas do not expose inventory cost, valuation, profit, supplier cost or company finance.

## Communication architecture

`WhatsAppProvider` has two implementations:

- `DevelopmentWhatsAppProvider`: records `SIMULATED` and a development reference. It never claims SENT, DELIVERED or READ.
- `MetaWhatsAppProvider`: uploads the protected invoice PDF through Meta media upload, invokes the configured approved template with the provider media ID, and records Meta's message ID. `SENT` means provider API acceptance only; DELIVERED and READ come exclusively from signed webhooks.

Invoice communication runs as a post-response background task with a fresh database transaction. Billing commits independently. One automatic idempotency key (`invoice:<id>:whatsapp:invoice`) prevents duplicate automatic sends when billing/idempotency retries occur. Manual resend creates an intentional new attempt and is rate limited. Failed messages remain persisted for controlled manual retry; maximum processing attempts are configured.

Communication states include `DISABLED`, `QUEUED`, `PROCESSING`, `SIMULATED`, `SENT`, `DELIVERED`, `READ`, `WAITING_FOR_DOCUMENT` and `FAILED`. Provider/message ID, recipient, attempt count, attempt/delivery/read/failure timestamps and safe failure information are persisted. Customer communication and WhatsApp opt-outs are enforced before job creation. Missing phone, opt-out and missing PDF do not affect the invoice.

## Configuration

All credentials are backend-only environment settings:

- `WHATSAPP_ENABLED`
- `WHATSAPP_PROVIDER=development|meta`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_BUSINESS_ACCOUNT_ID`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_APP_SECRET`
- `WHATSAPP_API_VERSION`
- `WHATSAPP_INVOICE_TEMPLATE_NAME`
- `WHATSAPP_TEMPLATE_LANGUAGE`
- `WHATSAPP_MAX_ATTEMPTS`

The safe settings API exposes only enabled/configured state, provider, template and language—never tokens or secrets.

## Webhook security

Meta webhook verification uses the configured verify token. Status POSTs require a valid `X-Hub-Signature-256` HMAC using the app secret. Events locate communications by provider message ID. Duplicate events are idempotent; stale SENT events cannot downgrade DELIVERED/READ, and late failures cannot downgrade a confirmed delivery/read.

## APIs added

- `GET /customers/{id}/loyalty/transactions`
- `GET /customers/{id}/memberships`
- `GET /customers/{id}/store-credit`
- `GET/POST /customers/{id}/notes`
- `GET /customers/{id}/communications`
- `GET /invoices/{id}/communications`
- `GET /communications/whatsapp/settings`
- `POST /communications/whatsapp/send`
- `POST /communications/{id}/retry`
- `GET/POST /communications/whatsapp/webhook`

Existing CRM, loyalty, membership, invoice, return/refund and analytics APIs were reused.

## Migration

`20260831_0014_whatsapp_communications` minimally extends `customer_communications`; it does not create a competing table. It adds purpose, recipient, provider, provider message ID, unique idempotency key, attempt count, delivery/read/failure timestamps and failure information. Legacy records receive stable `legacy:<uuid>` keys.

## PostgreSQL verification

Invoice `ANI-INV-000006` completed for an enrolled customer. Shop stock decreased exactly once, one payment and SALE movement existed, CRM lifetime orders/spend updated, one EARN transaction added 4 points, and one automatic communication was stored with one attempt as `SIMULATED/development`. Repeating the billing idempotency key returned the same invoice and did not add loyalty or communication duplicates.

Provider-failure acceptance used deliberately incomplete Meta configuration. Invoice `ANI-INV-000007` remained `COMPLETED/PAID`, with its payment, SALE movement and loyalty EARN intact, while communication independently became `FAILED/PROVIDER_ERROR`. An opted-out walk-in invoice returned `CUSTOMER_COMMUNICATION_OPT_OUT`.

## Real-provider verification and limitations

No Meta credentials or authorized recipient were provided, so real Meta send, delivery and read confirmation were not performed. Development simulation and provider failure were verified honestly. Redis was unavailable locally; persisted manual retry remains available, but no always-running Celery retry worker was introduced. Visual viewport verification depends on the in-app browser connection.

## Phase 6 handoff

The operational chain now produces real supplier/inventory/transfer/shop/POS/customer/payment/invoice/loyalty/communication data. Phase 6 can aggregate these records for owner command-center, finance, GST, store/product performance and profitability without replacing the operational domains.
