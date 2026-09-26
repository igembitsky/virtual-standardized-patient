# Sourced after a Start file was opened: wait for the simulator, check it answers, press
# Quit, and check it stops.
for i in $(seq 1 60); do
  [ "$(curl -s -m 2 http://127.0.0.1:8756/update)" = "can" ] && break
  sleep 1
done
[ "$(curl -s -m 2 http://127.0.0.1:8756/update)" = "can" ] || { echo "FAIL: the simulator did not start"; exit 1; }
echo "pass: the simulator started from its Start file"
page=$(curl -s -m 5 http://127.0.0.1:8756/)
case "$page" in *"Virtual Standardized Patient"*) ;; *) echo "FAIL: no page"; exit 1 ;; esac
echo "pass: it serves the page"
log=$(curl -s -m 5 http://127.0.0.1:8756/log)
case "$log" in *"Starting version"*) ;; *) echo "FAIL: no log"; exit 1 ;; esac
echo "pass: it keeps a log"
curl -s -m 5 -X POST http://127.0.0.1:8756/quit >/dev/null
for i in $(seq 1 15); do
  curl -s -m 1 http://127.0.0.1:8756/update >/dev/null || { echo "pass: Quit stopped it"; return 0 2>/dev/null || exit 0; }
  sleep 1
done
echo "FAIL: it did not stop after Quit"; exit 1
