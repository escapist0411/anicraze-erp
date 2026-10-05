<?php
declare(strict_types=1);

use Anicraze\Auth\AuthService;
use Anicraze\Auth\PasswordResetService;
use Anicraze\Database\Connection;
use Anicraze\Database\Uuid;
use Anicraze\Http\ApiException;

require dirname(__DIR__) . '/vendor/autoload.php';

if (!str_starts_with((string) getenv('DB_NAME'), 'anicraze_phase5b_')) throw new RuntimeException('Password reset test requires disposable database');
$db=Connection::open(); if($db->query('SELECT DATABASE()')->fetchColumn()!==getenv('DB_NAME')) throw new RuntimeException('Database identity mismatch');
$id=Uuid::v4(); $email='reset-'.bin2hex(random_bytes(5)).'@example.invalid'; $old='OldStrong!'.bin2hex(random_bytes(7)); $new='NewStrong!'.bin2hex(random_bytes(7));
$db->prepare('INSERT INTO users (id,email,full_name,password_hash) VALUES (?,?,?,?)')->execute([$id,$email,'Reset Test',password_hash($old,PASSWORD_DEFAULT)]);
$captured=null; $service=new PasswordResetService($db,function(string $to,string $name,string $url)use(&$captured):bool{$captured=[$to,$name,$url];return true;});
$passed=0;
try {
    $service->request('missing-'.bin2hex(random_bytes(3)).'@example.invalid'); $passed++;
    $service->request($email); if($captured===null||$captured[0]!==$email) throw new RuntimeException('Reset delivery was not invoked'); $passed++;
    $service->request($email);
    $service->request($email);
    try{$service->request($email);throw new RuntimeException('Reset rate limit was not enforced');}catch(ApiException $error){if($error->status!==429)throw $error;} $passed++;
    parse_str((string)parse_url($captured[2],PHP_URL_QUERY),$query); $token=$query['token']??null; if(!is_string($token)||strlen($token)<30) throw new RuntimeException('Reset token missing');
    $service->reset($token,$new); $passed++;
    try{$service->reset($token,$old);throw new RuntimeException('Reset token replay succeeded');}catch(ApiException $error){if($error->status!==400)throw $error;} $passed++;
    $auth=new AuthService($db); try{$auth->login($email,$old,false);throw new RuntimeException('Old password still works');}catch(ApiException $error){if($error->status!==401)throw $error;}
    if(($auth->login($email,$new,false)['user']['email']??null)!==$email) throw new RuntimeException('New password login failed'); $passed++;
} finally {
    $db->prepare('DELETE FROM refresh_sessions WHERE user_id=?')->execute([$id]);
    $db->prepare('DELETE FROM users WHERE id=?')->execute([$id]);
}
echo "php_password_reset_integration_passed={$passed}\n";
