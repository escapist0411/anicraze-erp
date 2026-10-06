<?php
declare(strict_types=1);

use Anicraze\Config\Environment;
use Anicraze\Config\DatabaseTargetGuard;
use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;

require dirname(__DIR__) . '/vendor/autoload.php';
Environment::load(dirname(__DIR__));

if (PHP_SAPI !== 'cli' || Environment::optional('ALLOW_ACCOUNT_PROVISIONING') !== '1') {
    throw new RuntimeException('Account provisioning requires explicit CLI confirmation');
}
$name = Environment::required('DB_NAME');
DatabaseTargetGuard::assertApproved($name);
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== $name) {
    throw new RuntimeException('Connected database identity differs');
}
$accounts = [
    ['owner@anicraze.in', 'ANICRAZE Owner', 'OWNER', null, 'ANICRAZE_OWNER_PASSWORD'],
    ['manager@anicraze.in', 'ANICRAZE Manager', 'MANAGER', null, 'ANICRAZE_MANAGER_PASSWORD'],
    ['elpro@anicraze.in', 'ANICRAZE ELPRO', 'SALES', 'ELPRO', 'ANICRAZE_ELPRO_PASSWORD'],
    ['westend@anicraze.in', 'ANICRAZE WESTEND', 'SALES', 'WESTEND', 'ANICRAZE_WESTEND_PASSWORD'],
    ['civil@anicraze.in', 'ANICRAZE CIVIL', 'SALES', 'CIVIL', 'ANICRAZE_CIVIL_PASSWORD'],
    ['swargate@anicraze.in', 'ANICRAZE SWARGATE', 'SALES', 'SWARGATE', 'ANICRAZE_SWARGATE_PASSWORD'],
    ['kalyani@anicraze.in', 'ANICRAZE KALYANI', 'SALES', 'KALYANI', 'ANICRAZE_KALYANI_PASSWORD'],
    ['shivaji@anicraze.in', 'ANICRAZE SHIVAJI', 'SALES', 'SHIVAJI', 'ANICRAZE_SHIVAJI_PASSWORD'],
    ['event.1@anicraze.in', 'ANICRAZE EVENT 1', 'SALES', 'EVENT1', 'ANICRAZE_EVENT1_PASSWORD'],
    ['event.2@anicraze.in', 'ANICRAZE EVENT 2', 'SALES', 'EVENT2', 'ANICRAZE_EVENT2_PASSWORD'],
];
$new = [];
foreach ($accounts as [$email, , , , $variable]) {
    $statement = $db->prepare('SELECT id FROM users WHERE email=?');
    $statement->execute([$email]);
    if ($statement->fetchColumn() === false) {
        $password = Environment::required($variable);
        if (strlen($password) < 12 || strlen($password) > 128) {
            throw new RuntimeException("Missing valid password environment variable for new account: {$variable}");
        }
        $new[$email] = $password;
    }
}
$grants = [
    'OWNER' => ['*'],
    'MANAGER' => ['dashboard.read', 'products.read', 'inventory.read', 'inventory.transfer',
        'inventory.adjust', 'stores.read', 'billing.read', 'billing.create', 'reports.sales.read',
        'reports.inventory.read', 'stock_receipts.read', 'stock_receipts.create'],
    'SALES' => ['dashboard.read', 'products.read', 'inventory.read', 'stores.read',
        'billing.read', 'billing.create', 'customers.read', 'profile.read'],
];
$created = Connection::transaction($db, static function () use ($db, $accounts, $new, $grants): int {
    $roleIds = [];
    $findRole = $db->prepare('SELECT id FROM roles WHERE code=?');
    foreach ($grants as $role => $permissions) {
        $findRole->execute([$role]);
        $id = $findRole->fetchColumn();
        if ($id === false) {
            $id = Uuid::v4();
            $db->prepare('INSERT INTO roles (id,code,name) VALUES (?,?,?)')->execute([$id, $role, $role]);
        }
        $roleIds[$role] = $id;
        foreach ($permissions as $code) {
            $query = $db->prepare('SELECT id FROM permissions WHERE code=?');
            $query->execute([$code]);
            $permissionId = $query->fetchColumn();
            if ($permissionId === false) {
                $permissionId = Uuid::v4();
                $db->prepare('INSERT INTO permissions (id,code) VALUES (?,?)')->execute([$permissionId, $code]);
            }
            $db->prepare('INSERT IGNORE INTO role_permissions (role_id,permission_id) VALUES (?,?)')->execute([$id, $permissionId]);
        }
    }
    $created = 0;
    foreach ($accounts as [$email, $fullName, $role, $storeCode]) {
        $query = $db->prepare('SELECT id,assigned_store_id,token_version,password_hash FROM users WHERE email=? FOR UPDATE');
        $query->execute([$email]);
        $existing = $query->fetch();
        $storeId = null;
        if ($storeCode !== null) {
            $shop = $db->prepare('SELECT id FROM stores WHERE code=? AND status=\'ACTIVE\'');
            $shop->execute([$storeCode]);
            $storeId = $shop->fetchColumn();
            if ($storeId === false) {
                throw new RuntimeException('Approved shop is missing');
            }
        }
        if ($existing) {
            if ($existing['assigned_store_id'] !== $storeId) {
                throw new RuntimeException('Existing shop assignment differs; no changes made');
            }
            $roleQuery = $db->prepare('SELECT role_id FROM user_roles WHERE user_id=?');
            $roleQuery->execute([$existing['id']]);
            if ($roleQuery->fetchAll(PDO::FETCH_COLUMN) !== [$roleIds[$role]]) {
                throw new RuntimeException('Existing role assignment differs; no changes made');
            }
            continue;
        }
        $userId = Uuid::v4();
        $db->prepare('INSERT INTO users (id,email,full_name,password_hash,assigned_store_id) VALUES (?,?,?,?,?)')
            ->execute([$userId, $email, $fullName, password_hash($new[$email], PASSWORD_DEFAULT), $storeId]);
        $db->prepare('INSERT INTO user_roles (user_id,role_id) VALUES (?,?)')->execute([$userId, $roleIds[$role]]);
        $created++;
    }
    return $created;
});
echo "accounts_created={$created} approved_accounts=10\n";
