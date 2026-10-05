<?php
declare(strict_types=1);

namespace Anicraze\Http;

use Anicraze\Auth\AuthService;
use Anicraze\Auth\PasswordResetService;
use Anicraze\Billing\BillingService;
use Anicraze\Catalog\BarcodeImage;
use Anicraze\Catalog\ProductService;
use Anicraze\Catalog\ProductWriteService;
use Anicraze\Catalog\ProductImportService;
use Anicraze\Catalog\ProductImageService;
use Anicraze\Catalog\ReferenceService;
use Anicraze\Database\Connection;
use Anicraze\Documents\PdfService;
use Anicraze\Documents\CsvService;
use Anicraze\Documents\ReportExportService;
use Anicraze\Inventory\ReceiptService;
use Anicraze\Inventory\StockPdfImportService;
use Anicraze\Inventory\TransferService;
use Anicraze\Inventory\InventoryService;
use Anicraze\Inventory\CorrectionService;
use Anicraze\Reports\ReportService;
use Anicraze\Reports\OwnerDashboardService;
use Anicraze\Reports\ReportScheduleService;
use Anicraze\Finance\SupplierService;
use Anicraze\Finance\PayableService;
use Anicraze\Notifications\NotificationService;
use Anicraze\People\AccountDirectoryService;

final class Application
{
    public function run(): void
    {
        $requestId = bin2hex(random_bytes(16));
        header_remove('X-Powered-By');
        header('Content-Type: application/json; charset=utf-8');
        header('X-Request-ID: ' . $requestId);
        header('X-Content-Type-Options: nosniff');
        header('Referrer-Policy: no-referrer');
        header('X-Frame-Options: DENY');
        header('Cache-Control: no-store');
        $origin = $_SERVER['HTTP_ORIGIN'] ?? '';
        $allowedOrigin = getenv('APP_ALLOWED_ORIGIN') ?: '';
        if ($origin !== '' && $allowedOrigin !== '' && hash_equals($allowedOrigin, $origin)) {
            header('Access-Control-Allow-Origin: ' . $allowedOrigin);
            header('Vary: Origin');
            header('Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS');
            header('Access-Control-Allow-Headers: Authorization, Content-Type, X-Request-ID');
        }
        $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
        $path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
        if ($method === 'OPTIONS') {
            http_response_code($origin !== '' && $allowedOrigin !== '' && hash_equals($allowedOrigin, $origin) ? 204 : 403);
            return;
        }
        if ($method === 'GET' && in_array($path, ['/health', '/api/v1/health'], true)) {
            http_response_code(200);
            echo json_encode(['status' => 'ok'], JSON_THROW_ON_ERROR);
            return;
        }
        if (!is_string($path) || !RouteCatalog::supports($method, $path)) {
            Response::error(404, 'not_implemented', 'Endpoint not implemented in Hostinger candidate', $requestId);
            return;
        }
        $activeAuthPaths = ['/api/v1/auth/login', '/api/v1/auth/forgot-password', '/api/v1/auth/reset-password', '/api/v1/auth/refresh', '/api/v1/auth/logout',
            '/api/v1/auth/logout-all', '/api/v1/auth/me'];
        $productPath = is_string($path) && ($path === '/api/v1/products' || str_starts_with($path, '/api/v1/products/'));
        $referencePath = in_array($path, ['/api/v1/categories', '/api/v1/anime', '/api/v1/brands', '/api/v1/characters'], true);
        $receiptPath = is_string($path) && ($path === '/api/v1/stock-receipts' || str_starts_with($path, '/api/v1/stock-receipts/'));
        $supplierPath = in_array($path, ['/api/v1/suppliers', '/api/v1/stock-receipt-suppliers'], true);
        $payablePath = is_string($path) && ($path === '/api/v1/purchase-payables' || str_starts_with($path, '/api/v1/purchase-payables/'));
        $notificationPath = is_string($path) && ($path === '/api/v1/notifications' || str_starts_with($path, '/api/v1/notifications/'));
        $directoryPath = $path === '/api/v1/employees';
        $dashboardPath = $path === '/api/v1/dashboard/owner';
        $transferPath = is_string($path) && ($path === '/api/v1/stock-transfers' || str_starts_with($path, '/api/v1/stock-transfers/'));
        $inventoryPath = is_string($path) && ($path === '/api/v1/inventory'
            || $path === '/api/v1/inventory/transactions' || $path === '/api/v1/inventory/ledger'
            || $path === '/api/v1/inventory/analytics/summary' || $path === '/api/v1/inventory/reports/stock'
            || $path === '/api/v1/stores' || $path === '/api/v1/warehouses');
        $correctionPath = is_string($path) && ($path === '/api/v1/stock-adjustments'
            || preg_match('#^/api/v1/inventory/[0-9a-fA-F-]{36}/damage$#D', $path) === 1);
        $billingPath = is_string($path) && ($path === '/api/v1/billing' || str_starts_with($path, '/api/v1/billing/')
            || $path === '/api/v1/invoices' || str_starts_with($path, '/api/v1/invoices/'));
        $reportPath = is_string($path) && str_starts_with($path, '/api/v1/reports/');
        $schedulePath = is_string($path) && ($path === '/api/v1/report-schedules' || str_starts_with($path, '/api/v1/report-schedules/'));
        if (!in_array($path, $activeAuthPaths, true) && !$productPath && !$referencePath && !$receiptPath && !$supplierPath && !$payablePath && !$notificationPath && !$directoryPath && !$dashboardPath && !$transferPath && !$inventoryPath && !$correctionPath && !$billingPath && !$reportPath && !$schedulePath) {
            Response::error(404, 'not_implemented', 'Endpoint not implemented in Hostinger candidate', $requestId);
            return;
        }
        try {
            $database = Connection::open();
            $service = new AuthService($database);
            if ($method === 'POST' && $path === '/api/v1/auth/login') {
                $body = Request::json();
                if (!is_string($body['email'] ?? null) || !is_string($body['password'] ?? null)
                    || !is_bool($body['remember_me'] ?? false)) {
                    throw new ApiException(422, 'validation_error', 'Request validation failed');
                }
                Response::success($service->login($body['email'], $body['password'], $body['remember_me'] ?? false), 'Login successful');
                return;
            }
            if ($method === 'POST' && $path === '/api/v1/auth/refresh') {
                $body = Request::json();
                if (!is_string($body['refresh_token'] ?? null)) {
                    throw new ApiException(422, 'validation_error', 'Request validation failed');
                }
                Response::success($service->refresh($body['refresh_token']), 'Token refreshed successfully');
                return;
            }
            if ($method === 'POST' && $path === '/api/v1/auth/forgot-password') {
                $body = Request::json();
                if (!is_string($body['email'] ?? null)) throw new ApiException(422, 'validation_error', 'Email is required');
                (new PasswordResetService($database))->request($body['email']);
                Response::success(null, 'If an account exists for this email, password reset instructions have been sent.');
                return;
            }
            if ($method === 'POST' && $path === '/api/v1/auth/reset-password') {
                $body = Request::json();
                if (!is_string($body['token'] ?? null) || !is_string($body['password'] ?? null)) throw new ApiException(422, 'validation_error', 'Reset token and password are required');
                (new PasswordResetService($database))->reset($body['token'], $body['password']);
                Response::success(null, 'Password reset successfully. Sign in with your new password.');
                return;
            }
            $actor = $service->authenticate(Request::bearer());
            if ($schedulePath) {
                $schedules = new ReportScheduleService($database);
                if ($method === 'GET' && $path === '/api/v1/report-schedules') {
                    Response::success($schedules->list($actor), 'Report schedules retrieved'); return;
                }
                if ($method === 'POST' && preg_match('#^/api/v1/report-schedules/([0-9a-fA-F-]{36})/run-now$#D', $path, $matches)) {
                    Response::success($schedules->run($actor, $matches[1]), 'Report schedule completed'); return;
                }
            }
            if ($method === 'GET' && $dashboardPath) {
                Response::success((new OwnerDashboardService($database))->get($actor, $_GET), 'Owner dashboard retrieved');
                return;
            }
            if ($method === 'GET' && $directoryPath) {
                Response::success((new AccountDirectoryService($database))->list($actor), 'Team accounts retrieved');
                return;
            }
            if ($supplierPath) {
                $suppliers = new SupplierService($database);
                if ($method === 'GET' && $path === '/api/v1/stock-receipt-suppliers') {
                    Response::success($suppliers->receiptChoices($actor), 'Suppliers retrieved');
                    return;
                }
                if ($method === 'GET' && $path === '/api/v1/suppliers') {
                    Response::success($suppliers->list($actor), 'Suppliers retrieved');
                    return;
                }
                if ($method === 'POST' && $path === '/api/v1/suppliers') {
                    Response::success($suppliers->create($actor, Request::json()), 'Supplier created', 201);
                    return;
                }
            }
            if ($payablePath) {
                $payables = new PayableService($database);
                if ($method === 'GET' && $path === '/api/v1/purchase-payables/summary') {
                    Response::success($payables->summary($actor), 'Purchase payment summary retrieved');
                    return;
                }
                if ($path === '/api/v1/purchase-payables') {
                    if ($method === 'GET') {
                        Response::success($payables->list($actor, isset($_GET['status']) ? (string) $_GET['status'] : null), 'Purchase payments retrieved');
                        return;
                    }
                    if ($method === 'POST') {
                        Response::success($payables->create($actor, Request::json()), 'Purchase payable created', 201);
                        return;
                    }
                }
                if ($method === 'POST' && preg_match('#^/api/v1/purchase-payables/([0-9a-fA-F-]{36})/(payments|reminders)$#D', $path, $matches)) {
                    Response::success($matches[2] === 'payments'
                        ? $payables->recordPayment($actor, $matches[1], Request::json())
                        : $payables->reminder($actor, $matches[1], Request::json()), 'Purchase payment updated', 201);
                    return;
                }
            }
            if ($notificationPath) {
                $notifications = new NotificationService($database);
                if ($method === 'GET' && $path === '/api/v1/notifications') {
                    Response::success($notifications->list($actor, $_GET), 'Notifications retrieved');
                    return;
                }
                if ($method === 'GET' && $path === '/api/v1/notifications/summary') {
                    Response::success($notifications->summary($actor), 'Notification summary retrieved');
                    return;
                }
                if ($method === 'POST' && $path === '/api/v1/notifications/mark-all-read') {
                    Response::success(['marked_count' => $notifications->markAllRead($actor)], 'Notifications marked read');
                    return;
                }
                if ($method === 'POST'
                    && preg_match('#^/api/v1/notifications/([0-9a-fA-F-]{36})/read$#D', $path, $matches)) {
                    Response::success($notifications->markRead($actor, $matches[1]), 'Notification marked read');
                    return;
                }
            }
            if ($method === 'GET' && in_array($path, ['/api/v1/products/export', '/api/v1/inventory/export'], true)) {
                $kind = $path === '/api/v1/products/export' ? 'products' : 'inventory';
                $csv = (new CsvService($database))->export($actor, $kind);
                header('Content-Type: text/csv; charset=utf-8');
                header('Content-Disposition: attachment; filename="ANICRAZE-' . $kind . '.csv"');
                header('Content-Length: ' . strlen($csv));
                echo $csv;
                return;
            }
            if ($method === 'GET' && $referencePath) {
                Response::success((new ReferenceService($database))->list($actor, basename($path), $_GET), 'Catalog references retrieved');
                return;
            }
            if ($method === 'GET' && $path === '/api/v1/reports/export') {
                if (!is_string($_GET['report_type'] ?? null) || !is_string($_GET['format'] ?? null)) {
                    throw new ApiException(422, 'validation_error', 'Report type and format are required');
                }
                $type = $_GET['report_type'];
                if ($_GET['format'] === 'PDF') {
                    $bytes = (new PdfService($database))->report($actor, $type, $_GET);
                    $contentType = 'application/pdf';
                    $extension = 'pdf';
                } else {
                    [$bytes, $contentType, $extension] = (new ReportExportService($database))
                        ->export($actor, $type, $_GET['format'], $_GET);
                }
                header('Content-Type: ' . $contentType);
                header('Content-Disposition: attachment; filename="ANICRAZE-report-' . preg_replace('/[^a-zA-Z0-9_-]/', '-', $type) . '.' . $extension . '"');
                header('Content-Length: ' . strlen($bytes));
                echo $bytes;
                return;
            }
            if ($method === 'GET' && is_string($path)
                && preg_match('#^/api/v1/products/([0-9a-fA-F-]{36})/barcode/label\.pdf$#D', $path, $label)) {
                $bytes = (new PdfService($database))->label($actor, $label[1]);
                header('Content-Type: application/pdf');
                header('Content-Disposition: attachment; filename="ANICRAZE-label-' . $label[1] . '.pdf"');
                header('Content-Length: ' . strlen($bytes));
                echo $bytes;
                return;
            }
            if ($reportPath && $method === 'GET' && preg_match('#^/api/v1/reports/(sales|inventory|finance)/(summary|shop-profit-loss)$#D', $path, $report)) {
                Response::success((new ReportService($database))->report($actor, $report[1], $report[2], $_GET), 'Report retrieved successfully');
                return;
            }
            if ($method === 'GET' && is_string($path)
                && preg_match('#^/api/v1/(invoices|stock-transfers)/([0-9a-fA-F-]{36})/(pdf|receipt)$#D', $path, $document)) {
                $pdf = new PdfService($database);
                if ($document[1] === 'invoices' && $document[3] === 'pdf') {
                    $bytes = $pdf->invoice($actor, $document[2]);
                    $filename = 'ANICRAZE-invoice-' . $document[2] . '.pdf';
                } elseif ($document[1] === 'stock-transfers' && $document[3] === 'receipt') {
                    $bytes = $pdf->transfer($actor, $document[2]);
                    $filename = 'ANICRAZE-transfer-' . $document[2] . '.pdf';
                } else {
                    throw new ApiException(404, 'not_implemented', 'Document is unavailable');
                }
                header('Content-Type: application/pdf');
                header('Content-Disposition: attachment; filename="' . $filename . '"');
                header('Content-Length: ' . strlen($bytes));
                echo $bytes;
                return;
            }
            if ($billingPath) {
                $billing = new BillingService($database);
                if ($method === 'GET' && in_array($path, ['/api/v1/billing/products', '/api/v1/billing/search'], true)) {
                    $storeId = $_GET['store_id'] ?? null;
                    if (!is_string($storeId)) {
                        throw new ApiException(422, 'validation_error', 'Shop is required');
                    }
                    Response::success($billing->products($actor, $storeId, $path === '/api/v1/billing/search' ? (string) ($_GET['query'] ?? '') : null), 'Shop products retrieved');
                    return;
                }
                if ($method === 'GET' && preg_match('#^/api/v1/billing/barcode/(.+)$#D', $path, $matches)) {
                    $storeId = $_GET['store_id'] ?? null;
                    if (!is_string($storeId)) {
                        throw new ApiException(422, 'validation_error', 'Shop is required');
                    }
                    Response::success($billing->products($actor, $storeId, null, rawurldecode($matches[1])), 'Shop product retrieved');
                    return;
                }
                if ($method === 'POST' && $path === '/api/v1/billing') {
                    Response::success($billing->create($actor, Request::json()), 'Invoice created successfully', 201);
                    return;
                }
                if ($method === 'GET' && $path === '/api/v1/invoices') {
                    Response::success($billing->list($actor), 'Invoices retrieved successfully');
                    return;
                }
                if ($method === 'GET' && preg_match('#^/api/v1/invoices/([0-9a-fA-F-]{36})$#D', $path, $matches)) {
                    Response::success($billing->get($actor, $matches[1]), 'Invoice retrieved successfully');
                    return;
                }
                if ($method === 'POST' && preg_match('#^/api/v1/invoices/([0-9a-fA-F-]{36})/cancel$#D', $path, $matches)) {
                    $body = Request::json();
                    if (!is_string($body['reason'] ?? null)) {
                        throw new ApiException(422, 'validation_error', 'Cancellation reason is required');
                    }
                    Response::success($billing->cancel($actor, $matches[1], $body['reason']), 'Invoice cancelled');
                    return;
                }
            }
            if ($inventoryPath && $method === 'GET') {
                $inventory = new InventoryService($database);
                if ($path === '/api/v1/stores' || $path === '/api/v1/warehouses') {
                    Response::success($inventory->locations($actor, basename($path)), 'Locations retrieved successfully');
                    return;
                }
                if ($path === '/api/v1/inventory') {
                    Response::success($inventory->list($actor, $_GET), 'Inventory retrieved successfully');
                    return;
                }
                if ($path === '/api/v1/inventory/analytics/summary') {
                    Response::success($inventory->summary($actor), 'Inventory summary retrieved successfully');
                    return;
                }
                if ($path === '/api/v1/inventory/reports/stock') {
                    Response::success($inventory->stockReport($actor), 'Stock report retrieved successfully');
                    return;
                }
                Response::success($inventory->movements($actor, $_GET), 'Inventory movements retrieved successfully');
                return;
            }
            if ($correctionPath && $method === 'POST') {
                $corrections = new CorrectionService($database);
                if ($path === '/api/v1/stock-adjustments') {
                    Response::success($corrections->adjust($actor, Request::json()), 'Stock adjustment completed', 201);
                    return;
                }
                if (preg_match('#^/api/v1/inventory/([0-9a-fA-F-]{36})/damage$#D', $path, $matches)) {
                    Response::success($corrections->damage($actor, $matches[1], Request::json()), 'Damaged stock recorded');
                    return;
                }
            }
            if ($transferPath) {
                $transfers = new TransferService($database);
                if ($method === 'GET' && $path === '/api/v1/stock-transfers') {
                    Response::success($transfers->list($actor), 'Stock transfers retrieved successfully');
                    return;
                }
                if ($method === 'POST' && $path === '/api/v1/stock-transfers/direct') {
                    Response::success($transfers->create($actor, Request::json()), 'Direct transfer completed', 201);
                    return;
                }
                if ($method === 'GET' && preg_match('#^/api/v1/stock-transfers/([0-9a-fA-F-]{36})$#D', $path, $matches)) {
                    Response::success($transfers->get($actor, $matches[1]), 'Stock transfer retrieved successfully');
                    return;
                }
            }
            if ($receiptPath) {
                if ($method === 'POST' && $path === '/api/v1/stock-receipts/import-pdf') {
                    $file = $_FILES['file'] ?? null;
                    if (!is_array($file) || ($file['error'] ?? null) !== UPLOAD_ERR_OK
                        || !is_string($file['tmp_name'] ?? null) || !is_uploaded_file($file['tmp_name'])
                        || !is_string($file['name'] ?? null) || !is_int($file['size'] ?? null)) {
                        throw new ApiException(422, 'validation_error', 'Valid PDF upload is required');
                    }
                    Response::success((new StockPdfImportService($database))->preview($actor,
                        $file['tmp_name'], $file['name'], $file['size'], (string) ($file['type'] ?? '')),
                        'Stock PDF reviewed');
                    return;
                }
                $receipts = new ReceiptService($database);
                if ($path === '/api/v1/stock-receipts') {
                    if ($method === 'GET') {
                        Response::success($receipts->list($actor), 'Stock receipts retrieved successfully');
                        return;
                    }
                    if ($method === 'POST') {
                        Response::success($receipts->create($actor, Request::json()), 'Stock receipt created successfully', 201);
                        return;
                    }
                }
                if (preg_match('#^/api/v1/stock-receipts/([0-9a-fA-F-]{36})(?:/(scan|finalize))?$#D', $path, $matches)) {
                    if ($method === 'GET' && !isset($matches[2])) {
                        Response::success($receipts->get($actor, $matches[1]), 'Stock receipt retrieved successfully');
                        return;
                    }
                    if ($method === 'POST' && ($matches[2] ?? '') === 'scan') {
                        $body = Request::json();
                        if (!is_string($body['code'] ?? null) || !is_string($body['scan_id'] ?? null)) {
                            throw new ApiException(422, 'validation_error', 'Barcode is required');
                        }
                        Response::success($receipts->scan($actor, $matches[1], $body['code'], $body['scan_id']), 'Barcode scanned');
                        return;
                    }
                    if ($method === 'POST' && ($matches[2] ?? '') === 'finalize') {
                        Response::success($receipts->finalize($actor, $matches[1]), 'Stock entered in Central Warehouse');
                        return;
                    }
                }
            }
            if ($productPath && $method === 'POST' && $path === '/api/v1/products') {
                Response::success((new ProductWriteService($database))->create($actor, Request::json()), 'Product created successfully', 201);
                return;
            }
            if ($productPath && $method === 'POST' && $path === '/api/v1/products/import') {
                $file = $_FILES['file'] ?? null;
                $flag = filter_var($_GET['dry_run'] ?? 'true', FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE);
                if (!is_array($file) || ($file['error'] ?? null) !== UPLOAD_ERR_OK
                    || !is_string($file['tmp_name'] ?? null) || !is_uploaded_file($file['tmp_name'])
                    || !is_string($file['name'] ?? null) || !is_int($file['size'] ?? null) || $flag === null) {
                    throw new ApiException(422, 'validation_error', 'Valid CSV upload and dry_run flag are required');
                }
                Response::success((new ProductImportService($database))->import($actor, $file['tmp_name'],
                    $file['name'], $file['size'], $flag), 'Product import checked');
                return;
            }
            if ($productPath && $method === 'POST'
                && preg_match('#^/api/v1/products/([0-9a-fA-F-]{36})/images$#D', $path, $matches)) {
                $file = $_FILES['file'] ?? null;
                if (!is_array($file) || ($file['error'] ?? null) !== UPLOAD_ERR_OK
                    || !is_string($file['tmp_name'] ?? null) || !is_uploaded_file($file['tmp_name'])
                    || !is_string($file['name'] ?? null) || !is_int($file['size'] ?? null)) {
                    throw new ApiException(422, 'validation_error', 'Valid image upload is required');
                }
                Response::success((new ProductImageService($database))->upload($actor, $matches[1],
                    $file['tmp_name'], $file['name'], $file['size']), 'Product image uploaded', 201);
                return;
            }
            if ($productPath && in_array($method, ['PATCH', 'DELETE'], true)
                && preg_match('#^/api/v1/products/([0-9a-fA-F-]{36})$#D', $path, $matches)) {
                $writer = new ProductWriteService($database);
                if ($method === 'PATCH') {
                    Response::success($writer->update($actor, $matches[1], Request::json()), 'Product updated successfully');
                } else {
                    $writer->archive($actor, $matches[1]);
                    Response::success(null, 'Product archived successfully');
                }
                return;
            }
            if ($productPath && $method === 'GET') {
                $products = new ProductService($database);
                if ($path === '/api/v1/products') {
                    Response::success($products->list($actor, $_GET), 'Products retrieved successfully');
                    return;
                }
                if (preg_match('#^/api/v1/products/search/(barcode|sku)/([^/]+)$#D', $path, $matches)) {
                    Response::success($products->find($actor, $matches[1], rawurldecode($matches[2])), 'Product retrieved successfully');
                    return;
                }
                if (preg_match('#^/api/v1/products/([0-9a-fA-F-]{36})/barcode$#D', $path, $matches)) {
                    $product = $products->find($actor, 'id', $matches[1]);
                    Response::success(['product_id' => $product['id'], 'sku' => $product['sku'],
                        'barcode' => $product['barcode'], 'format' => 'CODE128',
                        'image_url' => BarcodeImage::dataUri($product['barcode'])], 'Barcode retrieved successfully');
                    return;
                }
                if (preg_match('#^/api/v1/products/([0-9a-fA-F-]{36})$#D', $path, $matches)) {
                    Response::success($products->find($actor, 'id', $matches[1]), 'Product retrieved successfully');
                    return;
                }
            }
            if ($method === 'GET' && $path === '/api/v1/auth/me') {
                Response::success($service->profile($actor['id']), 'Profile retrieved successfully');
                return;
            }
            if ($method === 'POST' && $path === '/api/v1/auth/logout') {
                $body = Request::json();
                if (!is_string($body['refresh_token'] ?? null)) {
                    throw new ApiException(422, 'validation_error', 'Request validation failed');
                }
                $service->logout($actor, $body['refresh_token']);
                Response::success(null, 'Logout successful');
                return;
            }
            if ($method === 'POST' && $path === '/api/v1/auth/logout-all') {
                Response::success(['revoked_sessions' => $service->logoutAll($actor)], 'Logged out from all devices successfully');
                return;
            }
            throw new ApiException(405, 'method_not_allowed', 'Method not allowed');
        } catch (ApiException $error) {
            Response::error($error->status, $error->errorCode, $error->getMessage(), $requestId);
        } catch (\Throwable $error) {
            error_log('ANICRAZE PHP request failure request_id=' . $requestId . ' class=' . get_class($error)
                . ' file=' . basename($error->getFile()) . ' line=' . $error->getLine());
            Response::error(500, 'internal_error', 'An unexpected server error occurred', $requestId);
        }
    }
}
