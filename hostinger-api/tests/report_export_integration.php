<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Documents\ReportExportService;
use Anicraze\Http\ApiException;

require dirname(__DIR__) . '/vendor/autoload.php';

$expected = 'anicraze_phase5b_product5c2';
if (getenv('DB_NAME') !== $expected) {
    throw new RuntimeException('Report export test requires its disposable database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== $expected) {
    throw new RuntimeException('Database identity mismatch');
}
$service = new ReportExportService($db);
[$csv, $csvType, $csvExtension] = $service->export(['roles' => ['OWNER']], 'sales_summary', 'CSV', ['preset' => 'THIS_MONTH']);
if (!str_contains($csv, 'Net Sales') || $csvExtension !== 'csv' || !str_starts_with($csvType, 'text/csv')) {
    throw new RuntimeException('CSV report contract failed');
}
[$xlsx, $xlsxType, $xlsxExtension] = $service->export(['roles' => ['OWNER']], 'finance_summary', 'XLSX', ['preset' => 'THIS_MONTH']);
$temporary = tempnam(sys_get_temp_dir(), 'anicraze-test-xlsx-');
if ($temporary === false) { throw new RuntimeException('Temporary XLSX file unavailable'); }
try {
    file_put_contents($temporary, $xlsx);
    $zip = new ZipArchive();
    if ($zip->open($temporary) !== true || $zip->getFromName('xl/worksheets/sheet1.xml') === false) {
        throw new RuntimeException('XLSX report is unreadable');
    }
    $zip->close();
} finally {
    if (file_exists($temporary)) { unlink($temporary); }
}
if ($xlsxExtension !== 'xlsx' || !str_contains($xlsxType, 'spreadsheetml')) {
    throw new RuntimeException('XLSX content metadata failed');
}
try {
    $service->export(['roles' => ['MANAGER']], 'finance_summary', 'CSV', []);
    throw new RuntimeException('Manager exported Owner finance');
} catch (ApiException $error) {
    if ($error->status !== 403) { throw $error; }
}
echo "php_report_export_integration_passed=4\n";
