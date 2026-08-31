#!/usr/bin/env bash
#
# Cloud Agent install script for MBBSEmu.
#
# Idempotent repository bootstrap: installs the pinned .NET SDK (if missing),
# restores NuGet packages, and builds the solution in Release. Safe to run
# repeatedly and against a cached/partially-prepared VM.
set -euo pipefail

DOTNET_CHANNEL="10.0"
DOTNET_INSTALL_DIR="/usr/share/dotnet"

# Resolve the repository root from this script's location so the command works
# regardless of the current working directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export DOTNET_CLI_TELEMETRY_OPTOUT=1
export DOTNET_NOLOGO=1
export PATH="/usr/local/bin:${DOTNET_INSTALL_DIR}:${PATH}"

# 1. Install the .NET 10 SDK if a 10.x SDK is not already present.
#    dotnet-install.sh is itself idempotent, but we skip the download entirely
#    when a matching SDK is already installed.
if ! dotnet --list-sdks 2>/dev/null | grep -q '^10\.'; then
  echo "Installing .NET SDK (channel ${DOTNET_CHANNEL})..."
  curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh
  chmod +x /tmp/dotnet-install.sh
  sudo mkdir -p "${DOTNET_INSTALL_DIR}"
  sudo /tmp/dotnet-install.sh --channel "${DOTNET_CHANNEL}" --install-dir "${DOTNET_INSTALL_DIR}"
  sudo ln -sf "${DOTNET_INSTALL_DIR}/dotnet" /usr/local/bin/dotnet
else
  echo ".NET 10 SDK already installed: $(dotnet --version)"
fi

cd "${REPO_ROOT}"

# 2. Restore and build the full solution.
dotnet restore
dotnet build --no-restore --configuration Release

echo "MBBSEmu install complete."
