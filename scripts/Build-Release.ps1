param(
    [switch]$SkipTests,
    [switch]$SkipInstaller,
    [switch]$SkipZip,
    [switch]$NoClean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$releaseRoot = Join-Path $projectRoot "release"
$pyInstallerWorkRoot = Join-Path $releaseRoot "_pyinstaller_work"
$pyInstallerDistRoot = Join-Path $releaseRoot "_pyinstaller_dist"
$portableRoot = Join-Path $releaseRoot "portable\OPERATOR_ASSIST"
$portableZipPath = Join-Path $releaseRoot "portable\OPERATOR_ASSIST-portable.zip"
$installerRoot = Join-Path $releaseRoot "installer"
$publishRoot = Join-Path $releaseRoot "publish"
$specPath = Join-Path $projectRoot "packaging\pyinstaller\operator_assist.spec"
$innoScriptPath = Join-Path $projectRoot "packaging\inno\OperatorAssist.iss"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message"
}

function Find-PythonConsole {
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
            }
        }
    }

    return $null
}

function Get-ProjectVersion {
    $pyprojectPath = Join-Path $projectRoot "pyproject.toml"
    $match = Select-String -Path $pyprojectPath -Pattern '^\s*version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($null -eq $match) {
        throw "Unable to resolve project version from $pyprojectPath"
    }

    return $match.Matches[0].Groups[1].Value
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

    Invoke-Python -PythonCommand $PythonCommand -Arguments @("-c", $Code)
}

function Remove-TreeSafe {
    param([string]$TargetPath)

    $resolvedTarget = [System.IO.Path]::GetFullPath($TargetPath)
    $resolvedReleaseRoot = [System.IO.Path]::GetFullPath($releaseRoot)
    if (-not $resolvedTarget.StartsWith($resolvedReleaseRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to delete outside release root: $resolvedTarget"
    }

    if (Test-Path -LiteralPath $resolvedTarget) {
        Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
    }
}

function Ensure-Directory {
    param([string]$TargetPath)

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
    }
}

function Find-InnoSetupCompiler {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    $resolved = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($null -ne $resolved) {
        return $resolved.Source
    }

    return $null
}

function Copy-ProjectFile {
    param(
        [string]$RelativeSource,
        [string]$RelativeDestination
    )

    $sourcePath = Join-Path $projectRoot $RelativeSource
    $destinationPath = Join-Path $portableRoot $RelativeDestination
    $destinationParent = Split-Path -Parent $destinationPath
    Ensure-Directory -TargetPath $destinationParent
    Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
}

function Write-Sha256Manifest {
    param(
        [string[]]$FilePaths,
        [string]$OutputPath
    )

    $lines = @()
    foreach ($filePath in $FilePaths) {
        if (-not (Test-Path -LiteralPath $filePath)) {
            continue
        }

        $hash = (Get-FileHash -LiteralPath $filePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $fileName = Split-Path -Leaf $filePath
        $lines += "$hash *$fileName"
    }

    if ($lines.Count -eq 0) {
        return
    }

    Set-Content -LiteralPath $OutputPath -Value $lines -Encoding ASCII
}

$python = Find-PythonConsole
if ($null -eq $python) {
    throw "No usable Python runtime was found."
}
$projectVersion = Get-ProjectVersion
$versionedPortableZipPath = Join-Path $publishRoot "OPERATOR_ASSIST-portable-$projectVersion.zip"
$versionedInstallerPath = Join-Path $publishRoot "OPERATOR_ASSIST-Setup-$projectVersion.exe"
$checksumsPath = Join-Path $publishRoot "SHA256SUMS.txt"

Write-Step "Checking build prerequisites"
$pythonVersion = & $python.FilePath @($python.ArgumentPrefix + @("-c", "import sys; print(sys.version.split()[0])"))
Write-Host "Python: $pythonVersion via $($python.FilePath)"
Write-Host "Project version: $projectVersion"
Invoke-PythonSnippet -PythonCommand $python -Code "import PyInstaller; print(PyInstaller.__version__)"

if (-not $SkipTests) {
    Write-Step "Running repository tests"
    Push-Location $projectRoot
    try {
        Invoke-Python -PythonCommand $python -Arguments @("-m", "unittest", "discover", "-s", "tests")
    } finally {
        Pop-Location
    }
}

if (-not $NoClean) {
    Write-Step "Cleaning previous release output"
    Remove-TreeSafe -TargetPath $pyInstallerWorkRoot
    Remove-TreeSafe -TargetPath $pyInstallerDistRoot
    Remove-TreeSafe -TargetPath (Join-Path $releaseRoot "portable")
    Remove-TreeSafe -TargetPath $installerRoot
    Remove-TreeSafe -TargetPath $publishRoot
}

Ensure-Directory -TargetPath $releaseRoot
Ensure-Directory -TargetPath (Join-Path $releaseRoot "portable")
Ensure-Directory -TargetPath $publishRoot

Write-Step "Building PyInstaller bundle"
Push-Location $projectRoot
try {
    Invoke-Python -PythonCommand $python -Arguments @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath", $pyInstallerDistRoot,
        "--workpath", $pyInstallerWorkRoot,
        $specPath
    )
} finally {
    Pop-Location
}

$builtBundleRoot = Join-Path $pyInstallerDistRoot "OPERATOR_ASSIST"
if (-not (Test-Path -LiteralPath $builtBundleRoot)) {
    throw "PyInstaller did not produce the expected bundle at $builtBundleRoot"
}

Write-Step "Assembling portable release layout"
Copy-Item -LiteralPath $builtBundleRoot -Destination $portableRoot -Recurse -Force
Ensure-Directory -TargetPath (Join-Path $portableRoot "data\models")
Ensure-Directory -TargetPath (Join-Path $portableRoot "data\logs")
Ensure-Directory -TargetPath (Join-Path $portableRoot "data\transcripts")
Ensure-Directory -TargetPath (Join-Path $portableRoot "config")
Ensure-Directory -TargetPath (Join-Path $portableRoot "support\scripts")

Copy-ProjectFile -RelativeSource "technical_terms.json" -RelativeDestination "config\technical_terms.json"
Copy-ProjectFile -RelativeSource "chatgpt_prompt_template.txt" -RelativeDestination "config\chatgpt_prompt_template.txt"
Copy-ProjectFile -RelativeSource "scripts\paste_to_chat_window.vbs" -RelativeDestination "support\scripts\paste_to_chat_window.vbs"

$modelsReadme = @(
    "Add one supported Vosk model directory here before first launch:",
    "- models\vosk-model-ru-0.42",
    "- models\vosk-model-ru-0.22",
    "- models\vosk-model-small-ru-0.22",
    "",
    "The release bundle intentionally does not ship large speech models.",
    "Whisper large-v3 cache is created under models\whisper-cache when precise mode is prepared."
)
Set-Content -LiteralPath (Join-Path $portableRoot "data\models\README.txt") -Value $modelsReadme -Encoding UTF8

$quickStart = @(
    "OPERATOR_ASSIST quick start",
    "",
    "1. Open .\data\models and place one supported Russian Vosk model there.",
    "2. Start OPERATOR_ASSIST.exe.",
    "3. If the app still reports a missing model, click 'Папка models' and then 'Проверить снова'.",
    "4. Logs are written to .\data\logs and saved transcripts to .\data\transcripts.",
    "5. For caller-only playback tests choose 'Только собеседник'; use 'Найти звук' while audio is playing.",
    "6. 'Точный (Whisper)' favors accuracy and can use CUDA; 'Стабильный (Vosk)' starts faster.",
    "",
    "Editable helper files:",
    "- .\config\technical_terms.json",
    "- .\config\chatgpt_prompt_template.txt"
)
Set-Content -LiteralPath (Join-Path $portableRoot "support\HOW_TO_START.txt") -Value $quickStart -Encoding UTF8

$commitHash = ""
try {
    $commitHash = (git -C $projectRoot rev-parse --short HEAD).Trim()
} catch {
    $commitHash = "unavailable"
}

$buildInfo = @(
    "OPERATOR_ASSIST release bundle",
    "Version: $projectVersion",
    "Built at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "Commit: $commitHash",
    "Python: $pythonVersion",
    "Entry point: OPERATOR_ASSIST.exe",
    "Notes:",
    "- Place a supported Vosk model under .\data\models before first launch.",
    "- Editable helper files live under .\config.",
    "- Support materials live under .\support."
)
Set-Content -LiteralPath (Join-Path $portableRoot "support\BUILD_INFO.txt") -Value $buildInfo -Encoding UTF8

$publishedAssets = @()

if (-not $SkipZip) {
    Write-Step "Creating portable zip archive"
    if (Test-Path -LiteralPath $portableZipPath) {
        Remove-Item -LiteralPath $portableZipPath -Force
    }
    Compress-Archive -Path (Join-Path $portableRoot "*") -DestinationPath $portableZipPath -Force
    Copy-Item -LiteralPath $portableZipPath -Destination $versionedPortableZipPath -Force
    $publishedAssets += $versionedPortableZipPath
}

if (-not $SkipInstaller) {
    Write-Step "Building installer"
    $innoCompiler = Find-InnoSetupCompiler
    if ($null -eq $innoCompiler) {
        Write-Warning "Inno Setup 6 compiler was not found. Portable build is ready, installer step skipped."
    } else {
        Ensure-Directory -TargetPath $installerRoot
        & $innoCompiler "/DMyAppVersion=$projectVersion" "/DMyOutputBaseFilename=OPERATOR_ASSIST-Setup-$projectVersion" $innoScriptPath
        if ($LASTEXITCODE -ne 0) {
            throw "Inno Setup compiler failed with exit code $LASTEXITCODE"
        }

        $builtInstallerPath = Join-Path $installerRoot "OPERATOR_ASSIST-Setup-$projectVersion.exe"
        if (-not (Test-Path -LiteralPath $builtInstallerPath)) {
            throw "Inno Setup did not produce the expected installer at $builtInstallerPath"
        }

        $stableInstallerPath = Join-Path $installerRoot "OPERATOR_ASSIST-Setup.exe"
        Copy-Item -LiteralPath $builtInstallerPath -Destination $stableInstallerPath -Force
        Copy-Item -LiteralPath $builtInstallerPath -Destination $versionedInstallerPath -Force
        $publishedAssets += $versionedInstallerPath
    }
}

Write-Sha256Manifest -FilePaths $publishedAssets -OutputPath $checksumsPath

Write-Step "Release build completed"
Write-Host "Portable bundle: $portableRoot"
if (-not $SkipZip) {
    Write-Host "Portable zip:    $portableZipPath"
}
if (-not $SkipInstaller) {
    Write-Host "Installer dir:   $installerRoot"
}
if (Test-Path -LiteralPath $publishRoot) {
    Write-Host "Publish assets:  $publishRoot"
}
