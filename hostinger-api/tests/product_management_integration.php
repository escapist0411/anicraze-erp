<?php
declare(strict_types=1);

use Anicraze\Catalog\ProductService;
use Anicraze\Catalog\ProductWriteService;
use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_product5c2') {
    throw new RuntimeException('Product test requires its disposable database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_product5c2') {
    throw new RuntimeException('Database identity mismatch');
}
$ownerId = $db->query("SELECT id FROM users WHERE email='owner@anicraze.in'")->fetchColumn();
if (!$ownerId) {
    throw new RuntimeException('Disposable owner fixture is missing');
}
$owner = ['id' => $ownerId, 'roles' => ['OWNER']];
$manager = ['id' => $ownerId, 'roles' => ['MANAGER']];
$products = new ProductService($db);
$writer = new ProductWriteService($db);
$passed = 0;
$original = $db->query('SELECT id,sku,barcode FROM products ORDER BY id')->fetchAll();
if (count($original) !== 160) {
    throw new RuntimeException('Expected 160 approved products');
}
$passed++;
$categoryId = $db->query("SELECT id FROM categories WHERE status='ACTIVE' ORDER BY code LIMIT 1")->fetchColumn();
$created = $writer->create($owner, [
    'name' => 'Local Product Management Test', 'category_id' => $categoryId,
    'purchase_price' => 40, 'selling_price' => 99, 'status' => 'ACTIVE',
]);
if ($created['sku'] !== $created['barcode'] || preg_match('/^ANI-[A-Z0-9]{3}-\d{6}$/D', $created['sku']) !== 1) {
    throw new RuntimeException('New canonical identity differs');
}
$passed++;
$inventory = $db->prepare('SELECT COUNT(*),COALESCE(SUM(available_quantity),0) FROM inventory WHERE product_id=?');
$inventory->execute([$created['id']]);
if ($inventory->fetchAll(PDO::FETCH_NUM) !== [[9, '0']]) {
    throw new RuntimeException('New product zero-stock location rows differ');
}
$passed++;
try {
    $writer->create($owner, ['name' => 'Duplicate SKU Test', 'category_id' => $categoryId,
        'sku' => $created['sku'], 'purchase_price' => 1, 'selling_price' => 2]);
    throw new RuntimeException('Duplicate SKU was allowed');
} catch (ApiException $error) {
    if ($error->status !== 409) { throw $error; }
}
$passed++;
$updated = $writer->update($owner, $created['id'], ['name' => 'Updated Local Product Test', 'selling_price' => 109]);
if ($updated['barcode'] !== $created['barcode'] || $updated['selling_price'] !== '109.00') {
    throw new RuntimeException('Update changed identity or price differs');
}
$passed++;
try {
    $writer->update($owner, $created['id'], ['barcode' => 'ALTERED-BARCODE']);
    throw new RuntimeException('Existing barcode changed');
} catch (ApiException $error) {
    if ($error->status !== 409) { throw $error; }
}
$passed++;
try {
    $writer->create($manager, ['name' => 'Manager Product Test', 'category_id' => $categoryId,
        'purchase_price' => 1, 'selling_price' => 2]);
    throw new RuntimeException('Manager created product');
} catch (ApiException $error) {
    if ($error->status !== 403) { throw $error; }
}
$passed++;
$writer->archive($owner, $created['id']);
try {
    $products->find($owner, 'id', $created['id']);
    throw new RuntimeException('Archived product remained visible');
} catch (ApiException $error) {
    if ($error->status !== 404) { throw $error; }
}
$passed++;
$final = $db->query('SELECT id,sku,barcode FROM products ORDER BY id')->fetchAll();
$finalById = array_column($final, null, 'id');
foreach ($original as $row) {
    if (($finalById[$row['id']] ?? null) !== $row) { throw new RuntimeException('Approved barcode changed'); }
}
$passed++;
echo "php_product_management_integration_passed={$passed}\n";
