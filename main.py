import os
import time

import psycopg2

LAST_TRANSACTION_ID = 0
SHARD_COUNT = 2
WORKERS = ['port=7001 user=postgres', 'port=7002 user=postgres']
COORDINATOR = 'port=7000 user=postgres'

STEP = False


def connect(worker):
    if worker == 'coordinator':
        connstr = COORDINATOR
    else:
        connstr = WORKERS[worker]

    return psycopg2.connect(f'host={os.getcwd()}/data {connstr}')


def worker_for_account(name):
    shard_no = hash(name) % SHARD_COUNT
    return shard_no


def sql(worker, commands, params=tuple(), autocommit=True):
    conn = connect(worker)
    try:
        with conn.cursor() as curs:
            conn.autocommit = autocommit
            print(f'WORKER[{worker}]: executing SQL: {commands}; {params}')
            if STEP:
                input('Press Enter to continue...')
            curs.execute(commands, params)
            try:
                rows = curs.fetchall()
                print('Result:')
                for row in rows:
                    print(*row, sep=' | ')
                return rows
            except psycopg2.ProgrammingError:
                return []
    finally:
        conn.close()


def new_account(name, initial_balance):
    worker = worker_for_account(name)
    sql(worker, 'INSERT INTO accounts (name, balance) VALUES (%s, %s)',
            (name, initial_balance))


def balance(name):
    worker = worker_for_account(name)
    current_balance, = sql(worker, 'SELECT balance FROM accounts WHERE name = %s', (name,))
    return current_balance


def total_bank_liabilities():
    total = 0
    for worker in range(len(WORKERS)):
        rows = sql(worker, 'SELECT COALESCE(SUM(balance), 0) FROM accounts')
        total += rows[0][0]
    return total


def transfer_money(source, dest, amount):
    sql(worker_for_account(dest),
        'UPDATE accounts SET balance = balance + %s WHERE name = %s',
        (amount, dest))
    sql(worker_for_account(source),
        'UPDATE accounts SET balance = balance - %s WHERE name = %s',
        (amount, source))


def transfer_money_transaction(source, dest, amount):
    global LAST_TRANSACTION_ID
    transactions = []
    LAST_TRANSACTION_ID += 1
    transaction_id = f'piggybank_{LAST_TRANSACTION_ID}'

    try:
        worker = worker_for_account(dest)
        sql(worker,
            '''
            BEGIN;
            UPDATE accounts SET balance = balance + %s WHERE name = %s;
            PREPARE TRANSACTION %s;
            ''',
            (amount, dest, transaction_id), autocommit=True)
        transactions.append((worker, transaction_id))

        worker = worker_for_account(source)
        sql(worker,
            '''
            BEGIN;
            UPDATE accounts SET balance = balance - %s WHERE name = %s;
            PREPARE TRANSACTION %s;
            ''',
            (amount, source, transaction_id), autocommit=True)
        transactions.append((worker, transaction_id))
    except:
        for worker, transaction in transactions:
            sql(worker, 'ROLLBACK PREPARED %s', (transaction,), autocommit=True)
        raise
    else:
        for worker, transaction in transactions:
            sql(worker, 'COMMIT PREPARED %s', (transaction,), autocommit=True)


def transfer_money_transaction_safe(source, dest, amount):
    global LAST_TRANSACTION_ID

    with connect('coordinator') as conn:
        with conn.cursor() as coordinator:
            coordinator.execute('BEGIN')
            # Serialized access to make demo simpler
            coordinator.execute('LOCK TABLE transactions_to_commit')
            transactions = []
            LAST_TRANSACTION_ID += 1
            transaction_id = f'piggybank_{LAST_TRANSACTION_ID}'

            try:
                worker = worker_for_account(dest)
                sql(worker,
                    '''
                    BEGIN;
                    UPDATE accounts SET balance = balance + %s WHERE name = %s;
                    PREPARE TRANSACTION %s;
                    ''',
                    (amount, dest, transaction_id), autocommit=True)
                coordinator.execute('INSERT INTO transactions_to_commit VALUES (%s, %s)', (transaction_id, worker))

                worker = worker_for_account(source)
                sql(worker,
                    '''
                    BEGIN;
                    UPDATE accounts SET balance = balance - %s WHERE name = %s;
                    PREPARE TRANSACTION %s;
                    ''',
                    (amount, source, transaction_id), autocommit=True)
                coordinator.execute('INSERT INTO transactions_to_commit VALUES (%s, %s)', (transaction_id, worker))
            except:
                coordinator.execute('ROLLBACK')
                cleanup_transactions()
                raise
            else:
                coordinator.execute('COMMIT')
                cleanup_transactions()


def cleanup_transactions():
    with connect('coordinator') as conn, conn.cursor() as coordinator:
        coordinator.execute('BEGIN')
        # Serialized access to make demo simpler
        coordinator.execute('LOCK TABLE transactions_to_commit')
        coordinator.execute('SELECT transaction_id, worker_id FROM transactions_to_commit')
        for transaction_id, worker in coordinator.fetchall():
            sql(worker, 'COMMIT PREPARED %s', (transaction_id,))

        coordinator.execute('TRUNCATE TABLE transactions_to_commit')

        for worker in range(len(WORKERS)):
            for (transaction_id,) in sql(worker, 'SELECT gid FROM pg_prepared_xacts'):
                sql(worker, 'ROLLBACK PREPARED %s', (transaction_id,))

        coordinator.execute('COMMIT')
