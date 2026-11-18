#!/usr/bin/env bash
set -eu
cp -R "$(dirname "$0")/files/." .
bash make-test-stream.sh
rm make-test-stream.sh
