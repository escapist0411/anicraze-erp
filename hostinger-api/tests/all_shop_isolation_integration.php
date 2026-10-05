<?php
declare(strict_types=1);

use Anicraze\Auth\AuthService;
use Anicraze\Billing\BillingService;
use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;
use Anicraze\Documents\PdfService;
use Anicraze\Http\ApiException;
use Anicraze\Inventory\InventoryService;
use Anicraze\Inventory\ReceiptService;
use Anicraze\Inventory\TransferService;
use Anicraze\Reports\ReportService;

require dirname(__DIR__) . '/vendor/autoload.php';

$expected = (string) getenv('DB_NAME');
if (!str_starts_with($expected, 'anicraze_phase5b_shops5c')) {
    throw new RuntimeException('Shop isolation test requires its disposable database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== $expected) {
    throw new RuntimeException('Database identity mismatch');
}
$codes = ['ELPRO','WESTEND','CIVIL','SWARGATE','KALYANI','SHIVAJI','EVENT1','EVENT2'];
$emails = ['elpro@anicraze.in','westend@anicraze.in','civil@anicraze.in','swargate@anicraze.in',
    'kalyani@anicraze.in','shivaji@anicraze.in','event.1@anicraze.in','event.2@anicraze.in'];
$shops = [];
foreach ($db->query('SELECT id,code FROM stores') as $row) { $shops[$row['code']] = $row['id']; }
if (count($shops) !== 8 || (int) $db->query('SELECT COUNT(*) FROM invoices')->fetchColumn() !== 0) {
    throw new RuntimeException('Shop test must start clean');
}
$auth = new AuthService($db);
$ownerLogin = $auth->login('owner@anicraze.in', getenv('ANICRAZE_OWNER_PASSWORD'), false);
$owner = $auth->authenticate($ownerLogin['access_token']);
$warehouse = $db->query("SELECT id FROM warehouses WHERE code='ANICRAZE_CWH'")->fetchColumn();
$product = $db->query('SELECT id,barcode,selling_price FROM products ORDER BY sku LIMIT 1')->fetch();
$receiptService = new ReceiptService($db);
$receipt = $receiptService->create($owner, ['warehouse_id' => $warehouse,
    'items' => [['product_id' => $product['id'], 'quantity' => 8, 'unit_cost' => 100]]]);
for ($index = 0; $index < 8; $index++) {
    $receiptService->scan($owner, $receipt['id'], $product['barcode'], Uuid::v4());
}
$receiptService->finalize($owner, $receipt['id']);
$transferService = new TransferService($db);
foreach ($codes as $code) {
    $transferService->create($owner, ['idempotency_key' => 'shop-test-' . $code,
        'source_warehouse_id' => $warehouse, 'target_store_id' => $shops[$code],
        'items' => [['product_id' => $product['id'], 'quantity' => 1]]]);
}
$billing = new BillingService($db);
$inventory = new InventoryService($db);
$reports = new ReportService($db);
$pdf = new PdfService($db);
$actors = [];
$invoices = [];
$passed = 0;
foreach ($codes as $index => $code) {
    $login = $auth->login($emails[$index], getenv('ANICRAZE_SALES_TEST_PASSWORD'), false);
    $actor = $auth->authenticate($login['access_token']);
    $actors[$code] = $actor;
    if ($actor['assigned_store_id'] !== $shops[$code] || !in_array('SALES', $actor['roles'], true)) {
        throw new RuntimeException('Shop login assignment differs: ' . $code);
    }
    $passed++;
    $items = $billing->products($actor, $shops[$code]);
    $scanned = $billing->products($actor, $shops[$code], null, $product['barcode']);
    $ownStock = $inventory->list($actor, ['product_id' => $product['id']]);
    if (count($items) !== 1 || $scanned['available_quantity'] !== 1
        || $ownStock['total'] !== 1 || $ownStock['items'][0]['store']['id'] !== $shops[$code]) {
        throw new RuntimeException('Shop product/inventory scoping differs: ' . $code);
    }
    $passed++;
    $foreignCode = $codes[($index + 1) % 8];
    try {
        $billing->products($actor, $shops[$foreignCode]);
        throw new RuntimeException('Foreign shop products were readable');
    } catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
    if ($inventory->list($actor, ['store_id' => $shops[$foreignCode]])['total'] !== 0) {
        throw new RuntimeException('Foreign shop inventory was readable');
    }
    try {
        $reports->report($actor, 'sales', 'summary', ['store_id' => $shops[$foreignCode]]);
        throw new RuntimeException('Foreign shop report was readable');
    } catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
    $passed++;
    $amount = (string) ((int) $product['selling_price'] - 10);
    $invoice = $billing->create($actor, ['idempotency_key' => 'shop-sale-' . $code,
        'store_id' => $shops[$code], 'customer_name' => 'Local shop fixture',
        'customer_phone' => '9000000000', 'invoice_discount' => 10,
        'items' => [['inventory_id' => $scanned['inventory_id'], 'quantity' => 1]],
        'payments' => [['method' => 'CASH', 'amount' => $amount, 'tendered_amount' => $amount]]]);
    if ($invoice['invoice_status'] !== 'COMPLETED' || $invoice['customer_phone'] !== '9000000000'
        || count($billing->list($actor)) !== 1) {
        throw new RuntimeException('Shop POS/invoice state differs: ' . $code);
    }
    $invoices[$code] = $invoice['id'];
    $passed++;
    $ownReport = $reports->report($actor, 'sales', 'summary', ['preset' => 'TODAY']);
    if (($ownReport['summary']['orders'] ?? null) !== 1) {
        throw new RuntimeException('Shop sales report differs: ' . $code);
    }
    $passed++;
}
foreach ($codes as $index => $code) {
    $actor = $actors[$code];
    $foreignCode = $codes[($index + 1) % 8];
    try {
        $billing->get($actor, $invoices[$foreignCode]);
        throw new RuntimeException('Foreign invoice ID was readable');
    } catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
    try {
        $pdf->invoice($actor, $invoices[$foreignCode]);
        throw new RuntimeException('Foreign invoice PDF was readable');
    } catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
    try {
        $ownInventory = $db->prepare('SELECT id FROM inventory WHERE store_id=? AND product_id=?');
        $ownInventory->execute([$shops[$code], $product['id']]);
        $billing->create($actor, ['idempotency_key' => 'foreign-' . $code,
            'store_id' => $shops[$foreignCode],
            'items' => [['inventory_id' => $ownInventory->fetchColumn(), 'quantity' => 1]],
            'payments' => [['method' => 'CASH', 'amount' => (string) (int) $product['selling_price']]]]);
        throw new RuntimeException('Foreign POS body was accepted');
    } catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
    $passed++;
}
if ((int) $db->query('SELECT COUNT(*) FROM invoices')->fetchColumn() !== 8
    || (int) $db->query('SELECT MIN(available_quantity) FROM inventory')->fetchColumn() < 0) {
    throw new RuntimeException('Shop walkthrough invoice/stock totals differ');
}
echo "php_all_shop_isolation_integration_passed={$passed} shops=8 foreign_access=denied\n";
