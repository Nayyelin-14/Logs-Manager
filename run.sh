#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "run.sh is a thin wrapper around the root Makefile. Running: make up (local stack, project: lms_local)"
make up
