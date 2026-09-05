# Virtual Standardized Patient Simulator, Windows server.
# Started by start-windows.bat. Uses only what Windows already has.
# No installation, no administrator rights. Close the window to stop.
#
# In order:
#   1. Make sure Ollama is running, and download the patient model if it is missing.
#   2. Serve this folder on http://127.0.0.1:8756, to this computer only.
#   3. Open the browser there.

$root   = (Get-Location).Path
$port   = 8756
$ollama = 'http://127.0.0.1:11434'
$model  = 'qwen3:4b-instruct'
# Where "Update" in the page gets the new files. VSP_ZIP overrides it for testing.
$zipUrl = if ($env:VSP_ZIP) { $env:VSP_ZIP } else { 'https://github.com/igembitsky/virtual-standardized-patient/archive/refs/heads/main.zip' }
# Any one of these is enough. The page picks the first it recognises.
$known  = '^(qwen3:4b-instruct|qwen3:4b|llama3\.1:8b|granite4\.1:3b)(:|$)'
$types  = @{
  '.html'='text/html; charset=utf-8'; '.js'='application/javascript';
  '.css'='text/css'; '.json'='application/json'; '.txt'='text/plain; charset=utf-8';
  '.png'='image/png'; '.jpg'='image/jpeg'; '.jpeg'='image/jpeg'; '.svg'='image/svg+xml';
  '.ico'='image/x-icon'; '.md'='text/plain; charset=utf-8'
}

function Get-Tags {
  try { Invoke-RestMethod -Uri "$ollama/api/tags" -TimeoutSec 3 -ErrorAction Stop } catch { $null }
}
# Download the ZIP, unpack it beside this folder, check it is complete, then copy it over
# this folder. The old files stay until the whole ZIP has arrived and been checked.
function Invoke-Update {
  $tmp = Join-Path $root '.update-tmp'
  try {
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    New-Item -ItemType Directory -Path $tmp | Out-Null
    $zip = Join-Path $tmp 'latest.zip'
    Invoke-WebRequest -Uri $zipUrl -OutFile $zip -TimeoutSec 60 -UseBasicParsing -ErrorAction Stop
    if (-not (Test-Path $zip) -or (Get-Item $zip).Length -eq 0) { return @{ ok = $false; error = 'the download did not finish' } }
    Expand-Archive -Path $zip -DestinationPath $tmp -Force -ErrorAction Stop
    $src = Get-ChildItem -Path $tmp -Directory | Select-Object -First 1
    if (-not $src -or -not (Test-Path (Join-Path $src.FullName 'index.html')) -or
        -not (Test-Path (Join-Path $src.FullName 'VERSION')) -or
        -not (Test-Path (Join-Path $src.FullName 'cases'))) { return @{ ok = $false; error = 'the download was incomplete' } }
    Copy-Item -Path (Join-Path $src.FullName '*') -Destination $root -Recurse -Force -ErrorAction Stop
    $ver = (Get-Content (Join-Path $root 'VERSION') -Raw).Trim()
    return @{ ok = $true; version = $ver }
  } catch {
    return @{ ok = $false; error = ($_.Exception.Message -replace '["\\]', '') }
  } finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue   # leave no temporary folder behind
  }
}

function Test-Model($tags) {
  if (-not $tags) { return $false }
  foreach ($m in @($tags.models)) { if ($m.name -match $known) { return $true } }
  return $false
}

Write-Host "Virtual Standardized Patient Simulator"
Write-Host ""

# ---- 1. Ollama ------------------------------------------------------------
$tags = Get-Tags
if (-not $tags) {
  $app = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe'
  if (Test-Path $app) {
    Write-Host "Ollama is not running. Opening it ..."
    Start-Process $app | Out-Null
    for ($i = 0; $i -lt 40 -and -not $tags; $i++) { Start-Sleep -Seconds 1; $tags = Get-Tags }
  } else {
    Write-Host ""
    Write-Host "  Ollama is not installed. Get it from https://ollama.com/download"
    Write-Host "  Install it, open it once, then double-click start-windows.bat again."
    Write-Host ""
  }
}

# ---- 2. The model, downloaded once ---------------------------------------
if (Test-Model $tags) {
  Write-Host "Ollama is running and the patient model is ready."
} elseif ($tags) {
  Write-Host "Downloading the patient model, $model. About 2.5 GB, once."
  Write-Host "Leave this window open. It can take a while."
  try {
    $req = [System.Net.HttpWebRequest]::Create("$ollama/api/pull")
    $req.Method = 'POST'
    $req.ContentType = 'application/json'
    $req.ReadWriteTimeout = 600000
    $body = [System.Text.Encoding]::UTF8.GetBytes("{`"name`":`"$model`"}")
    $req.ContentLength = $body.Length
    $rs = $req.GetRequestStream(); $rs.Write($body, 0, $body.Length); $rs.Close()
    $resp   = $req.GetResponse()
    $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
    while (($line = $reader.ReadLine()) -ne $null) {
      try { $j = $line | ConvertFrom-Json -ErrorAction Stop } catch { continue }
      if ($j.error) { Write-Host "  Problem: $($j.error)"; break }
      if ($j.total -and $j.completed -and $j.total -gt 100MB) {
        $pct = [int]($j.completed * 100 / $j.total)
        $gb  = [math]::Round($j.total / 1GB, 1)
        Write-Progress -Activity "Downloading the patient model" -Status "$pct% of $gb GB" -PercentComplete $pct
      }
      if ($j.status -eq 'success') {
        Write-Progress -Activity "Downloading the patient model" -Completed
        Write-Host "  Download complete."
      }
    }
    $reader.Close(); $resp.Close()
  } catch {
    Write-Host "  The download did not finish: $($_.Exception.Message)"
  }
  if (-not (Test-Model (Get-Tags))) {
    Write-Host ""
    Write-Host "  The model is still missing. Check your internet connection and run this again,"
    Write-Host "  or open PowerShell and run:  ollama pull $model"
    Write-Host ""
  }
}

# ---- 3. Serve, and open the browser --------------------------------------
Write-Host ""
Write-Host "Starting on http://127.0.0.1:$port ..."
try {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse('127.0.0.1'), $port)
  $listener.Start()
} catch {
  Write-Host "Port $port is busy. The simulator is probably already running. Opening it ..."
  Start-Process "http://127.0.0.1:$port/"
  Read-Host "Press Enter to close"
  exit 0
}

Write-Host "Running. Open http://127.0.0.1:$port/"
Write-Host "Close this window to stop."
Start-Process "http://127.0.0.1:$port/"

while ($true) {
  $client = $listener.AcceptTcpClient()
  try {
    $stream = $client.GetStream()
    $reader = New-Object System.IO.StreamReader($stream)
    $line = $reader.ReadLine()
    if (-not $line) { $client.Close(); continue }

    $method = ($line -split ' ')[0]
    $path = ($line -split ' ')[1]
    $path = ($path -split '\?')[0]
    $path = [System.Uri]::UnescapeDataString($path)
    if ($path -eq '/') { $path = '/index.html' }

    $writer = New-Object System.IO.BinaryWriter($stream)

    # GET /update says this launcher can update. POST /update does it.
    if ($path -eq '/update') {
      if ($method -eq 'POST') {
        $r = Invoke-Update
        $json = if ($r.ok) { "{`"ok`":true,`"version`":`"$($r.version)`"}" } else { "{`"ok`":false,`"error`":`"$($r.error)`"}" }
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
        $head  = "HTTP/1.0 200 OK`r`nContent-Type: application/json`r`nContent-Length: $($bytes.Length)`r`nCache-Control: no-store`r`n`r`n"
      } else {
        $bytes = [System.Text.Encoding]::ASCII.GetBytes('can')
        $head  = "HTTP/1.0 200 OK`r`nContent-Type: text/plain`r`nContent-Length: $($bytes.Length)`r`nCache-Control: no-store`r`n`r`n"
      }
      $writer.Write([System.Text.Encoding]::ASCII.GetBytes($head))
      $writer.Write($bytes)
      $writer.Flush(); $client.Close(); continue
    }

    if ($path -eq '/cases' -or $path -eq '/cases/') {
      $names = @()
      $dir = Join-Path $root 'cases'
      if (Test-Path $dir) {
        $names = Get-ChildItem -Path $dir -Filter *.txt -File |
                 Sort-Object Name | ForEach-Object { $_.Name }
      }
      $json  = ConvertTo-Json @($names) -Compress
      $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
      $head  = "HTTP/1.0 200 OK`r`nContent-Type: application/json`r`nContent-Length: $($bytes.Length)`r`nCache-Control: no-store`r`n`r`n"
      $writer.Write([System.Text.Encoding]::ASCII.GetBytes($head))
      $writer.Write($bytes)
      $writer.Flush(); $client.Close(); continue
    }

    $rel  = $path.TrimStart('/') -replace '/', '\'
    $file = Join-Path $root $rel
    $ok   = $false
    if (Test-Path $file -PathType Leaf) {
      $full = (Resolve-Path $file).Path
      if ($full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) { $ok = $true }
    }

    if ($ok) {
      $bytes = [System.IO.File]::ReadAllBytes($full)
      $ext   = [System.IO.Path]::GetExtension($full).ToLower()
      $type  = $types[$ext]; if (-not $type) { $type = 'application/octet-stream' }
      $head  = "HTTP/1.0 200 OK`r`nContent-Type: $type`r`nContent-Length: $($bytes.Length)`r`nCache-Control: no-store`r`n`r`n"
      $writer.Write([System.Text.Encoding]::ASCII.GetBytes($head))
      $writer.Write($bytes)
    } else {
      $msg = [System.Text.Encoding]::ASCII.GetBytes("HTTP/1.0 404 Not Found`r`nContent-Type: text/plain`r`n`r`nNot found")
      $writer.Write($msg)
    }
    $writer.Flush()
  } catch {
    # one bad request must never stop the server
  } finally {
    $client.Close()
  }
}
