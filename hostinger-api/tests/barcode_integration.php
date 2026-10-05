<?php
declare(strict_types=1);

use Anicraze\Catalog\BarcodeImage;
use Anicraze\Database\Connection;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_clean') {
    throw new RuntimeException('Barcode integration test requires clean local database');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_clean') {
    throw new RuntimeException('Database identity mismatch');
}
$barcodes = $db->query('SELECT barcode FROM products ORDER BY sku')->fetchAll(PDO::FETCH_COLUMN);
if (count($barcodes) !== 160 || count(array_unique(array_map('strtolower', $barcodes))) !== 160) {
    throw new RuntimeException('Approved barcode count or uniqueness differs');
}
$passed = 1;
foreach ($barcodes as $code) {
    $bytes = BarcodeImage::png($code);
    $image = imagecreatefromstring($bytes);
    if ($image === false || imagesx($image) < 100 || imagesy($image) !== 120) {
        throw new RuntimeException('Code 128 PNG dimensions differ');
    }
    for ($x = 0; $x < 20; $x++) {
        $left = imagecolorsforindex($image, imagecolorat($image, $x, 50));
        $right = imagecolorsforindex($image, imagecolorat($image, imagesx($image) - 1 - $x, 50));
        if ($left['red'] !== 255 || $right['red'] !== 255) {
            throw new RuntimeException('Barcode quiet zone is missing');
        }
    }
}
$passed++;
echo "php_barcode_integration_passed={$passed} generated_code128=160\n";
