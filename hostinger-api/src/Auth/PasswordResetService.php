<?php
declare(strict_types=1);

namespace Anicraze\Auth;

use Anicraze\Config\Environment;
use Anicraze\Http\ApiException;
use Firebase\JWT\JWT;
use Firebase\JWT\Key;
use PDO;

final class PasswordResetService
{
    private const LIFETIME = 1800;
    private const ISSUER = 'anicraze-erp-api';
    private const AUDIENCE = 'anicraze-password-reset';

    /** @param null|callable(string,string,string):bool $sender */
    public function __construct(private readonly PDO $database, private readonly mixed $sender = null) {}

    public function request(string $email): void
    {
        $email = strtolower(trim($email));
        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
            throw new ApiException(422, 'validation_error', 'Enter a valid email address');
        }
        $this->throttle($email);
        $statement = $this->database->prepare("SELECT id,email,full_name,token_version FROM users WHERE email=? AND status='ACTIVE' AND is_active=1");
        $statement->execute([$email]);
        $user = $statement->fetch();
        if (!$user) return;
        $token = $this->issue($user['id'], (int) $user['token_version']);
        $url = rtrim(Environment::optional('FRONTEND_URL', ''), '/') . '/reset-password?token=' . rawurlencode($token);
        if ($this->sender !== null) { ($this->sender)($user['email'], $user['full_name'], $url); return; }
        if (Environment::optional('PASSWORD_RESET_EMAIL_ENABLED', '0') !== '1') return;
        $from = Environment::required('MAIL_FROM');
        if (!filter_var($from, FILTER_VALIDATE_EMAIL) || !str_starts_with($url, 'https://')) {
            throw new \RuntimeException('Password reset email configuration is invalid');
        }
        $body = "Hello {$user['full_name']},\n\nUse this secure link within 30 minutes to reset your ANICRAZE ERP password:\n{$url}\n\nIf you did not request this, ignore this email.";
        $headers = ['From: ANICRAZE ERP <' . $from . '>', 'Content-Type: text/plain; charset=UTF-8'];
        if (!mail($user['email'], 'Reset your ANICRAZE ERP password', $body, implode("\r\n", $headers))) {
            throw new \RuntimeException('Password reset email could not be queued');
        }
    }

    public function reset(string $token, string $password): void
    {
        if (strlen($password) < 12 || strlen($password) > 128 || !preg_match('/[A-Z]/', $password)
            || !preg_match('/[a-z]/', $password) || !preg_match('/\d/', $password)
            || !preg_match('/[^A-Za-z0-9]/', $password)) {
            throw new ApiException(422, 'validation_error', 'Password must be 12–128 characters with upper, lower, number, and symbol');
        }
        try { $claims = JWT::decode($token, new Key($this->secret(), 'HS256')); }
        catch (\Throwable) { throw new ApiException(400, 'AUTH_RESET_INVALID', 'Password reset link is invalid or expired'); }
        if (($claims->iss ?? null) !== self::ISSUER || ($claims->aud ?? null) !== self::AUDIENCE
            || ($claims->purpose ?? null) !== 'password-reset' || !is_string($claims->sub ?? null)
            || !is_int($claims->tv ?? null)) {
            throw new ApiException(400, 'AUTH_RESET_INVALID', 'Password reset link is invalid or expired');
        }
        $this->database->beginTransaction();
        try {
            $statement = $this->database->prepare("SELECT id,token_version FROM users WHERE id=? AND status='ACTIVE' AND is_active=1 FOR UPDATE");
            $statement->execute([$claims->sub]);
            $user = $statement->fetch();
            if (!$user || (int) $user['token_version'] !== $claims->tv) {
                throw new ApiException(400, 'AUTH_RESET_INVALID', 'Password reset link is invalid or expired');
            }
            $this->database->prepare('UPDATE users SET password_hash=?,token_version=token_version+1,failed_login_attempts=0,locked_until=NULL WHERE id=?')
                ->execute([password_hash($password, PASSWORD_DEFAULT), $user['id']]);
            $this->database->prepare('UPDATE refresh_sessions SET revoked_at=COALESCE(revoked_at,UTC_TIMESTAMP(6)) WHERE user_id=?')
                ->execute([$user['id']]);
            $this->database->commit();
        } catch (\Throwable $error) {
            if ($this->database->inTransaction()) $this->database->rollBack();
            throw $error;
        }
    }

    private function issue(string $userId, int $version): string
    {
        $now = time();
        return JWT::encode(['iss'=>self::ISSUER,'aud'=>self::AUDIENCE,'iat'=>$now,'nbf'=>$now,
            'exp'=>$now+self::LIFETIME,'sub'=>$userId,'tv'=>$version,'purpose'=>'password-reset'], $this->secret(), 'HS256');
    }

    private function throttle(string $email): void
    {
        $directory = dirname(__DIR__, 2) . '/storage/rate-limits';
        if (!is_dir($directory) && !mkdir($directory, 0700, true) && !is_dir($directory)) {
            throw new \RuntimeException('Password reset rate limiter is unavailable');
        }
        $path = $directory . '/' . hash_hmac('sha256', $email, $this->secret()) . '.json';
        $handle = fopen($path, 'c+');
        if ($handle === false || !flock($handle, LOCK_EX)) {
            if (is_resource($handle)) fclose($handle);
            throw new \RuntimeException('Password reset rate limiter is unavailable');
        }
        try {
            $raw = stream_get_contents($handle);
            $attempts = $raw === false || $raw === '' ? [] : json_decode($raw, true);
            if (!is_array($attempts)) $attempts = [];
            $cutoff = time() - 900;
            $attempts = array_values(array_filter($attempts, static fn (mixed $time): bool => is_int($time) && $time >= $cutoff));
            if (count($attempts) >= 3) throw new ApiException(429, 'AUTH_RESET_RATE_LIMITED', 'Please wait before requesting another reset link');
            $attempts[] = time();
            rewind($handle); ftruncate($handle, 0);
            fwrite($handle, json_encode($attempts, JSON_THROW_ON_ERROR)); fflush($handle); chmod($path, 0600);
        } finally {
            flock($handle, LOCK_UN); fclose($handle);
        }
    }

    private function secret(): string
    {
        $secret = Environment::required('APP_SECRET');
        if (strlen($secret) < 32) throw new \RuntimeException('APP_SECRET is too short');
        return $secret;
    }
}
