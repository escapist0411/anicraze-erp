<?php
declare(strict_types=1);

use Anicraze\Config\Environment;
use Anicraze\Config\DatabaseTargetGuard;
use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;

require dirname(__DIR__) . '/vendor/autoload.php';
Environment::load(dirname(__DIR__));

if (PHP_SAPI !== 'cli' || Environment::optional('ALLOW_CATALOG_IMPORT') !== '1') {
    throw new RuntimeException('Catalog import requires explicit CLI confirmation');
}
$name = Environment::required('DB_NAME');
DatabaseTargetGuard::assertApproved($name);
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== $name) {
    throw new RuntimeException('Connected database identity differs');
}

$readCsv = static function (string $name): array {
    $handle = fopen(__DIR__ . '/data/' . $name, 'rb');
    if ($handle === false) {
        throw new RuntimeException('Approved catalog file is missing');
    }
    $headers = fgetcsv($handle, 0, ',', '"', '');
    if ($headers === false) {
        throw new RuntimeException('Approved catalog header is missing');
    }
    $rows = [];
    while (($values = fgetcsv($handle, 0, ',', '"', '')) !== false) {
        if (count($headers) !== count($values)) {
            throw new RuntimeException('Approved catalog row width differs');
        }
        $rows[] = array_combine($headers, $values);
    }
    fclose($handle);
    return $rows;
};
$master = $readCsv('product_master.csv');
$barcodes = $readCsv('canonical_barcodes.csv');
if (count($master) !== 160 || count($barcodes) !== 160) {
    throw new RuntimeException('Approved catalog must contain exactly 160 products and 160 barcodes');
}
$barcodeByRef = [];
$seenCodes = [];
foreach ($barcodes as $row) {
    $reference = trim($row['import_reference'] ?? '');
    $sku = trim($row['sku'] ?? '');
    $barcode = trim($row['barcode'] ?? '');
    if ($reference === '' || $sku === '' || $barcode === '' || $sku !== $barcode
        || isset($barcodeByRef[$reference]) || isset($seenCodes[strtolower($barcode)])) {
        throw new RuntimeException('Approved barcode manifest is inconsistent');
    }
    $barcodeByRef[$reference] = [$sku, $barcode];
    $seenCodes[strtolower($barcode)] = true;
}
$categories = [
    'Action Figures' => ['ACTION_FIGURES', 'FIGURE'], 'Figure Sets' => ['FIGURE_SETS', 'COLLECTIBLE'],
    'Qposket Figures' => ['QPOSKET_FIGURES', 'FIGURE'], 'Keychains' => ['KEYCHAINS', 'KEYCHAIN'],
    'Card & Party Games' => ['CARD_PARTY_GAMES', 'TOY'],
    'Novelty / Collectibles' => ['NOVELTY_COLLECTIBLES', 'COLLECTIBLE'],
    'Anime Weapons / Props' => ['ANIME_WEAPONS_PROPS', 'ACCESSORY'],
];
$series = [
    'Naruto' => 'NARUTO', 'Demon Slayer' => 'DEMON_SLAYER', 'One Piece' => 'ONE_PIECE',
    'Dragon Ball Z' => 'DRAGON_BALL_Z', 'Jujutsu Kaisen' => 'JJK',
    'Marvel / DC / Movies' => 'MARVEL_DC_MOVIES', 'Character Sets' => 'CHARACTER_SETS',
    'Princess / Superhero' => 'PRINCESS_SUPERHERO', 'Generic Types' => 'GENERIC_TYPES',
    'Games' => 'GAMES', 'Novelty Items' => 'NOVELTY_ITEMS', 'Naruto / General' => 'NARUTO_GENERAL',
];
$stores = [
    ['ELPRO', 'ANICRAZE Elpro City Square Mall', 'Elpro Chinchwad', "Elpro City Square Mall,\nChinchwad Gaon,\nChinchwad,\nPune,\nPimpri-Chinchwad,\nMaharashtra 411033", 'PERMANENT_STORE'],
    ['WESTEND', 'ANICRAZE Westend Mall', 'Westend Mall', "Ground Floor,\nWESTEND MALL,\nWard No. 8,\nWireless Colony,\nAundh,\nPune,\nMaharashtra 411067", 'PERMANENT_STORE'],
    ['CIVIL', 'ANICRAZE Civil Court Metro Station', 'Civil Court Metro', "Civil Court Metro Station,\nPune,\nMaharashtra", 'PERMANENT_STORE'],
    ['SWARGATE', 'ANICRAZE Swargate Metro Station', 'Swargate Metro', "Swargate Metro Station,\nPune,\nMaharashtra", 'PERMANENT_STORE'],
    ['KALYANI', 'ANICRAZE Kalyani Nagar Metro Station', 'Kalyani Nagar Metro', "Kalyani Nagar Metro Station,\nPune,\nMaharashtra", 'PERMANENT_STORE'],
    ['SHIVAJI', 'ANICRAZE Shivaji Nagar Metro Station', 'Shivaji Nagar Metro', "Shivaji Nagar Metro Station,\nPune,\nMaharashtra", 'PERMANENT_STORE'],
    ['EVENT1', 'ANICRAZE Event 1', 'Event 1', null, 'EVENT_LOCATION'],
    ['EVENT2', 'ANICRAZE Event 2', 'Event 2', null, 'EVENT_LOCATION'],
];
$byCode = static function (string $table, string $code) use ($db): ?string {
    $query = $db->prepare("SELECT id FROM {$table} WHERE code=?");
    $query->execute([$code]);
    $result = $query->fetchColumn();
    return $result === false ? null : $result;
};

Connection::transaction($db, static function () use ($db, $master, $barcodeByRef, $categories, $series, $stores, $byCode): void {
    foreach ($stores as [$code, $name, $short, $address, $type]) {
        if ($byCode('stores', $code) === null) {
            $db->prepare('INSERT INTO stores (id,code,name,short_name,address,location_type) VALUES (?,?,?,?,?,?)')
                ->execute([Uuid::v4(), $code, $name, $short, $address, $type]);
        }
    }
    if ($byCode('warehouses', 'ANICRAZE_CWH') === null) {
        $db->prepare('INSERT INTO warehouses (id,code,name) VALUES (?,?,?)')
            ->execute([Uuid::v4(), 'ANICRAZE_CWH', 'ANICRAZE Central Warehouse']);
    }
    foreach ($categories as $category => [$code]) {
        if ($byCode('categories', $code) === null) {
            $db->prepare('INSERT INTO categories (id,code,name) VALUES (?,?,?)')->execute([Uuid::v4(), $code, $category]);
        }
    }
    foreach ($series as $name => $code) {
        if ($byCode('anime_franchises', $code) === null) {
            $db->prepare('INSERT INTO anime_franchises (id,code,name) VALUES (?,?,?)')->execute([Uuid::v4(), $code, $name]);
        }
    }
    $findProduct = $db->prepare('SELECT id,sku,barcode FROM products WHERE import_reference=? FOR UPDATE');
    $insert = $db->prepare('INSERT INTO products (id,sku,barcode,import_reference,name,category_id,anime_id,product_type,edition,selling_price) VALUES (?,?,?,?,?,?,?,?,?,?)');
    foreach ($master as $row) {
        $category = trim($row['category'] ?? '');
        $anime = trim($row['series'] ?? '');
        $product = trim($row['product'] ?? '');
        $variant = trim($row['variant'] ?? '');
        if (!isset($categories[$category], $series[$anime]) || $product === '' || !is_numeric($row['price'] ?? null)
            || (float) $row['price'] <= 0) {
            throw new RuntimeException('Invalid approved catalog row');
        }
        $edition = $variant === '' || $variant === '-' ? null : $variant;
        $identity = strtolower($anime) . '|' . strtolower($product) . '|' . strtolower($edition ?? '');
        $reference = 'FINAL_PRODUCT_MASTER_2026:' . substr(hash('sha256', $identity), 0, 20);
        if (!isset($barcodeByRef[$reference])) {
            throw new RuntimeException('Approved catalog/barcode identity differs');
        }
        [$sku, $barcode] = $barcodeByRef[$reference];
        $findProduct->execute([$reference]);
        $existing = $findProduct->fetch();
        if ($existing) {
            if ($existing['sku'] !== $sku || $existing['barcode'] !== $barcode) {
                throw new RuntimeException('Existing approved barcode differs; refusing modification');
            }
            continue;
        }
        $insert->execute([Uuid::v4(), $sku, $barcode, $reference,
            $product . ($edition === null ? '' : ' — ' . $edition),
            $byCode('categories', $categories[$category][0]), $byCode('anime_franchises', $series[$anime]),
            $categories[$category][1], $edition, $row['price']]);
    }
    $warehouseId = $byCode('warehouses', 'ANICRAZE_CWH');
    $shopIds = array_map(static fn (array $store): string => $byCode('stores', $store[0]), $stores);
    $productIds = $db->query('SELECT id FROM products')->fetchAll(PDO::FETCH_COLUMN);
    $findInventory = $db->prepare('SELECT id FROM inventory WHERE product_id=? AND store_id <=> ? AND warehouse_id <=> ?');
    $insertInventory = $db->prepare('INSERT INTO inventory (id,product_id,store_id,warehouse_id) VALUES (?,?,?,?)');
    foreach ($productIds as $productId) {
        foreach (array_merge([null], $shopIds) as $storeId) {
            $locationWarehouse = $storeId === null ? $warehouseId : null;
            $findInventory->execute([$productId, $storeId, $locationWarehouse]);
            if ($findInventory->fetchColumn() === false) {
                $insertInventory->execute([Uuid::v4(), $productId, $storeId, $locationWarehouse]);
            }
        }
    }
    $counts = [
        (int) $db->query('SELECT COUNT(*) FROM products')->fetchColumn(),
        (int) $db->query('SELECT COUNT(DISTINCT LOWER(barcode)) FROM products')->fetchColumn(),
        (int) $db->query('SELECT COUNT(*) FROM stores')->fetchColumn(),
        (int) $db->query('SELECT COUNT(*) FROM warehouses')->fetchColumn(),
        (int) $db->query('SELECT COUNT(*) FROM inventory')->fetchColumn(),
    ];
    if ($counts !== [160, 160, 8, 1, 1440]) {
        throw new RuntimeException('Final product/location count differs');
    }
});
echo "catalog_products=160 canonical_barcodes=160 stores=8 warehouses=1 zero_stock_inventory_rows=1440\n";
