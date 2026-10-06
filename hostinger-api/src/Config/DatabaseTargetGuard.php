<?php
declare(strict_types=1);

namespace Anicraze\Config;

final class DatabaseTargetGuard
{
    public static function assertApproved(string $database): void
    {
        if (Environment::required('ANICRAZE_CONFIRM_DATABASE') !== $database) {
            throw new \RuntimeException('Target database identity/confirmation is invalid');
        }

        $target = Environment::optional('ANICRAZE_DEPLOYMENT_TARGET', 'local');
        $approved = match ($target) {
            'local' => str_starts_with($database, 'anicraze_phase5b_'),
            'staging' => preg_match('/(?:^|_)anicraze_stg$/D', $database) === 1,
            'production' => preg_match('/(?:^|_)anicraze_prod$/D', $database) === 1,
            default => false,
        };
        if (!$approved) {
            throw new \RuntimeException('Database name is not approved for the declared deployment target');
        }
    }
}
