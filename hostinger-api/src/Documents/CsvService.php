<?php
declare(strict_types=1);

namespace Anicraze\Documents;

use Anicraze\Http\ApiException;
use PDO;

final class CsvService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function export(array $actor, string $kind): string
    {
        if (!array_intersect(['OWNER', 'MANAGER'], $actor['roles'] ?? [])) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Business data export is restricted');
        }
        [$headers, $sql] = match ($kind) {
            'products' => [
                ['SKU', 'Barcode', 'Product', 'Category', 'Anime', 'Purchase Price', 'Selling Price', 'Status'],
                'SELECT p.sku,p.barcode,p.name,c.name AS category,a.name AS anime,p.purchase_price,p.selling_price,p.status '
                . 'FROM products p JOIN categories c ON c.id=p.category_id LEFT JOIN anime_franchises a ON a.id=p.anime_id ORDER BY p.sku',
            ],
            'inventory' => [
                ['SKU', 'Barcode', 'Product', 'Location Type', 'Location', 'Available', 'Reserved', 'Damaged', 'Average Cost', 'Inventory Value'],
                'SELECT p.sku,p.barcode,p.name,CASE WHEN i.store_id IS NULL THEN \'WAREHOUSE\' ELSE \'SHOP\' END AS location_type,'
                . 'COALESCE(s.name,w.name) AS location,i.available_quantity,i.reserved_quantity,i.damaged_quantity,i.average_cost,'
                . 'i.available_quantity*i.average_cost AS inventory_value FROM inventory i JOIN products p ON p.id=i.product_id '
                . 'LEFT JOIN stores s ON s.id=i.store_id LEFT JOIN warehouses w ON w.id=i.warehouse_id ORDER BY p.sku,location',
            ],
            default => throw new ApiException(404, 'not_implemented', 'Export unavailable'),
        };
        $handle = fopen('php://temp', 'w+');
        if ($handle === false) {
            throw new \RuntimeException('CSV export buffer unavailable');
        }
        fputcsv($handle, $headers, ',', '"', '');
        foreach ($this->database->query($sql) as $row) {
            $cells = [];
            foreach ($row as $value) {
                $cell = (string) ($value ?? '');
                $cells[] = preg_match('/^[\s]*[=+@-]/u', $cell) ? "'" . $cell : $cell;
            }
            fputcsv($handle, $cells, ',', '"', '');
        }
        rewind($handle);
        $content = stream_get_contents($handle);
        fclose($handle);
        if ($content === false) {
            throw new \RuntimeException('CSV export could not be read');
        }
        return $content;
    }
}
