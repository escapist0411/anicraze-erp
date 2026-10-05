<?php
declare(strict_types=1);

use Anicraze\Billing\BillingService;
use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;

require dirname(__DIR__) . '/vendor/autoload.php';

if (!str_starts_with((string) getenv('DB_NAME'), 'anicraze_phase5b_workflow_cancel')) {
    throw new RuntimeException('Cancellation test requires its disposable local database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== getenv('DB_NAME')) {
    throw new RuntimeException('Connected database identity mismatch');
}
$invoiceId = $db->query('SELECT id FROM invoices ORDER BY created_at DESC LIMIT 1')->fetchColumn();
$ownerId = $db->query("SELECT id FROM users WHERE email='owner@anicraze.in'")->fetchColumn();
$managerId = $db->query("SELECT id FROM users WHERE email='manager@anicraze.in'")->fetchColumn();
$sales = $db->query("SELECT id,assigned_store_id FROM users WHERE email='elpro@anicraze.in'")->fetch();
if (!$invoiceId || !$ownerId || !$managerId || !$sales) {
    throw new RuntimeException('Disposable sale fixture is missing');
}
$owner = ['id' => $ownerId, 'roles' => ['OWNER']];
$manager = ['id' => $managerId, 'roles' => ['MANAGER']];
$employee = ['id' => $sales['id'], 'roles' => ['SALES'], 'assigned_store_id' => $sales['assigned_store_id']];
$service = new BillingService($db);
$items = $db->prepare('SELECT inventory_id,quantity FROM invoice_items WHERE invoice_id=?');
$items->execute([$invoiceId]);
$sold = $items->fetchAll();
$before = [];
foreach ($sold as $item) {
    $balance = $db->prepare('SELECT available_quantity FROM inventory WHERE id=?');
    $balance->execute([$item['inventory_id']]);
    $before[$item['inventory_id']] = (int) $balance->fetchColumn();
}
$passed = 0;
foreach ([$manager, $employee] as $actor) {
    try {
        $service->cancel($actor, $invoiceId, 'Unauthorized fixture');
        throw new RuntimeException('Non-Owner cancelled invoice');
    } catch (ApiException $error) {
        if ($error->status !== 403) {
            throw $error;
        }
    }
    $passed++;
}
$cancelled = $service->cancel($owner, $invoiceId, 'Local cancellation test');
if ($cancelled['invoice_status'] !== 'CANCELLED' || $cancelled['payment_status'] !== 'CANCELLED') {
    throw new RuntimeException('Invoice/payment state was not cancelled');
}
$passed++;
foreach ($sold as $item) {
    $balance = $db->prepare('SELECT available_quantity FROM inventory WHERE id=?');
    $balance->execute([$item['inventory_id']]);
    if ((int) $balance->fetchColumn() !== $before[$item['inventory_id']] + (int) $item['quantity']) {
        throw new RuntimeException('Cancelled invoice stock was not restored exactly once');
    }
}
$passed++;
$movement = $db->prepare("SELECT COUNT(*) FROM inventory_movements WHERE reference_id=? AND idempotency_key LIKE 'invoice-cancel:%'");
$movement->execute([$invoiceId]);
if ((int) $movement->fetchColumn() !== count($sold)) {
    throw new RuntimeException('Cancellation ledger count differs');
}
$passed++;
try {
    $service->cancel($owner, $invoiceId, 'Second cancellation');
    throw new RuntimeException('Invoice cancelled twice');
} catch (ApiException $error) {
    if ($error->status !== 409) {
        throw $error;
    }
}
$movement->execute([$invoiceId]);
if ((int) $movement->fetchColumn() !== count($sold)) {
    throw new RuntimeException('Retry duplicated stock movement');
}
$passed++;
$statuses = $db->prepare('SELECT COUNT(*) FROM payments WHERE invoice_id=? AND status=\'CANCELLED\'');
$statuses->execute([$invoiceId]);
if ((int) $statuses->fetchColumn() !== count($cancelled['payments'])) {
    throw new RuntimeException('Payment rows were not cancelled');
}
$passed++;
echo "php_cancellation_integration_passed={$passed}\n";
