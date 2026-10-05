<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;
use Anicraze\Inventory\TransferService;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_local') {
    throw new RuntimeException('Transfer integration test requires disposable local database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_local') {
    throw new RuntimeException('Database identity mismatch');
}
$userId = $db->query('SELECT id FROM users ORDER BY created_at LIMIT 1')->fetchColumn();
$warehouseId = $db->query("SELECT id FROM warehouses WHERE code='ANICRAZE_CWH'")->fetchColumn();
$storeId = $db->query("SELECT id FROM stores WHERE code='ELPRO'")->fetchColumn();
$product = $db->query('SELECT id FROM products ORDER BY sku LIMIT 1')->fetchColumn();
if (!$userId || !$warehouseId || !$storeId || !$product) {
    throw new RuntimeException('Local rehearsal prerequisites are missing');
}
$owner = ['id' => $userId, 'roles' => ['OWNER']];
$service = new TransferService($db);
$passed = 0;
$stock = $db->prepare('SELECT available_quantity FROM inventory WHERE product_id=? AND warehouse_id <=> ? AND store_id <=> ?');
$stock->execute([$product, $warehouseId, null]);
$sourceBefore = (int) $stock->fetchColumn();
$stock->execute([$product, null, $storeId]);
$targetBefore = (int) $stock->fetchColumn();
$payload = ['idempotency_key' => 'local-' . bin2hex(random_bytes(16)),
    'source_warehouse_id' => $warehouseId, 'source_store_id' => null,
    'target_store_id' => $storeId, 'target_warehouse_id' => null,
    'items' => [['product_id' => $product, 'quantity' => 1]], 'remarks' => 'Local integration test'];
$transfer = $service->create($owner, $payload);
if ($transfer['status'] !== 'COMPLETED' || count($transfer['items']) !== 1) {
    throw new RuntimeException('Direct transfer contract differs');
}
$passed++;
$stock->execute([$product, $warehouseId, null]);
$sourceAfter = (int) $stock->fetchColumn();
$stock->execute([$product, null, $storeId]);
$targetAfter = (int) $stock->fetchColumn();
if ($sourceAfter !== $sourceBefore - 1 || $targetAfter !== $targetBefore + 1) {
    throw new RuntimeException('Direct transfer stock movement differs');
}
$passed++;
$replayed = $service->create($owner, $payload);
if ($replayed['id'] !== $transfer['id']) {
    throw new RuntimeException('Direct transfer replay duplicated');
}
$passed++;
$stock->execute([$product, $warehouseId, null]);
if ((int) $stock->fetchColumn() !== $sourceAfter) {
    throw new RuntimeException('Direct transfer replay moved stock again');
}
$passed++;
try {
    $changed = $payload;
    $changed['items'][0]['quantity'] = 2;
    $service->create($owner, $changed);
    throw new RuntimeException('Idempotency key accepted changed payload');
} catch (ApiException $error) {
    if ($error->status !== 409) {
        throw $error;
    }
}
$passed++;
try {
    $tooMuch = $payload;
    $tooMuch['idempotency_key'] = 'local-' . bin2hex(random_bytes(16));
    $tooMuch['items'][0]['quantity'] = $sourceAfter + 1;
    $service->create($owner, $tooMuch);
    throw new RuntimeException('Oversell transfer succeeded');
} catch (ApiException $error) {
    if ($error->status !== 409) {
        throw $error;
    }
}
$passed++;
try {
    $service->get(['id' => $userId, 'roles' => ['SALES']], $transfer['id']);
    throw new RuntimeException('SALES read a transfer');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
$passed++;
echo "php_transfer_integration_passed={$passed}\n";
