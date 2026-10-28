[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$DependenciesOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$runtimeRoot = Join-Path $projectRoot '.runtime'
$statePath = Join-Path $runtimeRoot 'processes.json'
$composePath = Join-Path $projectRoot 'compose.yaml'
$dockerDesktop = 'E:\Docker\DockerDesktop\Docker Desktop.exe'

function Import-DotEnv([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        $parts = $trimmed.Split('=', 2)
        if ($parts.Count -ne 2) { continue }
        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if ($name -match '^[A-Za-z_][A-Za-z0-9_]*$') {
            [Environment]::SetEnvironmentVariable($name, $value, 'Process')
        }
    }
}

function Set-DefaultEnvironment([string]$Name, [string]$Value) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($Name, 'Process'))) {
        [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
    }
}

function Test-PortListening([int]$Port) {
    return $null -ne (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Assert-PortAvailable([int]$Port, [string]$Purpose) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) { return }
    $owners = ($listeners | Select-Object -ExpandProperty OwningProcess -Unique) -join ', '
    throw "Port $Port for $Purpose is already in use (PID(s): $owners). Stop the conflict or configure another port."
}

function Wait-DockerEngine {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'docker.exe was not found on PATH.' }
    docker info --format '{{.ServerVersion}}' *> $null
    if ($LASTEXITCODE -eq 0) { return }
    if (-not (Test-Path -LiteralPath $dockerDesktop -PathType Leaf)) {
        throw "Docker is unavailable and Docker Desktop was not found at $dockerDesktop."
    }
    if (-not (Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
    }
    $deadline = (Get-Date).AddSeconds(60)
    do {
        Start-Sleep -Seconds 2
        docker info --format '{{.ServerVersion}}' *> $null
        if ($LASTEXITCODE -eq 0) { return }
    } while ((Get-Date) -lt $deadline)
    throw 'Docker Desktop did not become ready within 60 seconds.'
}

function Read-ProcessState {
    if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) { return @() }
    try { return @(Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json) }
    catch { throw "Cannot parse runtime state at $statePath. Inspect it before retrying." }
}

function Save-ProcessState([object[]]$Records) {
    $json = if ($Records.Count -eq 0) { '[]' } else { $Records | ConvertTo-Json -Depth 4 }
    Set-Content -LiteralPath $statePath -Value $json -Encoding utf8
}

function Test-ManagedProcess([object]$Record) {
    $process = Get-Process -Id $Record.Pid -ErrorAction SilentlyContinue
    if (-not $process) { return $false }
    try {
        $actual = $process.StartTime.ToUniversalTime()
        $expected = ([DateTimeOffset]$Record.StartTimeUtc).UtcDateTime
        return [Math]::Abs(($actual - $expected).TotalSeconds) -lt 2 -and
            [IO.Path]::GetFullPath($process.Path) -eq [IO.Path]::GetFullPath($Record.ExecutablePath)
    } catch {
        Write-Verbose "Managed process validation failed for $($Record.Name) PID $($Record.Pid): $($_.Exception.Message)"
        return $false
    }
}

function Start-TrackedProcess(
    [string]$Name, [string]$FilePath, [string[]]$ArgumentList, [string]$WorkingDirectory
) {
    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimeRoot "$Name.stdout.log") `
        -RedirectStandardError (Join-Path $runtimeRoot "$Name.stderr.log")
    return [pscustomobject]@{
        Name = $Name
        Pid = $process.Id
        StartTimeUtc = $process.StartTime.ToUniversalTime().ToString('o')
        ExecutablePath = $process.Path
        WorkingDirectory = $WorkingDirectory
    }
}

Import-DotEnv (Join-Path $projectRoot '.env')
Set-DefaultEnvironment 'POSTGRES_USER' 'arena'
Set-DefaultEnvironment 'POSTGRES_PASSWORD' 'arena_local'
Set-DefaultEnvironment 'POSTGRES_DB' 'arena'
Set-DefaultEnvironment 'POSTGRES_PORT' '55433'
Set-DefaultEnvironment 'REDIS_PORT' '56379'
Set-DefaultEnvironment 'ARENA_DATABASE_URL' 'postgresql+psycopg://arena:arena_local@127.0.0.1:55433/arena'
Set-DefaultEnvironment 'ARENA_REDIS_URL' 'redis://127.0.0.1:56379/0'
Set-DefaultEnvironment 'API_HOST' '127.0.0.1'
Set-DefaultEnvironment 'API_PORT' '8000'
Set-DefaultEnvironment 'FRONTEND_HOST' '127.0.0.1'
Set-DefaultEnvironment 'FRONTEND_PORT' '5173'
Set-DefaultEnvironment 'API_PROXY_TARGET' 'http://127.0.0.1:8000'

New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
Wait-DockerEngine

$runningServices = @(docker compose --project-name investment-thesis-arena --file $composePath ps --services --filter status=running)
if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect the investment-thesis-arena Compose project.' }
if ('postgres' -notin $runningServices) { Assert-PortAvailable ([int]$env:POSTGRES_PORT) 'PostgreSQL' }
if ('redis' -notin $runningServices) { Assert-PortAvailable ([int]$env:REDIS_PORT) 'Redis' }
docker compose --project-name investment-thesis-arena --file $composePath up --detach --wait postgres redis
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL or Redis failed to start.' }
if ($DependenciesOnly) {
    Write-Host "Dependencies ready: PostgreSQL 127.0.0.1:$($env:POSTGRES_PORT), Redis 127.0.0.1:$($env:REDIS_PORT)"
    exit 0
}

$priorState = Read-ProcessState
$active = @($priorState | Where-Object { Test-ManagedProcess $_ })
$activeNames = @($active | ForEach-Object { $_.Name })
$allRunning = @('api', 'worker', 'frontend') | ForEach-Object { $_ -in $activeNames }
if ($false -notin $allRunning) {
    Write-Host 'Development runtime is already running; no host processes were duplicated.'
    exit 0
}

$uv = (Get-Command uv -ErrorAction Stop).Source
if (-not $SkipInstall -and $active.Count -eq 0) {
    Push-Location $backendRoot
    try { & $uv sync --frozen --group dev; $syncExit = $LASTEXITCODE }
    finally { Pop-Location }
    if ($syncExit -ne 0) { throw 'Backend dependency installation failed.' }
    & (Get-Command npm.cmd -ErrorAction Stop).Source ci --prefix $frontendRoot
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
} elseif ($active.Count -gt 0 -and -not $SkipInstall) {
    Write-Host 'Existing managed processes detected; dependency synchronization is skipped for this repair start.'
}

$python = Join-Path $backendRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'backend/.venv is missing. Run start-dev.ps1 without -SkipInstall first.'
}
Push-Location $backendRoot
try { & $python -m alembic upgrade head; $migrationExit = $LASTEXITCODE }
finally { Pop-Location }
if ($migrationExit -ne 0) { throw 'Database migration failed.' }

$newState = [System.Collections.Generic.List[object]]::new()
foreach ($record in $active) { $newState.Add($record) }
if ('api' -notin $activeNames) {
    Assert-PortAvailable ([int]$env:API_PORT) 'API'
    $newState.Add((Start-TrackedProcess 'api' $python @('-m', 'uvicorn', 'app.main:app', '--host', $env:API_HOST, '--port', $env:API_PORT) $backendRoot))
    Save-ProcessState @($newState)
}
if ('worker' -notin $activeNames) {
    $newState.Add((Start-TrackedProcess 'worker' $python @('-m', 'app.worker') $backendRoot))
    Save-ProcessState @($newState)
}
if ('frontend' -notin $activeNames) {
    Assert-PortAvailable ([int]$env:FRONTEND_PORT) 'frontend'
    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    $newState.Add((Start-TrackedProcess 'frontend' $npm @('run', 'dev', '--', '--host', $env:FRONTEND_HOST, '--port', $env:FRONTEND_PORT, '--strictPort') $frontendRoot))
    Save-ProcessState @($newState)
}

$deadline = (Get-Date).AddSeconds(30)
do {
    if ((Test-PortListening ([int]$env:API_PORT)) -and (Test-PortListening ([int]$env:FRONTEND_PORT))) { break }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $deadline)
if (-not (Test-PortListening ([int]$env:API_PORT))) {
    throw "API did not listen on port $($env:API_PORT). See .runtime/api.stderr.log."
}
if (-not (Test-PortListening ([int]$env:FRONTEND_PORT))) {
    throw "Frontend did not listen on port $($env:FRONTEND_PORT). See .runtime/frontend.stderr.log."
}
Write-Host "Development runtime ready: API http://$($env:API_HOST):$($env:API_PORT), frontend http://$($env:FRONTEND_HOST):$($env:FRONTEND_PORT)"

