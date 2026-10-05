<?php
declare(strict_types=1);

namespace Anicraze\Catalog;

use Anicraze\Http\ApiException;
use PDO;

final class ProductImportService
{
    private const COLUMNS = ['name', 'sku', 'category_id', 'brand_id', 'anime_id', 'character_id',
        'product_type', 'short_description', 'description', 'material', 'edition', 'manufacturer',
        'country_of_origin', 'import_reference', 'purchase_price', 'landed_cost', 'selling_price',
        'mrp', 'minimum_selling_price', 'discount_percentage', 'reorder_level', 'unit_of_measure',
        'weight', 'length', 'width', 'height', 'is_serialized', 'is_featured', 'status'];

    public function __construct(private readonly PDO $database)
    {
    }

    public function import(array $actor, string $path, string $filename, int $size, bool $dryRun): array
    {
        if (!in_array('OWNER', $actor['roles'] ?? [], true)) {
            throw new ApiException(403, 'AUTH_FORBIDDEN', 'Product import requires Owner access');
        }
        if (strtolower(pathinfo($filename, PATHINFO_EXTENSION)) !== 'csv' || $size < 1 || $size > 5 * 1024 * 1024
            || !is_file($path) || filesize($path) !== $size) {
            throw new ApiException(422, 'PRODUCT_IMPORT_TYPE_INVALID', 'Only a CSV file up to 5 MB is supported');
        }
        $raw = file_get_contents($path);
        if ($raw === false || str_contains($raw, "\0") || !mb_check_encoding($raw, 'UTF-8')) {
            throw new ApiException(422, 'PRODUCT_IMPORT_ENCODING_INVALID', 'CSV must be valid UTF-8 text');
        }
        $handle = fopen('php://temp', 'w+');
        if ($handle === false) {
            throw new \RuntimeException('CSV parser could not start');
        }
        try {
            fwrite($handle, preg_replace('/^\xEF\xBB\xBF/', '', $raw));
            rewind($handle);
            $header = fgetcsv($handle, 0, ',', '"', '');
            if (!is_array($header)) {
                throw new ApiException(422, 'PRODUCT_IMPORT_EMPTY', 'CSV header is missing');
            }
            $header = array_map(static fn (string $value): string => strtolower(trim($value)), $header);
            if (count($header) !== count(array_unique($header))
                || array_diff(['name', 'category_id', 'product_type'], $header) !== []) {
                throw new ApiException(422, 'PRODUCT_IMPORT_HEADER_INVALID', 'CSV requires unique name, category_id and product_type columns');
            }
            $rows = [];
            $line = 1;
            while (($cells = fgetcsv($handle, 0, ',', '"', '')) !== false) {
                $line++;
                if ($cells === [null] || (count($cells) === 1 && trim((string) $cells[0]) === '')) {
                    continue;
                }
                if (count($rows) >= 5000) {
                    throw new ApiException(422, 'PRODUCT_IMPORT_TOO_MANY_ROWS', 'CSV exceeds 5,000 product rows');
                }
                if (count($cells) !== count($header)) {
                    $rows[] = ['line' => $line, 'error' => 'Column count does not match header'];
                    continue;
                }
                $source = array_combine($header, $cells);
                $body = [];
                foreach (self::COLUMNS as $field) {
                    if (!array_key_exists($field, $source) || trim((string) $source[$field]) === '') {
                        continue;
                    }
                    $body[$field] = trim((string) $source[$field]);
                }
                if (isset($body['reorder_level'])) {
                    if (preg_match('/^\d+$/D', $body['reorder_level']) !== 1) {
                        $rows[] = ['line' => $line, 'error' => 'Invalid reorder level'];
                        continue;
                    }
                    $body['reorder_level'] = (int) $body['reorder_level'];
                }
                foreach (['is_serialized', 'is_featured'] as $flag) {
                    if (!isset($body[$flag])) { continue; }
                    if (!in_array(strtolower($body[$flag]), ['true', 'false', '1', '0', 'yes', 'no'], true)) {
                        $rows[] = ['line' => $line, 'error' => 'Invalid Boolean field'];
                        continue 2;
                    }
                    $body[$flag] = in_array(strtolower($body[$flag]), ['true', '1', 'yes'], true);
                }
                $rows[] = ['line' => $line, 'body' => $body];
            }
        } finally {
            fclose($handle);
        }
        if ($rows === []) {
            throw new ApiException(422, 'PRODUCT_IMPORT_EMPTY', 'CSV has no product rows');
        }
        $writer = new ProductWriteService($this->database);
        $errors = [];
        $valid = 0;
        $this->database->beginTransaction();
        try {
            foreach ($rows as $row) {
                if (isset($row['error'])) {
                    $errors[] = ['row' => $row['line'], 'field' => null, 'message' => $row['error']];
                    continue;
                }
                try {
                    $writer->create($actor, $row['body']);
                    $valid++;
                } catch (ApiException $error) {
                    $errors[] = ['row' => $row['line'], 'field' => null, 'message' => $error->getMessage()];
                }
            }
        } finally {
            $this->database->rollBack();
        }
        $created = 0;
        if (!$dryRun && $errors === []) {
            $this->database->beginTransaction();
            try {
                foreach ($rows as $row) {
                    $writer->create($actor, $row['body']);
                    $created++;
                }
                $this->database->commit();
            } catch (\Throwable $error) {
                if ($this->database->inTransaction()) { $this->database->rollBack(); }
                throw $error;
            }
        }
        return ['total_rows' => count($rows), 'valid_rows' => $valid, 'invalid_rows' => count($errors),
            'errors' => $errors, 'created_rows' => $created, 'dry_run' => $dryRun];
    }
}
