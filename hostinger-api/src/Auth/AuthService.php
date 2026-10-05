<?php
declare(strict_types=1);

namespace Anicraze\Auth;

use Anicraze\Config\Environment;
use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;
use Anicraze\Http\ApiException;
use Firebase\JWT\JWT;
use Firebase\JWT\Key;
use PDO;

final class AuthService
{
    private const ACCESS_SECONDS = 900;
    private const REFRESH_SECONDS = 604800;
    private const REMEMBER_SECONDS = 2592000;
    private const ISSUER = 'anicraze-erp-api';
    private const AUDIENCE = 'anicraze-erp-client';

    public function __construct(private readonly PDO $database)
    {
    }

    public function login(string $email, string $password, bool $remember): array
    {
        $email = strtolower(trim($email));
        if (!filter_var($email, FILTER_VALIDATE_EMAIL) || strlen($password) < 8 || strlen($password) > 128) {
            throw new ApiException(422, 'validation_error', 'Request validation failed');
        }
        return Connection::transaction($this->database, function () use ($email, $password, $remember): array {
            $statement = $this->database->prepare('SELECT * FROM users WHERE email = ? FOR UPDATE');
            $statement->execute([$email]);
            $user = $statement->fetch();
            if (!$user) {
                password_verify($password, password_hash('invalid-account-sentinel', PASSWORD_DEFAULT));
                throw new ApiException(401, 'AUTH_INVALID_CREDENTIALS', 'Invalid email or password');
            }
            if ($user['locked_until'] !== null && strtotime($user['locked_until'] . ' UTC') > time()) {
                throw new ApiException(429, 'AUTH_ACCOUNT_LOCKED', 'Please try again later');
            }
            if (!password_verify($password, $user['password_hash'])) {
                $attempts = (int) $user['failed_login_attempts'] + 1;
                $lockedUntil = $attempts >= 5 ? gmdate('Y-m-d H:i:s', time() + 900) : null;
                $update = $this->database->prepare('UPDATE users SET failed_login_attempts=?, locked_until=? WHERE id=?');
                $update->execute([$attempts, $lockedUntil, $user['id']]);
                // Commit the failed-attempt counter before returning the error.
                $this->database->commit();
                throw new ApiException(401, 'AUTH_INVALID_CREDENTIALS', 'Invalid email or password');
            }
            if ($user['status'] !== 'ACTIVE' || (int) $user['is_active'] !== 1) {
                throw new ApiException(403, 'AUTH_INACTIVE', 'Account is inactive');
            }
            $update = $this->database->prepare('UPDATE users SET failed_login_attempts=0, locked_until=NULL, last_login_at=UTC_TIMESTAMP(6) WHERE id=?');
            $update->execute([$user['id']]);
            $session = $this->createSession($user, $remember);
            return $session + ['user' => $this->profile($user['id'])];
        });
    }

    public function refresh(string $rawToken): array
    {
        if (strlen($rawToken) < 20) {
            throw new ApiException(422, 'validation_error', 'Request validation failed');
        }
        return Connection::transaction($this->database, function () use ($rawToken): array {
            $statement = $this->database->prepare(
                'SELECT s.*, u.status, u.is_active, u.token_version AS current_version '
                . 'FROM refresh_sessions s JOIN users u ON u.id=s.user_id '
                . 'WHERE s.token_hash=? FOR UPDATE'
            );
            $statement->execute([hash('sha256', $rawToken)]);
            $session = $statement->fetch();
            if (!$session || $session['revoked_at'] !== null || strtotime($session['expires_at'] . ' UTC') <= time()
                || $session['status'] !== 'ACTIVE' || (int) $session['is_active'] !== 1
                || (int) $session['token_version'] !== (int) $session['current_version']) {
                throw new ApiException(401, 'AUTH_INVALID_REFRESH', 'Refresh session is invalid');
            }
            $next = bin2hex(random_bytes(32));
            $update = $this->database->prepare('UPDATE refresh_sessions SET token_hash=? WHERE id=?');
            $update->execute([hash('sha256', $next), $session['id']]);
            return $this->tokenPair($session['user_id'], $session['id'], (int) $session['token_version'], $next,
                max(0, strtotime($session['expires_at'] . ' UTC') - time()));
        });
    }

    public function authenticate(string $accessToken): array
    {
        try {
            $claims = JWT::decode($accessToken, new Key($this->secret(), 'HS256'));
        } catch (\Throwable) {
            throw new ApiException(401, 'AUTH_INVALID_TOKEN', 'Authentication is required');
        }
        if (($claims->iss ?? null) !== self::ISSUER || ($claims->aud ?? null) !== self::AUDIENCE
            || !is_string($claims->sub ?? null) || !is_string($claims->sid ?? null)
            || !is_int($claims->tv ?? null)) {
            throw new ApiException(401, 'AUTH_INVALID_TOKEN', 'Authentication is required');
        }
        $statement = $this->database->prepare(
            'SELECT u.id, u.status, u.is_active, u.token_version, u.assigned_store_id, s.id AS session_id '
            . 'FROM users u JOIN refresh_sessions s ON s.user_id=u.id '
            . 'WHERE u.id=? AND s.id=? AND s.revoked_at IS NULL AND s.expires_at>UTC_TIMESTAMP(6)'
        );
        $statement->execute([$claims->sub, $claims->sid]);
        $actor = $statement->fetch();
        if (!$actor || $actor['status'] !== 'ACTIVE' || (int) $actor['is_active'] !== 1
            || (int) $actor['token_version'] !== $claims->tv) {
            throw new ApiException(401, 'AUTH_SESSION_REVOKED', 'Authentication is required');
        }
        $actor['roles'] = $this->roles($actor['id']);
        if (in_array('SALES', $actor['roles'], true) && !$actor['assigned_store_id']) {
            throw new ApiException(403, 'AUTH_SHOP_UNASSIGNED', 'Shop assignment is required');
        }
        return $actor;
    }

    public function logout(array $actor, string $rawToken): void
    {
        Connection::transaction($this->database, function () use ($actor, $rawToken): void {
            $statement = $this->database->prepare('UPDATE refresh_sessions SET revoked_at=UTC_TIMESTAMP(6) WHERE id=? AND user_id=? AND token_hash=? AND revoked_at IS NULL');
            $statement->execute([$actor['session_id'], $actor['id'], hash('sha256', $rawToken)]);
            if ($statement->rowCount() !== 1) {
                throw new ApiException(401, 'AUTH_INVALID_REFRESH', 'Refresh session is invalid');
            }
        });
    }

    public function logoutAll(array $actor): int
    {
        return Connection::transaction($this->database, function () use ($actor): int {
            $this->database->prepare('UPDATE users SET token_version=token_version+1 WHERE id=?')->execute([$actor['id']]);
            $statement = $this->database->prepare('UPDATE refresh_sessions SET revoked_at=UTC_TIMESTAMP(6) WHERE user_id=? AND revoked_at IS NULL');
            $statement->execute([$actor['id']]);
            return $statement->rowCount();
        });
    }

    public function profile(string $userId): array
    {
        $statement = $this->database->prepare('SELECT u.*, s.name AS assigned_store_name FROM users u LEFT JOIN stores s ON s.id=u.assigned_store_id WHERE u.id=?');
        $statement->execute([$userId]);
        $user = $statement->fetch();
        if (!$user) {
            throw new ApiException(401, 'AUTH_INVALID_TOKEN', 'Authentication is required');
        }
        return [
            'id' => $user['id'], 'email' => $user['email'], 'name' => $user['full_name'],
            'phone' => $user['phone'], 'avatar_url' => $user['avatar_url'], 'status' => $user['status'],
            'roles' => $this->roles($userId), 'permissions' => $this->permissions($userId),
            'assigned_store_id' => $user['assigned_store_id'],
            'assigned_store_name' => $user['assigned_store_name'], 'assigned_store' => null,
            'last_login_at' => $this->iso($user['last_login_at']),
            'created_at' => $this->iso($user['created_at']), 'updated_at' => $this->iso($user['updated_at']),
            'preferred_language' => $user['preferred_language'], 'timezone' => $user['timezone'],
        ];
    }

    private function createSession(array $user, bool $remember): array
    {
        $sessionId = Uuid::v4();
        $raw = bin2hex(random_bytes(32));
        $lifetime = $remember ? self::REMEMBER_SECONDS : self::REFRESH_SECONDS;
        $statement = $this->database->prepare('INSERT INTO refresh_sessions (id,user_id,token_hash,token_version,expires_at) VALUES (?,?,?,?,?)');
        $statement->execute([$sessionId, $user['id'], hash('sha256', $raw), (int) $user['token_version'],
            gmdate('Y-m-d H:i:s', time() + $lifetime)]);
        return $this->tokenPair($user['id'], $sessionId, (int) $user['token_version'], $raw, $lifetime);
    }

    private function tokenPair(string $userId, string $sessionId, int $version, string $refresh, int $refreshLifetime): array
    {
        $now = time();
        $access = JWT::encode([
            'iss' => self::ISSUER, 'aud' => self::AUDIENCE, 'iat' => $now, 'nbf' => $now,
            'exp' => $now + self::ACCESS_SECONDS, 'sub' => $userId, 'sid' => $sessionId,
            'tv' => $version, 'jti' => Uuid::v4(),
        ], $this->secret(), 'HS256');
        return ['access_token' => $access, 'refresh_token' => $refresh, 'token_type' => 'bearer',
            'access_token_expires_in' => self::ACCESS_SECONDS, 'refresh_token_expires_in' => $refreshLifetime];
    }

    private function roles(string $userId): array
    {
        $statement = $this->database->prepare('SELECT r.code FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=? ORDER BY r.code');
        $statement->execute([$userId]);
        return $statement->fetchAll(PDO::FETCH_COLUMN);
    }

    private function permissions(string $userId): array
    {
        $statement = $this->database->prepare('SELECT DISTINCT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id JOIN user_roles ur ON ur.role_id=rp.role_id WHERE ur.user_id=? ORDER BY p.code');
        $statement->execute([$userId]);
        return $statement->fetchAll(PDO::FETCH_COLUMN);
    }

    private function secret(): string
    {
        $secret = Environment::required('APP_SECRET');
        if (strlen($secret) < 32) {
            throw new \RuntimeException('APP_SECRET is too short');
        }
        return $secret;
    }

    private function iso(?string $value): ?string
    {
        return $value === null ? null : str_replace(' ', 'T', $value) . 'Z';
    }
}
