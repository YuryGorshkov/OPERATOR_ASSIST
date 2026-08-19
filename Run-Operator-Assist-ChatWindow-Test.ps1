Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$targetScript = Join-Path $scriptDir "operator_assist_chat_window_test.py"

function Find-PythonLauncher {
    $candidatePaths = @(
        (Join-Path $scriptDir ".venv\Scripts\pythonw.exe"),
        (Join-Path $scriptDir ".venv\Scripts\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\pythonw.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\pythonw.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\pythonw.exe"),
        (Join-Path $env:ProgramFiles "Python310\pythonw.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Python310\pythonw.exe")
    )

    foreach ($candidatePath in $candidatePaths) {
        if (Test-Path -LiteralPath $candidatePath) {
            return @{
                FilePath = $candidatePath
                ArgumentList = @()
            }
        }
    }

    $commands = @(
        @{ Name = "pythonw.exe"; Arguments = @() }
        @{ Name = "py.exe"; Arguments = @("-3.10") }
        @{ Name = "py.exe"; Arguments = @() }
        @{ Name = "python.exe"; Arguments = @() }
    )

    foreach ($command in $commands) {
        $resolved = Get-Command $command.Name -ErrorAction SilentlyContinue
        if ($null -ne $resolved) {
            return @{
                FilePath = $resolved.Source
                ArgumentList = $command.Arguments
            }
        }
    }

    return $null
}

if (-not (Test-Path -LiteralPath $targetScript -PathType Leaf)) {
    throw "Main script was not found: $targetScript"
}

$launcher = Find-PythonLauncher
if ($null -eq $launcher) {
    throw "Python launcher was not found. Install Python 3.10+ or run Setup-From-Git.cmd first."
}

$argumentList = @($launcher.ArgumentList + @($targetScript))
Start-Process -FilePath $launcher.FilePath -ArgumentList $argumentList | Out-Null
