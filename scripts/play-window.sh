#!/usr/bin/env bash
# Existing desktop files point here. Hand off to the packaged-style launcher.
exec "$(dirname "$(readlink -f "$0")")/FinnsRealm" "$@"
