<?php
declare(strict_types=1);

namespace Anicraze\Notifications;

use Anicraze\Database\Uuid;
use Anicraze\Http\ApiException;
use PDO;

final class NotificationService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function list(array $actor, array $query = []): array
    {
        $this->operator($actor);
        $category = $query['category'] ?? null;
        $unread = filter_var($query['unread'] ?? false, FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE);
        $limit = filter_var($query['limit'] ?? 100, FILTER_VALIDATE_INT);
        if ($category !== null && !in_array($category, ['INVENTORY', 'TRANSFER', 'PROCUREMENT', 'PAYMENT', 'COMMUNICATION', 'REPORT', 'SYSTEM'], true)
            || $unread === null || $limit === false || $limit < 1 || $limit > 200) {
            throw new ApiException(422, 'validation_error', 'Invalid notification filter');
        }
        $sql = 'SELECT * FROM notifications WHERE user_id=? AND is_resolved=0'
            . ($category !== null ? ' AND category=?' : '') . ($unread ? ' AND is_read=0' : '')
            . ' ORDER BY created_at DESC,id DESC LIMIT ' . (int) $limit;
        $statement = $this->database->prepare($sql);
        $statement->execute($category === null ? [$actor['id']] : [$actor['id'], $category]);
        return array_map(self::serialize(...), $statement->fetchAll());
    }

    public function summary(array $actor): array
    {
        $this->operator($actor);
        $statement = $this->database->prepare('SELECT COUNT(*) AS active_count,'
            . 'COALESCE(SUM(is_read=0),0) AS unread_count,'
            . "COALESCE(SUM(severity='CRITICAL'),0) AS critical_count,"
            . "COALESCE(SUM(severity='WARNING'),0) AS warning_count "
            . 'FROM notifications WHERE user_id=? AND is_resolved=0');
        $statement->execute([$actor['id']]);
        $row = $statement->fetch();
        return ['unread_count' => (int) $row['unread_count'], 'active_count' => (int) $row['active_count'],
            'critical_count' => (int) $row['critical_count'], 'warning_count' => (int) $row['warning_count'],
            'recent' => $this->list($actor, ['limit' => 5])];
    }

    public function markRead(array $actor, string $id): array
    {
        $this->operator($actor);
        $statement = $this->database->prepare('UPDATE notifications SET is_read=1,read_at=COALESCE(read_at,UTC_TIMESTAMP(6)) WHERE id=? AND user_id=? AND is_resolved=0');
        $statement->execute([$id, $actor['id']]);
        $query = $this->database->prepare('SELECT * FROM notifications WHERE id=? AND user_id=? AND is_resolved=0');
        $query->execute([$id, $actor['id']]);
        $row = $query->fetch();
        if (!$row) {
            throw new ApiException(404, 'NOTIFICATION_NOT_FOUND', 'Notification not found');
        }
        return self::serialize($row);
    }

    public function markAllRead(array $actor): int
    {
        $this->operator($actor);
        $statement = $this->database->prepare('UPDATE notifications SET is_read=1,read_at=UTC_TIMESTAMP(6) WHERE user_id=? AND is_read=0 AND is_resolved=0');
        $statement->execute([$actor['id']]);
        return $statement->rowCount();
    }

    public function emitToOperators(string $dedupeKey, string $category, string $severity, string $title,
        string $message, ?string $entityType = null, ?string $entityId = null, ?string $actionPath = null): void
    {
        if (strlen($dedupeKey) > 220 || strlen($title) > 160 || !in_array($category,
            ['INVENTORY', 'TRANSFER', 'PROCUREMENT', 'PAYMENT', 'COMMUNICATION', 'REPORT', 'SYSTEM'], true)
            || !in_array($severity, ['INFO', 'WARNING', 'HIGH', 'CRITICAL'], true)) {
            throw new \InvalidArgumentException('Invalid operational notification');
        }
        $recipients = $this->database->query("SELECT DISTINCT u.id FROM users u JOIN user_roles ur ON ur.user_id=u.id JOIN roles r ON r.id=ur.role_id WHERE r.code IN ('OWNER','MANAGER') AND u.status='ACTIVE' AND u.is_active=1")
            ->fetchAll(PDO::FETCH_COLUMN);
        $insert = $this->database->prepare('INSERT IGNORE INTO notifications (id,user_id,dedupe_key,category,severity,title,message,entity_type,entity_id,action_path) VALUES (?,?,?,?,?,?,?,?,?,?)');
        foreach ($recipients as $userId) {
            $insert->execute([Uuid::v4(), $userId, $dedupeKey, $category, $severity, $title,
                $message, $entityType, $entityId, $actionPath]);
        }
    }

    private static function serialize(array $row): array
    {
        $iso = static fn (?string $value): ?string => $value === null ? null : str_replace(' ', 'T', $value) . 'Z';
        return ['id' => $row['id'], 'category' => $row['category'], 'severity' => $row['severity'],
            'title' => $row['title'], 'message' => $row['message'], 'entity_type' => $row['entity_type'],
            'entity_id' => $row['entity_id'], 'action_path' => $row['action_path'],
            'is_read' => (bool) $row['is_read'], 'is_resolved' => (bool) $row['is_resolved'],
            'created_at' => $iso($row['created_at']), 'read_at' => $iso($row['read_at'])];
    }

    private function operator(array $actor): void
    {
        if (!array_intersect(['OWNER', 'MANAGER'], $actor['roles'] ?? [])) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Notifications are restricted');
        }
    }
}
