<?php
declare(strict_types=1);

namespace Anicraze\Reports;

use Anicraze\Http\ApiException;
use DateInterval;
use DateTimeImmutable;
use DateTimeZone;
use PDO;

final class ReportService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function report(array $actor, string $domain, string $report, array $query): array
    {
        if (!in_array($domain . ':' . $report, ['sales:summary', 'inventory:summary',
            'finance:summary', 'finance:shop-profit-loss'], true)) {
            throw new ApiException(404, 'not_implemented', 'Report is not implemented in this candidate');
        }
        if ($domain === 'finance' && !in_array('OWNER', $actor['roles'] ?? [], true)) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Owner finance report access is required');
        }
        $storeId = $this->scope($actor, $query['store_id'] ?? null);
        [$start, $end] = self::range((string) ($query['preset'] ?? 'THIS_MONTH'));
        $filters = ['preset' => $query['preset'] ?? 'THIS_MONTH', 'store_id' => $storeId];
        if ($domain === 'inventory') {
            return ['report_type' => 'inventory_summary', 'filters' => $filters,
                'summary' => $this->inventorySummary($storeId), 'rows' => []];
        }
        $returns = $this->database->prepare("SELECT COUNT(*) FROM sales_returns r WHERE r.status='COMPLETED' AND r.created_at>=? AND r.created_at<?"
            . ($storeId !== null ? ' AND r.store_id=?' : ''));
        $returns->execute(array_values(array_filter([$start, $end, $storeId], static fn ($value) => $value !== null)));
        if ((int) $returns->fetchColumn() > 0) {
            throw new ApiException(501, 'RETURNS_REPORT_UNAVAILABLE', 'Returns reporting requires the returns module');
        }
        if ($domain === 'finance' && $report === 'shop-profit-loss') {
            return ['report_type' => 'finance_shop-profit-loss', 'filters' => $filters,
                'date_range' => ['from' => $start, 'to' => $end],
                ...$this->profitLoss($start, $end, $storeId)];
        }
        $rows = $this->profitLoss($start, $end, $storeId);
        $summary = $rows['summary'];
        $orders = $this->database->prepare("SELECT COUNT(*) FROM invoices WHERE invoice_status='COMPLETED' AND created_at>=? AND created_at<?"
            . ($storeId !== null ? ' AND store_id=?' : ''));
        $orders->execute(array_values(array_filter([$start, $end, $storeId], static fn ($value) => $value !== null)));
        return ['report_type' => $domain . '_' . $report, 'filters' => $filters,
            'summary' => ['gross_sales' => $summary['gross_sales'], 'discounts' => $summary['discounts'],
                'net_sales' => $summary['net_sales'], 'revenue' => $summary['net_revenue'],
                'orders' => (int) $orders->fetchColumn(), 'cost_of_goods_sold' => $summary['cogs'],
                'gross_profit' => $summary['gross_profit'], 'returns' => '0.00', 'refunds' => '0.00'],
            'rows' => []];
    }

    private function profitLoss(string $start, string $end, ?string $storeId): array
    {
        $sql = "SELECT inv.store_id,s.name AS shop,COALESCE(SUM(inv.subtotal),0) AS gross_sales,"
            . "COALESCE(SUM(inv.discount),0) AS discounts,COALESCE(SUM(inv.grand_total),0) AS net_sales "
            . "FROM invoices inv JOIN stores s ON s.id=inv.store_id WHERE inv.invoice_status='COMPLETED' "
            . 'AND inv.created_at>=? AND inv.created_at<?'
            . ($storeId !== null ? ' AND inv.store_id=?' : '') . ' GROUP BY inv.store_id,s.name ORDER BY s.name';
        $params = $storeId === null ? [$start, $end] : [$start, $end, $storeId];
        $statement = $this->database->prepare($sql);
        $statement->execute($params);
        $rows = [];
        $sums = array_fill_keys(['gross_sales', 'discounts', 'net_sales', 'returns_refunds',
            'net_revenue', 'cogs', 'gross_profit'], 0);
        $cost = $this->database->prepare("SELECT COALESCE(SUM(ii.quantity*ii.unit_cost_snapshot),0) FROM invoice_items ii JOIN invoices inv ON inv.id=ii.invoice_id WHERE inv.invoice_status='COMPLETED' AND inv.store_id=? AND inv.created_at>=? AND inv.created_at<?");
        foreach ($statement->fetchAll() as $record) {
            $cost->execute([$record['store_id'], $start, $end]);
            $gross = self::cents($record['gross_sales']);
            $discount = self::cents($record['discounts']);
            $net = self::cents($record['net_sales']);
            $cogs = self::cents($cost->fetchColumn());
            $profit = $net - $cogs;
            $row = ['store_id' => $record['store_id'], 'shop' => $record['shop'],
                'gross_sales' => self::money($gross), 'discounts' => self::money($discount),
                'net_sales' => self::money($net), 'returns_refunds' => '0.00',
                'net_revenue' => self::money($net), 'cogs' => self::money($cogs),
                'gross_profit' => self::money($profit),
                'gross_margin_percentage' => $net > 0 ? number_format($profit * 100 / $net, 2, '.', '') : '0.00'];
            $rows[] = $row;
            foreach ($sums as $key => $value) {
                $sums[$key] += self::cents($row[$key]);
            }
        }
        $summary = [];
        foreach ($sums as $key => $value) {
            $summary[$key] = self::money($value);
        }
        $summary['gross_margin_percentage'] = $sums['net_revenue'] > 0
            ? number_format($sums['gross_profit'] * 100 / $sums['net_revenue'], 2, '.', '') : '0.00';
        return ['summary' => $summary, 'rows' => $rows];
    }

    private function inventorySummary(?string $storeId): array
    {
        $sql = 'SELECT COALESCE(SUM(available_quantity),0) AS available_units,COALESCE(SUM(damaged_quantity),0) AS damaged_units,'
            . 'SUM(CASE WHEN available_quantity=0 THEN 1 ELSE 0 END) AS out_of_stock_count,'
            . 'COALESCE(SUM(available_quantity*average_cost),0) AS inventory_value,'
            . 'COUNT(DISTINCT product_id) AS products FROM inventory'
            . ($storeId === null ? '' : ' WHERE store_id=?');
        $statement = $this->database->prepare($sql);
        $statement->execute($storeId === null ? [] : [$storeId]);
        $row = $statement->fetch();
        return ['inventory_value' => $row['inventory_value'], 'available_units' => (int) $row['available_units'],
            'damaged_units' => (int) $row['damaged_units'], 'out_of_stock_count' => (int) $row['out_of_stock_count'],
            'products' => (int) $row['products']];
    }

    private function scope(array $actor, mixed $requested): ?string
    {
        if ($requested !== null && (!is_string($requested) || strlen($requested) !== 36)) {
            throw new ApiException(422, 'validation_error', 'Invalid shop filter');
        }
        if (array_intersect(['OWNER', 'MANAGER'], $actor['roles'] ?? [])) {
            return $requested;
        }
        if (in_array('SALES', $actor['roles'] ?? [], true) && !empty($actor['assigned_store_id'])) {
            if ($requested !== null && $requested !== $actor['assigned_store_id']) {
                throw new ApiException(403, 'AUTH_SHOP_FORBIDDEN', 'Cross-shop report access is denied');
            }
            return $actor['assigned_store_id'];
        }
        throw new ApiException(403, 'AUTH_FORBIDDEN', 'Report access denied');
    }

    public static function range(string $preset): array
    {
        $zone = new DateTimeZone('Asia/Kolkata');
        $today = new DateTimeImmutable('today', $zone);
        $quarterMonth = intdiv((int) $today->format('n') - 1, 3) * 3 + 1;
        $quarterStart = $today->setDate((int) $today->format('Y'), $quarterMonth, 1);
        [$start, $end] = match ($preset) {
            'TODAY' => [$today, $today->add(new DateInterval('P1D'))],
            'THIS_WEEK' => [$today->modify('monday this week'), $today->modify('monday next week')],
            'THIS_MONTH' => [$today->modify('first day of this month'), $today->modify('first day of next month')],
            'THIS_QUARTER' => [$quarterStart, $quarterStart->add(new DateInterval('P3M'))],
            'LAST_MONTH' => [$today->modify('first day of last month'), $today->modify('first day of this month')],
            'THIS_YEAR' => [$today->setDate((int) $today->format('Y'), 1, 1), $today->setDate((int) $today->format('Y') + 1, 1, 1)],
            default => throw new ApiException(422, 'validation_error', 'Unsupported report period'),
        };
        $utc = new DateTimeZone('UTC');
        return [$start->setTimezone($utc)->format('Y-m-d H:i:s'), $end->setTimezone($utc)->format('Y-m-d H:i:s')];
    }

    private static function cents(mixed $money): int
    {
        $value = (string) $money;
        $negative = str_starts_with($value, '-');
        if ($negative) {
            $value = substr($value, 1);
        }
        [$whole, $fraction] = array_pad(explode('.', $value, 2), 2, '');
        $result = (int) $whole * 100 + (int) str_pad($fraction, 2, '0');
        return $negative ? -$result : $result;
    }

    private static function money(int $cents): string
    {
        $prefix = $cents < 0 ? '-' : '';
        $absolute = abs($cents);
        return $prefix . intdiv($absolute, 100) . '.' . str_pad((string) ($absolute % 100), 2, '0', STR_PAD_LEFT);
    }
}
