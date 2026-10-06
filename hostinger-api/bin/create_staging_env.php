<?php
declare(strict_types=1);

if (PHP_SAPI !== 'cli' || count($argv) !== 2 || preg_match('/^u[0-9]+$/D', $argv[1]) !== 1) {
    fwrite(STDERR, "Usage: php bin/create_staging_env.php <Hostinger account prefix>\n");
    exit(2);
}

$root = dirname(__DIR__);
$path = $root . '/.env.staging';
if (file_exists($path)) {
    fwrite(STDERR, "Refusing to replace existing .env.staging\n");
    exit(1);
}

$secret = static fn (int $bytes = 32): string => rtrim(strtr(base64_encode(random_bytes($bytes)), '+/', '-_'), '=');
$prefix = $argv[1];
$database = $prefix . '_anicraze_staging';
$user = $prefix . '_anicraze_stg';
$values = [
    'APP_ENV' => 'staging',
    'APP_DEBUG' => 'false',
    'APP_ALLOWED_ORIGIN' => 'https://staging.anicraze.com',
    'APP_BUSINESS_CONTACT' => '+918010526600',
    'DB_HOST' => 'localhost',
    'DB_PORT' => '3306',
    'DB_NAME' => $database,
    'DB_USER' => $user,
    'DB_PASSWORD' => $secret(36),
    'ANICRAZE_CONFIRM_DATABASE' => $database,
    'ANICRAZE_DEPLOYMENT_TARGET' => 'staging',
    'ALLOW_SCHEMA_MIGRATION' => '0',
    'ALLOW_CATALOG_IMPORT' => '0',
    'ALLOW_ACCOUNT_PROVISIONING' => '0',
    'APP_SECRET' => $secret(48),
    'FRONTEND_URL' => 'https://staging.anicraze.com',
    'PASSWORD_RESET_EMAIL_ENABLED' => '0',
    'MAIL_FROM' => '',
    'REPORT_SCHEDULES_JSON' => '[]',
    'REPORT_EMAIL_ENABLED' => '0',
    'WHATSAPP_ENABLED' => '0',
];
foreach (['OWNER', 'MANAGER', 'ELPRO', 'WESTEND', 'CIVIL', 'SWARGATE', 'KALYANI', 'SHIVAJI', 'EVENT1', 'EVENT2'] as $account) {
    $values['ANICRAZE_' . $account . '_PASSWORD'] = $secret(24);
}

$lines = [];
foreach ($values as $name => $value) {
    $lines[] = $name . '="' . addcslashes($value, "\\\"") . '"';
}
if (file_put_contents($path, implode("\n", $lines) . "\n", LOCK_EX) === false || !chmod($path, 0600)) {
    fwrite(STDERR, "Could not create secure staging environment file\n");
    exit(1);
}
echo "Created ignored staging configuration with mode 0600.\n";
