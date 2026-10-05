<?php
declare(strict_types=1);

namespace Anicraze\Inventory;

use Anicraze\Http\ApiException;
use PDO;
use Smalot\PdfParser\Parser;

/** Read-only stock receipt preview; confirmation remains the normal receipt workflow. */
final class StockPdfImportService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function preview(array $actor, string $path, string $filename, int $size, string $contentType): array
    {
        if (!array_intersect(['OWNER', 'MANAGER'], $actor['roles'] ?? [])) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Stock receipt access is restricted');
        }
        if (strtolower(pathinfo($filename, PATHINFO_EXTENSION)) !== 'pdf'
            || strtolower(trim(explode(';', $contentType)[0])) !== 'application/pdf') {
            throw new ApiException(422, 'STOCK_PDF_TYPE_INVALID', 'Choose a PDF file');
        }
        if ($size < 1 || $size > 10 * 1024 * 1024 || !is_file($path) || filesize($path) !== $size) {
            throw new ApiException(422, 'STOCK_PDF_TOO_LARGE', 'PDF must be smaller than 10 MB');
        }
        $raw = file_get_contents($path);
        if ($raw === false || !str_starts_with($raw, '%PDF-')
            || (new \finfo(FILEINFO_MIME_TYPE))->buffer($raw) !== 'application/pdf') {
            throw new ApiException(422, 'STOCK_PDF_INVALID', 'PDF could not be read safely');
        }
        try {
            $pdf = (new Parser())->parseContent($raw);
            if (count($pdf->getPages()) > 50) {
                throw new ApiException(422, 'STOCK_PDF_TOO_LONG', 'PDF has too many pages to preview');
            }
            $text = $pdf->getText(50);
        } catch (ApiException $error) {
            throw $error;
        } catch (\Throwable) {
            throw new ApiException(422, 'STOCK_PDF_INVALID', 'PDF could not be read safely');
        }
        if (trim($text) === '') {
            return ['rows' => [], 'readable_text' => false,
                'message' => 'This PDF does not contain readable text. Enter products manually.'];
        }
        $products = $this->database->query("SELECT id,name FROM products WHERE status='ACTIVE' AND deleted_at IS NULL ORDER BY name")
            ->fetchAll();
        $rows = [];
        foreach (preg_split('/\R/u', $text) ?: [] as $line) {
            if (preg_match('/^\s*(.+?)\s+(\d+)\s+(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d{1,2})?)(?:\s+|$)/iu', $line, $match) !== 1) {
                continue;
            }
            $description = mb_substr(trim(preg_replace('/\s+/u', ' ', $match[1]) ?? ''), 0, 240);
            $quantity = (int) $match[2];
            $cost = str_replace(',', '', $match[3]);
            if ($description === '' || $quantity < 1 || $quantity > 100000
                || !preg_match('/^\d{1,8}(?:\.\d{1,2})?$/D', $cost)) {
                continue;
            }
            $best = null;
            $score = 0.0;
            $normalized = mb_strtolower($description);
            foreach ($products as $product) {
                similar_text($normalized, mb_strtolower($product['name']), $percentage);
                if ($percentage > $score) {
                    $score = $percentage;
                    $best = $product;
                }
            }
            $matched = $best !== null && $score >= 45.0;
            [$whole, $fraction] = array_pad(explode('.', $cost, 2), 2, '');
            $costDisplay = (string) (int) $whole . '.' . str_pad($fraction, 2, '0');
            $rows[] = ['detected_product' => $description,
                'suggested_product_id' => $matched ? $best['id'] : null,
                'suggested_product_name' => $matched ? $best['name'] : null,
                'quantity' => $quantity, 'unit_cost' => $costDisplay,
                'status' => $score >= 75.0 ? 'Matched' : ($matched ? 'Needs Review' : 'Not Found')];
            if (count($rows) >= 200) { break; }
        }
        return ['rows' => $rows, 'readable_text' => true,
            'message' => $rows !== [] ? 'Review every extracted row before adding it to the receipt.'
                : 'Readable text was found, but no product rows could be extracted. Enter products manually.'];
    }
}
