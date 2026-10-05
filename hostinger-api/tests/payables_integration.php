<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Finance\PayableService;
use Anicraze\Finance\SupplierService;
use Anicraze\Http\ApiException;
use Anicraze\Inventory\ReceiptService;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_product5c2') {
    throw new RuntimeException('Payables test requires its disposable database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_product5c2') {
    throw new RuntimeException('Database identity mismatch');
}
$ownerId = $db->query("SELECT id FROM users WHERE email='owner@anicraze.in'")->fetchColumn();
$managerId = $db->query("SELECT id FROM users WHERE email='manager@anicraze.in'")->fetchColumn();
$productId = $db->query("SELECT id FROM products WHERE status='ACTIVE' AND deleted_at IS NULL ORDER BY id LIMIT 1")->fetchColumn();
$warehouseId = $db->query("SELECT id FROM warehouses WHERE code='ANICRAZE_CWH'")->fetchColumn();
if (!$ownerId || !$managerId || !$productId || !$warehouseId) { throw new RuntimeException('Local fixtures missing'); }
$owner = ['id' => $ownerId, 'roles' => ['OWNER']];
$manager = ['id' => $managerId, 'roles' => ['MANAGER']];
$sales = ['id' => $managerId, 'roles' => ['SALES']];
$suppliers = new SupplierService($db);
$payables = new PayableService($db);
$receipts = new ReceiptService($db);
$passed = 0;
$supplier = $suppliers->create($owner, ['display_name' => 'Local Test Supplier', 'company_name' => 'Local Test Supplier Company']);
if ($supplier['status'] !== 'ACTIVE' || $supplier['outstanding_balance'] !== '0.00') {
    throw new RuntimeException('Supplier creation response differs');
}
$passed++;
if (count($suppliers->receiptChoices($manager)) < 1) { throw new RuntimeException('Manager cannot select supplier'); }
$passed++;
try {
    $suppliers->list($manager);
    throw new RuntimeException('Manager read owner supplier balances');
} catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
$passed++;
$key = 'payable-test-' . bin2hex(random_bytes(10));
$future = gmdate('Y-m-d\TH:i:s\Z', time() + 2 * 86400);
$due = gmdate('Y-m-d', time() + 7 * 86400);
$payload = ['idempotency_key' => $key, 'supplier_id' => $supplier['id'], 'total_amount' => '1000.00',
    'initially_paid' => '100.00', 'initial_payment_method' => 'UPI', 'due_date' => $due, 'remind_at' => $future];
$payable = $payables->create($owner, $payload);
if ($payable['status'] !== 'PARTIALLY_PAID' || $payable['pending_amount'] !== '900.00'
    || count($payable['payments']) !== 1 || count($payable['reminders']) !== 1) {
    throw new RuntimeException('Initial payable state differs');
}
$passed++;
$replay = $payables->create($owner, $payload);
if ($replay['id'] !== $payable['id']) { throw new RuntimeException('Payable replay duplicated record'); }
$passed++;
try {
    $payables->create($owner, [...$payload, 'total_amount' => '2000.00']);
    throw new RuntimeException('Payable key conflict was accepted');
} catch (ApiException $error) { if ($error->status !== 409) { throw $error; } }
$passed++;
$paymentKey = 'payment-test-' . bin2hex(random_bytes(10));
$paymentPayload = ['idempotency_key' => $paymentKey, 'amount' => '200.00', 'payment_method' => 'CASH'];
$paid = $payables->recordPayment($owner, $payable['id'], $paymentPayload);
if ($paid['pending_amount'] !== '700.00' || count($paid['payments']) !== 2) {
    throw new RuntimeException('Recorded payment state differs');
}
$passed++;
$paidAgain = $payables->recordPayment($owner, $payable['id'], $paymentPayload);
if ($paidAgain['pending_amount'] !== '700.00' || count($paidAgain['payments']) !== 2) {
    throw new RuntimeException('Payment replay duplicated transaction');
}
$passed++;
try {
    $payables->recordPayment($owner, $payable['id'], [...$paymentPayload, 'amount' => '701.00',
        'idempotency_key' => 'overpayment-' . bin2hex(random_bytes(8))]);
    throw new RuntimeException('Overpayment succeeded');
} catch (ApiException $error) { if ($error->status !== 409) { throw $error; } }
$passed++;
$summary = $payables->summary($owner);
if ($summary['total_pending'] !== '700.00' || count($payables->list($owner)) !== 1) {
    throw new RuntimeException('Payable summary/list differs');
}
$passed++;
try {
    $payables->list($manager);
    throw new RuntimeException('Manager read owner payables');
} catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
$passed++;
$line = ['product_id' => $productId, 'quantity' => 2, 'unit_cost' => 25];
$plain = $receipts->create($manager, ['warehouse_id' => $warehouseId, 'supplier_id' => null, 'items' => [$line]]);
if ($plain['supplier_name'] !== null) { throw new RuntimeException('Supplier-free manager receipt failed'); }
$passed++;
$withSupplier = $receipts->create($manager, ['warehouse_id' => $warehouseId, 'supplier_id' => $supplier['id'], 'items' => [$line]]);
if ($withSupplier['supplier_name'] !== $supplier['display_name']) {
    throw new RuntimeException('Manager receipt supplier reference differs');
}
$passed++;
try {
    $receipts->create($manager, ['warehouse_id' => $warehouseId, 'supplier_id' => $supplier['id'],
        'payment_option' => 'PAY_LATER', 'items' => [$line]]);
    throw new RuntimeException('Manager created owner payable');
} catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
$passed++;
try {
    $receipts->create($owner, ['warehouse_id' => $warehouseId, 'supplier_id' => null,
        'payment_option' => 'PAY_LATER', 'items' => [$line]]);
    throw new RuntimeException('Owner payable without supplier succeeded');
} catch (ApiException $error) { if ($error->status !== 422) { throw $error; } }
$passed++;
$tracked = $receipts->create($owner, ['warehouse_id' => $warehouseId, 'supplier_id' => $supplier['id'],
    'payment_option' => 'PAY_LATER', 'items' => [$line]]);
$list = $payables->list($owner);
$linked = array_values(array_filter($list, static fn (array $p): bool => $p['stock_receipt_id'] === $tracked['id']));
if (count($linked) !== 1 || $linked[0]['pending_amount'] !== '50.00') {
    throw new RuntimeException('Receipt payable link differs');
}
$passed++;
try {
    $suppliers->receiptChoices($sales);
    throw new RuntimeException('SALES read supplier choices');
} catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
$passed++;
echo "php_payables_integration_passed={$passed}\n";
