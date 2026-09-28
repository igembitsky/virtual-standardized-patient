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
# It keeps a log, log.txt, in the downloaded folder beside the Start files, or in the temporary
# folder as virtual-standardized-patient.log if the folder cannot be written. If it cannot
# start, it opens a page in the browser with an error report to email or post on GitHub.
# To see its messages as it runs, right-click this file and choose Run with PowerShell.

$root   = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }   # the app folder, served
$top    = Split-Path $root -Parent         # the folder that was downloaded
$port   = 8756
$url    = "http://127.0.0.1:$port/"
$ollama = 'http://127.0.0.1:11434'
# The patient models. Only these are unloaded on the way out.
$known  = '^(qwen3:4b-instruct|qwen3:4b|llama3\.1:8b|granite4\.1:3b)(:|$)'
# How long to wait before stopping, in seconds.
$firstTab = 120   # for the browser to open the first tab
$lastTab  = 10    # after the last tab closes, so a reload does not stop it
$quietTab = 240   # a tab that has not been heard from, e.g. the browser was killed
# The log goes beside the Start files, where anyone can find it and send it. If the folder
# cannot be written, the temporary folder instead.
# The log is opened once and kept open, and never through a link or junction: a link could
# point anywhere, and one made later is not followed either.
function Test-IsLink($p) {
  $it = Get-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue
  return [bool]($it -and ($it.Attributes -band [System.IO.FileAttributes]::ReparsePoint))
}
function Open-Log($p) {
  if (Test-IsLink $p) { throw 'the log is a link' }
  try { if ((Get-Item -LiteralPath $p -ErrorAction Stop).Length -gt 200000) { Move-Item -Force -LiteralPath $p "$p.old" } } catch {}
  $fs = [System.IO.File]::Open($p, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write, [System.IO.FileShare]::ReadWrite)
  $w = New-Object System.IO.StreamWriter($fs, (New-Object System.Text.UTF8Encoding $false))
  $w.AutoFlush = $true
  return $w
}
$log = Join-Path $top 'log.txt'; $logWriter = $null
try { $logWriter = Open-Log $log } catch {
  $log = Join-Path ([System.IO.Path]::GetTempPath()) 'virtual-standardized-patient.log'
  try { $logWriter = Open-Log $log } catch {}
}
$types  = @{
  '.html'='text/html; charset=utf-8'; '.js'='application/javascript';
  '.css'='text/css'; '.json'='application/json'; '.txt'='text/plain; charset=utf-8';
  '.png'='image/png'; '.jpg'='image/jpeg'; '.jpeg'='image/jpeg'; '.svg'='image/svg+xml';
  '.ico'='image/x-icon'; '.md'='text/plain; charset=utf-8'
}

# True if any existing part of the path from $base down to $rel is a link or junction.
function Test-LinkOnTheWay($base, $rel) {
  $p = $base
  foreach ($part in ($rel -split '[\\/]')) {
    if (-not $part) { continue }
    $p = Join-Path $p $part
    $it = Get-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue
    if ($it -and ($it.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) { return $true }
  }
  return $false
}

# Patient models that were already loaded when the simulator started belong to someone else.
$before = New-Object System.Collections.Generic.HashSet[string]
try { foreach ($m in @((Invoke-RestMethod -Uri "$ollama/api/ps" -TimeoutSec 3 -ErrorAction Stop).models)) { [void]$before.Add($m.name) } } catch {}

# Give back the memory the patient model holds. Ollama itself is left as it was found.
function Stop-Patient {
  try {
    $ps = Invoke-RestMethod -Uri "$ollama/api/ps" -TimeoutSec 3 -ErrorAction Stop
    foreach ($name in (@($ps.models) | ForEach-Object { $_.name } | Select-Object -Unique)) {
      if ($name -match $known -and -not $before.Contains($name)) {   # not ours if it was loaded before we started
        Invoke-RestMethod -Uri "$ollama/api/generate" -Method Post -ContentType 'application/json' `
          -Body "{`"model`":`"$name`",`"keep_alive`":0}" -TimeoutSec 10 -ErrorAction Stop | Out-Null
        Log "Unloaded $name"
      }
    }
  } catch {}
}

function Log($msg) {
  $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss ') + $msg
  Write-Host $line
  try { if ($logWriter) { $logWriter.WriteLine($line) } } catch {}
}
function Get-LogTail($n) {
  if (Test-IsLink $log) { return '(no log)' }
  try { (Get-Content -LiteralPath $log -Tail $n -ErrorAction Stop) -join "`n" } catch { '(no log)' }
}
function Get-Version {
  try { if ((Get-Content -Raw -LiteralPath (Join-Path $root 'index.html')) -match 'version: "([^"]+)"') { return $matches[1] } } catch {}
  'unknown'
}
function Open-Browser($target) { if (-not $env:VSP_NO_BROWSER) { Start-Process $target } }   # tests set VSP_NO_BROWSER
function Get-Computer { "$([System.Environment]::OSVersion.VersionString), PowerShell $($PSVersionTable.PSVersion)" }

# It cannot start. Log why, and open a page with a report to send.
function Fail($what) {
  Log "PROBLEM: $what"
  $report = @(
    'Virtual Standardized Patient Simulator: problem report'
    "Version: $(Get-Version)"
    "When: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
    "Computer: $(Get-Computer)"
    "Folder: $top"
    "What happened: $what"
    ''
    '--- launcher log, last lines ---'
    (Get-LogTail 80)) -join "`n"
  try {
    $data = (ConvertTo-Json -Compress -InputObject @{ what = $what; report = $report }).Replace('</', '<\/')
    $page = (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $root 'problem.html')).Replace('/*REPORT*/null/*END*/', $data)
    $out = Join-Path ([System.IO.Path]::GetTempPath()) 'virtual-standardized-patient-problem.html'
    # a fresh file each time, never written through an existing file or link
    Remove-Item -LiteralPath $out -Force -ErrorAction SilentlyContinue
    $fs = [System.IO.File]::Open($out, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
    try { $bytes = (New-Object System.Text.UTF8Encoding $false).GetBytes($page); $fs.Write($bytes, 0, $bytes.Length) } finally { $fs.Close() }
    Open-Browser $out
  } catch { Log "Could not open the problem page: $($_.Exception.Message)" }
  exit 3
}

function Send($stream, $status, $type, [byte[]]$bytes) {
  $head = [System.Text.Encoding]::ASCII.GetBytes(
    "HTTP/1.0 $status`r`nContent-Type: $type`r`nContent-Length: $($bytes.Length)`r`nCache-Control: no-store`r`nX-Frame-Options: DENY`r`nContent-Security-Policy: frame-ancestors 'none'`r`nConnection: close`r`n`r`n")
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
  $len = 0; $hostName = $null; $origin = $null; $site = $null; $lines = 0
  while ($true) {
    $h = $reader.ReadLine()
    if ($h -eq $null -or $h -eq '') { break }
    $lines++
    if ($h.Length -gt 8192 -or $lines -gt 100) { return }   # far larger than a browser sends
    if ($h -match '^Content-Length:\s*(\d+)') { $len = [int]$matches[1] }
    if ($h -match '^Host:\s*(\S+)') { $hostName = $matches[1] }
    if ($h -match '^Origin:\s*(\S+)') { $origin = $matches[1] }
    if ($h -match '^Sec-Fetch-Site:\s*(\S+)') { $site = $matches[1] }   # where the browser says it comes from
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

  # Only this computer's own page may use the simulator. Another web site open in the browser
  # must not quit it (Origin), or read its files through a changed name (Host).
  if (($hostName -and $hostName -notmatch "^(127\.0\.0\.1|localhost):$port$") -or
      ($origin -and $origin -notmatch "^http://(127\.0\.0\.1|localhost):$port$") -or
      ($site -and $site -notmatch '^(same-origin|none)$')) {
    Log "Refused $method $path from $(if ($origin) { $origin } else { $hostName })"
    return Send $stream '403 Forbidden' 'text/plain' (Text "Forbidden`n")
  }

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
    '/log' {                               # for the problem report in the page
      return Send $stream '200 OK' 'text/plain; charset=utf-8' (Text ((Get-LogTail 150) + "`n"))
    }
    '/quit' {                              # Quit in the page
      if ($method -eq 'POST') { $script:quit = $true }
      return Send $stream '200 OK' 'text/plain' (Text 'ok')
    }
    '/ping' {                              # "this is the simulator", for a second start
      return Send $stream '200 OK' 'text/plain' (Text 'virtual-standardized-patient')
    }
    { $_ -eq '/cases' -or $_ -eq '/cases/' } {   # a list of the case files, so new ones just appear
      $names = @(Get-ChildItem -LiteralPath (Join-Path $root 'cases') -Filter *.txt -File -ErrorAction SilentlyContinue |
                 Sort-Object Name | ForEach-Object { $_.Name })
      return Send $stream '200 OK' 'application/json' (Text (ConvertTo-Json -InputObject $names -Compress))
    }
  }

  $sep  = [System.IO.Path]::DirectorySeparatorChar
  $file = [System.IO.Path]::GetFullPath((Join-Path $root ($path.TrimStart('/').Replace('/', $sep))))
  # Serve only real files inside the app folder: never through a link or junction.
  if ($file.StartsWith($root + $sep, [System.StringComparison]::OrdinalIgnoreCase) -and
      (Test-Path -LiteralPath $file -PathType Leaf) -and
      -not (Test-LinkOnTheWay $root $file.Substring($root.Length + 1))) {
    $type = $types[[System.IO.Path]::GetExtension($file).ToLower()]
    if (-not $type) { $type = 'application/octet-stream' }
    Send $stream '200 OK' $type ([System.IO.File]::ReadAllBytes($file))
  } else {
    Log "404 $method $path"
    Send $stream '404 Not Found' 'text/plain' (Text 'Not found')
  }
}

# Anything that goes wrong from here on ends in the problem page, not in silence.
trap { Log ($_ | Out-String); Fail "The launcher stopped with an error: $($_.Exception.Message)" }

Log "Starting version $(Get-Version) on $(Get-Computer), in $root"
try {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse('127.0.0.1'), $port)
  $listener.Start()
} catch {
  $why = $_.Exception.Message
  $mine = try { (Invoke-WebRequest -Uri "${url}ping" -UseBasicParsing -TimeoutSec 3).Content -eq 'virtual-standardized-patient' } catch { $false }
  if ($mine) { Log 'It is already running. Opening it.'; Open-Browser $url; exit 0 }
  Fail "Another program is using port $port, so the simulator cannot start. ($why)"
}

# Ollama: open it if it is installed but not running. The page reports anything else.
try { Invoke-RestMethod -Uri "$ollama/api/tags" -TimeoutSec 2 -ErrorAction Stop | Out-Null } catch {
  $app = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe' }
  if ($app -and (Test-Path $app)) { Log 'Ollama is not running. Opening it.'; Start-Process $app | Out-Null }
  else { Log 'Ollama is not running, and was not found in the usual place.' }
}

Log "Running on $url. It stops by itself when you close the browser tab, or press Quit in the page."
Open-Browser $url

$why = 'Quit was pressed'
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
    elseif (-not $seen)  { if (($now - $begun).TotalSeconds -gt $firstTab) { $why = 'no browser tab opened in 2 minutes'; break } }
    else {
      if (-not $emptySince) { $emptySince = $now }
      if (($now - $emptySince).TotalSeconds -ge $lastTab) { $why = 'the last tab closed'; break }
    }
  }
} finally {
  Log "Stopping: $why"
  $listener.Stop()
  Stop-Patient
  Log 'Stopped.'
}
