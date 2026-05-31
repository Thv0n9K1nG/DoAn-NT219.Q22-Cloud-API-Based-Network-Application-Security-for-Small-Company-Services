param(
    [string]$GatewayUrl = "https://host.docker.internal:8443",
    [string]$Image = "ghcr.io/zaproxy/zaproxy:stable",
    [int]$SpecPort = 18090
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$reportsDir = Join-Path $repoRoot "tests\reports"
$openApiPath = Join-Path $reportsDir "zap-openapi.json"

New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

if (Get-NetTCPConnection -LocalPort $SpecPort -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $SpecPort is already in use. Stop the existing process or pass -SpecPort with another free port."
}

python (Join-Path $repoRoot "scripts\generate-zap-openapi.py") `
    --server-url $GatewayUrl `
    --output $openApiPath

$server = Start-Process `
    -FilePath python `
    -ArgumentList @("-m", "http.server", "$SpecPort", "--bind", "127.0.0.1", "--directory", $reportsDir) `
    -PassThru `
    -WindowStyle Hidden

try {
    Start-Sleep -Seconds 2
    $specUrl = "http://host.docker.internal:$SpecPort/zap-openapi.json"
    Write-Host "Running ZAP against OpenAPI spec: $specUrl"
    Write-Host "Gateway target declared in spec: $GatewayUrl"

    docker run --rm `
        -v "${reportsDir}:/zap/wrk:rw" `
        $Image `
        zap-api-scan.py `
            -t $specUrl `
            -f openapi `
            -O $GatewayUrl `
            -J zap-report.json `
            -r zap-report.html `
            -I `
            -z "-config network.https.checkCertificate=false"
}
finally {
    Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
}
