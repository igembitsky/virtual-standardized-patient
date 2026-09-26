# Virtual Standardized Patient Simulator, the small web server for Windows.
# Started, with no window, by "Start on Windows.bat". Uses only what Windows already has.
# No installation, no administrator rights.
#
#   1. Opens Ollama if it is installed but not running.
#   2. Serves the app folder on http://127.0.0.1:8756, to this computer only.
#   3. Opens the browser there.
#   4. Stops by itself when the last browser tab closes, or when Quit is pressed in the page.
#      On the way out it unloads the patient model, so Ollama gives back the memory.
#
# To see its messages, right-click this file and choose Run with PowerShell.

$root   = $PSScriptRoot                    # the app folder, served
$top    = Split-Path $root -Parent         # the folder that was downloaded
$port   = 8756
$url    = "http://127.0.0.1:$port/"
$ollama = 'http://127.0.0.1:11434'
# Where "Update" in the page gets the new files. VSP_ZIP overrides it for testing.
$zipUrl = if ($env:VSP_ZIP) { $env:VSP_ZIP } else { 'https://github.com/igembitsky/virtual-standardized-patient/archive/refs/heads/main.zip' }
# The patient models. Only these are unloaded on the way out.
$known  = '^(qwen3:4b-instruct|qwen3:4b|llama3\.1:8b|granite4\.1:3b)(:|$)'
# How long to wait before stopping, in seconds.
$firstTab = 120   # for the browser to open the first tab
$lastTab  = 10    # after the last tab closes, so a reload does not stop it
$quietTab = 240   # a tab that has not been heard from, e.g. the browser was killed
$types  = @{
  '.html'='text/html; charset=utf-8'; '.js'='application/javascript';
  '.css'='text/css'; '.json'='application/json'; '.txt'='text/plain; charset=utf-8';
  '.png'='image/png'; '.jpg'='image/jpeg'; '.jpeg'='image/jpeg'; '.svg'='image/svg+xml';
  '.ico'='image/x-icon'; '.md'='text/plain; charset=utf-8'
}

# Download the ZIP, unpack it in a temporary folder, check it is complete, then copy it over
# this folder. The old files stay until the whole ZIP has arrived and been checked.
function Invoke-Update {
  $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('vsp-update-' + [guid]::NewGuid())
  try {
    New-Item -ItemType Directory -Path $tmp | Out-Null
    $zip = Join-Path $tmp 'latest.zip'
    Invoke-WebRequest -Uri $zipUrl -OutFile $zip -TimeoutSec 60 -UseBasicParsing -ErrorAction Stop
    Expand-Archive -Path $zip -DestinationPath $tmp -Force -ErrorAction Stop
    $src = Get-ChildItem -Path $tmp -Directory | Select-Object -First 1
    if (-not $src -or -not (Test-Path (Join-Path (Join-Path $src.FullName 'app') 'index.html')) -or
        -not (Test-Path (Join-Path (Join-Path $src.FullName 'app') 'cases'))) { return '{"ok":false,"error":"the download was incomplete"}' }
    Copy-Item -Path (Join-Path $src.FullName '*') -Destination $top -Recurse -Force -ErrorAction Stop
    return '{"ok":true}'
  } catch {
    return '{"ok":false,"error":"' + ($_.Exception.Message -replace '["\\\r\n]', '') + '"}'
  } finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue   # leave no temporary folder behind
  }
}

# Give back the memory the patient model holds. Ollama itself is left as it was found.
function Stop-Patient {
  try {
    $ps = Invoke-RestMethod -Uri "$ollama/api/ps" -TimeoutSec 3 -ErrorAction Stop
    foreach ($name in (@($ps.models) | ForEach-Object { $_.name } | Select-Object -Unique)) {
      if ($name -match $known) {
        Invoke-RestMethod -Uri "$ollama/api/generate" -Method Post -ContentType 'application/json' `
          -Body "{`"model`":`"$name`",`"keep_alive`":0}" -TimeoutSec 10 -ErrorAction Stop | Out-Null
      }
    }
  } catch {}
}

function Send($stream, $status, $type, [byte[]]$bytes) {
  $head = [System.Text.Encoding]::ASCII.GetBytes(
    "HTTP/1.0 $status`r`nContent-Type: $type`r`nContent-Length: $($bytes.Length)`r`nCache-Control: no-store`r`nConnection: close`r`n`r`n")
  $stream.Write($head, 0, $head.Length)
  $stream.Write($bytes, 0, $bytes.Length)
  $stream.Flush()
}
function Text($s) { [System.Text.Encoding]::UTF8.GetBytes($s) }

function Serve-Client($client) {
  $stream = $client.GetStream()
  $stream.ReadTimeout = 2000
  $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::ASCII)
  $line = $reader.ReadLine()
  if (-not $line) { return }
  # read the rest of the request before answering, so Windows does not reset the connection
  $len = 0
  while ($true) {
    $h = $reader.ReadLine()
    if ($h -eq $null -or $h -eq '') { break }
    if ($h -match '^Content-Length:\s*(\d+)') { $len = [int]$matches[1] }
  }
  if ($len -gt 0 -and $len -lt 65536) {
    $buf = New-Object char[] $len; $got = 0
    while ($got -lt $len) { $n = $reader.Read($buf, $got, $len - $got); if ($n -le 0) { break }; $got += $n }
  }

  $method, $target = ($line -split ' ')[0, 1]
  $path, $query = $target -split '\?', 2
  $path = [System.Uri]::UnescapeDataString($path)
  if ($path -eq '/') { $path = '/index.html' }
  $tab = if ($query -match '(?:^|&)tab=([\w-]{1,40})') { $matches[1] } else { $null }

  switch ($path) {
    '/alive' {                             # the page says it is still open
      if ($tab) { $tabs[$tab] = [DateTime]::UtcNow }
      $script:seen = $true
      return Send $stream '200 OK' 'text/plain' (Text 'ok')
    }
    '/bye' {                               # the page is closing
      if ($tab) { $tabs.Remove($tab) }
      return Send $stream '200 OK' 'text/plain' (Text 'ok')
    }
    '/quit' {                              # Quit in the page
      if ($method -eq 'POST') { $script:quit = $true }
      return Send $stream '200 OK' 'text/plain' (Text 'ok')
    }
    '/update' {                            # GET says it can; POST does it
      if ($method -eq 'POST') { return Send $stream '200 OK' 'application/json' (Text (Invoke-Update)) }
      return Send $stream '200 OK' 'text/plain' (Text 'can')
    }
    { $_ -eq '/cases' -or $_ -eq '/cases/' } {   # a list of the case files, so new ones just appear
      $names = @(Get-ChildItem -LiteralPath (Join-Path $root 'cases') -Filter *.txt -File -ErrorAction SilentlyContinue |
                 Sort-Object Name | ForEach-Object { $_.Name })
      return Send $stream '200 OK' 'application/json' (Text (ConvertTo-Json -InputObject $names -Compress))
    }
  }

  $sep  = [System.IO.Path]::DirectorySeparatorChar
  $file = [System.IO.Path]::GetFullPath((Join-Path $root ($path.TrimStart('/').Replace('/', $sep))))
  if ($file.StartsWith($root + $sep, [System.StringComparison]::OrdinalIgnoreCase) -and
      (Test-Path -LiteralPath $file -PathType Leaf)) {
    $type = $types[[System.IO.Path]::GetExtension($file).ToLower()]
    if (-not $type) { $type = 'application/octet-stream' }
    Send $stream '200 OK' $type ([System.IO.File]::ReadAllBytes($file))
  } else {
    Send $stream '404 Not Found' 'text/plain' (Text 'Not found')
  }
}

Write-Host "Virtual Standardized Patient Simulator"
try {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse('127.0.0.1'), $port)
  $listener.Start()
} catch {
  Write-Host "It is already running. Opening it ..."
  Start-Process $url
  exit 0
}

# Ollama: open it if it is installed but not running. The page reports anything else.
try { Invoke-RestMethod -Uri "$ollama/api/tags" -TimeoutSec 2 -ErrorAction Stop | Out-Null } catch {
  $app = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe' }
  if ($app -and (Test-Path $app)) { Start-Process $app | Out-Null }
}

Write-Host "Running on $url"
Write-Host "It stops by itself when you close the browser tab, or press Quit in the page."
Start-Process $url

$tabs = @{}                                # open tabs: id => when last heard from
$seen = $false; $quit = $false; $emptySince = $null
$begun = $tick = [DateTime]::UtcNow
$accept = $null
# A browser may open a connection and send nothing for a while. Those wait here, so they
# never hold up the others, and are dropped after 5 seconds.
$waiting = New-Object System.Collections.ArrayList
try {
  while (-not $quit) {
    if (-not $accept) { $accept = $listener.AcceptTcpClientAsync() }
    if ($accept.Wait($(if ($waiting.Count) { 50 } else { 1000 }))) {
      [void]$waiting.Add(@{ c = $accept.Result; t = [DateTime]::UtcNow }); $accept = $null
    }
    foreach ($w in @($waiting)) {
      if ($w.c.Available -gt 0) {
        $waiting.Remove($w)
        try { Serve-Client $w.c } catch {} finally { $w.c.Close() }   # one bad request must never stop it
      } elseif (([DateTime]::UtcNow - $w.t).TotalSeconds -gt 5) {
        $waiting.Remove($w); $w.c.Close()
      }
    }
    $now = [DateTime]::UtcNow
    if (($now - $tick).TotalSeconds -gt 30) {    # the computer slept; that is not a closed tab
      foreach ($k in @($tabs.Keys)) { $tabs[$k] = $now }
      $begun = $now; $emptySince = $null
    }
    $tick = $now
    foreach ($k in @($tabs.Keys)) { if (($now - $tabs[$k]).TotalSeconds -gt $quietTab) { $tabs.Remove($k) } }
    if ($tabs.Count -gt 0) { $emptySince = $null }
    elseif (-not $seen)  { if (($now - $begun).TotalSeconds -gt $firstTab) { break } }
    else {
      if (-not $emptySince) { $emptySince = $now }
      if (($now - $emptySince).TotalSeconds -ge $lastTab) { break }
    }
  }
} finally {
  Write-Host "Stopping ..."
  $listener.Stop()
  Stop-Patient
}
