<?php
declare(strict_types=1);

namespace Anicraze\Http;

final class Response
{
    public static function success(mixed $data, ?string $message = null, int $status = 200): void
    {
        self::send($status, [
            'success' => true,
            'data' => $data,
            'message' => $message,
            'timestamp' => gmdate('Y-m-d\TH:i:s\Z'),
        ]);
    }

    public static function error(int $status, string $code, string $message, string $requestId): void
    {
        self::send($status, [
            'success' => false,
            'message' => $message,
            'error' => ['code' => $code, 'request_id' => $requestId],
        ]);
    }

    private static function send(int $status, array $body): void
    {
        http_response_code($status);
        echo json_encode($body, JSON_THROW_ON_ERROR | JSON_INVALID_UTF8_SUBSTITUTE);
    }
}
