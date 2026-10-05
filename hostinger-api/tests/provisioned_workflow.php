<?php
declare(strict_types=1);

use Anicraze\Auth\AuthService;
use Anicraze\Billing\BillingService;
use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;
use Anicraze\Inventory\InventoryService;
use Anicraze\Inventory\ReceiptService;
use Anicraze\Inventory\TransferService;

require dirname(__DIR__) . '/vendor/autoload.php';

if (!str_starts_with((string) getenv('DB_NAME'), 'anicraze_phase5b_workflow')) {
    throw new RuntimeException('Workflow test requires isolated disposable database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== getenv('DB_NAME')) {
    throw new RuntimeException('Database identity mismatch');
}
$auth = new AuthService($db);
$ownerLogin = $auth->login('owner@anicraze.in', getenv('ANICRAZE_OWNER_PASSWORD'), false);
$salesLogin = $auth->login('elpro@anicraze.in', getenv('ANICRAZE_ELPRO_PASSWORD'), false);
$owner = $auth->authenticate($ownerLogin['access_token']);
$sales = $auth->authenticate($salesLogin['access_token']);
if (!in_array('OWNER', $owner['roles'], true) || !in_array('SALES', $sales['roles'], true)) {
    throw new RuntimeException('Provisioned account role mismatch');
}
$passed = 1;
$warehouseId = $db->query("SELECT id FROM warehouses WHERE code='ANICRAZE_CWH'")->fetchColumn();
$elproId = $db->query("SELECT id FROM stores WHERE code='ELPRO'")->fetchColumn();
$westendId = $db->query("SELECT id FROM stores WHERE code='WESTEND'")->fetchColumn();
$product = $db->query('SELECT id,barcode FROM products ORDER BY sku LIMIT 1')->fetch();
$receipts = new ReceiptService($db);
$receipt = $receipts->create($owner, ['warehouse_id' => $warehouseId, 'supplier_id' => null,
    'items' => [['product_id' => $product['id'], 'quantity' => 3, 'unit_cost' => 400]]]);
if ((int) $db->query('SELECT SUM(available_quantity) FROM inventory')->fetchColumn() !== 0) {
    throw new RuntimeException('Receipt creation added stock before godown confirmation');
}
$passed++;
for ($i = 0; $i < 3; $i++) {
    $receipts->scan($owner, $receipt['id'], $product['barcode'], \Anicraze\Database\Uuid::v4());
}
$receipts->finalize($owner, $receipt['id']);
$passed++;
$transfers = new TransferService($db);
$transfer = $transfers->create($owner, ['idempotency_key' => 'workflow-' . bin2hex(random_bytes(16)),
    'source_warehouse_id' => $warehouseId, 'target_store_id' => $elproId,
    'items' => [['product_id' => $product['id'], 'quantity' => 2]]]);
if ($transfer['status'] !== 'COMPLETED') {
    throw new RuntimeException('Direct transfer failed');
}
$passed++;
$inventory = new InventoryService($db);
$shopStock = $inventory->list($sales, ['product_id' => $product['id']]);
if ($shopStock['total'] !== 1 || $shopStock['items'][0]['available_quantity'] !== 2
    || $inventory->list($sales, ['store_id' => $westendId])['total'] !== 0) {
    throw new RuntimeException('Assigned-shop stock isolation differs');
}
$passed++;
$billing = new BillingService($db);
$posProduct = $billing->products($sales, $elproId, null, $product['barcode']);
$payload = ['idempotency_key' => 'workflow-sale-' . bin2hex(random_bytes(16)),
    'store_id' => $elproId, 'customer_name' => 'Local simulated customer', 'invoice_discount' => 10,
    'items' => [['inventory_id' => $posProduct['inventory_id'], 'quantity' => 1]],
    'payments' => [['method' => 'CASH', 'amount' => $posProduct['price'] - 10,
        'tendered_amount' => $posProduct['price'] - 10]]];
$invoice = $billing->create($sales, $payload);
if ($invoice['invoice_status'] !== 'COMPLETED' || count($invoice['payments']) !== 1) {
    throw new RuntimeException('Simulated sale failed');
}
$passed++;
if ($billing->create($sales, $payload)['id'] !== $invoice['id'] || $billing->products($sales, $elproId, null, $product['barcode'])['available_quantity'] !== 1) {
    throw new RuntimeException('Sale replay moved stock twice');
}
$passed++;
try {
    $billing->get(['id' => $sales['id'], 'roles' => ['SALES'], 'assigned_store_id' => $westendId], $invoice['id']);
    throw new RuntimeException('Cross-shop invoice leak');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
$passed++;
echo "php_provisioned_workflow_passed={$passed} pdf=not_implemented reports=not_implemented\n";
