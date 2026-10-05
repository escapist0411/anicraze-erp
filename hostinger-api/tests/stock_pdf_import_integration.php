<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;
use Anicraze\Inventory\StockPdfImportService;
use Dompdf\Dompdf;

require dirname(__DIR__) . '/vendor/autoload.php';

$expected = 'anicraze_phase5b_phase5c_rehearsal';
if (getenv('DB_NAME') !== $expected) {
    throw new RuntimeException('PDF import test requires the disposable clean rehearsal database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== $expected) {
    throw new RuntimeException('Database identity mismatch');
}
$product = $db->query("SELECT id,name FROM products WHERE sku='ANI-ACT-000001'")->fetch();
if (!$product) { throw new RuntimeException('Approved product fixture missing'); }
$before = [(int) $db->query('SELECT COUNT(*) FROM stock_receipts')->fetchColumn(),
    (int) $db->query('SELECT COALESCE(SUM(available_quantity),0) FROM inventory')->fetchColumn()];
$pdf = new Dompdf();
$pdf->loadHtml('<html><body><p>' . htmlspecialchars($product['name'], ENT_QUOTES, 'UTF-8')
    . ' 2 400.00</p></body></html>', 'UTF-8');
$pdf->render();
$file = tempnam(sys_get_temp_dir(), 'anicraze-stock-pdf-');
if ($file === false) { throw new RuntimeException('PDF fixture could not be created'); }
try {
    file_put_contents($file, $pdf->output());
    $service = new StockPdfImportService($db);
    $preview = $service->preview(['roles' => ['MANAGER']], $file, 'stock.pdf', filesize($file), 'application/pdf');
    if (!$preview['readable_text'] || count($preview['rows']) !== 1
        || $preview['rows'][0]['suggested_product_id'] !== $product['id']
        || $preview['rows'][0]['quantity'] !== 2 || $preview['rows'][0]['unit_cost'] !== '400.00'
        || $preview['rows'][0]['status'] !== 'Matched') {
        throw new RuntimeException('PDF import preview did not match approved product');
    }
    try {
        $service->preview(['roles' => ['SALES']], $file, 'stock.pdf', filesize($file), 'application/pdf');
        throw new RuntimeException('SALES imported stock PDF');
    } catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
    try {
        $service->preview(['roles' => ['OWNER']], $file, '../stock.pdf', filesize($file), 'text/plain');
        throw new RuntimeException('Invalid MIME was accepted');
    } catch (ApiException $error) { if ($error->status !== 422) { throw $error; } }
    $after = [(int) $db->query('SELECT COUNT(*) FROM stock_receipts')->fetchColumn(),
        (int) $db->query('SELECT COALESCE(SUM(available_quantity),0) FROM inventory')->fetchColumn()];
    if ($before !== $after) { throw new RuntimeException('PDF preview wrote operational data'); }
} finally {
    if (file_exists($file)) { unlink($file); }
}
echo "php_stock_pdf_import_integration_passed=4\n";
