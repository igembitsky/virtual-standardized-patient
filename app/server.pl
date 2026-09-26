#!/usr/bin/perl
# Virtual Standardized Patient Simulator, the small web server for macOS.
# Started by "Start on Mac.app". Uses the Perl that macOS ships. Installs nothing.
#
#   1. Serves the app folder on http://127.0.0.1:8756, to this computer only.
#   2. Opens the browser there.
#   3. Stops by itself when the last browser tab closes, or when Quit is pressed in the page.
#      On the way out it unloads the patient model, so Ollama gives back the memory.
use strict; use warnings;
use IO::Socket::INET; use IO::Select; use Cwd 'abs_path'; use File::Basename 'dirname';
use File::Temp 'tempdir'; use File::Path 'rmtree';

my $PORT   = 8756;
my $URL    = "http://127.0.0.1:$PORT/";
my $OLLAMA = 'http://127.0.0.1:11434';
# Where "Update" in the page gets the new files. VSP_ZIP overrides it for testing.
my $ZIP    = $ENV{VSP_ZIP} || 'https://github.com/igembitsky/virtual-standardized-patient/archive/refs/heads/main.zip';
# The patient models. Only these are unloaded on the way out.
my $KNOWN  = qr/^(qwen3:4b-instruct|qwen3:4b|llama3\.1:8b|granite4\.1:3b)(:|$)/;
my $OPEN   = $ENV{VSP_OPEN} || 'open';           # how to open the browser
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

my $srv = IO::Socket::INET->new(LocalAddr=>'127.0.0.1', LocalPort=>$PORT, Listen=>32,
                                ReuseAddr=>1, Proto=>'tcp');
unless ($srv) {                      # already running: just show it
  print "It is already running. Opening it ...\n";
  system($OPEN, $URL); exit 0;
}
$SIG{PIPE} = 'IGNORE';               # a tab that closes mid-reply must not stop the server
$SIG{$_} = \&stop for qw(INT TERM HUP);
print "Running on $URL\nIt stops by itself when you close the browser tab, or press Quit in the page.\n";
system($OPEN, $URL);

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
  elsif (!$seen) { $quit = 1 if $now - $begun > $FIRST_TAB }
  else           { $empty_since ||= $now; $quit = 1 if $now - $empty_since >= $LAST_TAB }
}
stop();

sub drop {
  my ($fh, $keep) = @_;
  $sel->remove($fh); delete $buf{$fh}; delete $born{$fh};
  close $fh unless $keep;
}

sub reply {
  my ($c, $status, $type, $body) = @_;
  print $c "HTTP/1.0 $status\r\nContent-Type: $type\r\nContent-Length: " . length($body)
         . "\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n", $body;
}

sub handle {
  my ($c, $req) = @_;
  my ($method, $path) = $req =~ m{^(GET|POST|HEAD)\s+(\S+)} ? ($1, $2) : ('GET', '/');
  my $query = $path =~ s/\?(.*)$// ? $1 : '';
  my ($tab) = $query =~ /(?:^|&)tab=([\w-]{1,40})/;
  $path =~ s{%([0-9A-Fa-f]{2})}{chr(hex($1))}ge;
  $path = '/index.html' if $path eq '/';

  if ($path eq '/alive') { $tabs{$tab} = time if $tab; $seen = 1; return reply($c, '200 OK', 'text/plain', 'ok') }
  if ($path eq '/bye')   { delete $tabs{$tab} if $tab;             return reply($c, '200 OK', 'text/plain', 'ok') }
  if ($path eq '/quit' && $method eq 'POST') { $quit = 1;          return reply($c, '200 OK', 'text/plain', 'ok') }

  # GET /update says this launcher can update. POST /update does it.
  if ($path eq '/update') {
    return reply($c, '200 OK', 'text/plain', 'can') unless $method eq 'POST';
    my $err = update_files();
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
  if ($file !~ m{^\Q$root\E/} || !-f $file) { return reply($c, '404 Not Found', 'text/plain', "Not found\n") }
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
sub update_from {
  my ($tmp) = @_;
  my $zip = "$tmp/latest.zip";
  system('curl', '-sfL', '-m', '60', '-o', $zip, $ZIP);
  return 'the download did not finish' unless -s $zip;
  system('tar', '-xf', $zip, '-C', $tmp) == 0 or return 'could not unpack the download';
  opendir(my $dh, $tmp) or return 'could not read the download';
  my ($src) = map { "$tmp/$_" } grep { !/^\./ && -d "$tmp/$_" } readdir($dh);
  closedir $dh;
  ($src && -f "$src/app/index.html" && -d "$src/app/cases") or return 'the download was incomplete';
  system('cp', '-R', "$src/.", "$top/") == 0 or return 'could not copy the new files';
  return;
}

# Give back the memory the patient model holds, then stop. Ollama itself is left as it was found.
sub stop {
  close $srv if $srv;
  my %done;
  for my $m (`curl -s -m 3 $OLLAMA/api/ps` =~ /"name"\s*:\s*"([^"]+)"/g) {
    next if $done{$m}++ || $m !~ $KNOWN;
    system('curl', '-s', '-m', '10', '-o', '/dev/null', "$OLLAMA/api/generate",
           '-d', "{\"model\":\"$m\",\"keep_alive\":0}");
  }
  print "Stopped.\n";
  exit 0;
}
