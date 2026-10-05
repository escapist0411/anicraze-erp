<?php
declare(strict_types=1);

namespace Anicraze\People;

use Anicraze\Http\ApiException;
use PDO;

final class AccountDirectoryService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function list(array $actor): array
    {
        $roles = $actor['roles'] ?? [];
        if (!array_intersect(['OWNER', 'MANAGER'], $roles)) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Team directory is restricted');
        }
        $owner = in_array('OWNER', $roles, true);
        $sql = 'SELECT u.id,u.email,u.full_name,u.status,s.name AS store_name,r.code AS role_code '
            . 'FROM users u JOIN user_roles ur ON ur.user_id=u.id JOIN roles r ON r.id=ur.role_id '
            . 'LEFT JOIN stores s ON s.id=u.assigned_store_id'
            . ($owner ? '' : " WHERE r.code='SALES' OR u.id=?")
            . ' ORDER BY r.code,u.full_name,u.id';
        $query = $this->database->prepare($sql);
        $query->execute($owner ? [] : [$actor['id']]);
        return array_map(static fn (array $row): array => [
            'id' => $row['id'], 'employee_code' => null, 'name' => $row['full_name'],
            'email' => $row['email'], 'department' => $row['store_name'] ?? 'Operations',
            'designation' => $row['role_code'], 'status' => $row['status'],
        ], $query->fetchAll());
    }
}
