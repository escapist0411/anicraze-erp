<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;
use Anicraze\Reports\ReportService;

require dirname(__DIR__) . '/vendor/autoload.php';

if (!str_starts_with((string) getenv('DB_NAME'), 'anicraze_phase5b_workflow')) {
    throw new RuntimeException('Report integration test requires isolated workflow database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== getenv('DB_NAME')) {
    throw new RuntimeException('Database identity mismatch');
}
$elpro = $db->query("SELECT id FROM stores WHERE code='ELPRO'")->fetchColumn();
$westend = $db->query("SELECT id FROM stores WHERE code='WESTEND'")->fetchColumn();
$owner = ['roles' => ['OWNER']];
$manager = ['roles' => ['MANAGER']];
$sales = ['roles' => ['SALES'], 'assigned_store_id' => $elpro];
$reports = new ReportService($db);
$passed = 0;
$pnl = $reports->report($owner, 'finance', 'shop-profit-loss', ['preset' => 'TODAY']);
if (count($pnl['rows']) !== 1 || $pnl['rows'][0]['store_id'] !== $elpro
    || $pnl['summary']['net_revenue'] !== '790.00' || $pnl['summary']['cogs'] !== '400.00'
    || $pnl['summary']['gross_profit'] !== '390.00') {
    throw new RuntimeException('Snapshot-cost P&L differs');
}
$passed++;
$salesSummary = $reports->report($sales, 'sales', 'summary', ['preset' => 'TODAY']);
if ($salesSummary['summary']['orders'] !== 1 || $salesSummary['summary']['net_sales'] !== '790.00') {
    throw new RuntimeException('Assigned-shop sales summary differs');
}
$passed++;
try {
    $reports->report($sales, 'sales', 'summary', ['preset' => 'TODAY', 'store_id' => $westend]);
    throw new RuntimeException('Cross-shop report filter succeeded');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
$passed++;
$quarter = $reports->report($owner, 'sales', 'summary', ['preset' => 'THIS_QUARTER']);
if ($quarter['summary']['orders'] !== 1 || $quarter['summary']['net_sales'] !== '790.00') {
    throw new RuntimeException('Current-quarter report filtering differs');
}
$passed++;
foreach ([$sales, $manager] as $actor) {
    try {
        $reports->report($actor, 'finance', 'shop-profit-loss', ['preset' => 'TODAY']);
        throw new RuntimeException('Non-owner finance access succeeded');
    } catch (ApiException $error) {
        if ($error->status !== 403) {
            throw $error;
        }
    }
}
$passed++;
echo "php_report_integration_passed={$passed}\n";
