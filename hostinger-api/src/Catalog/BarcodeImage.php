<?php
declare(strict_types=1);

namespace Anicraze\Catalog;

use Anicraze\Http\ApiException;
use Picqer\Barcode\Renderers\PngRenderer;
use Picqer\Barcode\Types\TypeCode128;

final class BarcodeImage
{
    public static function png(string $value): string
    {
        if (preg_match('/^[A-Za-z0-9_-]{4,64}$/D', $value) !== 1) {
            throw new ApiException(422, 'BARCODE_INVALID', 'Approved barcode is invalid');
        }
        $barcode = (new TypeCode128())->getBarcode($value);
        $renderer = new PngRenderer();
        $renderer->useGd();
        $renderer->setForegroundColor([0, 0, 0]);
        $renderer->setBackgroundColor([255, 255, 255]);
        $bars = $renderer->render($barcode, $barcode->getWidth() * 2, 120);
        $source = imagecreatefromstring($bars);
        if ($source === false) {
            throw new \RuntimeException('Barcode render failed');
        }
        $quiet = 20;
        $image = imagecreatetruecolor(imagesx($source) + 2 * $quiet, imagesy($source));
        if ($image === false) {
            throw new \RuntimeException('Barcode canvas failed');
        }
        $white = imagecolorallocate($image, 255, 255, 255);
        imagefill($image, 0, 0, $white);
        imagecopy($image, $source, $quiet, 0, 0, 0, imagesx($source), imagesy($source));
        ob_start();
        imagepng($image);
        $result = ob_get_clean();
        if (!is_string($result)) {
            throw new \RuntimeException('Barcode PNG failed');
        }
        return $result;
    }

    public static function dataUri(string $value): string
    {
        return 'data:image/png;base64,' . base64_encode(self::png($value));
    }
}
