[CmdletBinding()]
param(
    [ValidateRange(1, 64)]
    [int]$WorkerCount = 8,

    [ValidateRange(30, 1800)]
    [int]$DockerReadyTimeoutSeconds = 600,

    [string]$LogPath = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$composeFile = Join-Path $projectRoot "infra\compose\docker-compose.yml"
$envFile = Join-Path $projectRoot ".env"

if (-not $LogPath) {
    $LogPath = Join-Path $PSScriptRoot "start-photostock.log"
}

function Write-StartupLog {
    param([string]$Message)

    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding utf8
    Write-Host $line
}

function Find-DockerExecutable {
    $knownPath = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path -LiteralPath $knownPath) {
        return $knownPath
    }

    $command = Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "docker.exe was not found."
}

function Test-DockerReady {
    param([string]$DockerExecutable)

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $DockerExecutable
    $startInfo.Arguments = 'version --format "{{.Server.Version}}"'
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo

    try {
        if (-not $process.Start()) {
            return $false
        }

        if (-not $process.WaitForExit(5000)) {
            $process.Kill()
            $process.WaitForExit()
            return $false
        }

        return $process.ExitCode -eq 0
    }
    finally {
        $process.Dispose()
    }
}

function Invoke-NativeCommand {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )

    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & $Executable @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    return [pscustomobject]@{
        Output = @($output)
        ExitCode = $exitCode
    }
}

try {
    Write-StartupLog "PhotoStockService startup started."

    if (-not (Test-Path -LiteralPath $composeFile)) {
        throw "Compose file was not found: $composeFile"
    }
    if (-not (Test-Path -LiteralPath $envFile)) {
        throw "Environment file was not found: $envFile"
    }

    $dockerExe = Find-DockerExecutable
    $desktopExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"

    if (-not (Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue)) {
        if (-not (Test-Path -LiteralPath $desktopExe)) {
            throw "Docker Desktop was not found: $desktopExe"
        }

        Write-StartupLog "Starting Docker Desktop."
        Start-Process -FilePath $desktopExe
    }

    $contextResult = Invoke-NativeCommand `
        -Executable $dockerExe `
        -Arguments @("context", "use", "desktop-linux")
    foreach ($line in $contextResult.Output) {
        Write-StartupLog "docker context: $line"
    }
    if ($contextResult.ExitCode -ne 0) {
        throw "Could not select the desktop-linux Docker context."
    }

    $deadline = (Get-Date).AddSeconds($DockerReadyTimeoutSeconds)
    $nextProgressLog = Get-Date

    while (-not (Test-DockerReady -DockerExecutable $dockerExe)) {
        if ((Get-Date) -ge $deadline) {
            throw "Docker Engine did not become ready within $DockerReadyTimeoutSeconds seconds."
        }

        if ((Get-Date) -ge $nextProgressLog) {
            Write-StartupLog "Waiting for Docker Engine."
            $nextProgressLog = (Get-Date).AddSeconds(30)
        }

        Start-Sleep -Seconds 5
    }

    Write-StartupLog "Docker Engine is ready."

    $composeArguments = @(
        "compose",
        "--env-file", $envFile,
        "-f", $composeFile,
        "up", "-d",
        "--scale", "worker=$WorkerCount"
    )

    $composeResult = Invoke-NativeCommand `
        -Executable $dockerExe `
        -Arguments $composeArguments
    foreach ($line in $composeResult.Output) {
        Write-StartupLog "compose: $line"
    }
    if ($composeResult.ExitCode -ne 0) {
        throw "Docker Compose startup failed with exit code $($composeResult.ExitCode)."
    }

    Write-StartupLog "PhotoStockService startup completed."
    exit 0
}
catch {
    Write-StartupLog "ERROR: $($_.Exception.Message)"
    exit 1
}
