# distributed-postgres
A simple demo of two-phase commit over PostgreSQL


## Setup

```bash
./create_dbs.sh

poetry install
poetry shell

ipython
```


## Demo

In the IPython shell, you have several functions to try:

- `new_account` - creates a new account and assigns it to a server
- `balance` - query account's balance
- `total_bank_liabilities` - find out how much money can customers withdraw

The following functions demonstrate two-phase commit properties:
- `transfer_money` - no distributed transaction, inconsistent if any worker fails
- `transfer_money_transaction` - may be inconsistent if coordinator fails
- `transfer_money_transaction_safe` - resistant to coordinator failure if coordinator
  executes `cleanup_transactions` on startup


If you set `main.STEP` to `True`, the app will always wait for confirmation before
executing a SQL command on a worker.

```python
In [1]: import main

In [2]: main.new_account('Peter', 1700)
WORKER[1]: executing SQL: INSERT INTO accounts (name, balance) VALUES (%s, %s); ('Peter', 1700)

In [3]: main.new_account('Deborah', 1700)
WORKER[1]: executing SQL: INSERT INTO accounts (name, balance) VALUES (%s, %s); ('Deborah', 1700)

In [4]: main.STEP = True

In [5]: main.transfer_money_transaction_safe(source='Peter', dest='Deborah', amount=10)
WORKER[1]: executing SQL:
                    BEGIN;
                    UPDATE accounts SET balance = balance + %s WHERE name = %s;
                    PREPARE TRANSACTION %s;
                    ; (10, 'Deborah', 'piggybank_1')
Press Enter to continue...
WORKER[1]: executing SQL:
                    BEGIN;
                    UPDATE accounts SET balance = balance - %s WHERE name = %s;
                    PREPARE TRANSACTION %s;
                    ; (10, 'Peter', 'piggybank_1')
Press Enter to continue...
```
