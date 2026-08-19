param(
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$rootPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverScript = Join-Path $rootPath "scripts\\Serve-App-Tcp.ps1"
$url = "http://127.0.0.1:$Port/"
$healthUrl = "${url}health"

function Test-VoiceNotesServer {
    param([string]$Uri)

    try {
        $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Get-BrowserPath {
    $candidates = @(
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        (Join-Path $env:LOCALAPPDATA "Programs\\Opera\\opera.exe"),
        (Join-Path $env:ProgramFiles "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "BraveSoftware\\Brave-Browser\\Application\\brave.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    return $null
}

if (-not (Test-VoiceNotesServer -Uri $healthUrl)) {
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $serverScript,
            "-Port", $Port
        ) `
        -WindowStyle Hidden | Out-Null

    for ($i = 0; $i -lt 40; $i++) {
        if (Test-VoiceNotesServer -Uri $healthUrl) {
            break
        }

        Start-Sleep -Milliseconds 250
    }
}

if (-not (Test-VoiceNotesServer -Uri $healthUrl)) {
    throw "Voice Notes server did not start on $url"
}

$browserPath = Get-BrowserPath

if ($browserPath) {
    Start-Process -FilePath $browserPath -ArgumentList @("--new-window", "--app=$url") | Out-Null
} else {
    Start-Process $url | Out-Null
}
