<?php
declare(strict_types=1);

namespace Anicraze\Documents;

use Anicraze\Billing\BillingService;
use Anicraze\Catalog\BarcodeImage;
use Anicraze\Catalog\ProductService;
use Anicraze\Inventory\TransferService;
use Anicraze\Reports\ReportService;
use Dompdf\Dompdf;
use Dompdf\Options;
use PDO;

final class PdfService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function invoice(array $actor, string $id): string
    {
        $data = (new BillingService($this->database))->get($actor, $id);
        $rows = '';
        foreach ($data['items'] as $index => $item) {
            $rows .= '<tr><td>' . ($index + 1) . '</td><td><strong>' . self::h($item['product_name'])
                . '</strong><br><small>' . self::h($item['sku']) . '</small></td><td class="right">'
                . $item['quantity'] . '</td><td class="right">' . self::inr($item['unit_price'])
                . '</td><td class="right">' . self::inr($item['line_total']) . '</td></tr>';
        }
        $payment = implode(', ', $data['payment_methods']);
        $html = $this->start('Sales invoice', $data['invoice_number'])
            . '<div class="hero"><div><div class="eyebrow">SALES INVOICE</div><h1>' . self::h($data['invoice_number'])
            . '</h1><div class="muted">' . self::h($data['created_at']) . '</div></div><div class="pill">'
            . self::h($data['invoice_status']) . '</div></div>'
            . '<div class="split"><div class="box"><div class="eyebrow">SHOP</div><strong>'
            . self::h($data['store_name']) . '</strong><br>' . nl2br(self::h($data['store_address'] ?? ''))
            . '</div><div class="box"><div class="eyebrow">CUSTOMER</div><strong>'
            . self::h($data['customer_name']) . '</strong><br>' . self::h($data['customer_phone'] ?? 'No phone provided')
            . '</div></div>'
            . '<table><thead><tr><th>#</th><th>Item</th><th class="right">Qty</th><th class="right">Unit price</th><th class="right">Amount</th></tr></thead><tbody>'
            . $rows . '</tbody></table>'
            . '<div class="totals"><div><span>Subtotal</span><strong>' . self::inr($data['subtotal'])
            . '</strong></div><div><span>Discount</span><strong>' . self::inr($data['discount'])
            . '</strong></div><div class="grand"><span>Total paid</span><strong>' . self::inr($data['grand_total'])
            . '</strong></div></div>'
            . '<div class="box bottom"><div class="eyebrow">PAYMENT</div><strong>' . self::h($payment)
            . '</strong> · ' . self::h($data['payment_status']) . '<br>Served by '
            . self::h($data['employee_name']) . '</div>'
            . '<p class="thankyou">Thank you for shopping with ANICRAZE.</p>' . $this->end();
        return $this->render($html);
    }

    public function transfer(array $actor, string $id): string
    {
        $data = (new TransferService($this->database))->get($actor, $id);
        $source = $this->location('warehouses', $data['source_warehouse_id']);
        $target = $this->location('stores', $data['target_store_id']);
        $rows = '';
        $total = 0;
        foreach ($data['items'] as $index => $item) {
            $total += $item['quantity'];
            $rows .= '<tr><td>' . ($index + 1) . '</td><td><strong>' . self::h($item['product_name'])
                . '</strong><br><small>' . self::h($item['sku']) . ' · ' . self::h($item['barcode'] ?? '')
                . '</small></td><td class="right">' . $item['quantity'] . '</td></tr>';
        }
        $html = $this->start('Stock transfer receipt', $data['reference_number'])
            . '<div class="hero"><div><div class="eyebrow">STOCK TRANSFER RECEIPT</div><h1>'
            . self::h($data['reference_number']) . '</h1><div class="muted">' . self::h($data['created_at'])
            . '</div></div><div class="pill">' . self::h($data['status']) . '</div></div>'
            . '<div class="split"><div class="box"><div class="eyebrow">FROM</div><strong>'
            . self::h($source) . '</strong></div><div class="box"><div class="eyebrow">TO</div><strong>'
            . self::h($target) . '</strong></div></div>'
            . '<table><thead><tr><th>#</th><th>Product</th><th class="right">Units</th></tr></thead><tbody>'
            . $rows . '</tbody></table><div class="totals"><div class="grand"><span>Total units</span><strong>'
            . $total . '</strong></div></div><div class="box bottom"><div class="eyebrow">REMARKS</div>'
            . self::h($data['remarks'] ?: 'Direct warehouse-to-shop transfer') . '</div>' . $this->end();
        return $this->render($html);
    }

    public function label(array $actor, string $productId): string
    {
        $product = (new ProductService($this->database))->find($actor, 'id', $productId);
        $barcode = $product['barcode'];
        $name = $product['name'];
        $length = mb_strlen($name);
        $fontSize = $length > 42 ? 6.5 : ($length > 28 ? 7.25 : 8);
        $maxCharacters = $length > 42 ? 27 : ($length > 28 ? 26 : 28);
        if ($length > $maxCharacters) {
            $name = mb_substr($name, 0, $maxCharacters - 1) . '…';
        }
        $price = (float) $product['selling_price'];
        $whole = abs($price - round($price)) < 0.00001;
        $priceText = self::indianNumber($price, $whole ? 0 : 2);
        $image = BarcodeImage::dataUri($barcode);
        $html = '<!doctype html><html><head><meta charset="utf-8"><style>
            @page{size:50mm 25mm;margin:0}html,body{width:50mm;height:25mm;margin:0;padding:0;background:#fff}
            body{font-family:"DejaVu Sans",sans-serif;color:#000;overflow:hidden}
            .name{position:absolute;left:2mm;top:1.5mm;width:46mm;height:3.7mm;overflow:hidden;white-space:nowrap;text-align:center;font-size:'
            . $fontSize . 'pt;font-weight:bold;line-height:3.5mm}
            .bars{position:absolute;left:2mm;top:5.6mm;width:46mm;height:10mm}
            .code{position:absolute;left:2mm;top:16.2mm;width:46mm;height:2.8mm;text-align:center;font-family:monospace;font-size:6.5pt;line-height:2.8mm}
            .price{position:absolute;left:2mm;top:19mm;width:46mm;height:4.4mm;text-align:center;font-size:11pt;font-weight:bold;line-height:4.4mm}
            </style></head><body><div class="name">' . self::h($name) . '</div><img class="bars" src="'
            . self::h($image) . '"><div class="code">' . self::h($barcode)
            . '</div><div class="price">&#8377;' . self::h($priceText) . '</div></body></html>';
        $temp = dirname(__DIR__, 2) . '/storage/tmp';
        if (!is_dir($temp) && !mkdir($temp, 0700, true) && !is_dir($temp)) {
            throw new \RuntimeException('Private PDF temp directory unavailable');
        }
        $options = new Options();
        $options->set('defaultFont', 'DejaVu Sans');
        $options->set('isRemoteEnabled', false);
        $options->set('isPhpEnabled', false);
        $options->set('tempDir', $temp);
        $options->set('fontCache', $temp);
        $options->set('chroot', dirname(__DIR__, 2));
        $pdf = new Dompdf($options);
        $pdf->setPaper([0, 0, 50 * 72 / 25.4, 25 * 72 / 25.4]);
        $pdf->loadHtml($html, 'UTF-8');
        $pdf->render();
        return $pdf->output();
    }

    public function report(array $actor, string $type, array $filters): string
    {
        [$domain, $name] = match ($type) {
            'sales_summary' => ['sales', 'summary'],
            'inventory_summary' => ['inventory', 'summary'],
            'finance_summary' => ['finance', 'summary'],
            'finance_shop-profit-loss' => ['finance', 'shop-profit-loss'],
            default => throw new \Anicraze\Http\ApiException(404, 'not_implemented', 'Report PDF is unavailable'),
        };
        $data = (new ReportService($this->database))->report($actor, $domain, $name, $filters);
        $title = match ($type) {
            'sales_summary' => 'Sales summary', 'inventory_summary' => 'Inventory summary',
            'finance_summary' => 'Finance summary', default => 'Shop-wise profit and loss',
        };
        $summaryRows = '';
        foreach ($data['summary'] as $key => $value) {
            if (!is_scalar($value)) {
                continue;
            }
            $display = str_contains($key, 'percentage') && is_numeric($value)
                ? self::h($value) . '%'
                : (preg_match('/(sales|discount|revenue|cogs|profit|value|cost|refund|returns)/', $key)
                    && is_numeric($value) ? self::inr((float) $value) : self::h($value));
            $summaryRows .= '<tr><td>' . self::h(ucwords(str_replace('_', ' ', $key)))
                . '</td><td class="right">' . $display . '</td></tr>';
        }
        $html = $this->start($title, strtoupper((string) ($filters['preset'] ?? 'THIS_MONTH')))
            . '<div class="hero"><div><div class="eyebrow">BUSINESS REPORT</div><h1>' . self::h($title)
            . '</h1><div class="muted">Period: ' . self::h((string) ($filters['preset'] ?? 'THIS_MONTH'))
            . '</div></div></div><table><thead><tr><th>Metric</th><th class="right">Value</th></tr></thead><tbody>'
            . $summaryRows . '</tbody></table>';
        if ($name === 'shop-profit-loss') {
            $html .= '<h2 style="margin-top:9mm;font-size:12pt">Shop comparison</h2><table><thead><tr><th>Shop</th><th class="right">Net revenue</th><th class="right">COGS</th><th class="right">Gross profit</th><th class="right">Margin</th></tr></thead><tbody>';
            foreach ($data['rows'] as $row) {
                $html .= '<tr><td>' . self::h($row['shop']) . '</td><td class="right">'
                    . self::inr((float) $row['net_revenue']) . '</td><td class="right">' . self::inr((float) $row['cogs'])
                    . '</td><td class="right">' . self::inr((float) $row['gross_profit']) . '</td><td class="right">'
                    . self::h($row['gross_margin_percentage']) . '%</td></tr>';
            }
            $html .= '</tbody></table>';
        }
        return $this->render($html . $this->end());
    }

    private function location(string $table, string $id): string
    {
        $statement = $this->database->prepare("SELECT name FROM {$table} WHERE id=?");
        $statement->execute([$id]);
        $name = $statement->fetchColumn();
        return is_string($name) ? $name : 'Unknown location';
    }

    private function start(string $title, string $number): string
    {
        $logo = base64_encode((string) file_get_contents(dirname(__DIR__, 2) . '/assets/anicraze-logo.png'));
        return '<!doctype html><html><head><meta charset="utf-8"><title>' . self::h($title) . '</title><style>
            @page{size:A4;margin:18mm 15mm 17mm}body{font-family:"DejaVu Sans",sans-serif;color:#17202a;font-size:9pt}
            .header{border-bottom:2px solid #17202a;padding-bottom:9mm;min-height:19mm}.logo{width:42mm;height:14mm;object-fit:contain;background:#000}
            .header-right{float:right;text-align:right;font-size:8pt;color:#5e6975;margin-top:3mm}
            h1{font-size:17pt;margin:2mm 0 0}.eyebrow{font-size:7.2pt;font-weight:bold;letter-spacing:1.2px;color:#687484}
            .muted{color:#697586;font-size:8pt;margin-top:2mm}.hero{margin:10mm 0 7mm;height:22mm}.hero>div:first-child{float:left}
            .pill{float:right;padding:2.5mm 4mm;background:#eef7f2;color:#146b46;border-radius:3mm;font-weight:bold;font-size:8pt}
            .split{width:100%;margin:0 0 8mm}.split>.box{display:inline-block;vertical-align:top;width:43%;min-height:19mm}
            .split>.box+ .box{margin-left:3%}.box{background:#f5f7fa;border:1px solid #e2e7ec;border-radius:2mm;padding:4mm;line-height:1.55}
            table{border-collapse:collapse;width:100%;margin-top:5mm}th{background:#18212b;color:white;font-size:8pt;text-align:left;padding:3mm}
            td{border-bottom:1px solid #e3e8ee;padding:3mm;vertical-align:top}small{font-size:7.3pt;color:#66717f}.right{text-align:right}
            .totals{width:52%;margin:8mm 0 0 auto}.totals>div{display:table;width:100%;padding:2mm 0;border-bottom:1px solid #e3e8ee}
            .totals span{display:table-cell}.totals strong{display:table-cell;text-align:right}.totals .grand{font-size:12pt;font-weight:bold;border-top:2px solid #18212b;border-bottom:0}
            .bottom{margin-top:8mm}.thankyou{text-align:center;color:#51606c;margin-top:12mm}
            .footer{position:fixed;bottom:-11mm;left:0;right:0;border-top:1px solid #dce3e9;padding-top:2mm;color:#7a8590;font-size:7pt}
            </style></head><body><div class="header"><img class="logo" src="data:image/png;base64,' . $logo
            . '"><div class="header-right">ANICRAZE<br>Contact +91 8010526600<br>' . self::h($number)
            . '</div></div>';
    }

    private function end(): string
    {
        return '<div class="footer">ANICRAZE · Enterprise operations, simplified.</div></body></html>';
    }

    private function render(string $html): string
    {
        $temp = dirname(__DIR__, 2) . '/storage/tmp';
        if (!is_dir($temp) && !mkdir($temp, 0700, true) && !is_dir($temp)) {
            throw new \RuntimeException('Private PDF temp directory unavailable');
        }
        $options = new Options();
        $options->set('defaultFont', 'DejaVu Sans');
        $options->set('isRemoteEnabled', false);
        $options->set('isPhpEnabled', false);
        $options->set('tempDir', $temp);
        $options->set('fontCache', $temp);
        $options->set('chroot', dirname(__DIR__, 2));
        $pdf = new Dompdf($options);
        $pdf->setPaper('A4', 'portrait');
        $pdf->loadHtml($html, 'UTF-8');
        $pdf->render();
        $canvas = $pdf->getCanvas();
        $font = $pdf->getFontMetrics()->getFont('DejaVu Sans', 'normal');
        $canvas->page_text(470, 815, 'Page {PAGE_NUM} of {PAGE_COUNT}', $font, 7, [0.45, 0.49, 0.53]);
        return $pdf->output();
    }

    private static function h(mixed $value): string
    {
        return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }

    private static function inr(float|int $value): string
    {
        return '&#8377;' . self::indianNumber($value, 2);
    }

    private static function indianNumber(float|int $value, int $decimals): string
    {
        $rounded = number_format(abs((float) $value), $decimals, '.', '');
        [$whole, $fraction] = array_pad(explode('.', $rounded, 2), 2, '');
        $last = substr($whole, -3);
        $front = substr($whole, 0, -3);
        if ($front !== '') {
            $front = preg_replace('/\B(?=(\d{2})+(?!\d))/', ',', $front) . ',';
        }
        return ($value < 0 ? '-' : '') . $front . $last . ($decimals ? '.' . $fraction : '');
    }
}
