param(
    [switch]$NoVenv,
    [switch]$SkipPackageInstall,
    [switch]$SkipEnvironmentCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$venvRoot = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$requirementsPath = Join-Path $projectRoot "requirements.txt"
$checkScriptPath = Join-Path $projectRoot "scripts\Check-Environment.ps1"

function Write-Step {
    param([string]$Message)

    Write-Host ""
    Write-Host "==> $Message"
}

function Find-PythonConsole {
    $projectCandidates = @(
        $venvPython
    )

    foreach ($candidatePath in $projectCandidates) {
        if ($candidatePath -and (Test-Path -LiteralPath $candidatePath)) {
            return @{
                FilePath = $candidatePath
                ArgumentPrefix = @()
                Source = "project-venv"
            }
        }
    }

    $candidatePaths = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:ProgramFiles "Python310\python.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Python310\python.exe")
    )

    foreach ($candidatePath in $candidatePaths) {
        if ($candidatePath -and (Test-Path -LiteralPath $candidatePath)) {
            return @{
                FilePath = $candidatePath
                ArgumentPrefix = @()
                Source = "system-path"
            }
        }
    }

    $commands = @(
        @{ Name = "py.exe"; Arguments = @("-3.10") }
        @{ Name = "py.exe"; Arguments = @("-3") }
        @{ Name = "py.exe"; Arguments = @() }
        @{ Name = "python.exe"; Arguments = @() }
    )

    foreach ($command in $commands) {
        $resolved = Get-Command $command.Name -ErrorAction SilentlyContinue
        if ($null -ne $resolved) {
            return @{
                FilePath = $resolved.Source
                ArgumentPrefix = $command.Arguments
                Source = "launcher"
            }
        }
    }

    return $null
}

function Invoke-Python {
    param(
        [hashtable]$PythonCommand,
        [string[]]$Arguments
    )

    $resolvedArguments = @($PythonCommand.ArgumentPrefix + $Arguments)
    & $PythonCommand.FilePath @resolvedArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE"
    }
}

function Invoke-PythonSnippet {
    param(
        [hashtable]$PythonCommand,
        [string]$Code
    )

    $resolvedArguments = @($PythonCommand.ArgumentPrefix + @("-c", $Code))
    & $PythonCommand.FilePath @resolvedArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python snippet failed with exit code $LASTEXITCODE"
    }
}

function Ensure-Directory {
    param([string]$TargetPath)

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
    }
}

function Get-PythonVersion {
    param([hashtable]$PythonCommand)

    $versionText = Invoke-PythonSnippet -PythonCommand $PythonCommand -Code "import sys; print(sys.version.split()[0])"
    return [version]$versionText.Trim()
}

Write-Step "Preparing source installation from Git"
Write-Host "Project root: $projectRoot"

$python = Find-PythonConsole
if ($null -eq $python) {
    throw "No usable Python launcher was found. Install Python 3.10+ first."
}

$pythonVersion = Get-PythonVersion -PythonCommand $python
if ($pythonVersion -lt [version]"3.10") {
    throw "Python 3.10+ is required. Detected: $pythonVersion"
}

Write-Host "Using Python $pythonVersion via $($python.FilePath)"

if (-not $NoVenv) {
    Write-Step "Preparing project-local virtual environment"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Invoke-Python -PythonCommand $python -Arguments @("-m", "venv", $venvRoot)
        Write-Host "Created virtual environment: $venvRoot"
    } else {
        Write-Host "Virtual environment already exists: $venvRoot"
    }

    $python = @{
        FilePath = $venvPython
        ArgumentPrefix = @()
        Source = "project-venv"
    }
    $pythonVersion = Get-PythonVersion -PythonCommand $python
    Write-Host "Active environment Python: $pythonVersion via $($python.FilePath)"
} else {
    Write-Host "Virtual environment step skipped by request."
}

if (-not $SkipPackageInstall) {
    Write-Step "Installing Python dependencies"
    Invoke-Python -PythonCommand $python -Arguments @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Python -PythonCommand $python -Arguments @("-m", "pip", "install", "-r", $requirementsPath)
} else {
    Write-Host "Package installation skipped by request."
}

Write-Step "Ensuring local runtime folders"
Ensure-Directory -TargetPath (Join-Path $projectRoot "models")
Ensure-Directory -TargetPath (Join-Path $projectRoot "logs")
Ensure-Directory -TargetPath (Join-Path $projectRoot "transcripts")
Write-Host "Prepared: models, logs, transcripts"

if (-not $SkipEnvironmentCheck) {
    Write-Step "Running environment check"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $checkScriptPath
    if ($LASTEXITCODE -ne 0) {
        throw "Environment check failed with exit code $LASTEXITCODE"
    }
} else {
    Write-Host "Environment check skipped by request."
}

Write-Step "Next steps"
Write-Host "1. Place one supported Russian Vosk model into: $projectRoot\models"
Write-Host "2. Start the app with: Run-Operator-Assist.cmd"
Write-Host "3. If the app still shows readiness warnings, use the in-app re-check button after placing the model."
