#!/bin/bash

set -exuo pipefail

PG=/usr/lib/postgresql/15/bin

for i in $(seq 2); do
    port=$(( 7000 + i ))
    "$PG"/initdb data/worker"$i" --auth-local=trust

    cat >> data/worker"$i"/postgresql.conf <<EOF
unix_socket_directories = '..'
port = $port
listen_addresses = 'localhost'
EOF

    "$PG"/pg_ctl -D data/worker"$i" -l data/worker"$i".log start

    psql "dbname=postgres host=$(pwd)/data port=$port" -c 'CREATE TABLE accounts (
            name VARCHAR PRIMARY KEY,
            balance DECIMAL NOT NULL CHECK (balance >= 0)
        )'
done

