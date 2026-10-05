<?php
declare(strict_types=1);

namespace Anicraze\Config;

final class Environment
{
    public static function required(string $name): string
    {
        $value = getenv($name);
        if ($value === false || trim($value) === '') {
            throw new \RuntimeException('Missing required configuration: ' . $name);
        }
        return $value;
    }

    public static function optional(string $name, string $default = ''): string
    {
        $value = getenv($name);
        return $value === false ? $default : $value;
    }
}
