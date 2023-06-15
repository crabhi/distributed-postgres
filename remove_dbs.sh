#!/bin/bash

set -exuo pipefail

PG=/usr/lib/postgresql/15/bin

for i in $(seq 0 2); do
    "$PG"/pg_ctl -D data/worker"$i" stop || true
done

rm -rf data/worker*
