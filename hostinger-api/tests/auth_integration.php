<?php
declare(strict_types=1);

use Anicraze\Auth\AuthService;
use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;
use Anicraze\Http\ApiException;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_local') {
    throw new RuntimeException('Auth integration test requires disposable local database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_local') {
    throw new RuntimeException('Database identity mismatch');
}
$suffix = bin2hex(random_bytes(5));
$roleId = Uuid::v4();
$userId = Uuid::v4();
$password = bin2hex(random_bytes(16));
$db->prepare('INSERT INTO roles (id, code, name) VALUES (?, ?, ?)')->execute([$roleId, 'TEST_' . $suffix, 'Test role']);
$db->prepare('INSERT INTO users (id,email,full_name,password_hash) VALUES (?,?,?,?)')->execute([
    $userId, "auth-{$suffix}@example.invalid", 'Local test user', password_hash($password, PASSWORD_DEFAULT),
]);
$db->prepare('INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)')->execute([$userId, $roleId]);
$service = new AuthService($db);
$passed = 0;

$login = $service->login("auth-{$suffix}@example.invalid", $password, false);
if (($login['user']['id'] ?? null) !== $userId || empty($login['access_token']) || empty($login['refresh_token'])) {
    throw new RuntimeException('Login contract failed');
}
$passed++;
$actor = $service->authenticate($login['access_token']);
if ($actor['id'] !== $userId) {
    throw new RuntimeException('Bearer authentication failed');
}
$passed++;
$refreshed = $service->refresh($login['refresh_token']);
if ($refreshed['refresh_token'] === $login['refresh_token']) {
    throw new RuntimeException('Refresh did not rotate');
}
$passed++;
try {
    $service->refresh($login['refresh_token']);
    throw new RuntimeException('Old refresh token was reused');
} catch (ApiException $error) {
    if ($error->status !== 401) {
        throw $error;
    }
}
$passed++;
$service->logout($actor, $refreshed['refresh_token']);
try {
    $service->authenticate($refreshed['access_token']);
    throw new RuntimeException('Logged-out bearer token still works');
} catch (ApiException $error) {
    if ($error->status !== 401) {
        throw $error;
    }
}
$passed++;
try {
    $service->login("auth-{$suffix}@example.invalid", $password . 'wrong', false);
    throw new RuntimeException('Wrong password worked');
} catch (ApiException $error) {
    if ($error->status !== 401) {
        throw $error;
    }
}
if ((int) $db->query("SELECT failed_login_attempts FROM users WHERE id='{$userId}'")->fetchColumn() !== 1) {
    throw new RuntimeException('Failed-login counter did not persist');
}
$passed++;

echo "php_auth_integration_passed={$passed}\n";
