<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Documents\PdfService;
use Anicraze\Http\ApiException;
use Smalot\PdfParser\Parser;

require dirname(__DIR__) . '/vendor/autoload.php';

$expected = 'anicraze_phase5b_workflow5c2';
if (getenv('DB_NAME') !== $expected) {
    throw new RuntimeException('Complete PDF test requires its disposable workflow database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== $expected) {
    throw new RuntimeException('Database identity mismatch');
}
$ownerId = $db->query("SELECT id FROM users WHERE email='owner@anicraze.in'")->fetchColumn();
$owner = ['id' => $ownerId, 'roles' => ['OWNER']];
$invoiceId = $db->query('SELECT id FROM invoices ORDER BY created_at DESC LIMIT 1')->fetchColumn();
$transferId = $db->query('SELECT id FROM stock_transfers ORDER BY created_at DESC LIMIT 1')->fetchColumn();
$productId = $db->query('SELECT id FROM products ORDER BY CHAR_LENGTH(name) DESC LIMIT 1')->fetchColumn();
if (!$invoiceId || !$transferId || !$productId) {
    throw new RuntimeException('Populated workflow PDF fixtures are missing');
}
$service = new PdfService($db);
$documents = [
    'invoice' => $service->invoice($owner, $invoiceId),
    'transfer' => $service->transfer($owner, $transferId),
    'label' => $service->label($owner, $productId),
    'sales-report' => $service->report($owner, 'sales_summary', ['preset' => 'TODAY']),
    'inventory-report' => $service->report($owner, 'inventory_summary', ['preset' => 'TODAY']),
    'finance-report' => $service->report($owner, 'finance_summary', ['preset' => 'TODAY']),
    'profit-loss' => $service->report($owner, 'finance_shop-profit-loss', ['preset' => 'TODAY']),
];
$directory = dirname(__DIR__, 2) . '/tmp/pdfs';
if (!is_dir($directory) && !mkdir($directory, 0700, true) && !is_dir($directory)) {
    throw new RuntimeException('PDF proof directory unavailable');
}
$parser = new Parser();
foreach ($documents as $name => $bytes) {
    if (!str_starts_with($bytes, '%PDF-') || !str_contains($bytes, '%%EOF')) {
        throw new RuntimeException($name . ' is not a complete PDF');
    }
    $parsed = $parser->parseContent($bytes);
    if (count($parsed->getPages()) < 1) {
        throw new RuntimeException($name . ' has no pages');
    }
    $text = $parsed->getText();
    if ($name === 'invoice' && (!str_contains($text, 'Naruto Rasengan')
        || !str_contains($text, 'Local simulated customer')
        || !str_contains($text, '790.00'))) {
        throw new RuntimeException('Invoice PDF lacks sale/customer/discount data');
    }
    if ($name === 'label' && (!str_contains($text, 'ANI-ACT-000022') || !str_contains($text, '1,800'))) {
        throw new RuntimeException('Barcode label human-readable fields differ');
    }
    if (preg_match('/\b(?:GST|HSN|CGST|SGST|IGST)\b/i', $text)) {
        throw new RuntimeException($name . ' reintroduced removed tax labels');
    }
    file_put_contents($directory . '/phase5c-' . $name . '-proof.pdf', $bytes);
}
try {
    $service->invoice(['id' => $ownerId, 'roles' => ['SALES'], 'assigned_store_id' =>
        $db->query("SELECT id FROM stores WHERE code='WESTEND'")->fetchColumn()], $invoiceId);
    throw new RuntimeException('Foreign shop accessed invoice PDF');
} catch (ApiException $error) {
    if ($error->status !== 403) { throw $error; }
}
echo "php_pdf_complete_integration_passed=8\n";
