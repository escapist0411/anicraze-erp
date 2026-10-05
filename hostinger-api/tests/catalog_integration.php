<?php
declare(strict_types=1);

use Anicraze\Catalog\ProductService;
use Anicraze\Catalog\ReferenceService;
use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_local') {
    throw new RuntimeException('Catalog integration test requires disposable local database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_local') {
    throw new RuntimeException('Database identity mismatch');
}
$service = new ProductService($db);
$passed = 0;
$owner = ['roles' => ['OWNER'], 'assigned_store_id' => null];
$all = $service->list($owner, ['page' => 1, 'page_size' => 100]);
if ($all['total'] !== 160 || count($all['items']) !== 100 || $all['pages'] !== 2) {
    throw new RuntimeException('Approved product list/pagination differs');
}
$passed++;
$sku = $all['items'][0]['sku'];
$bySku = $service->find($owner, 'sku', $sku);
$byBarcode = $service->find($owner, 'barcode', ' ' . strtolower($sku) . ' ');
if ($bySku['id'] !== $byBarcode['id'] || $bySku['barcode'] !== $sku) {
    throw new RuntimeException('Canonical barcode lookup differs');
}
$passed++;
$missing = $service->list($owner, ['missing_barcode' => 'true']);
if ($missing['total'] !== 0) {
    throw new RuntimeException('Unexpected missing barcode');
}
$passed++;
$references = new ReferenceService($db);
if (count($references->list($owner, 'categories')) !== (int) $db->query('SELECT COUNT(*) FROM categories')->fetchColumn()
    || count($references->list($owner, 'anime')) !== (int) $db->query('SELECT COUNT(*) FROM anime_franchises')->fetchColumn()) {
    throw new RuntimeException('Catalog reference lists differ from approved data');
}
$passed++;
$sales = ['roles' => ['SALES'], 'assigned_store_id' => $db->query("SELECT id FROM stores WHERE code='ELPRO'")->fetchColumn()];
try {
    $service->list($sales, []);
    throw new RuntimeException('SALES read the product master');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
$passed++;
try {
    $references->list($sales, 'categories');
    throw new RuntimeException('SALES read restricted catalog references');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
$passed++;
try {
    $service->find($sales, 'id', $bySku['id']);
    throw new RuntimeException('SALES read product master detail');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
$passed++;
try {
    $service->list(['roles' => ['SALES'], 'assigned_store_id' => null], []);
    throw new RuntimeException('Unassigned SALES queried products');
} catch (ApiException $error) {
    if ($error->status !== 403) {
        throw $error;
    }
}
$passed++;
echo "php_catalog_integration_passed={$passed}\n";
