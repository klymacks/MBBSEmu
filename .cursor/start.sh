#!/usr/bin/env bash
#
# Cloud Agent per-boot start script for MBBSEmu.
#
# Defense-in-depth for the test suite's file-watcher usage. The primary fix is
# DOTNET_USE_POLLING_FILE_WATCHER=1 (configured in install.sh and captured in
# the snapshot), which makes .NET avoid inotify entirely. As an independent
# safety net we also raise the kernel inotify limits here, since these are
# runtime parameters that reset on every boot and are not captured in a disk
# snapshot. The command is idempotent and returns immediately; a failure to set
# them (e.g. restricted sudo) is non-fatal because polling already avoids the
# limit.
set -uo pipefail

sudo sysctl -w fs.inotify.max_user_instances=8192 || true
sudo sysctl -w fs.inotify.max_user_watches=524288 || true

echo "MBBSEmu start: inotify limits raised (polling watcher is the primary mitigation)."
