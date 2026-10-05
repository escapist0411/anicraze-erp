<?php
declare(strict_types=1);

namespace Anicraze\Finance;

use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;
use Anicraze\Http\ApiException;
use PDO;

final class SupplierService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function list(array $actor): array
    {
        $this->owner($actor);
        $query = $this->database->query('SELECT s.*,(SELECT COALESCE(SUM(p.total_amount-p.amount_paid),0) '
            . 'FROM purchase_payables p WHERE p.supplier_id=s.id) AS outstanding_balance '
            . 'FROM suppliers s ORDER BY s.display_name,s.id');
        return array_map(self::serialize(...), $query->fetchAll());
    }

    public function receiptChoices(array $actor): array
    {
        if (!array_intersect(['OWNER', 'MANAGER'], $actor['roles'] ?? [])) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Supplier selection is restricted');
        }
        return $this->database->query("SELECT id,display_name FROM suppliers WHERE status='ACTIVE' ORDER BY display_name,id")
            ->fetchAll();
    }

    public function create(array $actor, array $body): array
    {
        $this->owner($actor);
        $displayName = trim((string) ($body['display_name'] ?? ''));
        $companyName = trim((string) ($body['company_name'] ?? $displayName));
        $email = $body['email'] ?? null;
        $phone = $body['phone'] ?? null;
        $notes = $body['notes'] ?? null;
        if (mb_strlen($displayName) < 2 || mb_strlen($displayName) > 180
            || mb_strlen($companyName) < 2 || mb_strlen($companyName) > 180
            || ($email !== null && ($email !== '' && (!is_string($email) || !filter_var($email, FILTER_VALIDATE_EMAIL) || strlen($email) > 320)))
            || ($phone !== null && ($phone !== '' && (!is_string($phone) || preg_match('/^[0-9+() .-]{7,30}$/D', $phone) !== 1)))
            || ($notes !== null && (!is_string($notes) || mb_strlen($notes) > 2000))) {
            throw new ApiException(422, 'validation_error', 'Invalid supplier details');
        }
        $code = strtoupper(trim((string) ($body['supplier_code'] ?? '')));
        if ($code !== '' && preg_match('/^[A-Z0-9][A-Z0-9_-]{2,59}$/D', $code) !== 1) {
            throw new ApiException(422, 'validation_error', 'Invalid supplier code');
        }
        return Connection::transaction($this->database, function () use ($actor, $displayName, $companyName, $email, $phone, $notes, $code): array {
            $id = Uuid::v4();
            $supplierCode = $code !== '' ? $code : 'SUP-' . strtoupper(substr(str_replace('-', '', $id), 0, 8));
            try {
                $this->database->prepare('INSERT INTO suppliers (id,supplier_code,display_name,company_name,email,phone,notes) VALUES (?,?,?,?,?,?,?)')
                    ->execute([$id, $supplierCode, $displayName, $companyName, $email ?: null, $phone ?: null, $notes]);
            } catch (\PDOException $error) {
                if (($error->errorInfo[0] ?? '') === '23000') {
                    throw new ApiException(409, 'SUPPLIER_CODE_EXISTS', 'Supplier code already exists');
                }
                throw $error;
            }
            $this->database->prepare('INSERT INTO audit_logs (id,actor_user_id,action,entity_type,entity_id,context_json) VALUES (?,?,?,?,?,?)')
                ->execute([Uuid::v4(), $actor['id'], 'SUPPLIER_CREATED', 'supplier', $id,
                    json_encode(['supplier_code' => $supplierCode], JSON_THROW_ON_ERROR)]);
            $query = $this->database->prepare("SELECT s.*,'0.00' AS outstanding_balance FROM suppliers s WHERE s.id=?");
            $query->execute([$id]);
            return self::serialize($query->fetch());
        });
    }

    private static function serialize(array $row): array
    {
        return ['id' => $row['id'], 'supplier_code' => $row['supplier_code'],
            'display_name' => $row['display_name'], 'company_name' => $row['company_name'],
            'email' => $row['email'], 'phone' => $row['phone'],
            'outstanding_balance' => $row['outstanding_balance'], 'status' => $row['status'],
            'notes' => $row['notes'], 'created_at' => str_replace(' ', 'T', $row['created_at']) . 'Z',
            'updated_at' => str_replace(' ', 'T', $row['updated_at']) . 'Z'];
    }

    private function owner(array $actor): void
    {
        if (!in_array('OWNER', $actor['roles'] ?? [], true)) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Supplier management requires Owner access');
        }
    }
}
