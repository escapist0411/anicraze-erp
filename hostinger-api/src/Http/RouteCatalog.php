<?php
declare(strict_types=1);

namespace Anicraze\Http;

/** Routes with implemented handlers in Application. Keep this catalog fail-closed. */
final class RouteCatalog
{
    private const ROUTES = [
        ['GET', '/health'],
        ['GET', '/api/v1/health'],
        ['POST', '/api/v1/auth/login'],
        ['POST', '/api/v1/auth/forgot-password'],
        ['POST', '/api/v1/auth/reset-password'],
        ['POST', '/api/v1/auth/refresh'],
        ['POST', '/api/v1/auth/logout'],
        ['POST', '/api/v1/auth/logout-all'],
        ['GET', '/api/v1/auth/me'],
        ['GET', '/api/v1/categories'],
        ['GET', '/api/v1/anime'],
        ['GET', '/api/v1/brands'],
        ['GET', '/api/v1/characters'],
        ['GET', '/api/v1/suppliers'],
        ['POST', '/api/v1/suppliers'],
        ['GET', '/api/v1/stock-receipt-suppliers'],
        ['GET', '/api/v1/purchase-payables'],
        ['POST', '/api/v1/purchase-payables'],
        ['GET', '/api/v1/purchase-payables/summary'],
        ['POST', '/api/v1/purchase-payables/:id/payments'],
        ['POST', '/api/v1/purchase-payables/:id/reminders'],
        ['GET', '/api/v1/notifications'],
        ['GET', '/api/v1/employees'],
        ['GET', '/api/v1/dashboard/owner'],
        ['GET', '/api/v1/notifications/summary'],
        ['POST', '/api/v1/notifications/mark-all-read'],
        ['POST', '/api/v1/notifications/:id/read'],
        ['GET', '/api/v1/products'],
        ['POST', '/api/v1/products'],
        ['POST', '/api/v1/products/import'],
        ['POST', '/api/v1/products/:id/images'],
        ['GET', '/api/v1/products/export'],
        ['GET', '/api/v1/products/:id'],
        ['PATCH', '/api/v1/products/:id'],
        ['DELETE', '/api/v1/products/:id'],
        ['GET', '/api/v1/products/search/barcode/:code'],
        ['GET', '/api/v1/products/search/sku/:code'],
        ['GET', '/api/v1/products/:id/barcode'],
        ['GET', '/api/v1/products/:id/barcode/label.pdf'],
        ['GET', '/api/v1/stores'],
        ['GET', '/api/v1/warehouses'],
        ['GET', '/api/v1/inventory'],
        ['GET', '/api/v1/inventory/export'],
        ['GET', '/api/v1/inventory/analytics/summary'],
        ['GET', '/api/v1/inventory/reports/stock'],
        ['GET', '/api/v1/inventory/transactions'],
        ['GET', '/api/v1/inventory/ledger'],
        ['POST', '/api/v1/inventory/:id/damage'],
        ['POST', '/api/v1/stock-adjustments'],
        ['GET', '/api/v1/stock-receipts'],
        ['POST', '/api/v1/stock-receipts'],
        ['POST', '/api/v1/stock-receipts/import-pdf'],
        ['GET', '/api/v1/stock-receipts/:id'],
        ['POST', '/api/v1/stock-receipts/:id/scan'],
        ['POST', '/api/v1/stock-receipts/:id/finalize'],
        ['GET', '/api/v1/stock-transfers'],
        ['POST', '/api/v1/stock-transfers/direct'],
        ['GET', '/api/v1/stock-transfers/:id'],
        ['GET', '/api/v1/stock-transfers/:id/receipt'],
        ['GET', '/api/v1/billing/search'],
        ['GET', '/api/v1/billing/products'],
        ['GET', '/api/v1/billing/barcode/:code'],
        ['POST', '/api/v1/billing'],
        ['GET', '/api/v1/invoices'],
        ['GET', '/api/v1/invoices/:id'],
        ['POST', '/api/v1/invoices/:id/cancel'],
        ['GET', '/api/v1/invoices/:id/pdf'],
        ['GET', '/api/v1/reports/sales/summary'],
        ['GET', '/api/v1/reports/inventory/summary'],
        ['GET', '/api/v1/reports/finance/summary'],
        ['GET', '/api/v1/reports/finance/shop-profit-loss'],
        ['GET', '/api/v1/reports/export'],
        ['GET', '/api/v1/report-schedules'],
        ['POST', '/api/v1/report-schedules/:id/run-now'],
    ];

    public static function definitions(): array
    {
        return self::ROUTES;
    }

    public static function supports(string $method, string $path): bool
    {
        foreach (self::ROUTES as [$registeredMethod, $template]) {
            if ($registeredMethod !== $method) {
                continue;
            }
            $pattern = preg_quote($template, '#');
            $pattern = str_replace('\\:id', '[0-9a-fA-F-]{36}', $pattern);
            $pattern = str_replace('\\:code', '[^/]+', $pattern);
            if (preg_match('#^' . $pattern . '$#D', $path) === 1) {
                return true;
            }
        }
        return false;
    }
}
