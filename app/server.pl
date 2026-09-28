#!/usr/bin/perl
# Virtual Standardized Patient Simulator, the small web server for macOS.
# Started by "Start on Mac.app". Uses the Perl that macOS ships. Installs nothing.
#
#   1. Serves the app folder on http://127.0.0.1:8756, to this computer only.
#   2. Opens the browser there.
#   3. Stops by itself when the last browser tab closes, or when Quit is pressed in the page.
#      On the way out it unloads the patient model, so Ollama gives back the memory.
#
# It keeps a log, log.txt, in the downloaded folder beside the Start files, or in the temporary
# folder as virtual-standardized-patient.log if the folder cannot be written. If it cannot
# start, it opens a page in the browser with an error report to email or post on GitHub.
use strict; use warnings;
use IO::Socket::INET; use IO::Select; use Cwd 'abs_path'; use File::Basename 'dirname';
use File::Temp 'tempdir'; use File::Path 'rmtree'; use POSIX 'strftime';

my $PORT   = 8756;
my $URL    = "http://127.0.0.1:$PORT/";
my $OLLAMA = 'http://127.0.0.1:11434';
# Where "Update" in the page gets the new files. VSP_ZIP overrides it for testing.
my $ZIP    = $ENV{VSP_ZIP} || 'https://github.com/igembitsky/virtual-standardized-patient/archive/refs/heads/main.zip';
# The patient models. Only these are unloaded on the way out.
my $KNOWN  = qr/^(qwen3:4b-instruct|qwen3:4b|llama3\.1:8b|granite4\.1:3b)(:|$)/;
# How long to wait before stopping, in seconds.
my $FIRST_TAB = 120;   # for the browser to open the first tab
my $LAST_TAB  = 10;    # after the last tab closes, so a reload does not stop it
my $QUIET_TAB = 240;   # a tab that has not been heard from, e.g. the browser was killed

my %T = (html=>'text/html; charset=utf-8', js=>'application/javascript',
         css=>'text/css', json=>'application/json', txt=>'text/plain; charset=utf-8',
         png=>'image/png', jpg=>'image/jpeg', jpeg=>'image/jpeg', svg=>'image/svg+xml',
         ico=>'image/x-icon', md=>'text/plain; charset=utf-8');
my $root = dirname(abs_path($0));    # the app folder, served
my $top  = dirname($root);           # the folder that was downloaded
# The log goes beside the Start files, where anyone can find it and send it. If the folder
# cannot be written, the temporary folder instead.
my $LOG  = "$top/log.txt";
unless (open my $t, '>>', $LOG) { $LOG = ($ENV{TMPDIR} || '/tmp') . '/virtual-standardized-patient.log' }
$LOG =~ s{//+}{/}g;
my $srv;

# Anything that goes wrong from here on ends in the problem page, not in silence.
$SIG{__DIE__} = sub { return if $^S; fail("The launcher stopped with an error: $_[0]") };

rename $LOG, "$LOG.old" if -s $LOG && -s $LOG > 200_000;     # keep the log small
logline("Starting version " . version() . " on " . mac_version() . ", Perl $^V, in $root");

$srv = IO::Socket::INET->new(LocalAddr=>'127.0.0.1', LocalPort=>$PORT, Listen=>32,
                             ReuseAddr=>1, Proto=>'tcp');
unless ($srv) {
  my $why = $!;
  if (`curl -s -m 3 ${URL}update` eq 'can') {  # this simulator, already running: just show it
    logline("It is already running. Opening it.");
    open_browser($URL); exit 0;
  }
  fail("Another program is using port $PORT, so the simulator cannot start. ($why)");
}
$SIG{PIPE} = 'IGNORE';               # a tab that closes mid-reply must not stop the server
$SIG{$_} = sub { stop("signal $_[0]") } for qw(INT TERM HUP);
logline("Running on $URL. It stops by itself when you close the browser tab, or press Quit in the page.");
open_browser($URL);

my $sel = IO::Select->new($srv);
my (%buf, %born);        # per connection: what has arrived, and when it opened
my %tabs;                # open tabs: id => when last heard from
my ($seen, $quit, $empty_since) = (0, 0, 0);
my $begun = my $tick = time;

while (!$quit) {
  for my $fh ($sel->can_read(1)) {
    if ($fh == $srv) {
      my $c = $srv->accept or next;
      binmode $c; $sel->add($c); $buf{$c} = ''; $born{$c} = time;
      next;
    }
    my $n = sysread($fh, my $chunk, 65536);
    if (!$n) { drop($fh); next }
    $buf{$fh} .= $chunk;
    my $end = index($buf{$fh}, "\r\n\r\n");
    next if $end < 0 && length($buf{$fh}) < 65536;            # the headers are not all here yet
    my ($len) = $buf{$fh} =~ /^Content-Length:\s*(\d+)/mi;
    next if $end >= 0 && $len && $len < 65536 && length($buf{$fh}) < $end + 4 + $len;   # nor the body
    my $req = $buf{$fh};
    drop($fh, 1);
    handle($fh, $req);
    close $fh;
  }
  my $now = time;
  if ($now - $tick > 30) {           # the computer slept; that is not a closed tab
    $tabs{$_} = $now for keys %tabs;
    ($begun, $empty_since) = ($now, 0);
  }
  $tick = $now;
  # a browser may open a connection and send nothing; drop it after 5 seconds
  for my $c ($sel->handles) { drop($c) if $c != $srv && $now - $born{$c} > 5 }
  delete $tabs{$_} for grep { $now - $tabs{$_} > $QUIET_TAB } keys %tabs;
  if (%tabs)     { $empty_since = 0 }
  elsif (!$seen) { $quit = 'no browser tab opened in 2 minutes' if $now - $begun > $FIRST_TAB }
  else           { $empty_since ||= $now; $quit = 'the last tab closed' if $now - $empty_since >= $LAST_TAB }
}
stop($quit);

sub logline {
  my $line = strftime('%Y-%m-%d %H:%M:%S ', localtime) . join('', @_) . "\n";
  print $line if -t STDOUT;          # started from Terminal; otherwise STDOUT is the log already
  if (open my $fh, '>>', $LOG) { print $fh $line; close $fh }
}
sub log_tail {
  my ($n) = @_;
  open my $fh, '<', $LOG or return "(no log)\n";
  my @l = <$fh>; close $fh;
  return join '', @l[($#l - $n + 1 < 0 ? 0 : $#l - $n + 1) .. $#l];
}
sub version {
  open my $fh, '<', "$root/index.html" or return 'unknown';
  local $/; my ($v) = <$fh> =~ /version: "([^"]+)"/; close $fh;
  return $v || 'unknown';
}
sub mac_version { my $v = `sw_vers -productVersion 2>/dev/null`; chomp $v; $v ? "macOS $v" : $^O }
sub open_browser { system('open', $_[0]) unless $ENV{VSP_NO_BROWSER} }   # tests set VSP_NO_BROWSER
sub json_str {
  my $s = shift;
  $s =~ s/(["\\])/\\$1/g; $s =~ s/\n/\\n/g; $s =~ s/\r/\\r/g; $s =~ s/\t/\\t/g;
  $s =~ s/([\x00-\x1f])/sprintf('\\u%04x', ord $1)/ge; $s =~ s{</}{<\\/}g;
  return "\"$s\"";
}
# It cannot start. Log why, and open a page with a report to send.
sub fail {
  my ($what) = @_;
  $what =~ s/\s+$//;
  $SIG{__DIE__} = 'DEFAULT';
  logline("PROBLEM: $what");
  my $report = join "\n", 'Virtual Standardized Patient Simulator: problem report',
    'Version: ' . version(), 'When: ' . strftime('%Y-%m-%d %H:%M:%S %z', localtime),
    'Computer: ' . mac_version() . ", Perl $^V", "Folder: $top", "What happened: $what",
    '', '--- launcher log, last lines ---', log_tail(80);
  if (open my $in, '<', "$root/problem.html") {
    local $/; my $page = <$in>; close $in;
    my $data = '{"what":' . json_str($what) . ',"report":' . json_str($report) . '}';
    $page =~ s{/\*REPORT\*/null/\*END\*/}{$data};
    my $out = ($ENV{TMPDIR} || '/tmp') . '/virtual-standardized-patient-problem.html';
    $out =~ s{//+}{/}g;
    if (open my $o, '>', $out) { print $o $page; close $o; open_browser("file://$out") }
  }
  exit 3;
}

sub drop {
  my ($fh, $keep) = @_;
  $sel->remove($fh); delete $buf{$fh}; delete $born{$fh};
  close $fh unless $keep;
}

sub reply {
  my ($c, $status, $type, $body) = @_;
  print $c "HTTP/1.0 $status\r\nContent-Type: $type\r\nContent-Length: " . length($body)
         . "\r\nCache-Control: no-store\r\nX-Frame-Options: DENY\r\n"
         . "Content-Security-Policy: frame-ancestors 'none'\r\nConnection: close\r\n\r\n", $body;
}

sub handle {
  my ($c, $req) = @_;
  my ($method, $path) = $req =~ m{^(GET|POST|HEAD)\s+(\S+)} ? ($1, $2) : ('GET', '/');
  my $query = $path =~ s/\?(.*)$// ? $1 : '';
  my ($tab) = $query =~ /(?:^|&)tab=([\w-]{1,40})/;
  $path =~ s{%([0-9A-Fa-f]{2})}{chr(hex($1))}ge;
  $path = '/index.html' if $path eq '/';

  # Only this computer's own page may use the simulator. Another web site open in the browser
  # must not quit or update it (Origin), or read its files through a changed name (Host).
  my ($host)   = $req =~ /^Host:[ \t]*(\S+)/mi;
  my ($origin) = $req =~ /^Origin:[ \t]*(\S+)/mi;
  if ((defined $host && $host !~ /^(127\.0\.0\.1|localhost):$PORT$/i) ||
      (defined $origin && $origin !~ m{^http://(127\.0\.0\.1|localhost):$PORT$}i)) {
    logline("Refused $method $path from " . ($origin || $host));
    return reply($c, '403 Forbidden', 'text/plain', "Forbidden\n");
  }

  if ($path eq '/alive') { $tabs{$tab} = time if $tab; $seen = 1; return reply($c, '200 OK', 'text/plain', 'ok') }
  if ($path eq '/bye')   { delete $tabs{$tab} if $tab;             return reply($c, '200 OK', 'text/plain', 'ok') }
  if ($path eq '/quit' && $method eq 'POST') { $quit = 'Quit was pressed'; return reply($c, '200 OK', 'text/plain', 'ok') }
  if ($path eq '/log')   {                                          return reply($c, '200 OK', 'text/plain; charset=utf-8', log_tail(150)) }

  # GET /update says this launcher can update. POST /update does it.
  if ($path eq '/update') {
    return reply($c, '200 OK', 'text/plain', 'can') unless $method eq 'POST';
    my $err = update_files();
    logline('Update: ' . ($err || 'done'));
    $err =~ s/["\\]//g if $err;
    return reply($c, '200 OK', 'application/json', $err ? "{\"ok\":false,\"error\":\"$err\"}" : '{"ok":true}');
  }

  # a list of the case files, so new ones just appear
  if ($path eq '/cases/' or $path eq '/cases') {
    opendir(my $dh, "$root/cases") or return reply($c, '200 OK', 'application/json', '[]');
    my @f = sort grep { /\.txt$/i && -f "$root/cases/$_" } readdir($dh);
    closedir $dh;
    return reply($c, '200 OK', 'application/json',
                 '[' . join(',', map { my $s = $_; $s =~ s/(["\\])/\\$1/g; "\"$s\"" } @f) . ']');
  }

  my $file = abs_path($root . $path) || '';
  if ($file !~ m{^\Q$root\E/} || !-f $file) { logline("404 $method $path"); return reply($c, '404 Not Found', 'text/plain', "Not found\n") }
  my ($ext) = $file =~ /\.([A-Za-z0-9]+)$/;
  open my $fh, '<:raw', $file or return reply($c, '404 Not Found', 'text/plain', "Not found\n");
  my $body = do { local $/; <$fh> }; close $fh;
  reply($c, '200 OK', $T{lc($ext || 'txt')} || 'application/octet-stream', $body);
}

# Download the ZIP, unpack it in a temporary folder, check it is complete, then copy it
# over this folder. The old files stay until the whole ZIP has arrived and been checked.
# Returns nothing on success, or what went wrong.
sub update_files {
  my $tmp = tempdir('vsp-update-XXXXXX', TMPDIR => 1);
  my $err = update_from($tmp);
  rmtree($tmp);                      # whatever happened, leave no temporary folder behind
  return $err;
}
# Run a program without a shell (names from the download never reach a shell), return its lines.
sub run_lines {
  open(my $fh, '-|', @_) or return ();
  my @l = map { chomp; $_ } <$fh>; close $fh;
  return @l;
}

sub update_from {
  my ($tmp) = @_;
  # Every file a complete download must hold (declared here: the main loop above never
  # reaches file-level lines below it). An update that lacks one is refused.
  my @NEEDED  = ('app/index.html', 'app/server.pl', 'app/server.py', 'app/server.ps1', 'app/problem.html',
                 'Start on Windows.bat', 'Start on Linux.desktop', 'Start on Mac.app/Contents/MacOS/start');
  my @PROGRAM = ('app', 'Start on Windows.bat', 'Start on Linux.desktop', 'Start on Mac.app');
  my $zip = "$tmp/latest.zip";
  system('curl', '-sfL', '-m', '60', '-o', $zip, $ZIP);
  return 'the download did not finish' unless -s $zip;
  # Check every name before anything is written: no absolute path, no "..", no backslash.
  my @names = run_lines('tar', '-tf', $zip);
  return 'could not read the download' unless @names;
  for (@names) { chomp; return 'the download holds an unsafe file name' if m{^/|\\|(^|/)\.\.(/|$)} }
  my $new = "$tmp/new"; mkdir $new;
  system('tar', '-xf', $zip, '-C', $new) == 0 or return 'could not unpack the download';
  return 'the download holds a link' if run_lines('find', $new, '-type', 'l');
  opendir(my $dh, $new) or return 'could not read the download';
  my @dirs = grep { !/^\./ && -d "$new/$_" } readdir($dh);
  closedir $dh;
  return 'the download was incomplete' unless @dirs == 1;
  my $src = "$new/$dirs[0]";
  for (@NEEDED) { return 'the download was incomplete' unless -f "$src/$_" }
  opendir(my $cd, "$src/app/cases") or return 'the download was incomplete';
  my @cases = grep { /\.txt$/ } readdir($cd); closedir $cd;
  return 'the download was incomplete' unless @cases;
  # Never write through a link: it could lead outside this folder.
  for my $rel (map { substr($_, length($src) + 1) } run_lines('find', $src, '-type', 'f')) {
    my $p = $top;
    for my $part (split m{/}, $rel) { $p .= "/$part"; return 'a link in the folder is in the way' if -l $p }
  }
  # Back up the program files; if the copy fails, put them back, so it is never half and half.
  my $backup = "$tmp/backup"; mkdir $backup;
  for (@PROGRAM) { system('cp', '-RP', "$top/$_", "$backup/") if -e "$top/$_" }
  if (system('cp', '-R', "$src/.", "$top/") != 0) {
    system('cp', '-RP', "$backup/.", "$top/");
    return 'could not copy the new files, so the old ones were put back';
  }
  return;
}

# Give back the memory the patient model holds, then stop. Ollama itself is left as it was found.
sub stop {
  my ($why) = @_;
  logline("Stopping: $why");
  close $srv if $srv;
  my %done;
  for my $m (`curl -s -m 3 $OLLAMA/api/ps` =~ /"name"\s*:\s*"([^"]+)"/g) {
    next if $done{$m}++ || $m !~ $KNOWN;
    system('curl', '-s', '-m', '10', '-o', '/dev/null', "$OLLAMA/api/generate",
           '-d', "{\"model\":\"$m\",\"keep_alive\":0}");
    logline("Unloaded $m");
  }
  logline('Stopped.');
  exit 0;
}
