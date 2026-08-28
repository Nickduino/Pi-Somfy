#!/usr/bin/env python3
"""Patch pigpiod's unconditional /dev/pigerr error-FIFO setup (build-time only).

pigpiod.c's main() always does unlink()+mkfifo()+chmod()+freopen() on
/dev/pigerr, with no command-line flag to disable it (verified against
joan2937/pigpio master — -f only gates the /dev/pigpio *command* FIFO, not
this error-output companion). In a container where /dev is read-only except
for the specific device nodes this add-on's config.yaml requests, mkfifo()
silently fails and the following chmod() aborts the whole daemon.

This add-on only talks to pigpiod over its TCP socket interface, so the
error FIFO is unneeded — replace its setup with a direct assignment to the
process's own stderr, which the container already captures as add-on logs.
"""
import re
import sys

path = sys.argv[1]
with open(path) as f:
    src = f.read()

pattern = re.compile(
    r"/\*\s*create pipe for error reporting\s*\*/.*?"
    r"errFifo\s*=\s*freopen\(PI_ERRFIFO,\s*\"w\+\",\s*stderr\);",
    re.DOTALL)

patched, count = pattern.subn(
    "/* patched: container /dev is read-only, skip the error FIFO */\n"
    "   errFifo = stderr;",
    src, count=1)

if count != 1:
    sys.exit("patch_pigpiod.py: expected pigpiod.c pattern not found — "
             "pigpio source may have changed upstream, update the patch")

with open(path, "w") as f:
    f.write(patched)

print("pigpiod.c patched: error FIFO disabled (using stderr directly)")
