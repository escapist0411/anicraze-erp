<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;
use Anicraze\Inventory\InventoryService;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_local') {
    throw new RuntimeException('Inventory integration test requires disposable local database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_local') {
    throw new RuntimeException('Database identity mismatch');
}
$storeA = $db->query("SELECT id FROM stores WHERE code='ELPRO'")->fetchColumn();
$storeB = $db->query("SELECT id FROM stores WHERE code='WESTEND'")->fetchColumn();
$warehouseId = $db->query("SELECT id FROM warehouses WHERE code='ANICRAZE_CWH'")->fetchColumn();
$service = new InventoryService($db);
$owner = ['roles' => ['OWNER']];
$sales = ['roles' => ['SALES'], 'assigned_store_id' => $storeA];
$passed = 0;
if ($service->list($owner, ['page_size' => 100])['total'] !== 1440) {
    throw new RuntimeException('Global zero-stock inventory count differs');
}
$passed++;
if ($service->list($sales, ['page_size' => 100])['total'] !== 160) {
    throw new RuntimeException('Assigned shop inventory count differs');
}
$passed++;
if ($service->list($sales, ['store_id' => $storeB])['total'] !== 0
    || $service->list($sales, ['warehouse_id' => $warehouseId])['total'] !== 0) {
    throw new RuntimeException('Query filters bypassed assigned-shop scope');
}
$passed++;
if (count($service->locations($sales, 'stores')) !== 1 || count($service->locations($owner, 'stores')) !== 8) {
    throw new RuntimeException('Location scope differs');
}
$passed++;
try {
    $service->locations($sales, 'warehouses');
    throw new RuntimeException('SALES read warehouse locations');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
$passed++;
$otherInventory = $db->query("SELECT id FROM inventory WHERE store_id='{$storeB}' LIMIT 1")->fetchColumn();
if ($service->movements($sales, ['inventory_id' => $otherInventory]) !== []) {
    throw new RuntimeException('Known inventory ID leaked another shop ledger');
}
$passed++;
if (count($service->stockReport($owner)) !== 1440) {
    throw new RuntimeException('Complete stock report row count differs');
}
$passed++;
$summary = $service->summary($owner);
$expectedAvailable = (int) $db->query('SELECT COALESCE(SUM(available_quantity),0) FROM inventory')->fetchColumn();
if ($summary['total_available_quantity'] !== $expectedAvailable || count($summary['store_comparison']) !== 8
    || count($summary['warehouse_comparison']) !== 1) {
    throw new RuntimeException('Inventory summary does not match authoritative balances');
}
$passed++;
try {
    $service->summary($sales);
    throw new RuntimeException('SALES read global inventory summary');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
$passed++;
echo "php_inventory_integration_passed={$passed}\n";
