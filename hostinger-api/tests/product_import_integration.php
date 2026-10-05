<?php
declare(strict_types=1);

use Anicraze\Catalog\ProductImportService;
use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_product5c2') {
    throw new RuntimeException('Product import test requires its disposable database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_product5c2') {
    throw new RuntimeException('Database identity mismatch');
}
$ownerId = $db->query("SELECT id FROM users WHERE email='owner@anicraze.in'")->fetchColumn();
$categoryId = $db->query('SELECT id FROM categories ORDER BY code LIMIT 1')->fetchColumn();
$existingSku = $db->query('SELECT sku FROM products ORDER BY id LIMIT 1')->fetchColumn();
if (!$ownerId || !$categoryId || !$existingSku) { throw new RuntimeException('Fixtures missing'); }
$owner = ['id' => $ownerId, 'roles' => ['OWNER']];
$manager = ['id' => $ownerId, 'roles' => ['MANAGER']];
$service = new ProductImportService($db);
$newSku = 'ANI-TST-' . str_pad((string) random_int(100000, 999999), 6, '0', STR_PAD_LEFT);
$path = tempnam(sys_get_temp_dir(), 'anicraze-csv-');
if ($path === false) { throw new RuntimeException('Cannot create temporary CSV fixture'); }
$passed = 0;
try {
    $before = (int) $db->query('SELECT COUNT(*) FROM products')->fetchColumn();
    $content = "name,category_id,product_type,sku,purchase_price,selling_price\n"
        . "Local CSV Product,{$categoryId},FIGURE,{$newSku},10,20\n"
        . "Duplicate CSV Product,{$categoryId},FIGURE,{$existingSku},10,20\n";
    file_put_contents($path, $content);
    $preview = $service->import($owner, $path, 'products.csv', strlen($content), true);
    if ($preview['total_rows'] !== 2 || $preview['valid_rows'] !== 1 || $preview['invalid_rows'] !== 1
        || $preview['created_rows'] !== 0) { throw new RuntimeException('CSV dry run differs'); }
    $passed++;
    if ((int) $db->query('SELECT COUNT(*) FROM products')->fetchColumn() !== $before) {
        throw new RuntimeException('Dry run persisted a product');
    }
    $passed++;
    $blocked = $service->import($owner, $path, 'products.csv', strlen($content), false);
    if ($blocked['created_rows'] !== 0 || (int) $db->query('SELECT COUNT(*) FROM products')->fetchColumn() !== $before) {
        throw new RuntimeException('Invalid CSV was partly imported');
    }
    $passed++;
    $content = "name,category_id,product_type,sku,purchase_price,selling_price\n"
        . "Local CSV Product,{$categoryId},FIGURE,{$newSku},10,20\n";
    file_put_contents($path, $content);
    $created = $service->import($owner, $path, 'products.csv', strlen($content), false);
    if ($created['created_rows'] !== 1 || (int) $db->query('SELECT COUNT(*) FROM products')->fetchColumn() !== $before + 1) {
        throw new RuntimeException('Valid CSV import count differs');
    }
    $passed++;
    $lookup = $db->prepare('SELECT sku,barcode FROM products WHERE sku=?');
    $lookup->execute([$newSku]);
    $identity = $lookup->fetch();
    if (!$identity || $identity['barcode'] !== $identity['sku']) {
        throw new RuntimeException('Imported canonical barcode differs');
    }
    $passed++;
    try {
        $service->import($manager, $path, 'products.csv', strlen($content), true);
        throw new RuntimeException('Manager imported products');
    } catch (ApiException $error) { if ($error->status !== 403) { throw $error; } }
    $passed++;
    try {
        $service->import($owner, $path, '../products.php', strlen($content), true);
        throw new RuntimeException('Executable filename accepted');
    } catch (ApiException $error) { if ($error->status !== 422) { throw $error; } }
    $passed++;
} finally {
    unlink($path);
}
echo "php_product_import_integration_passed={$passed}\n";
