<?php
declare(strict_types=1);

namespace Anicraze\Catalog;

use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;
use Anicraze\Http\ApiException;
use PDO;
use PDOException;

final class ProductWriteService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function create(array $actor, array $body): array
    {
        $this->owner($actor);
        $values = $this->validate($body);
        try {
            $work = function () use ($actor, $body, $values): string {
                $sku = $body['sku'] ?? null;
                if ($sku === null || trim((string) $sku) === '') {
                    $sku = $this->nextSku($values['category_id']);
                } else {
                    $sku = strtoupper(trim((string) $sku));
                    if (preg_match('/^[A-Z0-9][A-Z0-9_-]{2,63}$/D', $sku) !== 1) {
                        throw new ApiException(422, 'validation_error', 'Invalid SKU');
                    }
                }
                $id = Uuid::v4();
                $columns = array_keys($values);
                $sql = 'INSERT INTO products (id,sku,barcode,' . implode(',', $columns) . ') VALUES (?,?,?,'
                    . implode(',', array_fill(0, count($columns), '?')) . ')';
                $this->database->prepare($sql)->execute([$id, $sku, $sku, ...array_values($values)]);
                $inventory = $this->database->prepare('INSERT INTO inventory (id,product_id,store_id,warehouse_id) VALUES (?,?,?,?)');
                foreach ($this->database->query("SELECT id FROM stores WHERE status='ACTIVE'")->fetchAll(PDO::FETCH_COLUMN) as $storeId) {
                    $inventory->execute([Uuid::v4(), $id, $storeId, null]);
                }
                foreach ($this->database->query("SELECT id FROM warehouses WHERE status='ACTIVE'")->fetchAll(PDO::FETCH_COLUMN) as $warehouseId) {
                    $inventory->execute([Uuid::v4(), $id, null, $warehouseId]);
                }
                $this->audit($actor, 'PRODUCT_CREATED', $id, ['sku' => $sku]);
                return $id;
            };
            $id = $this->database->inTransaction() ? $work() : Connection::transaction($this->database, $work);
        } catch (PDOException $error) {
            if (($error->errorInfo[0] ?? '') === '23000') {
                throw new ApiException(409, 'PRODUCT_IDENTITY_EXISTS', 'SKU, barcode, or import reference already exists');
            }
            throw $error;
        }
        return (new ProductService($this->database))->find($actor, 'id', $id);
    }

    public function update(array $actor, string $id, array $body): array
    {
        $this->owner($actor);
        try {
            Connection::transaction($this->database, function () use ($actor, $id, $body): void {
                $query = $this->database->prepare('SELECT * FROM products WHERE id=? AND deleted_at IS NULL FOR UPDATE');
                $query->execute([$id]);
                $current = $query->fetch();
                if (!$current) {
                    throw new ApiException(404, 'PRODUCT_NOT_FOUND', 'Product not found');
                }
                foreach (['sku', 'barcode'] as $identity) {
                    if (isset($body[$identity]) && trim((string) $body[$identity]) !== ''
                        && strcasecmp(trim((string) $body[$identity]), $current[$identity]) !== 0) {
                        throw new ApiException(409, 'PRODUCT_IDENTITY_IMMUTABLE', 'Existing SKU and barcode cannot be changed');
                    }
                }
                $values = $this->validate(array_merge($current, $body));
                $columns = array_keys($values);
                $assignments = array_map(static fn (string $column): string => $column . '=?', $columns);
                $this->database->prepare('UPDATE products SET ' . implode(',', $assignments)
                    . ',updated_at=UTC_TIMESTAMP(6) WHERE id=?')->execute([...array_values($values), $id]);
                $this->audit($actor, 'PRODUCT_UPDATED', $id, ['changed_fields' => array_keys($body)]);
            });
        } catch (PDOException $error) {
            if (($error->errorInfo[0] ?? '') === '23000') {
                throw new ApiException(409, 'PRODUCT_IDENTITY_EXISTS', 'Product identity already exists');
            }
            throw $error;
        }
        return (new ProductService($this->database))->find($actor, 'id', $id);
    }

    public function archive(array $actor, string $id): void
    {
        $this->owner($actor);
        Connection::transaction($this->database, function () use ($actor, $id): void {
            $query = $this->database->prepare('SELECT id FROM products WHERE id=? AND deleted_at IS NULL FOR UPDATE');
            $query->execute([$id]);
            if (!$query->fetchColumn()) {
                throw new ApiException(404, 'PRODUCT_NOT_FOUND', 'Product not found');
            }
            $this->database->prepare("UPDATE products SET status='ARCHIVED',deleted_at=UTC_TIMESTAMP(6),updated_at=UTC_TIMESTAMP(6) WHERE id=?")
                ->execute([$id]);
            $this->audit($actor, 'PRODUCT_ARCHIVED', $id, []);
        });
    }

    private function nextSku(string $categoryId): string
    {
        $category = $this->database->prepare('SELECT code FROM categories WHERE id=?');
        $category->execute([$categoryId]);
        $prefix = substr(preg_replace('/[^A-Z0-9]/', '', strtoupper((string) $category->fetchColumn())) . 'XXX', 0, 3);
        $this->database->exec("INSERT INTO product_sku_counters (counter_key,current_value) VALUES ('PRODUCT',0) ON DUPLICATE KEY UPDATE counter_key=counter_key");
        $counter = $this->database->query("SELECT current_value FROM product_sku_counters WHERE counter_key='PRODUCT' FOR UPDATE");
        $current = (int) $counter->fetchColumn();
        $maximum = (int) $this->database->query("SELECT COALESCE(MAX(CAST(SUBSTRING_INDEX(sku,'-',-1) AS UNSIGNED)),0) FROM products WHERE sku REGEXP '^ANI-[A-Z0-9]{3}-[0-9]{6}$'")->fetchColumn();
        $value = max($current, $maximum);
        do {
            $value++;
            $sku = 'ANI-' . $prefix . '-' . str_pad((string) $value, 6, '0', STR_PAD_LEFT);
            $probe = $this->database->prepare('SELECT id FROM products WHERE sku=?');
            $probe->execute([$sku]);
        } while ($probe->fetchColumn() !== false);
        $this->database->prepare("UPDATE product_sku_counters SET current_value=? WHERE counter_key='PRODUCT'")->execute([$value]);
        return $sku;
    }

    private function validate(array $body): array
    {
        $name = trim((string) ($body['name'] ?? ''));
        $categoryId = $body['category_id'] ?? null;
        if (mb_strlen($name) < 2 || mb_strlen($name) > 220 || !is_string($categoryId) || strlen($categoryId) !== 36) {
            throw new ApiException(422, 'validation_error', 'Product name and category are required');
        }
        $category = $this->database->prepare("SELECT id FROM categories WHERE id=? AND status='ACTIVE'");
        $category->execute([$categoryId]);
        if (!$category->fetchColumn()) {
            throw new ApiException(422, 'CATEGORY_NOT_FOUND', 'Active category is required');
        }
        foreach (['brand_id' => 'brands', 'anime_id' => 'anime_franchises', 'character_id' => 'characters'] as $field => $table) {
            $value = $body[$field] ?? null;
            if ($value === '') {
                $value = null;
            }
            if ($value !== null) {
                if (!is_string($value) || strlen($value) !== 36) {
                    throw new ApiException(422, 'validation_error', 'Invalid catalog reference');
                }
                $query = $this->database->prepare("SELECT id FROM {$table} WHERE id=? AND status='ACTIVE'");
                $query->execute([$value]);
                if (!$query->fetchColumn()) {
                    throw new ApiException(422, 'validation_error', 'Catalog reference not found');
                }
            }
            $body[$field] = $value;
        }
        if ($body['character_id'] !== null) {
            $query = $this->database->prepare('SELECT anime_id FROM characters WHERE id=?');
            $query->execute([$body['character_id']]);
            $characterAnime = $query->fetchColumn();
            if ($body['anime_id'] !== null && $body['anime_id'] !== $characterAnime) {
                throw new ApiException(422, 'PRODUCT_CHARACTER_ANIME_MISMATCH', 'Character does not belong to selected anime');
            }
            $body['anime_id'] = $characterAnime;
        }
        $values = ['name' => $name, 'category_id' => $categoryId,
            'brand_id' => $body['brand_id'], 'anime_id' => $body['anime_id'], 'character_id' => $body['character_id']];
        $type = strtoupper(trim((string) ($body['product_type'] ?? 'OTHER')));
        if (preg_match('/^[A-Z_]{3,30}$/D', $type) !== 1) {
            throw new ApiException(422, 'validation_error', 'Invalid product type');
        }
        $values['product_type'] = $type;
        foreach (['purchase_price', 'selling_price'] as $field) {
            $values[$field] = self::money($body[$field] ?? 0, false);
        }
        foreach (['landed_cost', 'mrp', 'minimum_selling_price'] as $field) {
            $values[$field] = self::money($body[$field] ?? null, true);
        }
        if ($values['landed_cost'] !== null && (int) str_replace('.', '', $values['landed_cost'])
            < (int) str_replace('.', '', $values['purchase_price'])) {
            throw new ApiException(422, 'PRODUCT_PRICING_INVALID', 'Landed cost cannot be below purchase price');
        }
        if ($values['mrp'] !== null && (int) str_replace('.', '', $values['mrp'])
            < (int) str_replace('.', '', $values['selling_price'])) {
            throw new ApiException(422, 'PRODUCT_PRICING_INVALID', 'MRP cannot be below selling price');
        }
        if ($values['minimum_selling_price'] !== null && (int) str_replace('.', '', $values['minimum_selling_price'])
            > (int) str_replace('.', '', $values['selling_price'])) {
            throw new ApiException(422, 'PRODUCT_PRICING_INVALID', 'Minimum price exceeds selling price');
        }
        foreach (['short_description' => 500, 'description' => 10000, 'material' => 120, 'edition' => 120,
            'manufacturer' => 160, 'country_of_origin' => 100, 'import_reference' => 120] as $field => $limit) {
            $value = $body[$field] ?? null;
            if ($value !== null && (!is_string($value) || mb_strlen($value) > $limit)) {
                throw new ApiException(422, 'validation_error', 'Invalid product field: ' . $field);
            }
            $values[$field] = $value === '' ? null : $value;
        }
        $discount = $body['discount_percentage'] ?? 0;
        if (!is_numeric($discount) || (float) $discount < 0 || (float) $discount > 100) {
            throw new ApiException(422, 'validation_error', 'Invalid discount percentage');
        }
        $values['discount_percentage'] = number_format((float) $discount, 2, '.', '');
        $reorder = $body['reorder_level'] ?? 0;
        if (!is_int($reorder) || $reorder < 0 || $reorder > 1000000) {
            throw new ApiException(422, 'validation_error', 'Invalid reorder level');
        }
        $values['reorder_level'] = $reorder;
        $unit = trim((string) ($body['unit_of_measure'] ?? 'piece'));
        if ($unit === '' || mb_strlen($unit) > 40) {
            throw new ApiException(422, 'validation_error', 'Invalid unit');
        }
        $values['unit_of_measure'] = $unit;
        foreach (['weight', 'length', 'width', 'height'] as $field) {
            $number = $body[$field] ?? null;
            if ($number !== null && (!is_numeric($number) || (float) $number < 0 || (float) $number > 999999999)) {
                throw new ApiException(422, 'validation_error', 'Invalid dimension');
            }
            $values[$field] = $number === null ? null : number_format((float) $number, 3, '.', '');
        }
        foreach (['is_serialized', 'is_featured'] as $field) {
            $values[$field] = !empty($body[$field]) ? 1 : 0;
        }
        $status = strtoupper((string) ($body['status'] ?? 'DRAFT'));
        if (!in_array($status, ['DRAFT', 'ACTIVE', 'INACTIVE'], true)) {
            throw new ApiException(422, 'validation_error', 'Invalid product status');
        }
        $values['status'] = $status;
        return $values;
    }

    private static function money(mixed $value, bool $optional): ?string
    {
        if ($optional && ($value === null || $value === '')) {
            return null;
        }
        if ((!is_string($value) && !is_int($value) && !is_float($value))
            || preg_match('/^\d{1,10}(?:\.\d{1,2})?$/D', (string) $value) !== 1) {
            throw new ApiException(422, 'validation_error', 'Invalid price');
        }
        [$whole, $fraction] = array_pad(explode('.', (string) $value, 2), 2, '');
        return (int) $whole . '.' . str_pad($fraction, 2, '0');
    }

    private function audit(array $actor, string $action, string $id, array $context): void
    {
        $this->database->prepare('INSERT INTO audit_logs (id,actor_user_id,action,entity_type,entity_id,context_json) VALUES (?,?,?,?,?,?)')
            ->execute([Uuid::v4(), $actor['id'], $action, 'product', $id, json_encode($context, JSON_THROW_ON_ERROR)]);
    }

    private function owner(array $actor): void
    {
        if (!in_array('OWNER', $actor['roles'] ?? [], true)) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Product changes require Owner access');
        }
    }
}
