#!/bin/sh
cd "$(dirname "$0")/.."
python3 bench/probe.py --runs 2 --variants V0 --tag=-live
python3 bench/probe.py --runs 3 --variants V0 --temp 0.3 --tag=-live-t03
python3 bench/bench.py
echo CHAIN-DONE
