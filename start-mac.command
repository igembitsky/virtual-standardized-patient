#!/bin/sh
# Virtual Standardized Patient Simulator, macOS launcher.
# Double-click this file. It does three things, in order:
#   1. Makes sure Ollama is running, and downloads the patient model if it is missing.
#   2. Serves this folder on http://127.0.0.1:8756 using the Perl that macOS already ships.
#   3. Opens your browser there.
# Nothing is installed. Nothing leaves this computer. Press Control-C, or close
# this window, to stop.
cd "$(dirname "$0")" || exit 1

OLLAMA="http://127.0.0.1:11434"
MODEL="qwen3:4b-instruct"
# Any one of these is enough. The page picks the first it recognises.
KNOWN='"name":"(qwen3:4b-instruct|qwen3:4b|llama3.1:8b|granite4.1:3b)(:|")'

tags() { curl -s -m 3 "$OLLAMA/api/tags" 2>/dev/null; }

echo "Virtual Standardized Patient Simulator"
echo

# 1. Ollama
if ! tags >/dev/null; then
  echo "Ollama is not running. Opening it ..."
  if open -a Ollama 2>/dev/null; then
    i=0
    while [ $i -lt 40 ] && ! tags >/dev/null; do sleep 1; i=$((i+1)); done
  else
    echo
    echo "  Ollama is not installed. Get it from https://ollama.com/download"
    echo "  Install it, open it once, then double-click this file again."
    echo
  fi
fi

# 2. The model, downloaded once
if tags | grep -qE "$KNOWN"; then
  echo "Ollama is running and the patient model is ready."
elif tags >/dev/null; then
  echo "Downloading the patient model, $MODEL. About 2.5 GB, once."
  echo "Leave this window open. It can take a while."
  curl -sN "$OLLAMA/api/pull" -d "{\"name\":\"$MODEL\"}" 2>/dev/null | /usr/bin/perl -ne '
    $| = 1;
    my ($t) = /"total":(\d+)/;  my ($c) = /"completed":(\d+)/;
    if (/"error":"([^"]*)"/)          { print "\n  Problem: $1\n" }
    elsif (defined $t && defined $c && $t > 100e6)
                                      { printf "\r  %3d%% of %.1f GB", $c*100/$t, $t/1e9 }
    elsif (/"status":"success"/)      { print "\r  Download complete.        \n" }'
  if ! tags | grep -qE "$KNOWN"; then
    echo
    echo "  The download did not finish. Check your internet connection and run this again,"
    echo "  or open Terminal and run:  ollama pull $MODEL"
    echo
  fi
fi

# 3. Serve, and open the browser
echo
echo "Starting on http://127.0.0.1:8756 ..."
( sleep 1; open "http://127.0.0.1:8756/" ) &
exec /usr/bin/perl -x "$0"
#!/usr/bin/perl
use strict; use warnings; use IO::Socket::INET; use IO::Select; use Cwd 'abs_path';
use File::Path qw(rmtree);
# Where "Update" in the page gets the new files. VSP_ZIP overrides it for testing.
my $ZIP = $ENV{VSP_ZIP} || 'https://github.com/igembitsky/virtual-standardized-patient/archive/refs/heads/main.zip';
my %T = (html=>'text/html; charset=utf-8', js=>'application/javascript',
         css=>'text/css', json=>'application/json', txt=>'text/plain; charset=utf-8',
         png=>'image/png', jpg=>'image/jpeg', jpeg=>'image/jpeg', svg=>'image/svg+xml',
         ico=>'image/x-icon', md=>'text/plain; charset=utf-8');
my $root = abs_path('.');
my $srv = IO::Socket::INET->new(LocalAddr=>'127.0.0.1', LocalPort=>8756, Listen=>32,
                                Reuse=>1, Proto=>'tcp')
  or die "Could not open port 8756: $!\nThe simulator is probably already running. Look for its browser tab.\n";
print "Running. Open http://127.0.0.1:8756/\nPress Control-C, or close this window, to stop.\n";
$SIG{CHLD} = 'IGNORE';   # reap finished children automatically
while (my $c = $srv->accept) {
  # Serve each connection in a child, so one browser that connects and then sends
  # nothing cannot hold up every other request.
  my $pid = fork();
  if (!defined $pid) { close $c; next }
  if ($pid) { close $c; next }        # parent goes straight back to accepting
  close $srv;                          # child does not need the listening socket
  my $sel = IO::Select->new($c);
  unless ($sel->can_read(5)) { close $c; exit 0 }   # idle connection, drop it
  my $req = <$c>;
  unless (defined $req) { close $c; exit 0 }
  while (my $h = <$c>) { last if $h =~ /^\r?\n$/ }   # buffered, so no select here
  my ($method, $path) = $req =~ m{^(GET|POST)\s+(\S+)\s+HTTP} ? ($1, $2) : ('GET', '/');
  $path =~ s/\?.*$//;
  $path =~ s{%([0-9A-Fa-f]{2})}{chr(hex($1))}ge;
  $path = '/index.html' if $path eq '/';

  # GET /update says this launcher can update. POST /update does it: download the ZIP,
  # unpack it beside this folder, check it is complete, then copy it over this folder.
  # The old files stay until the whole ZIP has arrived and been checked.
  if ($path eq '/update') {
    my $body;
    if ($method eq 'GET') { $body = "can" }
    else {
      my ($ok, $msg) = do_update();
      $msg =~ s/["\\]//g;
      $body = $ok ? "{\"ok\":true,\"version\":\"$msg\"}" : "{\"ok\":false,\"error\":\"$msg\"}";
    }
    my $type = $method eq 'GET' ? 'text/plain' : 'application/json';
    print $c "HTTP/1.0 200 OK\r\nContent-Type: $type\r\nContent-Length: " . length($body)
           . "\r\nCache-Control: no-store\r\n\r\n$body";
    close $c; exit 0;
  }

  # a JSON listing of the cases folder, so new case files just appear
  if ($path eq '/cases/' or $path eq '/cases') {
    opendir(my $dh, "$root/cases");
    my @f = sort grep { /\.txt$/i && -f "$root/cases/$_" } readdir($dh);
    closedir $dh;
    my $body = '[' . join(',', map { my $s=$_; $s =~ s/"/\\"/g; "\"$s\"" } @f) . ']';
    print $c "HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n"
           . "Content-Length: " . length($body) . "\r\nCache-Control: no-store\r\n\r\n$body";
    close $c; exit 0;
  }

  my $file = abs_path($root . $path) || '';
  if ($file !~ m{^\Q$root\E/} || !-f $file) {
    print $c "HTTP/1.0 404 Not Found\r\nContent-Type: text/plain\r\n\r\nNot found\n";
    close $c; exit 0;
  }
  my ($ext) = $file =~ /\.([A-Za-z0-9]+)$/; $ext = lc($ext || 'txt');
  my $type = $T{$ext} || 'application/octet-stream';
  open my $fh, '<:raw', $file or do { close $c; exit 0 };
  my $body = do { local $/; <$fh> }; close $fh;
  print $c "HTTP/1.0 200 OK\r\nContent-Type: $type\r\nContent-Length: " . length($body)
         . "\r\nCache-Control: no-store\r\n\r\n";
  print $c $body;
  close $c;
  exit 0;
}

sub do_update {
  my @r = update_files();
  rmtree("$root/.update-tmp");      # whatever happened, leave no temporary folder behind
  return @r;
}
sub update_files {
  my $tmp = "$root/.update-tmp";
  rmtree($tmp); mkdir $tmp or return (0, "could not make a temporary folder");
  my $zip = "$tmp/latest.zip";
  system('curl', '-sL', '-m', '60', '-o', $zip, $ZIP);
  (-s $zip) or return (0, "the download did not finish");
  system('tar', '-xf', $zip, '-C', $tmp) == 0 or return (0, "could not unpack the download");
  opendir(my $dh, $tmp) or return (0, "could not read the download");
  my ($src) = map { "$tmp/$_" } grep { !/^\./ && -d "$tmp/$_" } readdir($dh);
  closedir $dh;
  ($src && -f "$src/index.html" && -f "$src/VERSION" && -d "$src/cases")
    or return (0, "the download was incomplete");
  system('cp', '-R', "$src/.", "$root/") == 0 or return (0, "could not copy the new files");
  open my $vf, '<', "$root/VERSION" or return (0, "could not read the new version");
  my $ver = <$vf>; close $vf; $ver =~ s/\s+//g;
  return (1, $ver);
}
