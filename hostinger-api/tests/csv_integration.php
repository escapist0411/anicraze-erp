<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Documents\CsvService;
use Anicraze\Http\ApiException;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_clean') {
    throw new RuntimeException('CSV integration requires clean disposable database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_clean') {
    throw new RuntimeException('Connected database identity mismatch');
}
$service = new CsvService($db);
$owner = ['roles' => ['OWNER']];
$passed = 0;
foreach (['products' => 161, 'inventory' => 1441] as $kind => $expectedRows) {
    $csv = $service->export($owner, $kind);
    $stream = fopen('php://temp', 'w+');
    fwrite($stream, $csv);
    rewind($stream);
    $rows = 0;
    while (fgetcsv($stream, 0, ',', '"', '') !== false) {
        $rows++;
    }
    fclose($stream);
    if ($rows !== $expectedRows) {
        throw new RuntimeException('CSV row count differs for ' . $kind);
    }
    $passed++;
}
try {
    $service->export(['roles' => ['SALES'], 'assigned_store_id' => 'foreign'], 'products');
    throw new RuntimeException('SALES downloaded product master CSV');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
$passed++;
echo "php_csv_integration_passed={$passed}\n";
