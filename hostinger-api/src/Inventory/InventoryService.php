<?php
declare(strict_types=1);

namespace Anicraze\Inventory;

use Anicraze\Http\ApiException;
use PDO;

final class InventoryService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function locations(array $actor, string $kind): array
    {
        if ($kind === 'warehouses') {
            $this->operator($actor);
            return $this->database->query('SELECT id,code,name,NULL AS address,status FROM warehouses ORDER BY name')->fetchAll();
        }
        if ($kind !== 'stores') {
            throw new ApiException(404, 'not_found', 'Location not found');
        }
        if ($this->isGlobal($actor)) {
            return $this->database->query('SELECT id,code,name,address,status FROM stores ORDER BY name')->fetchAll();
        }
        $storeId = $this->salesStore($actor);
        $statement = $this->database->prepare('SELECT id,code,name,address,status FROM stores WHERE id=?');
        $statement->execute([$storeId]);
        return $statement->fetchAll();
    }

    public function list(array $actor, array $query): array
    {
        $page = filter_var($query['page'] ?? 1, FILTER_VALIDATE_INT);
        $size = filter_var($query['page_size'] ?? 25, FILTER_VALIDATE_INT);
        if ($page === false || $page < 1 || $size === false || $size < 1 || $size > 100) {
            throw new ApiException(422, 'validation_error', 'Invalid page or page size');
        }
        [$where, $params] = $this->scope($actor);
        foreach (['store_id' => 'i.store_id', 'warehouse_id' => 'i.warehouse_id',
            'product_id' => 'i.product_id'] as $key => $column) {
            if (isset($query[$key]) && trim((string) $query[$key]) !== '') {
                $where[] = $column . '=?';
                $params[] = trim((string) $query[$key]);
            }
        }
        if (isset($query['search']) && trim((string) $query['search']) !== '') {
            $where[] = '(p.name LIKE ? OR p.sku LIKE ? OR p.barcode LIKE ?)';
            $term = '%' . addcslashes(trim((string) $query['search']), '%_\\') . '%';
            array_push($params, $term, $term, $term);
        }
        $from = ' FROM inventory i JOIN products p ON p.id=i.product_id JOIN categories c ON c.id=p.category_id'
            . ' LEFT JOIN stores s ON s.id=i.store_id LEFT JOIN warehouses w ON w.id=i.warehouse_id';
        $clause = ' WHERE ' . implode(' AND ', $where);
        $count = $this->database->prepare('SELECT COUNT(*)' . $from . $clause);
        $count->execute($params);
        $total = (int) $count->fetchColumn();
        $statement = $this->database->prepare('SELECT i.*,i.available_quantity*i.average_cost AS inventory_value,p.sku,p.barcode,p.name AS product_name,p.reorder_level,c.name AS category_name,'
            . 's.name AS store_name,w.name AS warehouse_name,(SELECT MAX(m.created_at) FROM inventory_movements m WHERE m.inventory_id=i.id) AS last_movement_at'
            . $from . $clause . ' ORDER BY p.name,i.id LIMIT ' . (int) $size . ' OFFSET ' . (int) (($page - 1) * $size));
        $statement->execute($params);
        return ['items' => array_map($this->serialize(...), $statement->fetchAll()), 'page' => $page,
            'page_size' => $size, 'total' => $total, 'pages' => (int) ceil($total / $size)];
    }

    public function get(array $actor, string $id): array
    {
        $this->operator($actor);
        $statement = $this->database->prepare('SELECT i.*,i.available_quantity*i.average_cost AS inventory_value,'
            . 'p.sku,p.barcode,p.name AS product_name,p.reorder_level,c.name AS category_name,'
            . 's.name AS store_name,w.name AS warehouse_name,'
            . '(SELECT MAX(m.created_at) FROM inventory_movements m WHERE m.inventory_id=i.id) AS last_movement_at '
            . 'FROM inventory i JOIN products p ON p.id=i.product_id JOIN categories c ON c.id=p.category_id '
            . 'LEFT JOIN stores s ON s.id=i.store_id LEFT JOIN warehouses w ON w.id=i.warehouse_id WHERE i.id=?');
        $statement->execute([$id]);
        $row = $statement->fetch();
        if (!$row) {
            throw new ApiException(404, 'INVENTORY_NOT_FOUND', 'Inventory row not found');
        }
        return $this->serialize($row);
    }

    public function stockReport(array $actor): array
    {
        $this->operator($actor);
        $statement = $this->database->query('SELECT i.*,i.available_quantity*i.average_cost AS inventory_value,'
            . 'p.sku,p.barcode,p.name AS product_name,p.reorder_level,c.name AS category_name,s.name AS store_name,w.name AS warehouse_name,'
            . '(SELECT MAX(m.created_at) FROM inventory_movements m WHERE m.inventory_id=i.id) AS last_movement_at '
            . 'FROM inventory i JOIN products p ON p.id=i.product_id JOIN categories c ON c.id=p.category_id '
            . 'LEFT JOIN stores s ON s.id=i.store_id LEFT JOIN warehouses w ON w.id=i.warehouse_id '
            . 'ORDER BY p.name,i.id');
        return array_map($this->serialize(...), $statement->fetchAll());
    }

    public function summary(array $actor): array
    {
        $this->operator($actor);
        $totals = $this->database->query('SELECT COALESCE(SUM(i.available_quantity*i.average_cost),0) AS inventory_value,'
            . 'COALESCE(SUM(i.available_quantity),0) AS available_units,COALESCE(SUM(i.reserved_quantity),0) AS reserved_units,'
            . 'SUM(i.available_quantity=0) AS out_of_stock_count,'
            . 'SUM(i.available_quantity>0 AND i.available_quantity<=p.reorder_level) AS low_stock_count,'
            . 'COUNT(*) AS stock_rows FROM inventory i JOIN products p ON p.id=i.product_id')->fetch();
        $rows = $this->database->query('SELECT i.id,p.sku,p.name,i.available_quantity,'
            . '(SELECT MAX(m.created_at) FROM inventory_movements m WHERE m.inventory_id=i.id) AS last_movement_at '
            . 'FROM inventory i JOIN products p ON p.id=i.product_id ORDER BY i.available_quantity DESC,p.name')->fetchAll();
        $compact = static fn (array $row): array => ['inventory_id' => $row['id'], 'sku' => $row['sku'],
            'name' => $row['name'], 'quantity' => (int) $row['available_quantity']];
        $oldest = gmdate('Y-m-d H:i:s', time() - 90 * 86400);
        $dead = count(array_filter($rows, static fn (array $row): bool => $row['last_movement_at'] === null
            || $row['last_movement_at'] < $oldest));
        $comparison = static function (PDO $db, string $location): array {
            $table = $location === 'store' ? 'stores' : 'warehouses';
            $column = $location . '_id';
            $query = $db->query("SELECT l.name AS location,COALESCE(SUM(i.available_quantity),0) AS quantity,"
                . "COALESCE(SUM(i.available_quantity*i.average_cost),0) AS value FROM inventory i "
                . "JOIN {$table} l ON l.id=i.{$column} GROUP BY l.id,l.name ORDER BY l.name");
            return array_map(static fn (array $row): array => ['location' => $row['location'],
                'quantity' => (int) $row['quantity'], 'value' => $row['value']], $query->fetchAll());
        };
        return ['total_inventory_value' => $totals['inventory_value'],
            'total_available_quantity' => (int) $totals['available_units'],
            'total_reserved_quantity' => (int) $totals['reserved_units'],
            'low_stock_count' => (int) $totals['low_stock_count'], 'out_of_stock_count' => (int) $totals['out_of_stock_count'],
            'reorder_count' => (int) $totals['out_of_stock_count'] + (int) $totals['low_stock_count'], 'dead_stock_count' => $dead,
            'fast_moving' => array_map($compact, array_slice($rows, 0, 10)),
            'slow_moving' => array_map($compact, array_slice($rows, -10)),
            'top_products' => array_map($compact, array_slice($rows, 0, 10)),
            'store_comparison' => $comparison($this->database, 'store'),
            'warehouse_comparison' => $comparison($this->database, 'warehouse')];
    }

    public function movements(array $actor, array $query): array
    {
        [$where, $params] = $this->scope($actor);
        if (isset($query['inventory_id']) && $query['inventory_id'] !== '') {
            $where[] = 'i.id=?';
            $params[] = $query['inventory_id'];
        }
        $statement = $this->database->prepare('SELECT m.*,i.store_id,i.warehouse_id FROM inventory_movements m JOIN inventory i ON i.id=m.inventory_id WHERE '
            . implode(' AND ', $where) . ' ORDER BY m.created_at DESC LIMIT 200');
        $statement->execute($params);
        return array_map(static fn (array $row): array => [
            'id' => $row['id'], 'inventory_id' => $row['inventory_id'], 'product_id' => $row['product_id'],
            'store_id' => $row['store_id'], 'warehouse_id' => $row['warehouse_id'],
            'transaction_type' => $row['movement_type'], 'quantity' => (int) $row['quantity_delta'],
            'quantity_changed' => (int) $row['quantity_delta'], 'unit_cost' => $row['unit_cost'],
            'reference_number' => $row['reference_number'] ?? $row['reference_id'], 'remarks' => $row['remarks'],
            'created_at' => str_replace(' ', 'T', $row['created_at']) . 'Z',
        ], $statement->fetchAll());
    }

    private function scope(array $actor): array
    {
        if ($this->isGlobal($actor)) {
            return [['1=1'], []];
        }
        return [['i.store_id=?'], [$this->salesStore($actor)]];
    }

    private function isGlobal(array $actor): bool
    {
        return (bool) array_intersect(['OWNER', 'MANAGER'], $actor['roles'] ?? []);
    }

    private function operator(array $actor): void
    {
        if (!$this->isGlobal($actor)) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Warehouse access is restricted');
        }
    }

    private function salesStore(array $actor): string
    {
        if (!in_array('SALES', $actor['roles'] ?? [], true) || empty($actor['assigned_store_id'])) {
            throw new ApiException(403, 'AUTH_SHOP_UNASSIGNED', 'Assigned shop is required');
        }
        return $actor['assigned_store_id'];
    }

    private function serialize(array $row): array
    {
        $available = (int) $row['available_quantity'];
        $value = $row['inventory_value'];
        return [
            'id' => $row['id'], 'product_id' => $row['product_id'], 'variant_id' => null,
            'sku' => $row['sku'], 'barcode' => $row['barcode'], 'product_name' => $row['product_name'],
            'category' => $row['category_name'], 'brand' => null, 'anime' => null,
            'store' => $row['store_id'] === null ? null : ['id' => $row['store_id'], 'name' => $row['store_name']],
            'warehouse' => $row['warehouse_id'] === null ? null : ['id' => $row['warehouse_id'], 'name' => $row['warehouse_name']],
            'available_quantity' => $available, 'reserved_quantity' => (int) $row['reserved_quantity'],
            'damaged_quantity' => (int) $row['damaged_quantity'], 'minimum_stock' => (int) $row['reorder_level'],
            'reorder_level' => (int) $row['reorder_level'],
            'total_quantity' => $available + (int) $row['reserved_quantity'] + (int) $row['damaged_quantity'] + (int) $row['in_transit_quantity'],
            'maximum_stock' => null,
            'average_cost' => $row['average_cost'], 'last_purchase_cost' => $row['last_purchase_cost'],
            'inventory_value' => $value, 'stock_level' => $available === 0 ? 'OUT_OF_STOCK'
                : ($available <= (int) $row['reorder_level'] ? 'LOW_STOCK' : 'HEALTHY'),
            'reorder_recommended' => $available <= (int) $row['reorder_level'],
            'last_movement_at' => $row['last_movement_at'] === null ? null : str_replace(' ', 'T', $row['last_movement_at']) . 'Z',
            'updated_at' => str_replace(' ', 'T', $row['updated_at']) . 'Z',
        ];
    }
}
