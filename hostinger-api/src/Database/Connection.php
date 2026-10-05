<?php
declare(strict_types=1);

namespace Anicraze\Database;

use Anicraze\Config\Environment;
use PDO;

final class Connection
{
    public static function open(bool $allowMigrationStatements = false): PDO
    {
        $host = Environment::required('DB_HOST');
        $port = Environment::optional('DB_PORT', '3306');
        $name = Environment::required('DB_NAME');
        if (!ctype_digit($port) || (int) $port < 1 || (int) $port > 65535) {
            throw new \RuntimeException('Invalid DB_PORT');
        }
        if (!preg_match('/^[a-zA-Z0-9_.-]+$/D', $host) || !preg_match('/^[a-zA-Z0-9_]+$/D', $name)) {
            throw new \RuntimeException('Invalid database host or name configuration');
        }
        $socket = Environment::optional('DB_SOCKET');
        if ($socket !== '' && (!str_starts_with($socket, '/') || !file_exists($socket))) {
            throw new \RuntimeException('Invalid local DB_SOCKET');
        }
        $dsn = $socket !== ''
            ? "mysql:unix_socket={$socket};dbname={$name};charset=utf8mb4"
            : "mysql:host={$host};port={$port};dbname={$name};charset=utf8mb4";
        $multiStatementsOption = defined('Pdo\\Mysql::ATTR_MULTI_STATEMENTS')
            ? constant('Pdo\\Mysql::ATTR_MULTI_STATEMENTS')
            : PDO::MYSQL_ATTR_MULTI_STATEMENTS;
        $connection = new PDO(
            $dsn,
            Environment::required('DB_USER'),
            Environment::required('DB_PASSWORD'),
            [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES => false,
                $multiStatementsOption => $allowMigrationStatements,
            ],
        );
        $connection->exec("SET time_zone = '+00:00'");
        return $connection;
    }

    public static function transaction(PDO $connection, callable $work): mixed
    {
        $connection->beginTransaction();
        try {
            $result = $work($connection);
            $connection->commit();
            return $result;
        } catch (\Throwable $error) {
            if ($connection->inTransaction()) {
                $connection->rollBack();
            }
            throw $error;
        }
    }
}
