#!/usr/bin/env bash
# Install Stockfish binary for Render native Python builds (web + Celery worker).
set -euo pipefail

ROOT="${1:-.}"
STOCKFISH_DIR="${ROOT}/stockfish"
BINARY="${STOCKFISH_DIR}/stockfish"

if [ -x "${BINARY}" ]; then
  echo "Stockfish already installed at ${BINARY}"
  exit 0
fi

mkdir -p "${STOCKFISH_DIR}"
TMP_DIR="${STOCKFISH_DIR}/.build"
rm -rf "${TMP_DIR}"
mkdir -p "${TMP_DIR}"
cd "${TMP_DIR}"

wget -q https://github.com/official-stockfish/Stockfish/releases/download/sf_17.1/stockfish-ubuntu-x86-64-avx2.tar
tar -xf stockfish-ubuntu-x86-64-avx2.tar

# Tar layout: stockfish/stockfish-ubuntu-x86-64-avx2 (single binary)
mv stockfish/stockfish-ubuntu-x86-64-avx2 "${BINARY}"
chmod +x "${BINARY}"

rm -rf "${TMP_DIR}"
echo "Stockfish installed at ${BINARY}"
