<?php
declare(strict_types=1);

namespace Anicraze\Catalog;

use Anicraze\Http\ApiException;
use PDO;

final class ProductService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function list(array $actor, array $query): array
    {
        $page = filter_var($query['page'] ?? 1, FILTER_VALIDATE_INT);
        $size = filter_var($query['page_size'] ?? 25, FILTER_VALIDATE_INT);
        if ($page === false || $page < 1 || $size === false || $size < 1 || $size > 100) {
            throw new ApiException(422, 'validation_error', 'Invalid page or page size');
        }
        [$where, $params] = $this->scope($actor);
        $where[] = 'p.deleted_at IS NULL';
        if (isset($query['search']) && trim((string) $query['search']) !== '') {
            $where[] = '(p.name LIKE ? OR p.sku LIKE ? OR p.barcode LIKE ? OR a.name LIKE ?)';
            $term = '%' . addcslashes(trim((string) $query['search']), '%_\\') . '%';
            array_push($params, $term, $term, $term, $term);
        }
        foreach (['category_id' => 'p.category_id', 'anime_id' => 'p.anime_id', 'status' => 'p.status'] as $key => $column) {
            if (isset($query[$key]) && trim((string) $query[$key]) !== '') {
                $where[] = $column . '=?';
                $params[] = trim((string) $query[$key]);
            }
        }
        if (isset($query['missing_barcode'])) {
            $flag = filter_var($query['missing_barcode'], FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE);
            if ($flag === null) {
                throw new ApiException(422, 'validation_error', 'Invalid barcode filter');
            }
            $where[] = $flag ? "(p.barcode IS NULL OR p.barcode='')" : "(p.barcode IS NOT NULL AND p.barcode<>'')";
        }
        $from = ' FROM products p JOIN categories c ON c.id=p.category_id LEFT JOIN anime_franchises a ON a.id=p.anime_id'
            . ' LEFT JOIN brands b ON b.id=p.brand_id LEFT JOIN characters ch ON ch.id=p.character_id';
        $clause = $where === [] ? '' : ' WHERE ' . implode(' AND ', $where);
        $count = $this->database->prepare('SELECT COUNT(*)' . $from . $clause);
        $count->execute($params);
        $total = (int) $count->fetchColumn();
        $sql = 'SELECT p.*,c.name AS category_name,c.code AS category_code,a.name AS anime_name,a.code AS anime_code,'
            . 'b.name AS brand_name,b.code AS brand_code,ch.name AS character_name,ch.code AS character_code,'
            . '(SELECT storage_key FROM product_images im WHERE im.product_id=p.id ORDER BY im.is_primary DESC,im.sort_order,im.id LIMIT 1) AS primary_image_key'
            . $from . $clause . ' ORDER BY p.name,p.id LIMIT ' . (int) $size . ' OFFSET ' . (int) (($page - 1) * $size);
        $statement = $this->database->prepare($sql);
        $statement->execute($params);
        return ['items' => array_map($this->serialize(...), $statement->fetchAll()),
            'page' => $page, 'page_size' => $size, 'total' => $total, 'pages' => (int) ceil($total / $size)];
    }

    public function find(array $actor, string $field, string $value): array
    {
        if (!in_array($field, ['id', 'sku', 'barcode'], true) || strlen($value) > 128) {
            throw new ApiException(422, 'validation_error', 'Invalid product lookup');
        }
        $value = trim($value);
        if ($value === '') {
            throw new ApiException(422, 'validation_error', 'Invalid product lookup');
        }
        [$where, $params] = $this->scope($actor);
        $where[] = 'p.deleted_at IS NULL';
        $where[] = $field === 'barcode' ? 'LOWER(p.barcode)=LOWER(?)' : "p.{$field}=?";
        $params[] = $value;
        $statement = $this->database->prepare('SELECT p.*,c.name AS category_name,c.code AS category_code,a.name AS anime_name,a.code AS anime_code,'
            . 'b.name AS brand_name,b.code AS brand_code,ch.name AS character_name,ch.code AS character_code,'
            . '(SELECT storage_key FROM product_images im WHERE im.product_id=p.id ORDER BY im.is_primary DESC,im.sort_order,im.id LIMIT 1) AS primary_image_key'
            . ' FROM products p JOIN categories c ON c.id=p.category_id LEFT JOIN anime_franchises a ON a.id=p.anime_id'
            . ' LEFT JOIN brands b ON b.id=p.brand_id LEFT JOIN characters ch ON ch.id=p.character_id'
            . ' WHERE ' . implode(' AND ', $where) . ' LIMIT 1');
        $statement->execute($params);
        $product = $statement->fetch();
        if (!$product) {
            throw new ApiException(404, 'PRODUCT_NOT_FOUND', 'Product not found');
        }
        return $this->serialize($product, $this->images($product['id']));
    }

    private function scope(array $actor): array
    {
        $roles = $actor['roles'] ?? [];
        if (in_array('OWNER', $roles, true) || in_array('MANAGER', $roles, true)) {
            return [[], []];
        }
        throw new ApiException(403, 'AUTH_FORBIDDEN', 'Product master access is restricted');
    }

    private function images(string $productId): array
    {
        $statement = $this->database->prepare('SELECT id,storage_key,alt_text,sort_order,is_primary,created_at FROM product_images WHERE product_id=? ORDER BY is_primary DESC,sort_order,id');
        $statement->execute([$productId]);
        return array_map(static fn (array $image): array => [
            'id' => $image['id'], 'file_url' => '/product-images/' . $image['storage_key'],
            'alt_text' => $image['alt_text'], 'sort_order' => (int) $image['sort_order'],
            'is_primary' => (bool) $image['is_primary'],
            'created_at' => str_replace(' ', 'T', $image['created_at']) . 'Z',
        ], $statement->fetchAll());
    }

    private function serialize(array $row, array $images = []): array
    {
        return [
            'id' => $row['id'], 'sku' => $row['sku'], 'barcode' => $row['barcode'], 'name' => $row['name'],
            'slug' => strtolower(preg_replace('/[^a-z0-9]+/i', '-', $row['name'])),
            'short_description' => $row['short_description'], 'description' => $row['description'],
            'category' => ['id' => $row['category_id'], 'name' => $row['category_name'], 'code' => $row['category_code']],
            'brand' => $row['brand_id'] === null ? null : ['id' => $row['brand_id'], 'name' => $row['brand_name'], 'code' => $row['brand_code']],
            'anime' => $row['anime_id'] === null ? null : ['id' => $row['anime_id'], 'name' => $row['anime_name'], 'code' => $row['anime_code']],
            'character' => $row['character_id'] === null ? null : ['id' => $row['character_id'], 'name' => $row['character_name'], 'code' => $row['character_code']],
            'product_type' => $row['product_type'], 'edition' => $row['edition'],
            'import_reference' => $row['import_reference'], 'purchase_price' => $row['purchase_price'],
            'landed_cost' => $row['landed_cost'], 'selling_price' => $row['selling_price'],
            'mrp' => $row['mrp'], 'minimum_selling_price' => $row['minimum_selling_price'],
            'discount_percentage' => $row['discount_percentage'], 'reorder_level' => (int) $row['reorder_level'],
            'unit_of_measure' => $row['unit_of_measure'], 'material' => $row['material'],
            'manufacturer' => $row['manufacturer'], 'country_of_origin' => $row['country_of_origin'],
            'weight' => $row['weight'], 'length' => $row['length'], 'width' => $row['width'], 'height' => $row['height'],
            'is_serialized' => (bool) $row['is_serialized'], 'is_featured' => (bool) $row['is_featured'],
            'status' => $row['status'],
            'primary_image' => $row['primary_image_key'] === null ? null : '/product-images/' . $row['primary_image_key'],
            'images' => $images, 'variants' => [], 'updated_at' => str_replace(' ', 'T', $row['updated_at']) . 'Z',
        ];
    }
}
