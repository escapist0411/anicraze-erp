<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Documents\PdfService;
use Anicraze\Http\ApiException;

require dirname(__DIR__) . '/vendor/autoload.php';

if (!str_starts_with((string) getenv('DB_NAME'), 'anicraze_phase5b_workflow')) {
    throw new RuntimeException('PDF integration test requires isolated disposable database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== getenv('DB_NAME')) {
    throw new RuntimeException('Database identity mismatch');
}
$invoiceId = $db->query('SELECT id FROM invoices ORDER BY created_at DESC LIMIT 1')->fetchColumn();
$transferId = $db->query('SELECT id FROM stock_transfers ORDER BY created_at DESC LIMIT 1')->fetchColumn();
$ownerId = $db->query("SELECT id FROM users WHERE email='owner@anicraze.in'")->fetchColumn();
$westendId = $db->query("SELECT id FROM stores WHERE code='WESTEND'")->fetchColumn();
if (!$invoiceId || !$transferId || !$ownerId || !$westendId) {
    throw new RuntimeException('Simulated workflow documents are missing');
}
$service = new PdfService($db);
$owner = ['id' => $ownerId, 'roles' => ['OWNER']];
$output = dirname(__DIR__, 2) . '/tmp/pdfs';
if (!is_dir($output) && !mkdir($output, 0700, true) && !is_dir($output)) {
    throw new RuntimeException('Local PDF proof directory unavailable');
}
$invoice = $service->invoice($owner, $invoiceId);
$transfer = $service->transfer($owner, $transferId);
$labelProduct = $db->query('SELECT id FROM products ORDER BY CHAR_LENGTH(name) DESC LIMIT 1')->fetchColumn();
$label = $service->label($owner, $labelProduct);
$report = $service->report($owner, 'finance_shop-profit-loss', ['preset' => 'TODAY']);
foreach (['invoice' => $invoice, 'transfer' => $transfer, 'label' => $label, 'report' => $report] as $name => $bytes) {
    if (!str_starts_with($bytes, '%PDF-') || !str_contains($bytes, '%%EOF') || strlen($bytes) < 5000) {
        throw new RuntimeException("{$name} PDF was not rendered");
    }
    file_put_contents($output . '/phase5b-' . $name . '-proof.pdf', $bytes);
}
try {
    $service->invoice(['id' => $ownerId, 'roles' => ['SALES'], 'assigned_store_id' => $westendId], $invoiceId);
    throw new RuntimeException('Another shop opened a known invoice PDF');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
echo "php_pdf_integration_passed=5\n";
