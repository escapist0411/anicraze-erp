<?php
declare(strict_types=1);

namespace Anicraze\Http;

final class Request
{
    public static function json(): array
    {
        $length = (int) ($_SERVER['CONTENT_LENGTH'] ?? 0);
        if ($length > 1_048_576) {
            throw new ApiException(413, 'request_too_large', 'Request body is too large');
        }
        $type = strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0]));
        if ($type !== 'application/json') {
            throw new ApiException(415, 'unsupported_media_type', 'JSON Content-Type is required');
        }
        $raw = file_get_contents('php://input', false, null, 0, 1_048_577);
        try {
            $body = json_decode((string) $raw, true, 64, JSON_THROW_ON_ERROR);
        } catch (\JsonException) {
            throw new ApiException(422, 'validation_error', 'Request validation failed');
        }
        if (!is_array($body) || array_is_list($body)) {
            throw new ApiException(422, 'validation_error', 'Request validation failed');
        }
        return $body;
    }

    public static function bearer(): string
    {
        $header = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
        if (!preg_match('/^Bearer ([A-Za-z0-9._-]+)$/D', $header, $matches)) {
            throw new ApiException(401, 'AUTH_REQUIRED', 'Authentication is required');
        }
        return $matches[1];
    }
}
