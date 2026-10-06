<?php
declare(strict_types=1);

namespace Anicraze\Config;

final class Environment
{
    private static bool $loaded = false;

    public static function load(string $projectRoot): void
    {
        if (self::$loaded) {
            return;
        }
        self::$loaded = true;
        if (is_file($projectRoot . '/.env')) {
            \Dotenv\Dotenv::createImmutable($projectRoot)->safeLoad();
        }
    }

    public static function required(string $name): string
    {
        $value = self::value($name);
        if ($value === false || trim($value) === '') {
            throw new \RuntimeException('Missing required configuration: ' . $name);
        }
        return $value;
    }

    public static function optional(string $name, string $default = ''): string
    {
        $value = self::value($name);
        return $value === false ? $default : $value;
    }

    private static function value(string $name): string|false
    {
        $value = getenv($name);
        if ($value !== false) {
            return $value;
        }
        $value = $_ENV[$name] ?? $_SERVER[$name] ?? false;
        return is_string($value) ? $value : false;
    }
}
