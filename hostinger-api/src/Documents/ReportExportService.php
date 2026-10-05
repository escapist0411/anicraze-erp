<?php
declare(strict_types=1);

namespace Anicraze\Documents;

use Anicraze\Http\ApiException;
use Anicraze\Reports\ReportService;
use PDO;
use ZipArchive;

final class ReportExportService
{
    public function __construct(private readonly PDO $database)
    {
    }

    public function export(array $actor, string $type, string $format, array $filters): array
    {
        [$domain, $name] = match ($type) {
            'sales_summary' => ['sales', 'summary'],
            'inventory_summary' => ['inventory', 'summary'],
            'finance_summary' => ['finance', 'summary'],
            'finance_shop-profit-loss' => ['finance', 'shop-profit-loss'],
            default => throw new ApiException(422, 'validation_error', 'Unsupported report type'),
        };
        $report = (new ReportService($this->database))->report($actor, $domain, $name, $filters);
        $rows = [['Metric', 'Value']];
        foreach ($report['summary'] as $key => $value) {
            if (is_scalar($value) || $value === null) {
                $rows[] = [ucwords(str_replace('_', ' ', (string) $key)), (string) ($value ?? '')];
            }
        }
        if (count($report['rows'] ?? []) > 0) {
            $rows[] = ['', ''];
            $columns = array_keys($report['rows'][0]);
            $rows[] = $columns;
            foreach ($report['rows'] as $item) {
                $rows[] = array_map(static fn (string $column): string => (string) ($item[$column] ?? ''), $columns);
            }
        }
        if ($format === 'CSV') {
            return [$this->csv($rows), 'text/csv; charset=utf-8', 'csv'];
        }
        if ($format === 'XLSX') {
            return [$this->xlsx($rows), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'];
        }
        throw new ApiException(422, 'validation_error', 'Unsupported report format');
    }

    private function csv(array $rows): string
    {
        $stream = fopen('php://temp', 'w+');
        if ($stream === false) { throw new \RuntimeException('CSV buffer unavailable'); }
        foreach ($rows as $row) {
            $safe = array_map(static function (string $cell): string {
                return preg_match('/^[\s]*[=+@-]/u', $cell) ? "'" . $cell : $cell;
            }, $row);
            fputcsv($stream, $safe, ',', '"', '');
        }
        rewind($stream);
        $result = stream_get_contents($stream);
        fclose($stream);
        if ($result === false) { throw new \RuntimeException('CSV buffer unreadable'); }
        return $result;
    }

    private function xlsx(array $rows): string
    {
        if (!class_exists(ZipArchive::class)) {
            throw new ApiException(503, 'EXPORT_UNAVAILABLE', 'XLSX export requires the PHP zip extension');
        }
        $sheetRows = '';
        foreach ($rows as $rowIndex => $row) {
            $cells = '';
            foreach ($row as $columnIndex => $value) {
                $column = chr(65 + $columnIndex);
                $ref = $column . ($rowIndex + 1);
                $escaped = htmlspecialchars($value, ENT_XML1 | ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
                // Inline strings prevent imported text from becoming formulas.
                $cells .= '<c r="' . $ref . '" t="inlineStr"><is><t xml:space="preserve">'
                    . $escaped . '</t></is></c>';
            }
            $sheetRows .= '<row r="' . ($rowIndex + 1) . '">' . $cells . '</row>';
        }
        $temporary = tempnam(sys_get_temp_dir(), 'anicraze-report-');
        if ($temporary === false) { throw new \RuntimeException('XLSX temporary file unavailable'); }
        $zip = new ZipArchive();
        try {
            if ($zip->open($temporary, ZipArchive::OVERWRITE) !== true) {
                throw new \RuntimeException('XLSX archive could not be created');
            }
            $zip->addFromString('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                . '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                . '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                . '<Default Extension="xml" ContentType="application/xml"/>'
                . '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                . '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                . '</Types>');
            $zip->addFromString('_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                . '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                . '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                . '</Relationships>');
            $zip->addFromString('xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                . '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                . 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                . '<sheets><sheet name="ANICRAZE Report" sheetId="1" r:id="rId1"/></sheets></workbook>');
            $zip->addFromString('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                . '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                . '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                . '</Relationships>');
            $zip->addFromString('xl/worksheets/sheet1.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                . '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                . $sheetRows . '</sheetData></worksheet>');
            if (!$zip->close()) { throw new \RuntimeException('XLSX archive could not be closed'); }
            $bytes = file_get_contents($temporary);
            if ($bytes === false) { throw new \RuntimeException('XLSX archive could not be read'); }
            return $bytes;
        } finally {
            if (file_exists($temporary)) { unlink($temporary); }
        }
    }
}
