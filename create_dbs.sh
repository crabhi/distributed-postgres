#!/bin/bash

set -exuo pipefail

PG=/usr/lib/postgresql/15/bin
export PGUSER=postgres
export PGHOST="$(pwd)/data"


new_db() {
    local i="$1"
    local port="$2"

    "$PG"/initdb "$PGHOST"/worker"$i" --auth-local=trust --username=postgres

    cat >> data/worker"$i"/postgresql.conf <<EOF
unix_socket_directories = '$PGHOST'
port = $port
listen_addresses = 'localhost'
max_prepared_transactions = 100
EOF

    "$PG"/pg_ctl -D data/worker"$i" -l data/worker"$i".log start
}


for i in $(seq 2); do
    port=$(( 7000 + i ))
    new_db "$i" "$port"

    psql "port=$port" -c 'CREATE TABLE accounts (
            name VARCHAR PRIMARY KEY,
            balance DECIMAL NOT NULL CHECK (balance >= 0)
        )'
done


new_db 0 7000
psql "port=7000" -c 'CREATE TABLE transactions_to_commit (
    transaction_id VARCHAR,
    worker_id INT
)'
