<?php
declare(strict_types=1);

use Anicraze\Auth\AuthService;
use Anicraze\Database\Connection;

require dirname(__DIR__) . '/vendor/autoload.php';

if (getenv('DB_NAME') !== 'anicraze_phase5b_product5c2'
    || !is_string(getenv('ANICRAZE_LOCAL_TEST_PASSWORD'))
    || strlen(getenv('ANICRAZE_LOCAL_TEST_PASSWORD')) < 12) {
    throw new RuntimeException('Image HTTP test requires disposable database and ephemeral local password');
}
$db = Connection::open();
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'anicraze_phase5b_product5c2') {
    throw new RuntimeException('Database identity mismatch');
}
$owner = $db->query("SELECT id,password_hash FROM users WHERE email='owner@anicraze.in'")->fetch();
$productId = $db->query("SELECT id FROM products WHERE status='ACTIVE' AND deleted_at IS NULL ORDER BY id LIMIT 1")->fetchColumn();
if (!$owner || !$productId) { throw new RuntimeException('Local fixtures missing'); }
$oldHash = $owner['password_hash'];
$fixture = tempnam(sys_get_temp_dir(), 'anicraze-image-');
$listen = stream_socket_server('tcp://127.0.0.1:0', $errno, $error);
if ($fixture === false || $listen === false) { throw new RuntimeException('Local HTTP test fixture unavailable'); }
$address = stream_socket_get_name($listen, false);
fclose($listen);
$port = (int) substr($address, strrpos($address, ':') + 1);
$server = null;
$passed = 0;
try {
    $image = imagecreatetruecolor(2, 2);
    imagefill($image, 0, 0, imagecolorallocate($image, 20, 40, 60));
    imagepng($image, $fixture);
    $db->prepare('UPDATE users SET password_hash=? WHERE id=?')
        ->execute([password_hash(getenv('ANICRAZE_LOCAL_TEST_PASSWORD'), PASSWORD_DEFAULT), $owner['id']]);
    $token = (new AuthService($db))->login('owner@anicraze.in', getenv('ANICRAZE_LOCAL_TEST_PASSWORD'), false)['access_token'];
    $entry = dirname(__DIR__) . '/public/index.php';
    $pipes = [];
    $server = proc_open([PHP_BINARY, '-S', '127.0.0.1:' . $port, '-t', dirname($entry), $entry],
        [['file', '/dev/null', 'r'], ['file', '/dev/null', 'w'], ['pipe', 'w']], $pipes);
    if (!is_resource($server)) { throw new RuntimeException('Local PHP server did not start'); }
    stream_set_blocking($pipes[2], false);
    $base = 'http://127.0.0.1:' . $port;
    $ready = false;
    for ($attempt = 0; $attempt < 40; $attempt++) {
        $health = curl_init($base . '/health');
        curl_setopt_array($health, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT_MS => 500]);
        curl_exec($health);
        $ready = curl_getinfo($health, CURLINFO_HTTP_CODE) === 200;
        if ($ready) { break; }
        usleep(50000);
    }
    if (!$ready) { throw new RuntimeException('Local PHP API health failed'); }
    $passed++;
    $profile = curl_init($base . '/api/v1/auth/me');
    curl_setopt_array($profile, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 5,
        CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $token]]);
    curl_exec($profile);
    $profileStatus = curl_getinfo($profile, CURLINFO_HTTP_CODE);
    if ($profileStatus !== 200) {
        $log = stream_get_contents($pipes[2]);
        preg_match('/class=([A-Za-z_\\\\]+)/', (string) $log, $match);
        throw new RuntimeException('Local authenticated profile returned HTTP ' . $profileStatus . ' class=' . ($match[1] ?? 'unknown'));
    }
    $passed++;
    $upload = static function (string $name, ?string $bearer) use ($base, $productId, $fixture): array {
        $request = curl_init($base . '/api/v1/products/' . $productId . '/images');
        curl_setopt_array($request, [CURLOPT_POST => true, CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 10, CURLOPT_POSTFIELDS => ['file' => new CURLFile($fixture, 'image/png', $name)],
            CURLOPT_HTTPHEADER => $bearer === null ? [] : ['Authorization: Bearer ' . $bearer]]);
        $body = curl_exec($request);
        $code = curl_getinfo($request, CURLINFO_HTTP_CODE);
        return [$code, json_decode((string) $body, true)];
    };
    [$code] = $upload('test.png', null);
    if ($code !== 401) { throw new RuntimeException('Unauthenticated upload was accepted'); }
    $passed++;
    [$code] = $upload('test.php', $token);
    if ($code !== 422) {
        $log = stream_get_contents($pipes[2]);
        preg_match('/class=([A-Za-z_\\\\]+)/', (string) $log, $match);
        preg_match('/file=([A-Za-z0-9_.-]+) line=([0-9]+)/', (string) $log, $location);
        throw new RuntimeException('Executable image filename returned HTTP ' . $code . ' class=' . ($match[1] ?? 'unknown')
            . ' location=' . ($location[1] ?? 'unknown') . ':' . ($location[2] ?? 'unknown'));
    }
    $passed++;
    [$code] = $upload('test.jpg', $token);
    if ($code !== 422) { throw new RuntimeException('MIME/extension mismatch was accepted'); }
    $passed++;
    [$code, $result] = $upload('test.png', $token);
    if ($code !== 201 || !is_array($result['data'] ?? null)) { throw new RuntimeException('Valid image upload failed'); }
    $url = $result['data']['file_url'] ?? null;
    if (!is_string($url) || preg_match('#^/product-images/[0-9a-f]{32}\.png$#D', $url) !== 1
        || !is_file(dirname(__DIR__) . '/public' . $url)) {
        throw new RuntimeException('Stored image filename or path is invalid');
    }
    $passed++;
    $row = $db->prepare('SELECT storage_key,mime_type,size_bytes,is_primary FROM product_images WHERE id=?');
    $row->execute([$result['data']['id']]);
    $stored = $row->fetch();
    if (!$stored || $stored['mime_type'] !== 'image/png' || (int) $stored['size_bytes'] !== filesize($fixture)) {
        throw new RuntimeException('Image metadata differs');
    }
    $passed++;
    $product = (new \Anicraze\Catalog\ProductService($db))->find(['roles' => ['OWNER']], 'id', $productId);
    if ($product['primary_image'] !== $url || count($product['images']) < 1) {
        throw new RuntimeException('Product image read contract differs');
    }
    $passed++;
} finally {
    if (is_resource($server)) { proc_terminate($server); fclose($pipes[2]); proc_close($server); }
    $db->prepare('UPDATE users SET password_hash=? WHERE id=?')->execute([$oldHash, $owner['id']]);
    if (is_file($fixture)) { unlink($fixture); }
}
echo "php_product_image_http_integration_passed={$passed}\n";
