<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;
use Anicraze\Inventory\ReceiptService;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_local') {
    throw new RuntimeException('Receipt integration test requires disposable local database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_local') {
    throw new RuntimeException('Database identity mismatch');
}
$userId = $db->query('SELECT id FROM users ORDER BY created_at LIMIT 1')->fetchColumn();
$warehouseId = $db->query("SELECT id FROM warehouses WHERE code='ANICRAZE_CWH'")->fetchColumn();
$product = $db->query('SELECT id,barcode FROM products ORDER BY sku LIMIT 1')->fetch();
if (!$userId || !$warehouseId || !$product) {
    throw new RuntimeException('Local rehearsal prerequisites are missing');
}
$owner = ['id' => $userId, 'roles' => ['OWNER']];
$manager = ['id' => $userId, 'roles' => ['MANAGER']];
$sales = ['id' => $userId, 'roles' => ['SALES']];
$service = new ReceiptService($db);
$passed = 0;
$before = (int) $db->query("SELECT available_quantity FROM inventory WHERE product_id='{$product['id']}' AND warehouse_id='{$warehouseId}'")->fetchColumn();
$receipt = $service->create($manager, ['warehouse_id' => $warehouseId, 'supplier_id' => null,
    'items' => [['product_id' => $product['id'], 'quantity' => 2, 'unit_cost' => 400]]]);
if ($receipt['status'] !== 'READY_FOR_SCAN' || $receipt['total_expected'] !== 2) {
    throw new RuntimeException('Receipt creation failed');
}
$passed++;
$afterCreate = (int) $db->query("SELECT available_quantity FROM inventory WHERE product_id='{$product['id']}' AND warehouse_id='{$warehouseId}'")->fetchColumn();
if ($afterCreate !== $before) {
    throw new RuntimeException('Receipt creation incorrectly increased stock');
}
$passed++;
try {
    $service->finalize($owner, $receipt['id']);
    throw new RuntimeException('Incomplete receipt finalized');
} catch (ApiException $error) {
    if ($error->status !== 409) {
        throw $error;
    }
}
$passed++;
$firstScanId = \Anicraze\Database\Uuid::v4();
$service->scan($manager, $receipt['id'], ' ' . strtolower($product['barcode']) . ' ', $firstScanId);
$replayedScan = $service->scan($manager, $receipt['id'], strtolower($product['barcode']), $firstScanId);
if ($replayedScan['total_scanned'] !== 1) {
    throw new RuntimeException('Replayed scan incremented twice');
}
$passed++;
$scanned = $service->scan($manager, $receipt['id'], $product['barcode'], \Anicraze\Database\Uuid::v4());
if ($scanned['total_scanned'] !== 2) {
    throw new RuntimeException('Receipt scan count differs');
}
$passed++;
$complete = $service->finalize($manager, $receipt['id']);
$after = (int) $db->query("SELECT available_quantity FROM inventory WHERE product_id='{$product['id']}' AND warehouse_id='{$warehouseId}'")->fetchColumn();
if ($complete['status'] !== 'COMPLETED' || $after !== $before + 2) {
    throw new RuntimeException('Godown stock movement differs');
}
$passed++;
try {
    $service->finalize($owner, $receipt['id']);
    throw new RuntimeException('Receipt finalized twice');
} catch (ApiException $error) {
    if ($error->status !== 409) {
        throw $error;
    }
}
$passed++;
try {
    $service->create($sales, ['warehouse_id' => $warehouseId, 'items' => [['product_id' => $product['id'], 'quantity' => 1, 'unit_cost' => 1]]]);
    throw new RuntimeException('SALES created a warehouse receipt');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
$passed++;
try {
    $service->create($owner, ['warehouse_id' => $warehouseId, 'payment_option' => 'PAY_LATER',
        'items' => [['product_id' => $product['id'], 'quantity' => 1, 'unit_cost' => 1]]]);
    throw new RuntimeException('Unsupported payable was accepted');
} catch (ApiException $error) {
    if ($error->status !== 422) {
        throw $error;
    }
}
$passed++;
echo "php_receipt_integration_passed={$passed}\n";
