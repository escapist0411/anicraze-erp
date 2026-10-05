<?php
declare(strict_types=1);

namespace Anicraze\Catalog;

use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;
use Anicraze\Http\ApiException;
use PDO;

final class ProductImageService
{
    private const LIMIT_BYTES = 5 * 1024 * 1024;
    private const MIMES = ['image/jpeg' => 'jpg', 'image/png' => 'png', 'image/webp' => 'webp'];

    public function __construct(private readonly PDO $database)
    {
    }

    public static function validateFile(string $path, string $originalName, int $size): string
    {
        $extension = strtolower(pathinfo($originalName, PATHINFO_EXTENSION));
        if (!in_array($extension, ['jpg', 'jpeg', 'png', 'webp'], true)
            || $size < 1 || $size > self::LIMIT_BYTES || !is_file($path) || filesize($path) !== $size) {
            throw new ApiException(422, 'PRODUCT_IMAGE_TYPE_INVALID', 'Only JPEG, PNG and WEBP images up to 5 MB are allowed');
        }
        $mime = (new \finfo(FILEINFO_MIME_TYPE))->file($path);
        $expected = match ($extension) {
            'jpg', 'jpeg' => 'image/jpeg', 'png' => 'image/png', 'webp' => 'image/webp',
        };
        if ($mime !== $expected || !isset(self::MIMES[$mime])) {
            throw new ApiException(422, 'PRODUCT_IMAGE_CONTENT_INVALID', 'Image content does not match its file type');
        }
        $dimensions = @getimagesize($path);
        if (!is_array($dimensions) || $dimensions[0] < 1 || $dimensions[1] < 1
            || $dimensions[0] > 10000 || $dimensions[1] > 10000
            || $dimensions[0] * $dimensions[1] > 25000000) {
            throw new ApiException(422, 'PRODUCT_IMAGE_CONTENT_INVALID', 'Image dimensions are invalid');
        }
        return self::MIMES[$mime];
    }

    public function upload(array $actor, string $productId, string $sourcePath, string $originalName, int $size): array
    {
        if (!in_array('OWNER', $actor['roles'] ?? [], true)) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Product image upload requires Owner access');
        }
        $extension = self::validateFile($sourcePath, $originalName, $size);
        $product = $this->database->prepare('SELECT id FROM products WHERE id=? AND deleted_at IS NULL');
        $product->execute([$productId]);
        if (!$product->fetchColumn()) {
            throw new ApiException(404, 'PRODUCT_NOT_FOUND', 'Product not found');
        }
        $folder = dirname(__DIR__, 2) . '/public/product-images';
        if (!is_dir($folder) || !is_writable($folder)) {
            throw new ApiException(503, 'PRODUCT_IMAGE_STORAGE_UNAVAILABLE', 'Product image storage is unavailable');
        }
        $key = bin2hex(random_bytes(16)) . '.' . $extension;
        $destination = $folder . '/' . $key;
        if (!move_uploaded_file($sourcePath, $destination)) {
            throw new ApiException(500, 'PRODUCT_IMAGE_SAVE_FAILED', 'Product image could not be stored');
        }
        try {
            [$id, $imageCount] = Connection::transaction($this->database, function () use ($actor, $productId, $key, $size, $extension): array {
                $lock = $this->database->prepare('SELECT id FROM products WHERE id=? AND deleted_at IS NULL FOR UPDATE');
                $lock->execute([$productId]);
                if (!$lock->fetchColumn()) {
                    throw new ApiException(404, 'PRODUCT_NOT_FOUND', 'Product not found');
                }
                $count = $this->database->prepare('SELECT COUNT(*) FROM product_images WHERE product_id=?');
                $count->execute([$productId]);
                $imageCount = (int) $count->fetchColumn();
                if ($imageCount >= 10) {
                    throw new ApiException(409, 'PRODUCT_IMAGE_LIMIT', 'A product can have at most 10 images');
                }
                $id = Uuid::v4();
                $mime = array_search($extension, self::MIMES, true);
                $this->database->prepare('INSERT INTO product_images (id,product_id,storage_key,mime_type,size_bytes,sort_order,is_primary) VALUES (?,?,?,?,?,?,?)')
                    ->execute([$id, $productId, $key, $mime, $size, $imageCount, $imageCount === 0 ? 1 : 0]);
                $this->database->prepare('INSERT INTO audit_logs (id,actor_user_id,action,entity_type,entity_id,context_json) VALUES (?,?,?,?,?,?)')
                    ->execute([Uuid::v4(), $actor['id'], 'PRODUCT_IMAGE_UPLOADED', 'product', $productId,
                        json_encode(['image_id' => $id], JSON_THROW_ON_ERROR)]);
                return [$id, $imageCount];
            });
        } catch (\Throwable $error) {
            unlink($destination);
            throw $error;
        }
        return ['id' => $id, 'file_url' => '/product-images/' . $key, 'alt_text' => null,
            'sort_order' => $imageCount, 'is_primary' => $imageCount === 0,
            'created_at' => gmdate('Y-m-d\TH:i:s\Z')];
    }
}
