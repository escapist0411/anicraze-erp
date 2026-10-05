<?php
declare(strict_types=1);

namespace Anicraze\Inventory;

use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;
use Anicraze\Http\ApiException;
use Anicraze\Notifications\NotificationService;
use PDO;
use PDOException;

final class TransferService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function create(array $actor, array $body): array
    {
        $this->operator($actor);
        $key = $body['idempotency_key'] ?? null;
        $warehouseId = $body['source_warehouse_id'] ?? null;
        $storeId = $body['target_store_id'] ?? null;
        if (!is_string($key) || strlen($key) < 8 || strlen($key) > 160
            || !is_string($warehouseId) || !is_string($storeId)
            || ($body['source_store_id'] ?? null) !== null || ($body['target_warehouse_id'] ?? null) !== null
            || !is_array($body['items'] ?? null) || count($body['items']) < 1 || count($body['items']) > 100) {
            throw new ApiException(422, 'validation_error', 'Invalid direct warehouse-to-shop transfer');
        }
        $items = [];
        foreach ($body['items'] as $item) {
            $productId = $item['product_id'] ?? null;
            $quantity = $item['quantity'] ?? null;
            if (!is_string($productId) || !is_int($quantity) || $quantity < 1 || $quantity > 100000
                || isset($items[$productId])) {
                throw new ApiException(422, 'validation_error', 'Invalid or duplicate transfer line');
            }
            $items[$productId] = $quantity;
        }
        ksort($items);
        for ($attempt = 0; $attempt < 3; $attempt++) {
        try {
            return Connection::transaction($this->database, function () use ($actor, $body, $key, $warehouseId, $storeId, $items): array {
                $prior = $this->byKey($key);
                if ($prior !== null) {
                    $this->assertSameRequest($prior, $warehouseId, $storeId, $items);
                    return $this->get($actor, $prior['id']);
                }
                $location = $this->database->prepare("SELECT id FROM stores WHERE id=? AND status='ACTIVE'");
                $location->execute([$storeId]);
                if ($location->fetchColumn() === false) {
                    throw new ApiException(422, 'validation_error', 'Destination shop is unavailable');
                }
                $location = $this->database->prepare("SELECT id FROM warehouses WHERE id=? AND code='ANICRAZE_CWH' AND status='ACTIVE'");
                $location->execute([$warehouseId]);
                if ($location->fetchColumn() === false) {
                    throw new ApiException(422, 'validation_error', 'Source warehouse is unavailable');
                }
                $id = Uuid::v4();
                $number = 'TRF-' . gmdate('Ymd') . '-' . strtoupper(substr(str_replace('-', '', $id), 0, 8));
                $this->database->prepare('INSERT INTO stock_transfers (id,transfer_number,idempotency_key,source_warehouse_id,target_store_id,status,remarks,created_by_id) VALUES (?,?,?,?,?,?,?,?)')
                    ->execute([$id, $number, $key, $warehouseId, $storeId, 'COMPLETED', $body['remarks'] ?? null, $actor['id']]);
                $find = $this->database->prepare('SELECT * FROM inventory WHERE product_id=? AND warehouse_id=? FOR UPDATE');
                $findShop = $this->database->prepare('SELECT * FROM inventory WHERE product_id=? AND store_id=? FOR UPDATE');
                $update = $this->database->prepare('UPDATE inventory SET available_quantity=?,average_cost=?,last_purchase_cost=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?');
                $movement = $this->database->prepare('INSERT INTO inventory_movements (id,inventory_id,product_id,movement_type,quantity_delta,quantity_before,quantity_after,unit_cost,reference_type,reference_id,idempotency_key,created_by_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)');
                $line = $this->database->prepare('INSERT INTO stock_transfer_items (id,transfer_id,product_id,quantity,unit_cost) VALUES (?,?,?,?,?)');
                foreach ($items as $productId => $quantity) {
                    $find->execute([$productId, $warehouseId]);
                    $source = $find->fetch();
                    $findShop->execute([$productId, $storeId]);
                    $target = $findShop->fetch();
                    if (!$source || !$target || (int) $source['available_quantity'] < $quantity) {
                        throw new ApiException(409, 'INSUFFICIENT_STOCK', 'Warehouse stock is insufficient');
                    }
                    $sourceBefore = (int) $source['available_quantity'];
                    $targetBefore = (int) $target['available_quantity'];
                    $cost = $source['average_cost'];
                    $newAverage = intdiv(self::cents($target['average_cost']) * $targetBefore
                        + self::cents($cost) * $quantity + intdiv($targetBefore + $quantity, 2), $targetBefore + $quantity);
                    $update->execute([$sourceBefore - $quantity, $source['average_cost'], $source['last_purchase_cost'], $source['id']]);
                    $update->execute([$targetBefore + $quantity, self::money($newAverage), $cost, $target['id']]);
                    $line->execute([Uuid::v4(), $id, $productId, $quantity, $cost]);
                    $movement->execute([Uuid::v4(), $source['id'], $productId, 'TRANSFER_OUT', -$quantity,
                        $sourceBefore, $sourceBefore - $quantity, $cost, 'STOCK_TRANSFER', $id,
                        'transfer:' . $id . ':out:' . $productId, $actor['id']]);
                    $movement->execute([Uuid::v4(), $target['id'], $productId, 'TRANSFER_IN', $quantity,
                        $targetBefore, $targetBefore + $quantity, $cost, 'STOCK_TRANSFER', $id,
                        'transfer:' . $id . ':in:' . $productId, $actor['id']]);
                }
                (new NotificationService($this->database))->emitToOperators('transfer:completed:' . $id,
                    'TRANSFER', 'INFO', 'Stock transferred',
                    'Transfer ' . $number . ' moved ' . array_sum($items) . ' units from Central Warehouse to a shop.',
                    'STOCK_TRANSFER', $id, 'inventory');
                return $this->get($actor, $id);
            });
        } catch (PDOException $error) {
            if (($error->errorInfo[0] ?? '') === '40001' && $attempt < 2) {
                usleep(random_int(10000, 40000));
                continue;
            }
            if (($error->errorInfo[0] ?? '') === '23000') {
                $prior = $this->byKey($key);
                if ($prior !== null) {
                    $this->assertSameRequest($prior, $warehouseId, $storeId, $items);
                    return $this->get($actor, $prior['id']);
                }
            }
            throw $error;
        }
        }
        throw new \RuntimeException('Transfer retry limit reached');
    }

    public function get(array $actor, string $id): array
    {
        $this->operator($actor);
        $statement = $this->database->prepare('SELECT * FROM stock_transfers WHERE id=?');
        $statement->execute([$id]);
        $transfer = $statement->fetch();
        if (!$transfer) {
            throw new ApiException(404, 'TRANSFER_NOT_FOUND', 'Transfer not found');
        }
        $rows = $this->items($id);
        $items = array_map(static fn (array $row): array => [
            'id' => $row['id'], 'product_id' => $row['product_id'], 'variant_id' => null,
            'product_name' => $row['name'], 'sku' => $row['sku'], 'barcode' => $row['barcode'],
            'quantity' => (int) $row['quantity'], 'picked_quantity' => (int) $row['quantity'],
            'received_quantity' => (int) $row['quantity'], 'damaged_quantity' => 0,
            'shortage_quantity' => 0, 'excess_quantity' => 0, 'discrepancy_note' => null,
        ], $rows);
        return [
            'id' => $id, 'reference_number' => $transfer['transfer_number'], 'source_store_id' => null,
            'source_warehouse_id' => $transfer['source_warehouse_id'], 'target_store_id' => $transfer['target_store_id'],
            'target_warehouse_id' => null, 'status' => $transfer['status'], 'remarks' => $transfer['remarks'],
            'created_by_id' => $transfer['created_by_id'], 'approved_by_id' => null, 'picked_by_id' => null,
            'packed_by_id' => null, 'dispatched_by_id' => null, 'received_by_id' => null,
            'approved_at' => null, 'picking_started_at' => null, 'picked_at' => null, 'packed_at' => null,
            'dispatched_at' => null, 'receiving_started_at' => null, 'received_at' => null,
            'completed_at' => str_replace(' ', 'T', $transfer['created_at']) . 'Z',
            'cancellation_reason' => null, 'discrepancy_notes' => null,
            'created_at' => str_replace(' ', 'T', $transfer['created_at']) . 'Z', 'items' => $items,
        ];
    }

    public function list(array $actor): array
    {
        $this->operator($actor);
        $ids = $this->database->query('SELECT id FROM stock_transfers ORDER BY created_at DESC LIMIT 100')->fetchAll(PDO::FETCH_COLUMN);
        return array_map(fn (string $id): array => $this->get($actor, $id), $ids);
    }

    private function byKey(string $key): ?array
    {
        $statement = $this->database->prepare('SELECT * FROM stock_transfers WHERE idempotency_key=? FOR UPDATE');
        $statement->execute([$key]);
        $row = $statement->fetch();
        return $row ?: null;
    }

    private function assertSameRequest(array $prior, string $warehouseId, string $storeId, array $items): void
    {
        if ($prior['source_warehouse_id'] !== $warehouseId || $prior['target_store_id'] !== $storeId) {
            throw new ApiException(409, 'IDEMPOTENCY_CONFLICT', 'Idempotency key was used for another transfer');
        }
        $existing = [];
        foreach ($this->items($prior['id']) as $item) {
            $existing[$item['product_id']] = (int) $item['quantity'];
        }
        ksort($existing);
        if ($existing !== $items) {
            throw new ApiException(409, 'IDEMPOTENCY_CONFLICT', 'Idempotency key was used for another transfer');
        }
    }

    private function items(string $id): array
    {
        $statement = $this->database->prepare('SELECT ti.*,p.name,p.sku,p.barcode FROM stock_transfer_items ti JOIN products p ON p.id=ti.product_id WHERE ti.transfer_id=? ORDER BY ti.id');
        $statement->execute([$id]);
        return $statement->fetchAll();
    }

    private function operator(array $actor): void
    {
        if (!array_intersect(['OWNER', 'MANAGER'], $actor['roles'] ?? [])) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Stock transfers are restricted');
        }
    }

    private static function cents(string $value): int
    {
        [$whole, $fraction] = array_pad(explode('.', $value, 2), 2, '');
        return (int) $whole * 100 + (int) str_pad($fraction, 2, '0');
    }

    private static function money(int $cents): string
    {
        return intdiv($cents, 100) . '.' . str_pad((string) ($cents % 100), 2, '0', STR_PAD_LEFT);
    }
}
