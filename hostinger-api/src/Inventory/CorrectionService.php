<?php
declare(strict_types=1);

namespace Anicraze\Inventory;

use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;
use Anicraze\Http\ApiException;
use Anicraze\Notifications\NotificationService;
use PDO;
use PDOException;

final class CorrectionService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function adjust(array $actor, array $body): array
    {
        $this->operator($actor);
        $reference = $body['reference_number'] ?? null;
        $reason = $body['reason'] ?? null;
        $lines = $body['items'] ?? null;
        if (!is_string($reference) || mb_strlen(trim($reference)) < 3 || mb_strlen($reference) > 100
            || !is_string($reason) || mb_strlen(trim($reason)) < 2 || mb_strlen($reason) > 255
            || !is_array($lines) || count($lines) < 1 || count($lines) > 100) {
            throw new ApiException(422, 'validation_error', 'Invalid stock adjustment');
        }
        $normalized = [];
        foreach ($lines as $line) {
            $id = $line['inventory_id'] ?? null;
            $change = $line['quantity_change'] ?? null;
            if (!is_string($id) || preg_match('/^[0-9a-fA-F-]{36}$/D', $id) !== 1
                || !is_int($change) || $change === 0 || abs($change) > 1000000 || isset($normalized[$id])) {
                throw new ApiException(422, 'validation_error', 'Invalid or duplicate adjustment line');
            }
            $batch = $line['batch_number'] ?? null;
            $remarks = $line['remarks'] ?? null;
            if ($batch !== null && (!is_string($batch) || mb_strlen($batch) > 100)
                || $remarks !== null && (!is_string($remarks) || mb_strlen($remarks) > 2000)) {
                throw new ApiException(422, 'validation_error', 'Invalid adjustment note');
            }
            $normalized[$id] = ['change' => $change, 'batch' => $batch, 'remarks' => $remarks];
        }
        ksort($normalized);
        $reference = trim($reference);
        $reason = trim($reason);
        $hash = hash('sha256', json_encode([$reason, $normalized], JSON_THROW_ON_ERROR));
        try {
            return Connection::transaction($this->database, function () use ($actor, $reference, $reason, $normalized, $hash): array {
                $existing = $this->database->prepare('SELECT id,request_hash FROM stock_adjustments WHERE reference_number=? FOR UPDATE');
                $existing->execute([$reference]);
                $prior = $existing->fetch();
                if ($prior) {
                    if (!hash_equals($prior['request_hash'], $hash)) {
                        throw new ApiException(409, 'ADJUSTMENT_REFERENCE_CONFLICT', 'Adjustment reference has a different request');
                    }
                    return $this->getAdjustment($prior['id']);
                }
                $id = Uuid::v4();
                $this->database->prepare('INSERT INTO stock_adjustments (id,reference_number,request_hash,reason,created_by_id) VALUES (?,?,?,?,?)')
                    ->execute([$id, $reference, $hash, $reason, $actor['id']]);
                $stock = $this->database->prepare('SELECT id,product_id,available_quantity,average_cost FROM inventory WHERE id=? FOR UPDATE');
                $item = $this->database->prepare('INSERT INTO stock_adjustment_items (id,adjustment_id,inventory_id,quantity_change,quantity_before,quantity_after,batch_number,remarks) VALUES (?,?,?,?,?,?,?,?)');
                $movement = $this->database->prepare('INSERT INTO inventory_movements (id,inventory_id,product_id,movement_type,quantity_delta,quantity_before,quantity_after,unit_cost,reference_type,reference_id,idempotency_key,created_by_id,reference_number,remarks) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)');
                $update = $this->database->prepare('UPDATE inventory SET available_quantity=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?');
                foreach ($normalized as $inventoryId => $line) {
                    $stock->execute([$inventoryId]);
                    $row = $stock->fetch();
                    if (!$row) {
                        throw new ApiException(404, 'INVENTORY_NOT_FOUND', 'Inventory row not found');
                    }
                    $before = (int) $row['available_quantity'];
                    $after = $before + $line['change'];
                    if ($after < 0) {
                        throw new ApiException(409, 'INSUFFICIENT_STOCK', 'Adjustment would make stock negative');
                    }
                    $item->execute([Uuid::v4(), $id, $inventoryId, $line['change'], $before, $after, $line['batch'], $line['remarks']]);
                    $update->execute([$after, $inventoryId]);
                    $movement->execute([Uuid::v4(), $inventoryId, $row['product_id'], 'ADJUSTMENT', $line['change'],
                        $before, $after, $row['average_cost'], 'STOCK_ADJUSTMENT', $id,
                        'adjustment:' . $id . ':' . $inventoryId, $actor['id'], $reference, $line['remarks']]);
                }
                $this->audit($actor, 'STOCK_ADJUSTED', $id, ['reference_number' => $reference, 'lines' => count($normalized)]);
                (new NotificationService($this->database))->emitToOperators('stock:adjustment:' . $id,
                    'INVENTORY', 'HIGH', 'Stock adjustment recorded',
                    'Stock adjustment ' . $reference . ' changed ' . count($normalized) . ' inventory rows.',
                    'STOCK_ADJUSTMENT', $id, 'inventory');
                return $this->getAdjustment($id);
            });
        } catch (PDOException $error) {
            if (($error->errorInfo[0] ?? '') === '23000') {
                $prior = $this->database->prepare('SELECT id,request_hash FROM stock_adjustments WHERE reference_number=?');
                $prior->execute([$reference]);
                $record = $prior->fetch();
                if ($record && hash_equals($record['request_hash'], $hash)) {
                    return $this->getAdjustment($record['id']);
                }
                throw new ApiException(409, 'ADJUSTMENT_REFERENCE_CONFLICT', 'Adjustment reference already exists');
            }
            throw $error;
        }
    }

    public function damage(array $actor, string $inventoryId, array $body): array
    {
        $this->operator($actor);
        $quantity = $body['quantity'] ?? null;
        $key = $body['idempotency_key'] ?? null;
        $reference = $body['reference_number'] ?? null;
        if (!is_int($quantity) || $quantity < 1 || $quantity > 1000000 || !is_string($key)
            || strlen($key) < 8 || strlen($key) > 100 || !is_string($reference)
            || mb_strlen(trim($reference)) < 2 || mb_strlen($reference) > 100) {
            throw new ApiException(422, 'validation_error', 'Invalid damaged-stock request');
        }
        $remarks = $body['remarks'] ?? null;
        if ($remarks !== null && (!is_string($remarks) || mb_strlen($remarks) > 2000)) {
            throw new ApiException(422, 'validation_error', 'Invalid damage note');
        }
        $movementKey = 'damage:' . $key;
        $reference = trim($reference);
        return Connection::transaction($this->database, function () use ($actor, $inventoryId, $quantity, $movementKey, $reference, $remarks): array {
            $stock = $this->database->prepare('SELECT id,product_id,available_quantity,damaged_quantity,average_cost FROM inventory WHERE id=? FOR UPDATE');
            $stock->execute([$inventoryId]);
            $row = $stock->fetch();
            if (!$row) {
                throw new ApiException(404, 'INVENTORY_NOT_FOUND', 'Inventory row not found');
            }
            $prior = $this->database->prepare('SELECT inventory_id,quantity_delta,movement_type,reference_number,remarks FROM inventory_movements WHERE idempotency_key=?');
            $prior->execute([$movementKey]);
            $existing = $prior->fetch();
            if ($existing) {
                if ($existing['inventory_id'] !== $inventoryId || (int) $existing['quantity_delta'] !== -$quantity
                    || $existing['movement_type'] !== 'DAMAGE' || $existing['reference_number'] !== $reference
                    || $existing['remarks'] !== $remarks) {
                    throw new ApiException(409, 'DAMAGE_IDEMPOTENCY_CONFLICT', 'Damage request ID was reused for another change');
                }
                return (new InventoryService($this->database))->get($actor, $inventoryId);
            }
            $before = (int) $row['available_quantity'];
            if ($before < $quantity) {
                throw new ApiException(409, 'INSUFFICIENT_STOCK', 'Available stock is insufficient');
            }
            $movementId = Uuid::v4();
            $this->database->prepare('UPDATE inventory SET available_quantity=?,damaged_quantity=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?')
                ->execute([$before - $quantity, (int) $row['damaged_quantity'] + $quantity, $inventoryId]);
            $this->database->prepare('INSERT INTO inventory_movements (id,inventory_id,product_id,movement_type,quantity_delta,quantity_before,quantity_after,unit_cost,reference_type,reference_id,idempotency_key,created_by_id,reference_number,remarks) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)')
                ->execute([$movementId, $inventoryId, $row['product_id'], 'DAMAGE', -$quantity, $before,
                    $before - $quantity, $row['average_cost'], 'DAMAGE', $movementId, $movementKey, $actor['id'], $reference, $remarks]);
            $this->audit($actor, 'STOCK_DAMAGED', $movementId, ['inventory_id' => $inventoryId, 'quantity' => $quantity]);
            (new NotificationService($this->database))->emitToOperators('stock:damage:' . $movementId,
                'INVENTORY', 'HIGH', 'Damaged stock recorded',
                $quantity . ' units were marked damaged in inventory.',
                'INVENTORY', $inventoryId, 'inventory');
            return (new InventoryService($this->database))->get($actor, $inventoryId);
        });
    }

    public function getAdjustment(string $id): array
    {
        $query = $this->database->prepare('SELECT * FROM stock_adjustments WHERE id=?');
        $query->execute([$id]);
        $row = $query->fetch();
        if (!$row) {
            throw new ApiException(404, 'ADJUSTMENT_NOT_FOUND', 'Adjustment not found');
        }
        $items = $this->database->prepare('SELECT id,inventory_id,quantity_change,batch_number,remarks FROM stock_adjustment_items WHERE adjustment_id=? ORDER BY inventory_id');
        $items->execute([$id]);
        return ['id' => $id, 'reference_number' => $row['reference_number'], 'reason' => $row['reason'],
            'status' => $row['status'], 'items' => array_map(static fn (array $item): array => [
                'id' => $item['id'], 'inventory_id' => $item['inventory_id'], 'quantity_change' => (int) $item['quantity_change'],
                'batch_number' => $item['batch_number'], 'remarks' => $item['remarks'],
            ], $items->fetchAll()), 'created_by_id' => $row['created_by_id'],
            'created_at' => str_replace(' ', 'T', $row['created_at']) . 'Z'];
    }

    private function audit(array $actor, string $action, string $id, array $context): void
    {
        $this->database->prepare('INSERT INTO audit_logs (id,actor_user_id,action,entity_type,entity_id,context_json) VALUES (?,?,?,?,?,?)')
            ->execute([Uuid::v4(), $actor['id'], $action, 'inventory', $id, json_encode($context, JSON_THROW_ON_ERROR)]);
    }

    private function operator(array $actor): void
    {
        if (!array_intersect(['OWNER', 'MANAGER'], $actor['roles'] ?? [])) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Stock corrections are restricted');
        }
    }
}
