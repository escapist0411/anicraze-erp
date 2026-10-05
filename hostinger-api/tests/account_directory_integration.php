<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;
use Anicraze\People\AccountDirectoryService;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_product5c2') {
    throw new RuntimeException('Directory test requires its disposable database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_product5c2') {
    throw new RuntimeException('Database identity mismatch');
}
$id = $db->query("SELECT id FROM users WHERE email='manager@anicraze.in'")->fetchColumn();
$service = new AccountDirectoryService($db);
$owner = $service->list(['roles' => ['OWNER']]);
if (count($owner) !== 10) { throw new RuntimeException('Owner approved account count differs'); }
$manager = $service->list(['id' => $id, 'roles' => ['MANAGER']]);
if (count($manager) !== 9 || count(array_filter($manager, static fn (array $row): bool => $row['designation'] === 'OWNER'))) {
    throw new RuntimeException('Manager directory scope differs');
}
foreach ([$owner, $manager] as $rows) {
    foreach ($rows as $row) {
        if (array_key_exists('password_hash', $row) || array_key_exists('token_version', $row)) {
            throw new RuntimeException('Credential field leaked into directory');
        }
    }
}
try {
    $service->list(['roles' => ['SALES']]);
    throw new RuntimeException('SALES read account directory');
} catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
echo "php_account_directory_integration_passed=4\n";
