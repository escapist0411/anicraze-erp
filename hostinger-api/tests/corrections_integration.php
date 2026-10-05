<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;
use Anicraze\Inventory\CorrectionService;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_product5c2') {
    throw new RuntimeException('Correction test requires its disposable database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_product5c2') {
    throw new RuntimeException('Database identity mismatch');
}
$ownerId = $db->query("SELECT id FROM users WHERE email='owner@anicraze.in'")->fetchColumn();
$warehouseId = $db->query("SELECT id FROM warehouses WHERE code='ANICRAZE_CWH'")->fetchColumn();
$inventory = $db->prepare('SELECT id FROM inventory WHERE warehouse_id=? ORDER BY product_id LIMIT 1');
$inventory->execute([$warehouseId]);
$inventoryId = $inventory->fetchColumn();
if (!$ownerId || !$inventoryId) { throw new RuntimeException('Disposable fixtures missing'); }
$owner = ['id' => $ownerId, 'roles' => ['OWNER']];
$sales = ['id' => $ownerId, 'roles' => ['SALES'], 'assigned_store_id' => null];
$service = new CorrectionService($db);
$passed = 0;
$adjustment = $service->adjust($owner, ['reference_number' => 'PHASE5C-ADJ-1', 'reason' => 'Local physical count',
    'items' => [['inventory_id' => $inventoryId, 'quantity_change' => 10, 'remarks' => 'Disposable test']]]);
if ($adjustment['status'] !== 'COMPLETED' || count($adjustment['items']) !== 1) {
    throw new RuntimeException('Adjustment response differs');
}
$passed++;
$quantity = $db->prepare('SELECT available_quantity,damaged_quantity FROM inventory WHERE id=?');
$quantity->execute([$inventoryId]);
$balance = $quantity->fetch();
if ((int) $balance['available_quantity'] !== 10 || (int) $balance['damaged_quantity'] !== 0) {
    throw new RuntimeException('Adjustment balance differs');
}
$passed++;
$repeat = $service->adjust($owner, ['reference_number' => 'PHASE5C-ADJ-1', 'reason' => 'Local physical count',
    'items' => [['inventory_id' => $inventoryId, 'quantity_change' => 10, 'remarks' => 'Disposable test']]]);
if ($repeat['id'] !== $adjustment['id']) { throw new RuntimeException('Adjustment replay was not idempotent'); }
$passed++;
try {
    $service->adjust($owner, ['reference_number' => 'PHASE5C-ADJ-1', 'reason' => 'Local physical count',
        'items' => [['inventory_id' => $inventoryId, 'quantity_change' => 20]]]);
    throw new RuntimeException('Different adjustment reused reference');
} catch (ApiException $error) { if ($error->status !== 409) { throw $error; } }
$passed++;
try {
    $service->adjust($owner, ['reference_number' => 'PHASE5C-ADJ-NEGATIVE', 'reason' => 'Invalid decrease',
        'items' => [['inventory_id' => $inventoryId, 'quantity_change' => -11]]]);
    throw new RuntimeException('Negative stock adjustment succeeded');
} catch (ApiException $error) { if ($error->status !== 409) { throw $error; } }
$passed++;
try {
    $service->adjust($sales, ['reference_number' => 'PHASE5C-SALES-ADJ', 'reason' => 'Forbidden',
        'items' => [['inventory_id' => $inventoryId, 'quantity_change' => 1]]]);
    throw new RuntimeException('SALES adjusted stock');
} catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
$passed++;
$damage = ['quantity' => 3, 'reference_number' => 'PHASE5C-DMG-1', 'idempotency_key' => 'phase5c-damage-1',
    'remarks' => 'Disposable damage test'];
$result = $service->damage($owner, $inventoryId, $damage);
if ($result['available_quantity'] !== 7 || $result['damaged_quantity'] !== 3) {
    throw new RuntimeException('Damage balance differs');
}
$passed++;
$result = $service->damage($owner, $inventoryId, $damage);
if ($result['available_quantity'] !== 7 || $result['damaged_quantity'] !== 3) {
    throw new RuntimeException('Damage replay changed stock');
}
$passed++;
try {
    $service->damage($owner, $inventoryId, [...$damage, 'quantity' => 4]);
    throw new RuntimeException('Different damage reused idempotency key');
} catch (ApiException $error) { if ($error->status !== 409) { throw $error; } }
$passed++;
try {
    $service->damage($owner, $inventoryId, [...$damage, 'idempotency_key' => 'phase5c-damage-too-many', 'quantity' => 8]);
    throw new RuntimeException('Damage exceeded available stock');
} catch (ApiException $error) { if ($error->status !== 409) { throw $error; } }
$passed++;
try {
    $service->damage($sales, $inventoryId, [...$damage, 'idempotency_key' => 'phase5c-sales-damage']);
    throw new RuntimeException('SALES marked stock damaged');
} catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
$passed++;
$movements = $db->prepare("SELECT COUNT(*) FROM inventory_movements WHERE inventory_id=? AND movement_type IN ('ADJUSTMENT','DAMAGE')");
$movements->execute([$inventoryId]);
if ((int) $movements->fetchColumn() !== 2) { throw new RuntimeException('Correction ledger count differs'); }
$passed++;
echo "php_corrections_integration_passed={$passed}\n";
