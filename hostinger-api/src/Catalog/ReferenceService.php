<?php
declare(strict_types=1);

namespace Anicraze\Catalog;

use Anicraze\Http\ApiException;
use PDO;

final class ReferenceService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function list(array $actor, string $kind, array $query = []): array
    {
        if (!array_intersect(['OWNER', 'MANAGER'], $actor['roles'] ?? [])) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Catalog reference access is restricted');
        }
        $table = match ($kind) {
            'categories' => 'categories',
            'anime' => 'anime_franchises',
            'brands' => 'brands',
            'characters' => 'characters',
            default => throw new ApiException(404, 'not_implemented', 'Catalog reference unavailable'),
        };
        $order = $kind === 'categories' ? 'sort_order,name' : 'name';
        if ($kind === 'categories') {
            return $this->database->query("SELECT id,code,name,description,status FROM {$table} ORDER BY {$order}")->fetchAll();
        }
        if ($kind === 'characters') {
            $anime = $this->database->prepare('SELECT id,code,name,NULL AS description,status,anime_id FROM characters'
                . ' WHERE (? IS NULL OR anime_id=?) ORDER BY name');
            $id = $query['anime_id'] ?? null;
            if ($id !== null && (!is_string($id) || strlen($id) !== 36)) {
                throw new ApiException(422, 'validation_error', 'Invalid anime filter');
            }
            $anime->execute([$id, $id]);
            return $anime->fetchAll();
        }
        return $this->database->query("SELECT id,code,name,NULL AS description,status FROM {$table} ORDER BY {$order}")->fetchAll();
    }
}
