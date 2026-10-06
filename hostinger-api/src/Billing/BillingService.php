<?php
declare(strict_types=1);

namespace Anicraze\Billing;

use Anicraze\Config\Environment;
use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;
use Anicraze\Http\ApiException;
use PDO;
use PDOException;

final class BillingService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function products(array $actor, string $storeId, ?string $query = null, ?string $barcode = null): array
    {
        $this->assertStore($actor, $storeId);
        $sql = "SELECT i.id AS inventory_id,i.product_id,p.sku,p.barcode,p.name,p.selling_price,i.available_quantity
            FROM inventory i JOIN products p ON p.id=i.product_id
            WHERE i.store_id=? AND p.status='ACTIVE' AND i.available_quantity>0";
        $params = [$storeId];
        if ($barcode !== null) {
            $sql .= ' AND LOWER(p.barcode)=LOWER(?)';
            $params[] = trim($barcode);
        } elseif ($query !== null && trim($query) !== '') {
            $term = '%' . addcslashes(trim($query), '%_\\') . '%';
            $sql .= ' AND (p.name LIKE ? OR p.sku LIKE ? OR p.barcode LIKE ?)';
            array_push($params, $term, $term, $term);
        }
        $sql .= ' ORDER BY p.name LIMIT 100';
        $statement = $this->database->prepare($sql);
        $statement->execute($params);
        $rows = array_map(static fn (array $row): array => [
            'inventory_id' => $row['inventory_id'], 'product_id' => $row['product_id'],
            'sku' => $row['sku'], 'barcode' => $row['barcode'], 'name' => $row['name'],
            'price' => (float) $row['selling_price'], 'available_quantity' => (int) $row['available_quantity'],
        ], $statement->fetchAll());
        if ($barcode !== null) {
            if ($rows === []) {
                throw new ApiException(404, 'PRODUCT_NOT_FOUND', 'Product is unavailable at this shop');
            }
            return $rows[0];
        }
        return $rows;
    }

    public function create(array $actor, array $body): array
    {
        $storeId = $body['store_id'] ?? null;
        $key = $body['idempotency_key'] ?? null;
        if (!is_string($storeId) || !is_string($key) || strlen($key) < 8 || strlen($key) > 160
            || !is_array($body['items'] ?? null) || count($body['items']) < 1 || count($body['items']) > 100
            || !is_array($body['payments'] ?? null) || count($body['payments']) < 1 || count($body['payments']) > 2) {
            throw new ApiException(422, 'validation_error', 'Invalid bill');
        }
        $this->assertStore($actor, $storeId);
        $items = [];
        foreach ($body['items'] as $item) {
            $id = $item['inventory_id'] ?? null;
            $quantity = $item['quantity'] ?? null;
            if (!is_string($id) || !is_int($quantity) || $quantity < 1 || $quantity > 1000 || isset($items[$id])) {
                throw new ApiException(422, 'validation_error', 'Invalid or duplicate bill item');
            }
            $items[$id] = $quantity;
        }
        ksort($items);
        $discount = self::cents($body['invoice_discount'] ?? 0);
        $payments = [];
        foreach ($body['payments'] as $payment) {
            $method = $payment['method'] ?? null;
            if (!in_array($method, ['CASH', 'UPI', 'CARD', 'OTHER'], true) || isset($payments[$method])) {
                throw new ApiException(422, 'validation_error', 'Payment method is unavailable');
            }
            $amount = self::cents($payment['amount'] ?? null);
            $tendered = isset($payment['tendered_amount']) ? self::cents($payment['tendered_amount']) : null;
            $reference = $payment['transaction_reference'] ?? null;
            if ($amount <= 0 || ($method === 'CASH' && $tendered !== null && $tendered < $amount)
                || ($method !== 'CASH' && (!is_string($reference) || trim($reference) === ''))) {
                throw new ApiException(422, 'validation_error', 'Invalid payment details');
            }
            $payments[$method] = [$amount, $tendered, $reference];
        }
        $name = trim((string) ($body['customer_name'] ?? 'Walk-in Customer'));
        $phone = $body['customer_phone'] ?? null;
        if ($name === '' || mb_strlen($name) > 180 || ($phone !== null && (!is_string($phone) || strlen($phone) > 30))) {
            throw new ApiException(422, 'validation_error', 'Invalid customer details');
        }
        ksort($payments);
        $requestHash = hash('sha256', json_encode([$storeId, $items, $discount, $payments, $name, $phone], JSON_THROW_ON_ERROR));
        for ($attempt = 0; $attempt < 3; $attempt++) {
        try {
            return Connection::transaction($this->database, function () use ($actor, $body, $storeId, $key, $items, $discount, $payments, $name, $phone, $requestHash): array {
            $prior = $this->database->prepare('SELECT id,store_id,employee_id,request_hash FROM invoices WHERE idempotency_key=? FOR UPDATE');
            $prior->execute([$key]);
            $existing = $prior->fetch();
            if ($existing) {
                if ($existing['store_id'] !== $storeId || $existing['employee_id'] !== $actor['id']
                    || !is_string($existing['request_hash']) || !hash_equals($existing['request_hash'], $requestHash)) {
                    throw new ApiException(409, 'IDEMPOTENCY_CONFLICT', 'Idempotency key was used for another bill');
                }
                return $this->get($actor, $existing['id']);
            }
            $stockStatement = $this->database->prepare('SELECT i.*,p.name,p.sku,p.selling_price,p.status FROM inventory i JOIN products p ON p.id=i.product_id WHERE i.id=? AND i.store_id=? FOR UPDATE');
            $stock = [];
            $subtotal = 0;
            foreach ($items as $id => $quantity) {
                $stockStatement->execute([$id, $storeId]);
                $row = $stockStatement->fetch();
                if (!$row || $row['status'] !== 'ACTIVE' || (int) $row['available_quantity'] < $quantity) {
                    throw new ApiException(409, 'INSUFFICIENT_STOCK', 'Shop stock is unavailable or insufficient');
                }
                $subtotal += self::cents($row['selling_price']) * $quantity;
                $stock[] = [$row, $quantity];
            }
            if ($discount > $subtotal) {
                throw new ApiException(422, 'validation_error', 'Discount exceeds subtotal');
            }
            $total = $subtotal - $discount;
            if ($total <= 0 || array_sum(array_column($payments, 0)) !== $total) {
                throw new ApiException(422, 'validation_error', 'Payment amounts must equal bill total');
            }
            $counter = 'INV-' . gmdate('Y');
            $this->database->prepare('INSERT INTO invoice_counters (counter_key,current_value) VALUES (?,0) ON DUPLICATE KEY UPDATE counter_key=counter_key')->execute([$counter]);
            $value = $this->database->prepare('SELECT current_value FROM invoice_counters WHERE counter_key=? FOR UPDATE');
            $value->execute([$counter]);
            $next = (int) $value->fetchColumn() + 1;
            $this->database->prepare('UPDATE invoice_counters SET current_value=? WHERE counter_key=?')->execute([$next, $counter]);
            $invoiceId = Uuid::v4();
            $number = $counter . '-' . str_pad((string) $next, 6, '0', STR_PAD_LEFT);
            $this->database->prepare('INSERT INTO invoices (id,invoice_number,idempotency_key,request_hash,store_id,employee_id,customer_name_snapshot,customer_phone_snapshot,subtotal,discount,grand_total,payment_status,invoice_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)')
                ->execute([$invoiceId, $number, $key, $requestHash, $storeId, $actor['id'], $name, $phone,
                    self::money($subtotal), self::money($discount), self::money($total), 'PAID', 'COMPLETED']);
            $insertItem = $this->database->prepare('INSERT INTO invoice_items (id,invoice_id,product_id,inventory_id,product_name_snapshot,sku_snapshot,quantity,unit_price,unit_cost_snapshot,line_total) VALUES (?,?,?,?,?,?,?,?,?,?)');
            $movement = $this->database->prepare('INSERT INTO inventory_movements (id,inventory_id,product_id,movement_type,quantity_delta,quantity_before,quantity_after,unit_cost,reference_type,reference_id,idempotency_key,created_by_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)');
            foreach ($stock as [$row, $quantity]) {
                $before = (int) $row['available_quantity'];
                $this->database->prepare('UPDATE inventory SET available_quantity=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?')
                    ->execute([$before - $quantity, $row['id']]);
                $insertItem->execute([Uuid::v4(), $invoiceId, $row['product_id'], $row['id'], $row['name'], $row['sku'],
                    $quantity, $row['selling_price'], $row['average_cost'], self::money(self::cents($row['selling_price']) * $quantity)]);
                $movement->execute([Uuid::v4(), $row['id'], $row['product_id'], 'SALE_OUT', -$quantity,
                    $before, $before - $quantity, $row['average_cost'], 'INVOICE', $invoiceId,
                    'invoice:' . $invoiceId . ':' . $row['id'], $actor['id']]);
            }
            $insertPayment = $this->database->prepare('INSERT INTO payments (id,invoice_id,method,amount,reference_number) VALUES (?,?,?,?,?)');
            foreach ($payments as $method => [$amount, $tendered, $reference]) {
                $insertPayment->execute([Uuid::v4(), $invoiceId, $method, self::money($amount), $reference]);
            }
            return $this->get($actor, $invoiceId);
            });
        } catch (PDOException $error) {
            if (($error->errorInfo[0] ?? '') === '40001' && $attempt < 2) {
                usleep(random_int(10000, 40000));
                continue;
            }
            if (($error->errorInfo[0] ?? '') === '23000') {
                $prior = $this->database->prepare('SELECT id,store_id,employee_id,request_hash FROM invoices WHERE idempotency_key=?');
                $prior->execute([$key]);
                $existing = $prior->fetch();
                if ($existing) {
                    if ($existing['store_id'] !== $storeId || $existing['employee_id'] !== $actor['id']
                        || !is_string($existing['request_hash']) || !hash_equals($existing['request_hash'], $requestHash)) {
                        throw new ApiException(409, 'IDEMPOTENCY_CONFLICT', 'Idempotency key was used for another bill');
                    }
                    return $this->get($actor, $existing['id']);
                }
            }
            throw $error;
        }
        }
        throw new \RuntimeException('Billing retry limit reached');
    }

    public function get(array $actor, string $id): array
    {
        $statement = $this->database->prepare('SELECT inv.*,s.name AS store_name,s.address AS store_address,u.full_name AS employee_name,u.employee_code FROM invoices inv JOIN stores s ON s.id=inv.store_id JOIN users u ON u.id=inv.employee_id WHERE inv.id=?');
        $statement->execute([$id]);
        $invoice = $statement->fetch();
        if (!$invoice) {
            throw new ApiException(404, 'INVOICE_NOT_FOUND', 'Invoice not found');
        }
        $this->assertStore($actor, $invoice['store_id']);
        $itemQuery = $this->database->prepare('SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY id');
        $itemQuery->execute([$id]);
        $items = array_map(static fn (array $row): array => [
            'id' => $row['id'], 'inventory_id' => $row['inventory_id'], 'product_id' => $row['product_id'],
            'sku' => $row['sku_snapshot'], 'product_name' => $row['product_name_snapshot'],
            'quantity' => (int) $row['quantity'], 'unit_price' => (float) $row['unit_price'], 'discount' => 0,
            'line_total' => (float) $row['line_total'],
        ], $itemQuery->fetchAll());
        $payQuery = $this->database->prepare('SELECT * FROM payments WHERE invoice_id=? ORDER BY id');
        $payQuery->execute([$id]);
        $payments = array_map(static fn (array $row): array => [
            'id' => $row['id'], 'amount' => (float) $row['amount'], 'tendered_amount' => null,
            'change_amount' => null, 'transaction_reference' => $row['reference_number'], 'status' => $row['status'],
            'method' => $row['method'],
        ], $payQuery->fetchAll());
        return [
            'id' => $id, 'invoice_number' => $invoice['invoice_number'], 'customer_id' => null,
            'store_id' => $invoice['store_id'], 'employee_id' => $invoice['employee_id'],
            'store_name' => $invoice['store_name'], 'store_address' => $invoice['store_address'],
            'employee_name' => $invoice['employee_name'], 'employee_code' => $invoice['employee_code'],
            'customer_name' => $invoice['customer_name_snapshot'], 'customer_phone' => $invoice['customer_phone_snapshot'],
            'customer_address' => null, 'payment_methods' => array_column($payments, 'method'),
            'business_contact' => Environment::optional('APP_BUSINESS_CONTACT', '+918010526600'),
            'subtotal' => (float) $invoice['subtotal'], 'discount' => (float) $invoice['discount'],
            'grand_total' => (float) $invoice['grand_total'], 'payment_status' => $invoice['payment_status'],
            'invoice_status' => $invoice['invoice_status'], 'notes' => null,
            'items' => $items, 'payments' => $payments,
            'created_at' => str_replace(' ', 'T', $invoice['created_at']) . 'Z',
        ];
    }

    public function cancel(array $actor, string $id, string $reason): array
    {
        if (!in_array('OWNER', $actor['roles'] ?? [], true)) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Invoice cancellation requires Owner access');
        }
        $reason = trim($reason);
        if ($reason === '' || mb_strlen($reason) > 500) {
            throw new ApiException(422, 'validation_error', 'Cancellation reason is required');
        }
        for ($attempt = 0; $attempt < 3; $attempt++) {
            try {
                Connection::transaction($this->database, function () use ($actor, $id, $reason): void {
                    $invoiceQuery = $this->database->prepare('SELECT id,store_id,invoice_status,invoice_number FROM invoices WHERE id=? FOR UPDATE');
                    $invoiceQuery->execute([$id]);
                    $invoice = $invoiceQuery->fetch();
                    if (!$invoice) {
                        throw new ApiException(404, 'INVOICE_NOT_FOUND', 'Invoice not found');
                    }
                    if ($invoice['invoice_status'] !== 'COMPLETED') {
                        throw new ApiException(409, 'INVOICE_CANCEL_INVALID', 'Only completed invoices can be cancelled');
                    }
                    $itemQuery = $this->database->prepare('SELECT id,inventory_id,product_id,quantity FROM invoice_items WHERE invoice_id=? ORDER BY inventory_id FOR UPDATE');
                    $itemQuery->execute([$id]);
                    $items = $itemQuery->fetchAll();
                    $stockQuery = $this->database->prepare('SELECT id,store_id,product_id,available_quantity,average_cost FROM inventory WHERE id=? FOR UPDATE');
                    $updateStock = $this->database->prepare('UPDATE inventory SET available_quantity=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?');
                    $movement = $this->database->prepare('INSERT INTO inventory_movements (id,inventory_id,product_id,movement_type,quantity_delta,quantity_before,quantity_after,unit_cost,reference_type,reference_id,idempotency_key,created_by_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)');
                    foreach ($items as $item) {
                        $stockQuery->execute([$item['inventory_id']]);
                        $stock = $stockQuery->fetch();
                        if (!$stock || $stock['store_id'] !== $invoice['store_id'] || $stock['product_id'] !== $item['product_id']) {
                            throw new ApiException(409, 'INVOICE_STOCK_INCONSISTENT', 'Invoice stock record is inconsistent');
                        }
                        $before = (int) $stock['available_quantity'];
                        $after = $before + (int) $item['quantity'];
                        $updateStock->execute([$after, $stock['id']]);
                        $movement->execute([Uuid::v4(), $stock['id'], $stock['product_id'], 'RETURN', (int) $item['quantity'],
                            $before, $after, $stock['average_cost'], 'INVOICE', $id,
                            'invoice-cancel:' . $id . ':' . $item['id'], $actor['id']]);
                    }
                    $this->database->prepare("UPDATE invoices SET invoice_status='CANCELLED',payment_status='CANCELLED',cancellation_reason=?,cancelled_at=UTC_TIMESTAMP(6) WHERE id=?")
                        ->execute([$reason, $id]);
                    $this->database->prepare("UPDATE payments SET status='CANCELLED' WHERE invoice_id=?")->execute([$id]);
                    $this->database->prepare('INSERT INTO audit_logs (id,actor_user_id,action,entity_type,entity_id,context_json) VALUES (?,?,?,?,?,?)')
                        ->execute([Uuid::v4(), $actor['id'], 'INVOICE_CANCELLED', 'invoice', $id,
                            json_encode(['reason' => $reason, 'store_id' => $invoice['store_id']], JSON_THROW_ON_ERROR)]);
                });
                return $this->get($actor, $id);
            } catch (PDOException $error) {
                if (($error->errorInfo[0] ?? '') === '40001' && $attempt < 2) {
                    usleep(random_int(10000, 40000));
                    continue;
                }
                throw $error;
            }
        }
        throw new \RuntimeException('Invoice cancellation retry limit reached');
    }

    public function list(array $actor): array
    {
        $params = [];
        $sql = 'SELECT id FROM invoices';
        if (in_array('SALES', $actor['roles'] ?? [], true)) {
            $storeId = $actor['assigned_store_id'] ?? null;
            if (!is_string($storeId) || $storeId === '') {
                throw new ApiException(403, 'AUTH_SHOP_UNASSIGNED', 'Assigned shop is required');
            }
            $sql .= ' WHERE store_id=?';
            $params[] = $storeId;
        } elseif (!array_intersect(['OWNER', 'MANAGER'], $actor['roles'] ?? [])) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Access denied');
        }
        $statement = $this->database->prepare($sql . ' ORDER BY created_at DESC LIMIT 100');
        $statement->execute($params);
        return array_map(fn (string $id): array => $this->get($actor, $id), $statement->fetchAll(PDO::FETCH_COLUMN));
    }

    private function assertStore(array $actor, string $storeId): void
    {
        if (in_array('SALES', $actor['roles'] ?? [], true)) {
            if (($actor['assigned_store_id'] ?? null) !== $storeId) {
                throw new ApiException(403, 'AUTH_SHOP_FORBIDDEN', 'Access to this shop is denied');
            }
            return;
        }
        if (!array_intersect(['OWNER', 'MANAGER'], $actor['roles'] ?? [])) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Access denied');
        }
    }

    private static function cents(mixed $value): int
    {
        if ((!is_string($value) && !is_int($value) && !is_float($value))
            || preg_match('/^\d{1,8}(?:\.\d{1,2})?$/D', (string) $value) !== 1) {
            throw new ApiException(422, 'validation_error', 'Invalid money amount');
        }
        [$whole, $fraction] = array_pad(explode('.', (string) $value, 2), 2, '');
        return (int) $whole * 100 + (int) str_pad($fraction, 2, '0');
    }

    private static function money(int $cents): string
    {
        return intdiv($cents, 100) . '.' . str_pad((string) ($cents % 100), 2, '0', STR_PAD_LEFT);
    }
}
