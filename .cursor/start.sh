#!/usr/bin/env bash
#
# Cloud Agent per-boot start script for MBBSEmu.
#
# Raises the kernel inotify limits. The xUnit test suite runs test collections
# in parallel, and each host/config fixture opens a FileSystemWatcher (inotify
# instance). The default limit of 128 instances is exhausted under parallelism,
# causing ~1000 spurious failures with:
#   IOException: The configured user limit (128) on the number of inotify
#   instances has been reached ...
#
# These are kernel runtime parameters that reset on every boot and are NOT
# captured in a disk snapshot, so they must be reconciled here on each start.
# The command is idempotent and returns immediately.
set -euo pipefail

sudo sysctl -w fs.inotify.max_user_instances=8192
sudo sysctl -w fs.inotify.max_user_watches=524288

echo "MBBSEmu start: inotify limits raised."
