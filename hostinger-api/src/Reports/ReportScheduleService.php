<?php
declare(strict_types=1);

namespace Anicraze\Reports;

use Anicraze\Config\Environment;
use Anicraze\Documents\PdfService;
use Anicraze\Http\ApiException;
use PDO;

final class ReportScheduleService
{
    public function __construct(private readonly PDO $database) {}

    public function list(array $actor): array { $this->owner($actor); return $this->configured(); }

    public function run(array $actor, string $id): array
    {
        $this->owner($actor); $schedule = null;
        foreach ($this->configured() as $candidate) if (hash_equals($candidate['id'], $id)) { $schedule=$candidate; break; }
        if ($schedule === null || !$schedule['is_active']) throw new ApiException(404, 'REPORT_SCHEDULE_NOT_FOUND', 'Report schedule not found');
        $bytes = (new PdfService($this->database))->report($actor, $schedule['report_type'], ['preset'=>'THIS_WEEK']);
        $directory = dirname(__DIR__, 2) . '/storage/generated-reports';
        if (!is_dir($directory) && !mkdir($directory, 0700, true) && !is_dir($directory)) throw new \RuntimeException('Private report storage is unavailable');
        $filename = 'owner-report-' . gmdate('Ymd-His') . '-' . bin2hex(random_bytes(6)) . '.pdf';
        $path = $directory . '/' . $filename;
        if (file_put_contents($path, $bytes, LOCK_EX) !== strlen($bytes) || !chmod($path, 0600)) throw new \RuntimeException('Private report could not be stored');
        $email = ['status'=>'DISABLED','attempts'=>[]];
        if (Environment::optional('REPORT_EMAIL_ENABLED', '0') === '1') $email = $this->mail($schedule, $path);
        return ['report'=>['status'=>'SUCCESS','filename'=>$filename], 'email'=>$email];
    }

    private function configured(): array
    {
        try { $items = json_decode(Environment::optional('REPORT_SCHEDULES_JSON', '[]'), true, 32, JSON_THROW_ON_ERROR); }
        catch (\JsonException) { throw new \RuntimeException('REPORT_SCHEDULES_JSON is invalid'); }
        if (!is_array($items) || count($items)>20) throw new \RuntimeException('REPORT_SCHEDULES_JSON must be a list of at most 20 schedules');
        return array_map(function(mixed $item): array {
            if (!is_array($item) || !is_string($item['id']??null) || preg_match('/^[0-9a-fA-F-]{36}$/D',$item['id'])!==1
                || !is_string($item['name']??null) || trim($item['name'])==='' || strlen($item['name'])>120
                || preg_match('/[\x00-\x1F\x7F]/', $item['name']) === 1
                || !in_array($item['report_type']??null,['sales_summary','inventory_summary','finance_summary','finance_shop-profit-loss'],true)
                || ($item['format']??'PDF')!=='PDF' || !in_array($item['frequency']??null,['DAILY','WEEKLY','MONTHLY'],true)
                || !is_string($item['timezone']??null) || !in_array($item['timezone'],timezone_identifiers_list(),true)
                || !is_array($item['recipient_emails_json']??null) || count($item['recipient_emails_json'])>20) throw new \RuntimeException('Report schedule configuration is invalid');
            foreach ($item['recipient_emails_json'] as $email) if (!is_string($email)||!filter_var($email,FILTER_VALIDATE_EMAIL)) throw new \RuntimeException('Report schedule recipient is invalid');
            return ['id'=>strtolower($item['id']),'name'=>trim($item['name']),'report_type'=>$item['report_type'],'format'=>'PDF',
                'frequency'=>$item['frequency'],'timezone'=>$item['timezone'],'recipient_emails_json'=>array_values($item['recipient_emails_json']),
                'is_active'=>(bool)($item['is_active']??true),'last_run_at'=>null,'next_run_at'=>null];
        }, array_values($items));
    }

    private function mail(array $schedule, string $path): array
    {
        $from=Environment::required('MAIL_FROM'); if(!filter_var($from,FILTER_VALIDATE_EMAIL)) throw new \RuntimeException('MAIL_FROM is invalid');
        $attempts=[];
        foreach($schedule['recipient_emails_json'] as $recipient){$boundary='anicraze-'.bin2hex(random_bytes(12));$headers=['From: ANICRAZE ERP <'.$from.'>','MIME-Version: 1.0','Content-Type: multipart/mixed; boundary="'.$boundary.'"'];$attachment=chunk_split(base64_encode((string)file_get_contents($path)));$body='--'.$boundary."\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\nYour scheduled ANICRAZE ERP report is attached.\r\n".'--'.$boundary."\r\nContent-Type: application/pdf; name=report.pdf\r\nContent-Transfer-Encoding: base64\r\nContent-Disposition: attachment; filename=report.pdf\r\n\r\n".$attachment.'--'.$boundary."--\r\n";$sent=mail($recipient,$schedule['name'],$body,implode("\r\n",$headers));$attempts[]=['recipient'=>$recipient,'status'=>$sent?'SENT':'FAILED'];}
        return ['status'=>array_filter($attempts,static fn(array $a):bool=>$a['status']!=='SENT')===[]?'SENT':'FAILED','attempts'=>$attempts];
    }

    private function owner(array $actor): void { if(!in_array('OWNER',$actor['roles']??[],true)) throw new ApiException(403,'AUTH_FORBIDDEN','Owner report automation access is required'); }
}
