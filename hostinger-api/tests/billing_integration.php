<?php
declare(strict_types=1);

use Anicraze\Billing\BillingService;
use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_local') {
    throw new RuntimeException('Billing integration test requires disposable local database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_local') {
    throw new RuntimeException('Database identity mismatch');
}
$storeA = $db->query("SELECT id FROM stores WHERE code='ELPRO'")->fetchColumn();
$storeB = $db->query("SELECT id FROM stores WHERE code='WESTEND'")->fetchColumn();
$userId = $db->query('SELECT id FROM users ORDER BY created_at LIMIT 1')->fetchColumn();
$actor = ['id' => $userId, 'roles' => ['SALES'], 'assigned_store_id' => $storeA];
$service = new BillingService($db);
$passed = 0;
$stocked = $service->products($actor, $storeA);
if ($stocked === []) {
    throw new RuntimeException('Simulated shop stock not found');
}
$product = $stocked[0];
$invoiceCountBefore = count($service->list($actor));
$passed++;
try {
    $service->products($actor, $storeB);
    throw new RuntimeException('Cross-shop POS lookup succeeded');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
$passed++;
$payload = ['idempotency_key' => 'local-sale-' . bin2hex(random_bytes(16)), 'store_id' => $storeA,
    'customer_name' => 'Local workflow test', 'invoice_discount' => 0,
    'items' => [['inventory_id' => $product['inventory_id'], 'quantity' => 1]],
    'payments' => [['method' => 'CASH', 'amount' => $product['price'], 'tendered_amount' => $product['price']]]];
$wrong = $payload;
$wrong['payments'][0]['amount'] = 1;
try {
    $service->create($actor, $wrong);
    throw new RuntimeException('Wrong payment amount accepted');
} catch (ApiException $error) {
    if ($error->status !== 422) {
        throw $error;
    }
}
$passed++;
$bill = $service->create($actor, $payload);
if ($bill['invoice_status'] !== 'COMPLETED' || $bill['store_id'] !== $storeA
    || $bill['grand_total'] !== $product['price']) {
    throw new RuntimeException('POS invoice contract differs');
}
$passed++;
$replayed = $service->create($actor, $payload);
if ($replayed['id'] !== $bill['id'] || count($service->list($actor)) !== $invoiceCountBefore + 1) {
    throw new RuntimeException('Invoice idempotency failed');
}
$passed++;
$changed = $payload;
$changed['customer_name'] = 'Different customer';
try {
    $service->create($actor, $changed);
    throw new RuntimeException('Invoice idempotency accepted changed payload');
} catch (ApiException $error) {
    if ($error->status !== 409) {
        throw $error;
    }
}
$passed++;
$remaining = $db->prepare('SELECT available_quantity FROM inventory WHERE id=?');
$remaining->execute([$product['inventory_id']]);
if ((int) $remaining->fetchColumn() !== $product['available_quantity'] - 1) {
    throw new RuntimeException('POS stock movement differs');
}
$passed++;
try {
    $service->get(['id' => $userId, 'roles' => ['SALES'], 'assigned_store_id' => $storeB], $bill['id']);
    throw new RuntimeException('Known invoice ID leaked across shops');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
$passed++;
echo "php_billing_integration_passed={$passed}\n";
