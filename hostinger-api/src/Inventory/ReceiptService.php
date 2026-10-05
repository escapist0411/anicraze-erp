<?php
declare(strict_types=1);

namespace Anicraze\Inventory;

use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;
use Anicraze\Http\ApiException;
use Anicraze\Finance\PayableService;
use Anicraze\Notifications\NotificationService;
use PDO;

final class ReceiptService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function create(array $actor, array $body): array
    {
        $this->operator($actor);
        $supplierId = $body['supplier_id'] ?? null;
        $paymentOption = $body['payment_option'] ?? null;
        if ($supplierId !== null && (!is_string($supplierId) || preg_match('/^[0-9a-fA-F-]{36}$/D', $supplierId) !== 1)) {
            throw new ApiException(422, 'validation_error', 'Invalid supplier selection');
        }
        if ($paymentOption !== null && !in_array($paymentOption, ['FULLY_PAID', 'PARTIALLY_PAID', 'PAY_LATER'], true)) {
            throw new ApiException(422, 'validation_error', 'Invalid purchase payment option');
        }
        if ($paymentOption !== null && !in_array('OWNER', $actor['roles'] ?? [], true)) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Purchase payments require Owner access');
        }
        if ($paymentOption !== null && $supplierId === null) {
            throw new ApiException(422, 'SUPPLIER_REQUIRED', 'Select a supplier to track this purchase payment.');
        }
        $warehouseId = $this->warehouseId();
        if (($body['warehouse_id'] ?? null) !== $warehouseId || !is_array($body['items'] ?? null)
            || count($body['items']) < 1 || count($body['items']) > 100) {
            throw new ApiException(422, 'validation_error', 'Invalid stock receipt');
        }
        $items = [];
        foreach ($body['items'] as $item) {
            $productId = $item['product_id'] ?? null;
            $quantity = $item['quantity'] ?? null;
            $cost = $item['unit_cost'] ?? null;
            if (!is_string($productId) || !is_int($quantity) || $quantity < 1 || $quantity > 100000
                || !self::validMoney($cost) || isset($items[$productId])) {
                throw new ApiException(422, 'validation_error', 'Invalid or duplicate receipt line');
            }
            $items[$productId] = [$quantity, self::cents($cost)];
        }
        return Connection::transaction($this->database, function () use ($actor, $body, $items, $supplierId, $paymentOption): array {
            if ($supplierId !== null) {
                $supplier = $this->database->prepare("SELECT id FROM suppliers WHERE id=? AND status='ACTIVE'");
                $supplier->execute([$supplierId]);
                if (!$supplier->fetchColumn()) {
                    throw new ApiException(422, 'SUPPLIER_NOT_FOUND', 'Selected supplier is unavailable');
                }
            }
            $id = Uuid::v4();
            $number = 'RCV-' . gmdate('Ymd') . '-' . strtoupper(substr(str_replace('-', '', $id), 0, 8));
            $insert = $this->database->prepare('INSERT INTO stock_receipts (id,receipt_number,status,supplier_id,supplier_reference,notes,created_by_id) VALUES (?,?,?,?,?,?,?)');
            $insert->execute([$id, $number, 'READY_FOR_SCAN', $supplierId, $body['invoice_number'] ?? null,
                $body['notes'] ?? null, $actor['id']]);
            $product = $this->database->prepare("SELECT id FROM products WHERE id=? AND status='ACTIVE'");
            $line = $this->database->prepare('INSERT INTO stock_receipt_items (id,receipt_id,product_id,quantity,purchase_cost) VALUES (?,?,?,?,?)');
            foreach ($items as $productId => [$quantity, $cost]) {
                $product->execute([$productId]);
                if ($product->fetchColumn() === false) {
                    throw new ApiException(422, 'validation_error', 'Receipt product is unavailable');
                }
                $line->execute([Uuid::v4(), $id, $productId, $quantity, self::money($cost)]);
            }
            if ($paymentOption !== null) {
                $total = 0;
                foreach ($items as [$quantity, $cost]) { $total += $quantity * $cost; }
                if ($total <= 0) {
                    throw new ApiException(422, 'PAYABLE_AMOUNT_INVALID', 'Purchase payable requires a positive purchase value');
                }
                $initial = match ($paymentOption) {
                    'FULLY_PAID' => $total,
                    'PARTIALLY_PAID' => self::cents($body['initially_paid'] ?? 0),
                    default => 0,
                };
                if ($paymentOption === 'PARTIALLY_PAID' && ($initial <= 0 || $initial >= $total)) {
                    throw new ApiException(422, 'PAYABLE_AMOUNT_INVALID', 'Partial payment must be above zero and below the purchase total');
                }
                $method = $paymentOption === 'PAY_LATER' ? null : ($body['initial_payment_method'] ?? null);
                (new PayableService($this->database))->create($actor, [
                    'idempotency_key' => 'receipt-payable:' . $id, 'supplier_id' => $supplierId,
                    'stock_receipt_id' => $id, 'invoice_number' => $body['invoice_number'] ?? null,
                    'total_amount' => self::money($total), 'initially_paid' => self::money($initial),
                    'initial_payment_method' => $method, 'due_date' => $body['payment_due_date'] ?? null,
                    'remind_at' => $body['payment_remind_at'] ?? null, 'notes' => $body['notes'] ?? null,
                ]);
            }
            return $this->get($actor, $id);
        });
    }

    public function scan(array $actor, string $id, string $code, string $scanId): array
    {
        $this->operator($actor);
        $code = trim($code);
        if ($code === '' || strlen($code) > 64 || preg_match('/^[0-9a-fA-F-]{36}$/D', $scanId) !== 1) {
            throw new ApiException(422, 'validation_error', 'Invalid barcode or SKU');
        }
        return Connection::transaction($this->database, function () use ($actor, $id, $code, $scanId): array {
            $receipt = $this->lockReceipt($id);
            $prior = $this->database->prepare('SELECT code_normalized FROM stock_receipt_scans WHERE receipt_id=? AND scan_id=?');
            $prior->execute([$id, $scanId]);
            $previousCode = $prior->fetchColumn();
            if ($previousCode !== false) {
                if ($previousCode !== strtolower($code)) {
                    throw new ApiException(409, 'SCAN_ID_CONFLICT', 'Scan request ID was used for another barcode');
                }
                return $this->get($actor, $id);
            }
            if ($receipt['status'] !== 'READY_FOR_SCAN') {
                throw new ApiException(409, 'RECEIPT_NOT_SCANNABLE', 'Receipt is not awaiting scans');
            }
            $statement = $this->database->prepare('SELECT ri.id,ri.quantity,ri.scanned_quantity FROM stock_receipt_items ri JOIN products p ON p.id=ri.product_id WHERE ri.receipt_id=? AND (LOWER(p.barcode)=LOWER(?) OR LOWER(p.sku)=LOWER(?)) FOR UPDATE');
            $statement->execute([$id, $code, $code]);
            $item = $statement->fetch();
            if (!$item) {
                throw new ApiException(404, 'BARCODE_NOT_IN_RECEIPT', 'Barcode is not part of this receipt');
            }
            if ((int) $item['scanned_quantity'] >= (int) $item['quantity']) {
                throw new ApiException(409, 'RECEIPT_ITEM_FULLY_SCANNED', 'All pieces of this product are already scanned');
            }
            $this->database->prepare('UPDATE stock_receipt_items SET scanned_quantity=scanned_quantity+1 WHERE id=?')->execute([$item['id']]);
            $this->database->prepare('INSERT INTO stock_receipt_scans (id,receipt_id,receipt_item_id,scan_id,code_normalized,created_by_id) VALUES (?,?,?,?,?,?)')
                ->execute([Uuid::v4(), $id, $item['id'], $scanId, strtolower($code), $actor['id']]);
            return $this->get($actor, $id);
        });
    }

    public function finalize(array $actor, string $id): array
    {
        $this->operator($actor);
        return Connection::transaction($this->database, function () use ($actor, $id): array {
            $receipt = $this->lockReceipt($id);
            if ($receipt['status'] !== 'READY_FOR_SCAN') {
                throw new ApiException(409, 'RECEIPT_NOT_FINALIZABLE', 'Receipt is not awaiting confirmation');
            }
            $items = $this->items($id);
            if ($items === []) {
                throw new ApiException(409, 'RECEIPT_EMPTY', 'Receipt has no products');
            }
            $warehouse = $this->warehouseId();
            foreach ($items as $item) {
                $quantity = (int) $item['quantity'];
                if ((int) $item['scanned_quantity'] !== $quantity) {
                    throw new ApiException(409, 'RECEIPT_SCAN_INCOMPLETE', 'Scan all receipt pieces first');
                }
                $stock = $this->database->prepare('SELECT * FROM inventory WHERE product_id=? AND warehouse_id=? FOR UPDATE');
                $stock->execute([$item['product_id'], $warehouse]);
                $inventory = $stock->fetch();
                if (!$inventory) {
                    throw new ApiException(409, 'WAREHOUSE_INVENTORY_MISSING', 'Warehouse inventory is missing');
                }
                $before = (int) $inventory['available_quantity'];
                $newAverage = intdiv(self::cents($inventory['average_cost']) * $before
                    + self::cents($item['purchase_cost']) * $quantity + intdiv($before + $quantity, 2), $before + $quantity);
                $this->database->prepare('UPDATE inventory SET available_quantity=?,average_cost=?,last_purchase_cost=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?')
                    ->execute([$before + $quantity, self::money($newAverage), $item['purchase_cost'], $inventory['id']]);
                $this->database->prepare('INSERT INTO inventory_movements (id,inventory_id,product_id,movement_type,quantity_delta,quantity_before,quantity_after,unit_cost,reference_type,reference_id,idempotency_key,created_by_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)')
                    ->execute([Uuid::v4(), $inventory['id'], $item['product_id'], 'RECEIPT_IN', $quantity, $before,
                        $before + $quantity, $item['purchase_cost'], 'STOCK_RECEIPT', $id, 'receipt:' . $item['id'], $actor['id']]);
            }
            $this->database->prepare("UPDATE stock_receipts SET status='COMPLETED',finalized_at=UTC_TIMESTAMP(6) WHERE id=?")->execute([$id]);
            (new NotificationService($this->database))->emitToOperators('receipt:finalized:' . $id,
                'INVENTORY', 'INFO', 'Stock received',
                'Receipt ' . $receipt['receipt_number'] . ' was entered into Central Warehouse.',
                'STOCK_RECEIPT', $id, 'inventory');
            return $this->get($actor, $id);
        });
    }

    public function get(array $actor, string $id): array
    {
        $this->operator($actor);
        $statement = $this->database->prepare('SELECT * FROM stock_receipts WHERE id=?');
        $statement->execute([$id]);
        $receipt = $statement->fetch();
        if (!$receipt) {
            throw new ApiException(404, 'RECEIPT_NOT_FOUND', 'Stock receipt not found');
        }
        $items = $this->items($id);
        $totalValue = 0;
        foreach ($items as &$item) {
            $totalValue += (int) $item['quantity'] * self::cents($item['purchase_cost']);
            $item = [
                'id' => $item['id'], 'product_id' => $item['product_id'], 'variant_id' => null,
                'product_name' => $item['product_name'], 'sku' => $item['sku'], 'barcode' => $item['barcode'],
                'expected_quantity' => (int) $item['quantity'], 'scanned_quantity' => (int) $item['scanned_quantity'],
                'unit_cost' => $item['purchase_cost'], 'selling_price' => $item['selling_price'],
            ];
        }
        unset($item);
        $supplierName = null;
        if ($receipt['supplier_id'] !== null) {
            $supplier = $this->database->prepare('SELECT display_name FROM suppliers WHERE id=?');
            $supplier->execute([$receipt['supplier_id']]);
            $supplierName = $supplier->fetchColumn() ?: null;
        }
        return [
            'id' => $id, 'reference_number' => $receipt['receipt_number'], 'warehouse_id' => $this->warehouseId(),
            'status' => $receipt['status'], 'supplier_name' => $supplierName,
            'invoice_number' => $receipt['supplier_reference'], 'purchase_date' => null, 'notes' => $receipt['notes'],
            'items' => $items, 'total_products' => count($items),
            'total_expected' => array_sum(array_column($items, 'expected_quantity')),
            'total_scanned' => array_sum(array_column($items, 'scanned_quantity')),
            'total_purchase_value' => self::money($totalValue),
            'completed_at' => $receipt['finalized_at'] === null ? null : self::iso($receipt['finalized_at']),
            'created_at' => self::iso($receipt['created_at']),
        ];
    }

    public function list(array $actor): array
    {
        $this->operator($actor);
        $ids = $this->database->query('SELECT id FROM stock_receipts ORDER BY created_at DESC LIMIT 100')->fetchAll(PDO::FETCH_COLUMN);
        return array_map(fn (string $id): array => $this->get($actor, $id), $ids);
    }

    private function lockReceipt(string $id): array
    {
        $statement = $this->database->prepare('SELECT * FROM stock_receipts WHERE id=? FOR UPDATE');
        $statement->execute([$id]);
        $receipt = $statement->fetch();
        if (!$receipt) {
            throw new ApiException(404, 'RECEIPT_NOT_FOUND', 'Stock receipt not found');
        }
        return $receipt;
    }

    private function items(string $id): array
    {
        $statement = $this->database->prepare('SELECT ri.*,p.name AS product_name,p.sku,p.barcode,p.selling_price FROM stock_receipt_items ri JOIN products p ON p.id=ri.product_id WHERE ri.receipt_id=? ORDER BY ri.id');
        $statement->execute([$id]);
        return $statement->fetchAll();
    }

    private function warehouseId(): string
    {
        $result = $this->database->query("SELECT id FROM warehouses WHERE code='ANICRAZE_CWH' AND status='ACTIVE'")->fetchColumn();
        if ($result === false) {
            throw new ApiException(503, 'WAREHOUSE_UNAVAILABLE', 'Central Warehouse is unavailable');
        }
        return $result;
    }

    private function operator(array $actor): void
    {
        if (!array_intersect(['OWNER', 'MANAGER'], $actor['roles'] ?? [])) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Stock receiving is restricted');
        }
    }

    private static function validMoney(mixed $value): bool
    {
        return (is_string($value) || is_int($value) || is_float($value))
            && preg_match('/^\d{1,8}(?:\.\d{1,2})?$/D', (string) $value) === 1;
    }

    private static function cents(mixed $value): int
    {
        [$whole, $fraction] = array_pad(explode('.', (string) $value, 2), 2, '');
        return (int) $whole * 100 + (int) str_pad($fraction, 2, '0');
    }

    private static function money(int $cents): string
    {
        return intdiv($cents, 100) . '.' . str_pad((string) ($cents % 100), 2, '0', STR_PAD_LEFT);
    }

    private static function iso(string $value): string
    {
        return str_replace(' ', 'T', $value) . 'Z';
    }
}
