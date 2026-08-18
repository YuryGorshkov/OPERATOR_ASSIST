param(
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$appRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\\app"))
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)

function Get-ContentType {
    param([string]$Path)

    switch ([System.IO.Path]::GetExtension($Path).ToLowerInvariant()) {
        ".html" { "text/html; charset=utf-8" }
        ".css"  { "text/css; charset=utf-8" }
        ".js"   { "application/javascript; charset=utf-8" }
        ".json" { "application/json; charset=utf-8" }
        ".svg"  { "image/svg+xml" }
        ".png"  { "image/png" }
        ".jpg"  { "image/jpeg" }
        ".jpeg" { "image/jpeg" }
        ".ico"  { "image/x-icon" }
        ".txt"  { "text/plain; charset=utf-8" }
        default { "application/octet-stream" }
    }
}

function Send-HttpResponse {
    param(
        [System.IO.Stream]$Stream,
        [int]$StatusCode,
        [string]$StatusText,
        [byte[]]$Body,
        [string]$ContentType
    )

    $headerText = @(
        "HTTP/1.1 $StatusCode $StatusText",
        "Content-Type: $ContentType",
        "Content-Length: $($Body.Length)",
        "Connection: close",
        ""
        ""
    ) -join "`r`n"

    $headerBytes = [System.Text.Encoding]::ASCII.GetBytes($headerText)
    $Stream.Write($headerBytes, 0, $headerBytes.Length)
    if ($Body.Length -gt 0) {
        $Stream.Write($Body, 0, $Body.Length)
    }
}

function Send-TextResponse {
    param(
        [System.IO.Stream]$Stream,
        [int]$StatusCode,
        [string]$StatusText,
        [string]$Text,
        [string]$ContentType = "text/plain; charset=utf-8"
    )

    $body = [System.Text.Encoding]::UTF8.GetBytes($Text)
    Send-HttpResponse -Stream $Stream -StatusCode $StatusCode -StatusText $StatusText -Body $body -ContentType $ContentType
}

$listener.Start()

try {
    while ($true) {
        $client = $listener.AcceptTcpClient()

        try {
            $stream = $client.GetStream()
            $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::ASCII, $false, 4096, $true)
            $requestLine = $reader.ReadLine()

            if ([string]::IsNullOrWhiteSpace($requestLine)) {
                continue
            }

            while ($true) {
                $headerLine = $reader.ReadLine()
                if ($null -eq $headerLine -or $headerLine -eq "") {
                    break
                }
            }

            $parts = $requestLine.Split(" ")
            if ($parts.Length -lt 2) {
                Send-TextResponse -Stream $stream -StatusCode 400 -StatusText "Bad Request" -Text "Bad request"
                continue
            }

            $requestPath = [Uri]::UnescapeDataString($parts[1].Split("?")[0])

            if ($requestPath -eq "/health") {
                Send-TextResponse -Stream $stream -StatusCode 200 -StatusText "OK" -Text "ok"
                continue
            }

            $relativePath = if ($requestPath -eq "/") { "index.html" } else { $requestPath.TrimStart("/") }
            $relativePath = $relativePath -replace "/", "\\"
            $fullPath = [System.IO.Path]::GetFullPath((Join-Path $appRoot $relativePath))

            if (-not $fullPath.StartsWith($appRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                Send-TextResponse -Stream $stream -StatusCode 403 -StatusText "Forbidden" -Text "Forbidden"
                continue
            }

            if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
                Send-TextResponse -Stream $stream -StatusCode 404 -StatusText "Not Found" -Text "Not found"
                continue
            }

            $body = [System.IO.File]::ReadAllBytes($fullPath)
            $contentType = Get-ContentType -Path $fullPath
            Send-HttpResponse -Stream $stream -StatusCode 200 -StatusText "OK" -Body $body -ContentType $contentType
        } catch {
            if ($stream) {
                Send-TextResponse -Stream $stream -StatusCode 500 -StatusText "Server Error" -Text "Server error"
            }
        } finally {
            if ($reader) {
                $reader.Dispose()
            }
            if ($stream) {
                $stream.Dispose()
            }
            $client.Close()
        }
    }
} finally {
    $listener.Stop()
}
