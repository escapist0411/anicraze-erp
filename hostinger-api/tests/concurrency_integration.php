<?php
declare(strict_types=1);

use Anicraze\Billing\BillingService;
use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;
use Anicraze\Inventory\ReceiptService;
use Anicraze\Inventory\TransferService;

require dirname(__DIR__) . '/vendor/autoload.php';

if (!str_starts_with((string) getenv('DB_NAME'), 'anicraze_phase5b_race') || !function_exists('pcntl_fork')) {
    throw new RuntimeException('Concurrency test requires disposable race database and pcntl');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== getenv('DB_NAME')) {
    throw new RuntimeException('Database identity mismatch');
}
$ownerId = $db->query("SELECT id FROM users WHERE email='owner@anicraze.in'")->fetchColumn();
$salesId = $db->query("SELECT id FROM users WHERE email='elpro@anicraze.in'")->fetchColumn();
$warehouse = $db->query("SELECT id FROM warehouses WHERE code='ANICRAZE_CWH'")->fetchColumn();
$elpro = $db->query("SELECT id FROM stores WHERE code='ELPRO'")->fetchColumn();
$ids = $db->query('SELECT id,barcode,selling_price FROM products ORDER BY sku LIMIT 3')->fetchAll();
if (!$ownerId || !$salesId || !$warehouse || !$elpro || count($ids) !== 3) {
    throw new RuntimeException('Race prerequisites missing');
}
$owner = ['id' => $ownerId, 'roles' => ['OWNER']];
$sales = ['id' => $salesId, 'roles' => ['SALES'], 'assigned_store_id' => $elpro];
$receipts = new ReceiptService($db);
foreach ($ids as $product) {
    $receipt = $receipts->create($owner, ['warehouse_id' => $warehouse, 'items' => [
        ['product_id' => $product['id'], 'quantity' => 1, 'unit_cost' => 100],
    ]]);
    $receipts->scan($owner, $receipt['id'], $product['barcode'], \Anicraze\Database\Uuid::v4());
    $receipts->finalize($owner, $receipt['id']);
}
$transfers = new TransferService($db);
$first = $transfers->create($owner, ['idempotency_key' => 'race-setup-' . bin2hex(random_bytes(8)),
    'source_warehouse_id' => $warehouse, 'target_store_id' => $elpro,
    'items' => [['product_id' => $ids[0]['id'], 'quantity' => 1]]]);
if ($first['status'] !== 'COMPLETED') {
    throw new RuntimeException('Race setup transfer failed');
}

$race = static function (callable $work): array {
    $children = [];
    for ($i = 0; $i < 2; $i++) {
        $pid = pcntl_fork();
        if ($pid === -1) {
            throw new RuntimeException('Fork failed');
        }
        if ($pid === 0) {
            try {
                usleep(10000);
                $work($i, Connection::open());
                exit(0);
            } catch (ApiException $error) {
                exit($error->status === 409 ? 10 : 20);
            } catch (Throwable $error) {
                fwrite(STDERR, 'concurrency_worker_error=' . get_class($error)
                    . ($error instanceof PDOException ? ' sqlstate=' . ($error->errorInfo[0] ?? 'unknown') : '') . "\n");
                exit(30);
            }
        }
        $children[] = $pid;
    }
    $codes = [];
    foreach ($children as $pid) {
        pcntl_waitpid($pid, $status);
        $codes[] = pcntl_wexitstatus($status);
    }
    sort($codes);
    return $codes;
};
$inventoryId = $db->query("SELECT id FROM inventory WHERE product_id='{$ids[0]['id']}' AND store_id='{$elpro}'")->fetchColumn();
$saleCodes = $race(static function (int $index, PDO $connection) use ($sales, $elpro, $inventoryId, $ids): void {
    (new BillingService($connection))->create($sales, [
        'idempotency_key' => 'race-sale-' . $index . '-' . $inventoryId,
        'store_id' => $elpro, 'customer_name' => 'Race fixture', 'invoice_discount' => 0,
        'items' => [['inventory_id' => $inventoryId, 'quantity' => 1]],
        'payments' => [['method' => 'CASH', 'amount' => (float) $ids[0]['selling_price']]],
    ]);
});
if ($saleCodes !== [0, 10]) {
    throw new RuntimeException('Last-item POS race did not produce one sale and one stock conflict; codes=' . implode(',', $saleCodes));
}
$db = Connection::open();
$saleCount = (int) $db->query('SELECT COUNT(*) FROM invoices')->fetchColumn();
$remaining = (int) $db->query("SELECT available_quantity FROM inventory WHERE id='{$inventoryId}'")->fetchColumn();
if ($saleCount !== 1 || $remaining !== 0) {
    throw new RuntimeException('Last-item race duplicated sale or oversold stock');
}
$winningSale = $db->query('SELECT id,idempotency_key FROM invoices LIMIT 1')->fetch();
$saleReplay = (new BillingService($db))->create($sales, [
    'idempotency_key' => $winningSale['idempotency_key'], 'store_id' => $elpro,
    'customer_name' => 'Race fixture', 'invoice_discount' => 0,
    'items' => [['inventory_id' => $inventoryId, 'quantity' => 1]],
    'payments' => [['method' => 'CASH', 'amount' => (float) $ids[0]['selling_price']]],
]);
if ($saleReplay['id'] !== $winningSale['id']
    || (int) $db->query('SELECT COUNT(*) FROM invoices')->fetchColumn() !== 1
    || (int) $db->query('SELECT COUNT(*) FROM payments')->fetchColumn() !== 1) {
    throw new RuntimeException('Duplicate POS submission created another sale or payment');
}
$transferCodes = $race(static function (int $index, PDO $connection) use ($owner, $warehouse, $elpro, $ids): void {
    (new TransferService($connection))->create($owner, [
        'idempotency_key' => 'race-transfer-' . $index . '-' . $ids[1]['id'],
        'source_warehouse_id' => $warehouse, 'target_store_id' => $elpro,
        'items' => [['product_id' => $ids[1]['id'], 'quantity' => 1]],
    ]);
});
if ($transferCodes !== [0, 10]) {
    throw new RuntimeException('Transfer race did not produce one movement and one stock conflict; codes=' . implode(',', $transferCodes));
}
$db = Connection::open();
$transferCount = (int) $db->query('SELECT COUNT(*) FROM stock_transfers')->fetchColumn();
if ($transferCount !== 2) {
    throw new RuntimeException('Transfer race duplicated movement');
}
$winningTransfer = $db->query("SELECT id,idempotency_key FROM stock_transfers WHERE idempotency_key LIKE 'race-transfer-%' LIMIT 1")->fetch();
$transferReplay = (new TransferService($db))->create($owner, [
    'idempotency_key' => $winningTransfer['idempotency_key'],
    'source_warehouse_id' => $warehouse, 'target_store_id' => $elpro,
    'items' => [['product_id' => $ids[1]['id'], 'quantity' => 1]],
]);
if ($transferReplay['id'] !== $winningTransfer['id']
    || (int) $db->query('SELECT COUNT(*) FROM stock_transfers')->fetchColumn() !== 2) {
    throw new RuntimeException('Duplicate transfer submission created another transfer');
}
$db = Connection::open();
$receipts = new ReceiptService($db);
$third = $receipts->create($owner, ['warehouse_id' => $warehouse, 'items' => [
    ['product_id' => $ids[2]['id'], 'quantity' => 1, 'unit_cost' => 100],
]]);
$scanId = \Anicraze\Database\Uuid::v4();
$receipts->scan($owner, $third['id'], $ids[2]['barcode'], $scanId);
$scanReplay = $receipts->scan($owner, $third['id'], $ids[2]['barcode'], $scanId);
if ($scanReplay['total_scanned'] !== 1) {
    throw new RuntimeException('Duplicate receipt scan increased quantity twice');
}
$receipts->finalize($owner, $third['id']);
try {
    $receipts->finalize($owner, $third['id']);
    throw new RuntimeException('Duplicate receipt finalization unexpectedly succeeded');
} catch (ApiException $error) {
    if ($error->status !== 409) { throw $error; }
}
$receiptMovement = $db->prepare("SELECT COUNT(*) FROM inventory_movements WHERE reference_type='STOCK_RECEIPT' AND reference_id=?");
$receiptMovement->execute([$third['id']]);
if ((int) $receiptMovement->fetchColumn() !== 1) {
    throw new RuntimeException('Duplicate receipt finalization created another stock movement');
}
echo "php_concurrency_integration_passed=7 last_item=one_sale transfer=one_move replay=no_duplicates\n";
