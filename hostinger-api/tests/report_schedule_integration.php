<?php
declare(strict_types=1);

use Anicraze\Database\Connection;
use Anicraze\Http\ApiException;
use Anicraze\Reports\ReportScheduleService;

require dirname(__DIR__) . '/vendor/autoload.php';

if (!str_starts_with((string)getenv('DB_NAME'),'anicraze_phase5b_workflow')) throw new RuntimeException('Report schedule test requires disposable workflow database');
$db=Connection::open(); if($db->query('SELECT DATABASE()')->fetchColumn()!==getenv('DB_NAME')) throw new RuntimeException('Database identity mismatch');
$id='11111111-2222-4333-8444-555555555555';
putenv('REPORT_EMAIL_ENABLED=0');
putenv('REPORT_SCHEDULES_JSON='.json_encode([['id'=>$id,'name'=>'Weekly owner report','report_type'=>'sales_summary','format'=>'PDF','frequency'=>'WEEKLY','timezone'=>'Asia/Kolkata','recipient_emails_json'=>['owner@example.invalid'],'is_active'=>true]],JSON_THROW_ON_ERROR));
$service=new ReportScheduleService($db); $owner=['roles'=>['OWNER']]; $passed=0;
$list=$service->list($owner); if(count($list)!==1||$list[0]['id']!==$id) throw new RuntimeException('Configured schedule list failed'); $passed++;
$result=$service->run($owner,$id); if(($result['report']['status']??null)!=='SUCCESS'||($result['email']['status']??null)!=='DISABLED') throw new RuntimeException('Schedule run result failed');
$filename=$result['report']['filename']??''; $path=dirname(__DIR__).'/storage/generated-reports/'.$filename;
if(!is_file($path)||!str_starts_with((string)file_get_contents($path,false,null,0,5),'%PDF-')) throw new RuntimeException('Private report was not generated'); $passed++;
try{$service->list(['roles'=>['MANAGER']]);throw new RuntimeException('Manager accessed schedules');}catch(ApiException $error){if($error->status!==403)throw $error;} $passed++;
try{$service->run($owner,'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee');throw new RuntimeException('Unknown schedule ran');}catch(ApiException $error){if($error->status!==404)throw $error;} $passed++;
if(is_file($path)) unlink($path);
echo "php_report_schedule_integration_passed={$passed}\n";
