param(
    [switch]$Strict
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))

function Write-CheckResult {
    param(
        [ValidateSet("OK", "WARN", "FAIL")]
        [string]$Level,
        [string]$Label,
        [string]$Details
    )

    Write-Host ("[{0}] {1} - {2}" -f $Level, $Label, $Details)
}

function Find-PythonConsole {
    $projectCandidates = @(
        (Join-Path $projectRoot ".venv\Scripts\python.exe")
    )

    foreach ($candidatePath in $projectCandidates) {
        if ($candidatePath -and (Test-Path -LiteralPath $candidatePath)) {
            return @{
                FilePath = $candidatePath
                ArgumentPrefix = @()
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
        if (Test-Path -LiteralPath $candidatePath) {
            return @{
                FilePath = $candidatePath
                ArgumentPrefix = @()
            }
        }
    }

    $commands = @(
        @{ Name = "py.exe"; Arguments = @("-3.10") }
        @{ Name = "py.exe"; Arguments = @() }
        @{ Name = "python.exe"; Arguments = @() }
    )

    foreach ($command in $commands) {
        $resolved = Get-Command $command.Name -ErrorAction SilentlyContinue
        if ($null -ne $resolved) {
            return @{
                FilePath = $resolved.Source
                ArgumentPrefix = $command.Arguments
            }
        }
    }

    return $null
}

function Invoke-PythonSnippet {
    param(
        [hashtable]$PythonCommand,
        [string]$Code
    )

    $arguments = @($PythonCommand.ArgumentPrefix + @("-c", $Code))
    & $PythonCommand.FilePath @arguments
}

$failed = $false

Write-Host ""
Write-Host "OPERATOR_ASSIST environment check"
Write-Host "Project root: $projectRoot"
Write-Host ""

$python = Find-PythonConsole
if ($null -eq $python) {
    Write-CheckResult -Level "FAIL" -Label "Python" -Details "No usable Python launcher was found."
    $failed = $true
} else {
    $version = Invoke-PythonSnippet -PythonCommand $python -Code "import sys; print(sys.version.split()[0])"
    Write-CheckResult -Level "OK" -Label "Python" -Details ("{0} via {1}" -f $version, $python.FilePath)
}

$requiredFiles = @(
    "operator_assist.py",
    "operator_assist_chat_bridge_v5_base.py",
    "operator_assist_runtime\base_runtime.py",
    "backups\operator_assist_chat_bridge_base.py",
    "technical_terms.json",
    "scripts\Serve-App-Tcp.ps1",
    "scripts\Setup-From-Git.ps1",
    "Run-Operator-Assist.cmd",
    "Run-Operator-Assist.ps1",
    "Setup-From-Git.cmd"
)

foreach ($relativePath in $requiredFiles) {
    $fullPath = Join-Path $projectRoot $relativePath
    if (Test-Path -LiteralPath $fullPath) {
        Write-CheckResult -Level "OK" -Label "File" -Details $relativePath
    } else {
        Write-CheckResult -Level "FAIL" -Label "File" -Details ("Missing {0}" -f $relativePath)
        $failed = $true
    }
}

$modelCandidates = @(
    "models\vosk-model-ru-0.42",
    "models\vosk-model-ru-0.22",
    "models\vosk-model-small-ru-0.22"
)

$presentModels = @()
foreach ($relativeModel in $modelCandidates) {
    $fullPath = Join-Path $projectRoot $relativeModel
    if (Test-Path -LiteralPath $fullPath -PathType Container) {
        $presentModels += $relativeModel
    }
}

if ($presentModels.Count -gt 0) {
    Write-CheckResult -Level "OK" -Label "Vosk model" -Details ($presentModels -join ", ")
} else {
    Write-CheckResult -Level "WARN" -Label "Vosk model" -Details "No supported local model directory was found."
}

$vendoredPackages = @(
    "vendor\numpy",
    "vendor\soundcard",
    "vendor\cffi"
)

foreach ($relativePath in $vendoredPackages) {
    $fullPath = Join-Path $projectRoot $relativePath
    if (Test-Path -LiteralPath $fullPath) {
        Write-CheckResult -Level "OK" -Label "Vendored package" -Details $relativePath
    } else {
        Write-CheckResult -Level "WARN" -Label "Vendored package" -Details ("Missing {0}" -f $relativePath)
    }
}

if ($null -ne $python) {
    $pythonPackages = @(
        "vosk",
        "sounddevice",
        "websockets"
    )

    foreach ($package in $pythonPackages) {
        try {
            $version = Invoke-PythonSnippet -PythonCommand $python -Code "import importlib.metadata as m; print(m.version('$package'))"
            Write-CheckResult -Level "OK" -Label "Package" -Details ("{0}=={1}" -f $package, $version)
        } catch {
            Write-CheckResult -Level "FAIL" -Label "Package" -Details ("{0} is not installed in the active Python environment." -f $package)
            $failed = $true
        }
    }
}

Write-Host ""
if ($failed) {
    Write-Host "Environment check finished with failures."
    if ($Strict) {
        exit 1
    }
} else {
    Write-Host "Environment check finished successfully."
}
