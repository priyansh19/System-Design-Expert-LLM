$ErrorActionPreference = 'SilentlyContinue'
$logPath = 'C:\Users\Priyansh\Desktop\SystemDesignExpertLLM\logs\run_pipeline.log'

function Get-PipelineProc {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*run_pipeline.py*' }
}

function Is-Complete {
    if (-not (Test-Path $logPath)) { return $false }
    $tail = Get-Content $logPath -Tail 5 -ErrorAction SilentlyContinue
    return ($tail -join "`n") -match 'DPO done:'
}

while ($true) {
    $procs = Get-PipelineProc
    $ts = Get-Date -Format 'HH:mm:ss'

    if ($procs) {
        Write-Host "[$ts] alive (pid $($procs[0].ProcessId)), $($procs.Count) proc(s)"
        Get-Content $logPath -Tail 4
        Start-Sleep -Seconds 90
        continue
    }

    if (Is-Complete) {
        Write-Host "PIPELINE_DONE at $ts"
    } else {
        Write-Host "PIPELINE_GONE_INCOMPLETE at $ts -- process exited without a completion marker, needs manual relaunch"
    }
    break
}

Write-Host '--- FINAL LOG (last 100 lines) ---'
Get-Content $logPath -Tail 100
