# ANICRAZE public website — local static project

This is the brand website intended for `https://anicraze.com`, **not** the ERP. It lives in `public-website/` and has its own Vite/TypeScript toolchain and lockfile. It does not import ERP code, call ERP APIs, implement ecommerce, or require a backend.

## Develop and build

Use Node.js **20.19+** and npm. From `public-website/`:

```sh
npm ci
npm run dev
npm run typecheck
npm run build
npm run preview
```

The production output is `public-website/dist/` (ordinary HTML, CSS, JS, images and `robots.txt`/`sitemap.xml`). The site has one document and in-page anchor navigation, so it needs **no SPA rewrite**. A future multi-page implementation would need its own routing decision. No server-side process is required.

## Public configuration

`src/config.ts` centralizes the staff **ERP Login** navigation URL. The default is `https://erp.anicraze.com`. `VITE_ERP_URL` may be set at build time; only the exact HTTPS `erp.anicraze.com` origin is accepted, and invalid values fall back to the default. This is only a public URL, never a credential or authentication implementation. The link may not work until that domain is configured in a later phase. No customer account or checkout is present.

The official phone/WhatsApp contact is `+91 80105 26600` (`tel:+918010526600`, `https://wa.me/918010526600`). The public `wa.me` action is unrelated to the disabled ERP invoice-automation provider. No Meta token is used. `SOCIAL_LINKS` and `STORE_MAP_LINKS` are intentionally empty in `src/config.ts`; add only independently confirmed official social/map URLs. A map link renders only for a configured permanent store and never for an event card. The eight store names/addresses are from the approved Phase 4 brief; EVENT1 and EVENT2 are explicitly temporary with no invented permanent address.

## Brand and content assets

`public/anicraze-logo.png` is an optimized copy of the existing official `frontend/public/anicraze-logo.png` (800×266 instead of 2172×724). The favicon is a simple brand-inspired local vector. Category and featured graphics are CSS illustration, clearly not product photography or live-stock representations. When approved product photography is available, replace the abstract artwork with optimized WebP/AVIF assets and accurate alt text; retain correct names/usage rights. Catalogue category names came from `backend/data/anicraze_final_product_master.csv`, not live inventory. This site intentionally has no API dependency.

## Future Hostinger static deployment — not performed

The purchased Hostinger Unlimited Web Hosting plan should be able to serve static files, subject to the account's actual document-root, HTTPS and custom-domain settings. In a later authorized deployment: build locally/CI, upload the **contents** of `public-website/dist/` to the `anicraze.com` document root (often `public_html`), ensure `index.html`, assets, `robots.txt` and `sitemap.xml` are at the site root, set TLS/redirects as appropriate, and verify the canonical domain and contact/ERP links. No `.env`, `node_modules`, source secrets or ERP files should be uploaded. This phase has not accessed Hostinger, DNS or hosted services.

Before cutover, verify real store details, event availability, phone operation, the ERP domain, official social/map links if added, accessibility/device acceptance and search metadata on the final HTTPS domain. Do not repoint the existing Netlify/Render/Neon demo as part of this website build.
