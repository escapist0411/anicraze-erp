<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;
use Anicraze\Reports\OwnerDashboardService;

require dirname(__DIR__) . '/vendor/autoload.php';

$expected = 'anicraze_phase5b_product5c2';
if (getenv('DB_NAME') !== $expected) {
    throw new RuntimeException('Owner dashboard test requires its disposable database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== $expected) {
    throw new RuntimeException('Database identity mismatch');
}
$service = new OwnerDashboardService($db);
$result = $service->get(['roles' => ['OWNER']], ['preset' => 'THIS_MONTH']);
foreach (['kpis', 'inventory_summary', 'sales_trend', 'store_performance',
    'top_selling_products', 'payment_summary', 'active_employees', 'alerts', 'definitions'] as $key) {
    if (!array_key_exists($key, $result)) {
        throw new RuntimeException('Owner dashboard contract missing ' . $key);
    }
}
if (count($result['store_performance']) !== 8 || $result['active_employees'] !== 8) {
    throw new RuntimeException('Owner dashboard location/account metrics differ');
}
$aggregate = $db->query("SELECT COALESCE(SUM(available_quantity),0) FROM inventory")->fetchColumn();
if ($result['inventory_summary']['available_units'] !== (int) $aggregate) {
    throw new RuntimeException('Owner inventory metric differs from database');
}
try {
    $service->get(['roles' => ['MANAGER']], []);
    throw new RuntimeException('Manager read owner dashboard');
} catch (ApiException $error) {
    if ($error->status !== 403) { throw $error; }
}
try {
    $service->get(['roles' => ['SALES']], []);
    throw new RuntimeException('SALES read owner dashboard');
} catch (ApiException $error) {
    if ($error->status !== 403) { throw $error; }
}
echo "php_owner_dashboard_integration_passed=5\n";
