<?php
declare(strict_types=1);

namespace Anicraze\Finance;

use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;
use Anicraze\Http\ApiException;
use DateTimeImmutable;
use DateTimeZone;
use PDO;
use PDOException;

final class PayableService
{
    private const METHODS = ['CASH', 'BANK_TRANSFER', 'UPI', 'CHEQUE', 'OTHER'];

    public function __construct(private readonly PDO $database)
    {
    }

    public function list(array $actor, ?string $status = null): array
    {
        $this->owner($actor);
        if ($status !== null && !in_array($status, ['UNPAID', 'PARTIALLY_PAID', 'PAID', 'OVERDUE'], true)) {
            throw new ApiException(422, 'validation_error', 'Invalid payment status filter');
        }
        $query = $this->database->query('SELECT id FROM purchase_payables ORDER BY created_at DESC,id DESC LIMIT 200');
        $rows = array_map(fn (string $id): array => $this->get($actor, $id), $query->fetchAll(PDO::FETCH_COLUMN));
        return $status === null ? $rows : array_values(array_filter($rows, static fn (array $row): bool => $row['status'] === $status));
    }

    public function summary(array $actor): array
    {
        $this->owner($actor);
        $today = new DateTimeImmutable('today', new DateTimeZone('Asia/Kolkata'));
        $weekEnd = $today->modify('+7 days')->format('Y-m-d');
        $query = $this->database->prepare('SELECT COALESCE(SUM(total_amount),0) AS total_value,'
            . 'COALESCE(SUM(amount_paid),0) AS paid,COALESCE(SUM(total_amount-amount_paid),0) AS pending,'
            . 'COALESCE(SUM(CASE WHEN due_date<? AND total_amount>amount_paid THEN total_amount-amount_paid ELSE 0 END),0) AS overdue,'
            . 'COALESCE(SUM(CASE WHEN due_date>=? AND due_date<=? AND total_amount>amount_paid THEN total_amount-amount_paid ELSE 0 END),0) AS due_week '
            . 'FROM purchase_payables');
        $query->execute([$today->format('Y-m-d'), $today->format('Y-m-d'), $weekEnd]);
        $row = $query->fetch();
        $next = $this->database->prepare('SELECT id FROM purchase_payables WHERE total_amount>amount_paid AND due_date IS NOT NULL ORDER BY due_date,id LIMIT 1');
        $next->execute();
        $nextId = $next->fetchColumn();
        return ['total_purchase_value' => $row['total_value'], 'total_paid' => $row['paid'],
            'total_pending' => $row['pending'], 'overdue' => $row['overdue'],
            'due_this_week' => $row['due_week'],
            'next_payment' => $nextId === false ? null : $this->get($actor, $nextId)];
    }

    public function create(array $actor, array $body): array
    {
        $this->owner($actor);
        $supplierId = $body['supplier_id'] ?? null;
        if (!is_string($supplierId) || preg_match('/^[0-9a-fA-F-]{36}$/D', $supplierId) !== 1) {
            throw new ApiException(422, 'SUPPLIER_REQUIRED', 'Select a supplier to track this purchase payment.');
        }
        $total = self::cents($body['total_amount'] ?? null, false);
        $paid = self::cents($body['initially_paid'] ?? 0, true);
        if ($total <= 0 || $paid > $total) {
            throw new ApiException(422, 'PAYABLE_AMOUNT_INVALID', 'Purchase payment amounts are invalid');
        }
        $method = $body['initial_payment_method'] ?? null;
        if ($paid > 0 && !in_array($method, self::METHODS, true)
            || $paid === 0 && $method !== null) {
            throw new ApiException(422, 'PAYABLE_PAYMENT_METHOD_INVALID', 'Initial payment method is invalid');
        }
        $key = $body['idempotency_key'] ?? null;
        if (!is_string($key) || strlen($key) < 8 || strlen($key) > 160) {
            throw new ApiException(422, 'validation_error', 'Purchase payable request ID is required');
        }
        $receiptId = $body['stock_receipt_id'] ?? null;
        if ($receiptId !== null && (!is_string($receiptId) || preg_match('/^[0-9a-fA-F-]{36}$/D', $receiptId) !== 1)) {
            throw new ApiException(422, 'validation_error', 'Invalid receipt reference');
        }
        $invoice = $body['invoice_number'] ?? null;
        $notes = $body['notes'] ?? null;
        if ($invoice !== null && (!is_string($invoice) || mb_strlen($invoice) > 100)
            || $notes !== null && (!is_string($notes) || mb_strlen($notes) > 2000)) {
            throw new ApiException(422, 'validation_error', 'Invalid purchase reference');
        }
        $invoiceDate = self::date($body['invoice_date'] ?? null, true);
        $dueDate = self::date($body['due_date'] ?? null, false);
        $remindAt = self::utcDateTime($body['remind_at'] ?? null);
        $hash = hash('sha256', json_encode([$supplierId, $receiptId, $invoice, $invoiceDate, $total,
            $paid, $method, $dueDate, $remindAt, $notes], JSON_THROW_ON_ERROR));
        $work = function () use ($actor, $supplierId, $receiptId, $invoice, $invoiceDate, $total, $paid,
            $method, $dueDate, $remindAt, $notes, $key, $hash): array {
            $prior = $this->database->prepare('SELECT id,request_hash FROM purchase_payables WHERE idempotency_key=? FOR UPDATE');
            $prior->execute([$key]);
            $existing = $prior->fetch();
            if ($existing) {
                if (!hash_equals($existing['request_hash'], $hash)) {
                    throw new ApiException(409, 'PAYABLE_IDEMPOTENCY_CONFLICT', 'Purchase payment request ID was reused');
                }
                return $this->get($actor, $existing['id']);
            }
            $supplier = $this->database->prepare("SELECT display_name FROM suppliers WHERE id=? AND status='ACTIVE'");
            $supplier->execute([$supplierId]);
            $supplierName = $supplier->fetchColumn();
            if ($supplierName === false) {
                throw new ApiException(422, 'SUPPLIER_NOT_FOUND', 'Select an active supplier to track this purchase payment.');
            }
            if ($receiptId !== null) {
                $receipt = $this->database->prepare('SELECT id FROM stock_receipts WHERE id=?');
                $receipt->execute([$receiptId]);
                if (!$receipt->fetchColumn()) {
                    throw new ApiException(422, 'RECEIPT_NOT_FOUND', 'Purchase receipt not found');
                }
            }
            $id = Uuid::v4();
            $number = 'PAY-' . gmdate('Ymd') . '-' . strtoupper(substr(str_replace('-', '', $id), 0, 8));
            $status = $paid === $total ? 'PAID' : ($paid > 0 ? 'PARTIALLY_PAID' : 'UNPAID');
            $this->database->prepare('INSERT INTO purchase_payables (id,idempotency_key,request_hash,reference_number,supplier_id,supplier_name_snapshot,stock_receipt_id,invoice_number,invoice_date,total_amount,amount_paid,status,due_date,reminder_enabled,notes,created_by_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)')
                ->execute([$id, $key, $hash, $number, $supplierId, $supplierName, $receiptId,
                    $invoice, $invoiceDate, self::money($total), self::money($paid), $status,
                    $dueDate, $remindAt !== null ? 1 : 0, $notes, $actor['id']]);
            if ($paid > 0) {
                $this->insertPayment($actor, $id, 'initial:' . $id, $paid, $method, $invoiceDate, null, null);
            }
            if ($remindAt !== null) {
                $this->insertReminder($id, 'initial:' . $id, $remindAt);
            }
            $this->audit($actor, 'PURCHASE_PAYABLE_CREATED', $id, ['supplier_id' => $supplierId]);
            return $this->get($actor, $id);
        };
        try {
            return $this->database->inTransaction() ? $work() : Connection::transaction($this->database, $work);
        } catch (PDOException $error) {
            if (($error->errorInfo[0] ?? '') === '23000') {
                throw new ApiException(409, 'PAYABLE_DUPLICATE', 'Purchase payable already exists');
            }
            throw $error;
        }
    }

    public function recordPayment(array $actor, string $id, array $body): array
    {
        $this->owner($actor);
        $amount = self::cents($body['amount'] ?? null, false);
        $method = $body['payment_method'] ?? null;
        $key = $body['idempotency_key'] ?? null;
        $date = self::date($body['payment_date'] ?? null, true);
        $reference = $body['reference_number'] ?? null;
        $notes = $body['notes'] ?? null;
        if ($amount <= 0 || !in_array($method, self::METHODS, true)
            || !is_string($key) || strlen($key) < 8 || strlen($key) > 160
            || $reference !== null && (!is_string($reference) || mb_strlen($reference) > 120)
            || $notes !== null && (!is_string($notes) || mb_strlen($notes) > 1000)) {
            throw new ApiException(422, 'validation_error', 'Invalid purchase payment');
        }
        $hash = hash('sha256', json_encode([$id, $amount, $method, $date, $reference, $notes], JSON_THROW_ON_ERROR));
        return Connection::transaction($this->database, function () use ($actor, $id, $amount, $method, $key,
            $date, $reference, $notes, $hash): array {
            $payable = $this->lockedPayable($id);
            $prior = $this->database->prepare('SELECT request_hash FROM purchase_payments WHERE idempotency_key=?');
            $prior->execute([$key]);
            $existingHash = $prior->fetchColumn();
            if ($existingHash !== false) {
                if (!hash_equals($existingHash, $hash)) {
                    throw new ApiException(409, 'PAYMENT_IDEMPOTENCY_CONFLICT', 'Payment request ID was reused');
                }
                return $this->get($actor, $id);
            }
            $pending = self::cents($payable['total_amount'], false) - self::cents($payable['amount_paid'], true);
            if ($amount > $pending) {
                throw new ApiException(409, 'PAYMENT_EXCEEDS_DUE', 'Payment exceeds pending amount');
            }
            $this->insertPayment($actor, $id, $key, $amount, $method, $date, $reference, $notes, $hash);
            $paid = self::cents($payable['amount_paid'], true) + $amount;
            $status = $paid === self::cents($payable['total_amount'], false) ? 'PAID' : 'PARTIALLY_PAID';
            $this->database->prepare('UPDATE purchase_payables SET amount_paid=?,status=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?')
                ->execute([self::money($paid), $status, $id]);
            $this->audit($actor, 'PURCHASE_PAYMENT_RECORDED', $id, ['amount' => self::money($amount)]);
            return $this->get($actor, $id);
        });
    }

    public function reminder(array $actor, string $id, array $body): array
    {
        $this->owner($actor);
        $when = self::utcDateTime($body['remind_at'] ?? null);
        $key = $body['idempotency_key'] ?? null;
        if ($when === null || !is_string($key) || strlen($key) < 8 || strlen($key) > 160) {
            throw new ApiException(422, 'validation_error', 'Reminder time and request ID are required');
        }
        if ($when <= gmdate('Y-m-d H:i:s')) {
            throw new ApiException(422, 'validation_error', 'Reminder must be in the future');
        }
        return Connection::transaction($this->database, function () use ($actor, $id, $when, $key): array {
            $payable = $this->lockedPayable($id);
            if (self::cents($payable['total_amount'], false) <= self::cents($payable['amount_paid'], true)) {
                throw new ApiException(409, 'PAYABLE_ALREADY_PAID', 'Paid purchase has no pending reminder');
            }
            $prior = $this->database->prepare('SELECT request_hash FROM payment_reminders WHERE idempotency_key=?');
            $prior->execute([$key]);
            $existingHash = $prior->fetchColumn();
            $hash = hash('sha256', $id . '|' . $when);
            if ($existingHash !== false) {
                if (!hash_equals($existingHash, $hash)) {
                    throw new ApiException(409, 'REMINDER_IDEMPOTENCY_CONFLICT', 'Reminder request ID was reused');
                }
                return $this->get($actor, $id);
            }
            $this->insertReminder($id, $key, $when);
            $this->database->prepare('UPDATE purchase_payables SET reminder_enabled=1,updated_at=UTC_TIMESTAMP(6) WHERE id=?')
                ->execute([$id]);
            $this->audit($actor, 'PAYMENT_REMINDER_SCHEDULED', $id, ['remind_at' => $when]);
            return $this->get($actor, $id);
        });
    }

    public function get(array $actor, string $id): array
    {
        $this->owner($actor);
        $query = $this->database->prepare('SELECT * FROM purchase_payables WHERE id=?');
        $query->execute([$id]);
        $row = $query->fetch();
        if (!$row) {
            throw new ApiException(404, 'PAYABLE_NOT_FOUND', 'Purchase payable not found');
        }
        $payments = $this->database->prepare('SELECT id,amount,payment_method,payment_date,reference_number,notes,created_at FROM purchase_payments WHERE payable_id=? ORDER BY created_at,id');
        $payments->execute([$id]);
        $paymentRows = array_map(static fn (array $p): array => [
            'id' => $p['id'], 'amount' => $p['amount'], 'payment_method' => $p['payment_method'],
            'payment_date' => $p['payment_date'], 'reference_number' => $p['reference_number'],
            'notes' => $p['notes'], 'created_at' => self::iso($p['created_at']),
        ], $payments->fetchAll());
        $reminders = $this->database->prepare('SELECT id,remind_at,status,triggered_at,dismissed_at,snoozed_from_id FROM payment_reminders WHERE payable_id=? ORDER BY remind_at,id');
        $reminders->execute([$id]);
        $reminderRows = array_map(static fn (array $r): array => [
            'id' => $r['id'], 'remind_at' => self::iso($r['remind_at']), 'status' => $r['status'],
            'triggered_at' => self::iso($r['triggered_at']), 'dismissed_at' => self::iso($r['dismissed_at']),
            'snoozed_from_id' => $r['snoozed_from_id'],
        ], $reminders->fetchAll());
        $pending = self::cents($row['total_amount'], false) - self::cents($row['amount_paid'], true);
        $today = (new DateTimeImmutable('today', new DateTimeZone('Asia/Kolkata')))->format('Y-m-d');
        $status = $pending > 0 && $row['due_date'] !== null && $row['due_date'] < $today ? 'OVERDUE' : $row['status'];
        $next = null;
        foreach ($reminderRows as $reminder) {
            if ($reminder['status'] === 'SCHEDULED') {
                $next = $reminder['remind_at'];
                break;
            }
        }
        return ['id' => $id, 'supplier_id' => $row['supplier_id'], 'supplier_name' => $row['supplier_name_snapshot'],
            'stock_receipt_id' => $row['stock_receipt_id'], 'reference_number' => $row['reference_number'],
            'invoice_number' => $row['invoice_number'], 'invoice_date' => $row['invoice_date'],
            'total_amount' => $row['total_amount'], 'amount_paid' => $row['amount_paid'],
            'pending_amount' => self::money($pending), 'status' => $status, 'due_date' => $row['due_date'],
            'next_reminder_at' => $next, 'reminder_enabled' => (bool) $row['reminder_enabled'],
            'notes' => $row['notes'], 'payments' => $paymentRows, 'reminders' => $reminderRows,
            'created_at' => self::iso($row['created_at']), 'updated_at' => self::iso($row['updated_at'])];
    }

    private function lockedPayable(string $id): array
    {
        $query = $this->database->prepare('SELECT * FROM purchase_payables WHERE id=? FOR UPDATE');
        $query->execute([$id]);
        $row = $query->fetch();
        if (!$row) { throw new ApiException(404, 'PAYABLE_NOT_FOUND', 'Purchase payable not found'); }
        return $row;
    }

    private function insertPayment(array $actor, string $id, string $key, int $amount, string $method,
        string $date, ?string $reference, ?string $notes, ?string $hash = null): void
    {
        $fingerprint = $hash ?? hash('sha256', json_encode([$id, $amount, $method, $date, $reference, $notes], JSON_THROW_ON_ERROR));
        $this->database->prepare('INSERT INTO purchase_payments (id,payable_id,idempotency_key,request_hash,amount,payment_method,payment_date,reference_number,notes,created_by_id) VALUES (?,?,?,?,?,?,?,?,?,?)')
            ->execute([Uuid::v4(), $id, $key, $fingerprint, self::money($amount), $method, $date,
                $reference, $notes, $actor['id']]);
    }

    private function insertReminder(string $id, string $key, string $when): void
    {
        $this->database->prepare('INSERT INTO payment_reminders (id,payable_id,idempotency_key,request_hash,remind_at) VALUES (?,?,?,?,?)')
            ->execute([Uuid::v4(), $id, $key, hash('sha256', $id . '|' . $when), $when]);
    }

    private function audit(array $actor, string $action, string $id, array $context): void
    {
        $this->database->prepare('INSERT INTO audit_logs (id,actor_user_id,action,entity_type,entity_id,context_json) VALUES (?,?,?,?,?,?)')
            ->execute([Uuid::v4(), $actor['id'], $action, 'purchase_payable', $id,
                json_encode($context, JSON_THROW_ON_ERROR)]);
    }

    private static function cents(mixed $value, bool $zeroAllowed): int
    {
        if ((!is_int($value) && !is_float($value) && !is_string($value))
            || preg_match('/^\d{1,15}(?:\.\d{1,2})?$/D', (string) $value) !== 1) {
            throw new ApiException(422, 'validation_error', 'Invalid purchase amount');
        }
        [$whole, $fraction] = array_pad(explode('.', (string) $value, 2), 2, '');
        $cents = (int) $whole * 100 + (int) str_pad($fraction, 2, '0');
        if (!$zeroAllowed && $cents === 0) {
            throw new ApiException(422, 'validation_error', 'Amount must be positive');
        }
        return $cents;
    }

    private static function money(int $cents): string
    {
        return intdiv($cents, 100) . '.' . str_pad((string) ($cents % 100), 2, '0', STR_PAD_LEFT);
    }

    private static function date(mixed $value, bool $defaultToday): ?string
    {
        if ($value === null || $value === '') {
            return $defaultToday ? (new DateTimeImmutable('today', new DateTimeZone('Asia/Kolkata')))->format('Y-m-d') : null;
        }
        if (!is_string($value)) { throw new ApiException(422, 'validation_error', 'Invalid date'); }
        $date = DateTimeImmutable::createFromFormat('!Y-m-d', $value, new DateTimeZone('Asia/Kolkata'));
        if (!$date || $date->format('Y-m-d') !== $value) {
            throw new ApiException(422, 'validation_error', 'Invalid date');
        }
        return $value;
    }

    private static function utcDateTime(mixed $value): ?string
    {
        if ($value === null || $value === '') { return null; }
        if (!is_string($value) || strlen($value) > 40) {
            throw new ApiException(422, 'validation_error', 'Invalid reminder time');
        }
        try {
            return (new DateTimeImmutable($value, new DateTimeZone('UTC')))
                ->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s');
        } catch (\Throwable) {
            throw new ApiException(422, 'validation_error', 'Invalid reminder time');
        }
    }

    private static function iso(?string $value): ?string
    {
        return $value === null ? null : str_replace(' ', 'T', $value) . 'Z';
    }

    private function owner(array $actor): void
    {
        if (!in_array('OWNER', $actor['roles'] ?? [], true)) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Purchase payments require Owner access');
        }
    }
}
