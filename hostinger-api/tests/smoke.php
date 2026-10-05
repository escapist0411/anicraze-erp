<?php
declare(strict_types=1);

use Anicraze\Http\Application;

require dirname(__DIR__) . '/vendor/autoload.php';

function request(string $method, string $path, ?string $origin = null): array
{
    $_SERVER = ['REQUEST_METHOD' => $method, 'REQUEST_URI' => $path];
    if ($origin !== null) {
        $_SERVER['HTTP_ORIGIN'] = $origin;
    }
    http_response_code(200);
    ob_start();
    (new Application())->run();
    return [http_response_code(), json_decode((string) ob_get_clean(), true)];
}

$passed = 0;
[$status, $body] = request('GET', '/health');
if ($status !== 200 || $body !== ['status' => 'ok']) {
    throw new RuntimeException('Public health contract differs');
}
$passed++;
[$status, $body] = request('GET', '/api/v1/health');
if ($status !== 200 || $body !== ['status' => 'ok']) {
    throw new RuntimeException('API health contract differs');
}
$passed++;
[$status, $body] = request('POST', '/api/v1/payroll');
if ($status !== 404 || ($body['error']['code'] ?? null) !== 'not_implemented') {
    throw new RuntimeException('Unported business route must fail closed');
}
$passed++;
putenv('APP_ALLOWED_ORIGIN=https://erp.anicraze.com');
[$status] = request('OPTIONS', '/api/v1/billing', 'https://evil.example');
if ($status !== 403) {
    throw new RuntimeException('Foreign origin preflight must fail');
}
$passed++;
[$status] = request('OPTIONS', '/api/v1/billing', 'https://erp.anicraze.com');
if ($status !== 204) {
    throw new RuntimeException('Configured ERP origin preflight must pass');
}
$passed++;

echo "php_scaffold_smoke_passed={$passed}\n";
