<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;
use Anicraze\Notifications\NotificationService;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_product5c2') {
    throw new RuntimeException('Notification test requires its disposable database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_product5c2') {
    throw new RuntimeException('Database identity mismatch');
}
$ownerId = $db->query("SELECT id FROM users WHERE email='owner@anicraze.in'")->fetchColumn();
$managerId = $db->query("SELECT id FROM users WHERE email='manager@anicraze.in'")->fetchColumn();
$salesId = $db->query("SELECT id FROM users WHERE email='elpro@anicraze.in'")->fetchColumn();
if (!$ownerId || !$managerId || !$salesId) { throw new RuntimeException('Local accounts missing'); }
$owner = ['id' => $ownerId, 'roles' => ['OWNER']];
$manager = ['id' => $managerId, 'roles' => ['MANAGER']];
$sales = ['id' => $salesId, 'roles' => ['SALES']];
$service = new NotificationService($db);
$passed = 0;
$key = 'local:test:' . bin2hex(random_bytes(10));
$title = 'Local notification test ' . substr($key, -8);
$service->emitToOperators($key, 'INVENTORY', 'HIGH', $title, 'Disposable alert', 'INVENTORY', null, 'inventory');
$onlyTest = static fn (array $rows): array => array_values(array_filter($rows, static fn (array $row): bool => $row['title'] === $title));
$ownerRows = $onlyTest($service->list($owner, ['category' => 'INVENTORY', 'unread' => true]));
$managerRows = $onlyTest($service->list($manager, ['category' => 'INVENTORY', 'unread' => true]));
if (count($ownerRows) !== 1 || count($managerRows) !== 1 || $ownerRows[0]['id'] === $managerRows[0]['id']) {
    throw new RuntimeException('Operator recipient isolation differs');
}
$passed++;
$service->emitToOperators($key, 'INVENTORY', 'HIGH', $title, 'Disposable alert', 'INVENTORY', null, 'inventory');
if (count($onlyTest($service->list($owner))) !== 1) { throw new RuntimeException('Notification deduplication failed'); }
$passed++;
$ownerUnreadBefore = $service->summary($owner)['unread_count'];
if ($ownerUnreadBefore < 1) { throw new RuntimeException('Unread summary differs'); }
$passed++;
$read = $service->markRead($owner, $ownerRows[0]['id']);
if (!$read['is_read'] || $service->summary($owner)['unread_count'] !== $ownerUnreadBefore - 1
    || count($onlyTest($service->list($manager, ['unread' => true]))) !== 1) {
    throw new RuntimeException('Mark-read scope differs');
}
$passed++;
try {
    $service->markRead($owner, $managerRows[0]['id']);
    throw new RuntimeException('Owner read another user notification');
} catch (ApiException $error) { if ($error->status !== 404) { throw $error; } }
$passed++;
if ($service->markAllRead($manager) < 1 || $service->summary($manager)['unread_count'] !== 0) {
    throw new RuntimeException('Manager mark-all-read differs');
}
$passed++;
try {
    $service->list($sales);
    throw new RuntimeException('SALES read protected notifications');
} catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
$passed++;
echo "php_notifications_integration_passed={$passed}\n";
