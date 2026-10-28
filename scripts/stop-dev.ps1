[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtimeRoot = Join-Path $projectRoot '.runtime'
$statePath = Join-Path $runtimeRoot 'processes.json'
$composePath = Join-Path $projectRoot 'compose.yaml'

function Get-DescendantProcessIds([int]$ParentId) {
    $all = @(Get-CimInstance Win32_Process)
    $result = [System.Collections.Generic.List[int]]::new()
    $queue = [System.Collections.Generic.Queue[int]]::new()
    $queue.Enqueue($ParentId)
    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        foreach ($child in $all | Where-Object ParentProcessId -eq $current) {
            $result.Add([int]$child.ProcessId)
            $queue.Enqueue([int]$child.ProcessId)
        }
    }
    return @($result)
}

if (Test-Path -LiteralPath $statePath -PathType Leaf) {
    $records = @(Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json)
    foreach ($record in $records) {
        $process = Get-Process -Id $record.Pid -ErrorAction SilentlyContinue
        if (-not $process) { continue }
        $expectedStart = ([DateTimeOffset]$record.StartTimeUtc).UtcDateTime
        $actualStart = $process.StartTime.ToUniversalTime()
        $expectedPath = [IO.Path]::GetFullPath($record.ExecutablePath)
        $actualPath = [IO.Path]::GetFullPath($process.Path)
        if ([Math]::Abs(($actualStart - $expectedStart).TotalSeconds) -ge 2 -or $actualPath -ne $expectedPath) {
            Write-Warning "Skipping PID $($record.Pid): path or start time does not match recorded process $($record.Name)."
            continue
        }

        $descendants = @(Get-DescendantProcessIds ([int]$record.Pid))
        [array]::Reverse($descendants)
        foreach ($processId in $descendants) {
            Stop-Process -Id $processId -ErrorAction SilentlyContinue
        }
        Stop-Process -Id $record.Pid -ErrorAction SilentlyContinue
        Write-Host "Stopped $($record.Name) (PID $($record.Pid))."
    }
    Set-Content -LiteralPath $statePath -Value '[]' -Encoding utf8
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        docker compose --project-name investment-thesis-arena --file $composePath stop postgres redis
        if ($LASTEXITCODE -ne 0) { throw 'Failed to stop the investment-thesis-arena dependency containers.' }
    } else {
        Write-Warning 'Docker is unavailable; application processes stopped, but containers could not be stopped.'
    }
}

Write-Host 'Development runtime stopped. The PostgreSQL named volume was preserved.'

