<?php
declare(strict_types=1);

namespace Anicraze\Reports;

use Anicraze\Http\ApiException;
use PDO;

final class OwnerDashboardService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function get(array $actor, array $query): array
    {
        if (!in_array('OWNER', $actor['roles'] ?? [], true)) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Owner dashboard access is required');
        }
        [$start, $end] = ReportService::range((string) ($query['preset'] ?? 'THIS_MONTH'));
        $returns = $this->one("SELECT COUNT(*) AS total FROM sales_returns WHERE status='COMPLETED' AND created_at>=? AND created_at<?", [$start, $end]);
        if ((int) $returns['total'] > 0) {
            throw new ApiException(501, 'RETURNS_DASHBOARD_UNAVAILABLE', 'Dashboard returns accounting requires the returns module');
        }
        $sales = $this->one("SELECT COUNT(*) AS orders,COALESCE(SUM(subtotal),0) AS gross_sales,"
            . "COALESCE(SUM(discount),0) AS discounts,COALESCE(SUM(grand_total),0) AS net_sales "
            . "FROM invoices WHERE invoice_status='COMPLETED' AND created_at>=? AND created_at<?", [$start, $end]);
        $cost = $this->one("SELECT COALESCE(SUM(ii.quantity*ii.unit_cost_snapshot),0) AS cost "
            . "FROM invoice_items ii JOIN invoices inv ON inv.id=ii.invoice_id "
            . "WHERE inv.invoice_status='COMPLETED' AND inv.created_at>=? AND inv.created_at<?", [$start, $end]);
        $gross = self::cents($sales['gross_sales']);
        $discounts = self::cents($sales['discounts']);
        $net = self::cents($sales['net_sales']);
        $cogs = self::cents($cost['cost']);
        $orders = (int) $sales['orders'];
        $inventory = $this->database->query('SELECT COALESCE(SUM(i.available_quantity*i.average_cost),0) AS inventory_value,'
            . 'COALESCE(SUM(i.available_quantity),0) AS available_units,'
            . 'COALESCE(SUM(i.damaged_quantity),0) AS damaged_units,'
            . 'COALESCE(SUM(i.in_transit_quantity),0) AS in_transit_units,'
            . 'COALESCE(SUM(i.available_quantity>0 AND i.available_quantity<=p.reorder_level),0) AS low_stock_count,'
            . 'COALESCE(SUM(i.available_quantity=0),0) AS out_of_stock_count,'
            . 'COALESCE(SUM(CASE WHEN i.warehouse_id IS NOT NULL THEN i.available_quantity ELSE 0 END),0) AS godown_units,'
            . 'COALESCE(SUM(CASE WHEN i.store_id IS NOT NULL THEN i.available_quantity ELSE 0 END),0) AS shop_units '
            . 'FROM inventory i JOIN products p ON p.id=i.product_id')->fetch();
        $trendRows = $this->rows("SELECT DATE(created_at) AS date,COALESCE(SUM(grand_total),0) AS revenue,COUNT(*) AS orders "
            . "FROM invoices WHERE invoice_status='COMPLETED' AND created_at>=? AND created_at<? "
            . 'GROUP BY DATE(created_at) ORDER BY date', [$start, $end]);
        $stores = $this->rows("SELECT s.id AS store_id,s.name AS store_name,COUNT(inv.id) AS orders,"
            . "COALESCE(SUM(inv.grand_total),0) AS net_sales FROM stores s "
            . "LEFT JOIN invoices inv ON inv.store_id=s.id AND inv.invoice_status='COMPLETED' "
            . 'AND inv.created_at>=? AND inv.created_at<? GROUP BY s.id,s.name ORDER BY s.name', [$start, $end]);
        $products = $this->rows("SELECT ii.product_id,ii.product_name_snapshot AS product_name,ii.sku_snapshot AS sku,"
            . 'SUM(ii.quantity) AS quantity,COALESCE(SUM(ii.line_total),0) AS net_sales,'
            . 'COALESCE(SUM(ii.quantity*ii.unit_cost_snapshot),0) AS cost '
            . "FROM invoice_items ii JOIN invoices inv ON inv.id=ii.invoice_id "
            . "WHERE inv.invoice_status='COMPLETED' AND inv.created_at>=? AND inv.created_at<? "
            . 'GROUP BY ii.product_id,ii.product_name_snapshot,ii.sku_snapshot '
            . 'ORDER BY quantity DESC,ii.product_name_snapshot LIMIT 10', [$start, $end]);
        $paymentRows = $this->rows("SELECT pay.method AS payment_method,COALESCE(SUM(pay.amount),0) AS amount,COUNT(*) AS transactions "
            . "FROM payments pay JOIN invoices inv ON inv.id=pay.invoice_id "
            . "WHERE inv.invoice_status='COMPLETED' AND inv.created_at>=? AND inv.created_at<? "
            . 'GROUP BY pay.method ORDER BY pay.method', [$start, $end]);
        $paymentTotal = array_sum(array_map(static fn (array $row): int => self::cents($row['amount']), $paymentRows));
        $activeEmployees = (int) $this->database->query("SELECT COUNT(DISTINCT u.id) FROM users u "
            . "JOIN user_roles ur ON ur.user_id=u.id JOIN roles r ON r.id=ur.role_id "
            . "WHERE u.is_active=1 AND r.code='SALES'")->fetchColumn();
        $alerts = [];
        if ((int) $inventory['low_stock_count'] > 0) {
            $alerts[] = ['severity' => 'WARNING', 'code' => 'LOW_STOCK',
                'message' => (int) $inventory['low_stock_count'] . ' location-product rows are below reorder level.'];
        }
        return [
            'kpis' => ['gross_sales' => self::money($gross), 'discounts' => self::money($discounts),
                'returns' => '0.00', 'net_sales' => self::money($net), 'revenue' => self::money($net),
                'orders' => $orders, 'cost_of_goods_sold' => self::money($cogs),
                'gross_profit' => self::money($net - $cogs), 'expenses' => '0.00', 'refunds' => '0.00',
                'estimated_net_operating_profit' => self::money($net - $cogs),
                'net_profit' => self::money($net - $cogs),
                'average_order_value' => self::money($orders > 0 ? intdiv($net, $orders) : 0)],
            'inventory_summary' => ['inventory_value' => $inventory['inventory_value'],
                'available_units' => (int) $inventory['available_units'],
                'low_stock_count' => (int) $inventory['low_stock_count'],
                'out_of_stock_count' => (int) $inventory['out_of_stock_count'],
                'damaged_units' => (int) $inventory['damaged_units'],
                'godown_units' => (int) $inventory['godown_units'],
                'shop_units' => (int) $inventory['shop_units'],
                'in_transit_units' => (int) $inventory['in_transit_units']],
            'sales_trend' => array_map(static fn (array $row): array => [
                'date' => $row['date'], 'revenue' => $row['revenue'], 'orders' => (int) $row['orders']], $trendRows),
            'store_performance' => array_map(static fn (array $row): array => [
                'store_id' => $row['store_id'], 'store_name' => $row['store_name'],
                'net_sales' => $row['net_sales'], 'revenue' => $row['net_sales'],
                'orders' => (int) $row['orders'],
                'average_order_value' => self::money((int) $row['orders'] > 0
                    ? intdiv(self::cents($row['net_sales']), (int) $row['orders']) : 0)], $stores),
            'top_selling_products' => array_map(static fn (array $row): array => [
                'product_id' => $row['product_id'], 'product_name' => $row['product_name'], 'sku' => $row['sku'],
                'quantity' => (int) $row['quantity'], 'net_sales' => $row['net_sales'],
                'revenue' => $row['net_sales'],
                'gross_profit' => self::money(self::cents($row['net_sales']) - self::cents($row['cost']))], $products),
            'payment_summary' => array_map(static fn (array $row): array => [
                'payment_method' => $row['payment_method'], 'amount' => $row['amount'],
                'transactions' => (int) $row['transactions'],
                'percentage' => $paymentTotal > 0
                    ? number_format(self::cents($row['amount']) * 100 / $paymentTotal, 2, '.', '') : '0.00'], $paymentRows),
            'active_employees' => $activeEmployees,
            'attendance_percentage' => '0.00',
            'alerts' => $alerts, 'business_insights' => [],
            'definitions' => [
                'net_sales' => 'Completed invoice value after discounts; cancelled invoices excluded.',
                'gross_profit' => 'Net sales less invoice item purchase-cost snapshots.',
                'estimated_net_operating_profit' => 'Gross profit only; expense and returns modules are not yet ported.',
                'attendance_percentage' => 'Attendance is not tracked by this Hostinger candidate.',
            ],
        ];
    }

    private function one(string $sql, array $params): array
    {
        $statement = $this->database->prepare($sql);
        $statement->execute($params);
        return $statement->fetch() ?: [];
    }

    private function rows(string $sql, array $params): array
    {
        $statement = $this->database->prepare($sql);
        $statement->execute($params);
        return $statement->fetchAll();
    }

    private static function cents(mixed $value): int
    {
        $string = (string) $value;
        $negative = str_starts_with($string, '-');
        [$whole, $fraction] = array_pad(explode('.', ltrim($string, '-'), 2), 2, '');
        $result = (int) $whole * 100 + (int) str_pad($fraction, 2, '0');
        return $negative ? -$result : $result;
    }

    private static function money(int $cents): string
    {
        return ($cents < 0 ? '-' : '') . intdiv(abs($cents), 100) . '.'
            . str_pad((string) (abs($cents) % 100), 2, '0', STR_PAD_LEFT);
    }
}
