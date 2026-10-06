<?php
declare(strict_types=1);

use Anicraze\Config\Environment;
use Anicraze\Config\DatabaseTargetGuard;
use Anicraze\Database\Connection;

require dirname(__DIR__) . '/vendor/autoload.php';
Environment::load(dirname(__DIR__));

if (PHP_SAPI !== 'cli') {
    throw new RuntimeException('Migrations are CLI-only');
}
if (Environment::optional('ALLOW_SCHEMA_MIGRATION') !== '1') {
    throw new RuntimeException('Explicit ALLOW_SCHEMA_MIGRATION=1 is required');
}
$name = Environment::required('DB_NAME');
DatabaseTargetGuard::assertApproved($name);
$database = Connection::open(true);
if ($database->query('SELECT DATABASE()')->fetchColumn() !== $name) {
    throw new RuntimeException('Connected database identity differs');
}
$database->exec('CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(100) PRIMARY KEY, checksum CHAR(64) NOT NULL, applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4');
$files = glob(__DIR__ . '/migrations/*.sql');
sort($files, SORT_STRING);
foreach ($files as $file) {
    $version = basename($file);
    $sql = file_get_contents($file);
    if ($sql === false) {
        throw new RuntimeException('Migration file is unreadable');
    }
    $checksum = hash('sha256', $sql);
    $statement = $database->prepare('SELECT checksum FROM schema_migrations WHERE version = ?');
    $statement->execute([$version]);
    $prior = $statement->fetchColumn();
    if ($prior !== false) {
        if (!hash_equals((string) $prior, $checksum)) {
            throw new RuntimeException('Applied migration checksum differs: ' . $version);
        }
        echo "already_applied={$version}\n";
        continue;
    }
    // MariaDB DDL commits implicitly. On an error, stop for manual inspection;
    // never pretend a partially applied migration rolled back cleanly.
    $database->exec($sql);
    $statement = $database->prepare('INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)');
    $statement->execute([$version, $checksum]);
    echo "applied={$version}\n";
}
