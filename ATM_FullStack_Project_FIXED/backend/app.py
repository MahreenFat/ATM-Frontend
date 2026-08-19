from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
from datetime import datetime, date
from abc import ABC, abstractmethod
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB_PATH = BASE.parent / "database" / "atm.db"

app = Flask(__name__, static_folder=str(BASE.parent / "frontend"), static_url_path="")
CORS(app)

class ATMError(Exception): pass
class InvalidPINError(ATMError): pass
class CardBlockedError(ATMError): pass
class InsufficientBalanceError(ATMError): pass
class InsufficientATMFundsError(ATMError): pass
class InvalidAmountError(ATMError): pass
class AccountInactiveError(ATMError): pass
class DailyLimitExceededError(ATMError): pass
class InvalidAccountError(ATMError): pass

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS customers(
      customer_id TEXT PRIMARY KEY, name TEXT NOT NULL, contact TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS accounts(
      account_no TEXT PRIMARY KEY, customer_id TEXT NOT NULL,
      account_type TEXT NOT NULL, balance REAL NOT NULL,
      pin TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE');
    CREATE TABLE IF NOT EXISTS cards(
      card_no TEXT PRIMARY KEY, customer_id TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'ACTIVE', failed_attempts INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS transactions(
      id TEXT PRIMARY KEY, account_no TEXT NOT NULL, type TEXT NOT NULL,
      amount REAL NOT NULL, destination_account TEXT, status TEXT NOT NULL,
      created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS atm_cash(
      denomination INTEGER PRIMARY KEY, quantity INTEGER NOT NULL);
    """)
    if cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0:
        cur.execute("INSERT INTO customers VALUES(?,?,?)", ("C001","Fatima Ahmed","fatima@example.com"))
        cur.execute("INSERT INTO accounts VALUES(?,?,?,?,?,?)", ("10002345","C001","Savings",75000,"1234","ACTIVE"))
        cur.execute("INSERT INTO accounts VALUES(?,?,?,?,?,?)", ("20004567","C001","Current",100000,"5678","ACTIVE"))
        cur.execute("INSERT INTO cards VALUES(?,?,?,?)", ("4111111111111111","C001","ACTIVE",0))
        for d,q in [(500,20),(1000,30),(5000,10)]:
            cur.execute("INSERT INTO atm_cash VALUES(?,?)",(d,q))
    con.commit(); con.close()

class Account(ABC):
    def __init__(self, row): self.row = row
    @property
    def balance(self): return float(self.row["balance"])
    @abstractmethod
    def can_withdraw(self, amount): ...
    @abstractmethod
    def withdrawal_limit(self): ...

class SavingsAccount(Account):
    def can_withdraw(self, amount): return self.balance - amount >= 5000
    def withdrawal_limit(self): return 50000

class CurrentAccount(Account):
    def can_withdraw(self, amount): return self.balance - amount >= -50000
    def withdrawal_limit(self): return 100000

class Transaction:
    def __init__(self, account_no, kind, amount, destination=None):
        self.id = "TXN-" + uuid.uuid4().hex[:8].upper()
        self.account_no, self.kind, self.amount, self.destination = account_no, kind, amount, destination
        self.created_at = datetime.now().isoformat(timespec="seconds")

def account_obj(row):
    if row["account_type"] == "Savings": return SavingsAccount(row)
    return CurrentAccount(row)

def record_tx(con, account_no, kind, amount, destination=None):
    t = Transaction(account_no, kind, amount, destination)
    con.execute("INSERT INTO transactions VALUES(?,?,?,?,?,?,?)",
                (t.id, t.account_no, t.kind, t.amount, t.destination, "SUCCESS", t.created_at))
    return t

def atm_total(con):
    return sum(r["denomination"]*r["quantity"] for r in con.execute("SELECT * FROM atm_cash"))

@app.route("/")
def index(): return send_from_directory(app.static_folder, "index.html")

@app.get("/api/health")
def health(): return jsonify({"ok": True})

@app.post("/api/login")
def login():
    data=request.json or {}; card_no=str(data.get("card_no","")).strip(); pin=str(data.get("pin",""))
    con=db()
    card=con.execute("SELECT * FROM cards WHERE card_no=?",(card_no,)).fetchone()
    if not card:
        con.close(); return jsonify(error="Invalid card"),404
    if card["status"]=="BLOCKED":
        con.close(); return jsonify(error="Card is blocked"),403
    account=con.execute("SELECT * FROM accounts WHERE customer_id=? ORDER BY account_no LIMIT 1",(card["customer_id"],)).fetchone()
    if pin != account["pin"]:
        attempts=card["failed_attempts"]+1; status="BLOCKED" if attempts>=3 else "ACTIVE"
        con.execute("UPDATE cards SET failed_attempts=?,status=? WHERE card_no=?",(attempts,status,card_no)); con.commit(); con.close()
        msg="Three incorrect PIN attempts. Card is now blocked." if status=="BLOCKED" else f"Incorrect PIN. Attempts remaining: {3-attempts}"
        return jsonify(error=msg, blocked=status=="BLOCKED"),401
    con.execute("UPDATE cards SET failed_attempts=0 WHERE card_no=?",(card_no,)); con.commit()
    customer=con.execute("SELECT * FROM customers WHERE customer_id=?",(card["customer_id"],)).fetchone()
    accounts=con.execute("SELECT account_no,account_type,balance,status FROM accounts WHERE customer_id=?",(card["customer_id"],)).fetchall()
    con.close()
    return jsonify(customer=dict(customer),accounts=[dict(x) for x in accounts],card_status=card["status"])

@app.get("/api/account/<account_no>")
def account_info(account_no):
    con=db(); row=con.execute("SELECT account_no,account_type,balance,status FROM accounts WHERE account_no=?",(account_no,)).fetchone()
    con.close()
    if not row: return jsonify(error="Account not found"),404
    return jsonify(account=dict(row))

@app.post("/api/deposit")
def deposit():
    data=request.json or {}; amount=float(data.get("amount",0)); no=str(data.get("account_no",""))
    if amount<=0: return jsonify(error="Deposit amount must be positive"),400
    con=db(); row=con.execute("SELECT * FROM accounts WHERE account_no=?",(no,)).fetchone()
    if not row: con.close(); return jsonify(error="Invalid account"),404
    if row["status"]!="ACTIVE": con.close(); return jsonify(error="Account inactive"),400
    con.execute("UPDATE accounts SET balance=balance+? WHERE account_no=?",(amount,no))
    t=record_tx(con,no,"DEPOSIT",amount); con.commit()
    new=con.execute("SELECT balance FROM accounts WHERE account_no=?",(no,)).fetchone()["balance"]; con.close()
    return jsonify(message="Deposit successful",transaction_id=t.id,balance=new)

@app.post("/api/withdraw")
def withdraw():
    data=request.json or {}; amount=float(data.get("amount",0)); no=str(data.get("account_no",""))
    if amount<500 or amount>50000: return jsonify(error="Withdrawal must be between Rs. 500 and Rs. 50,000"),400
    con=db(); row=con.execute("SELECT * FROM accounts WHERE account_no=?",(no,)).fetchone()
    if not row: con.close(); return jsonify(error="Invalid account"),404
    obj=account_obj(row)
    if not obj.can_withdraw(amount): con.close(); return jsonify(error="Insufficient available balance"),400
    if amount > obj.withdrawal_limit(): con.close(); return jsonify(error="Withdrawal limit exceeded"),400
    remaining=int(amount); selected={}
    for note in sorted([500,1000,5000],reverse=True):
        q=con.execute("SELECT quantity FROM atm_cash WHERE denomination=?",(note,)).fetchone()["quantity"]
        take=min(q,remaining//note)
        if take: selected[note]=take; remaining-=note*take
    if remaining: con.close(); return jsonify(error="ATM cannot dispense this denomination combination"),400
    if amount>atm_total(con): con.close(); return jsonify(error="ATM has insufficient cash"),400
    con.execute("UPDATE accounts SET balance=balance-? WHERE account_no=?",(amount,no))
    for note,q in selected.items(): con.execute("UPDATE atm_cash SET quantity=quantity-? WHERE denomination=?",(q,note))
    t=record_tx(con,no,"WITHDRAWAL",amount); con.commit()
    new=con.execute("SELECT balance FROM accounts WHERE account_no=?",(no,)).fetchone()["balance"]; con.close()
    return jsonify(message="Withdrawal successful",transaction_id=t.id,balance=new,notes=selected)

@app.post("/api/transfer")
def transfer():
    data=request.json or {}; sender=str(data.get("from_account","")); receiver=str(data.get("to_account","")); amount=float(data.get("amount",0))
    if amount<=0: return jsonify(error="Transfer amount must be positive"),400
    if sender==receiver: return jsonify(error="Sender and receiver cannot be the same"),400
    con=db(); a=con.execute("SELECT * FROM accounts WHERE account_no=?",(sender,)).fetchone(); b=con.execute("SELECT * FROM accounts WHERE account_no=?",(receiver,)).fetchone()
    if not a or not b: con.close(); return jsonify(error="Sender or receiver account not found"),404
    obj=account_obj(a)
    if not obj.can_withdraw(amount): con.close(); return jsonify(error="Insufficient balance"),400
    con.execute("UPDATE accounts SET balance=balance-? WHERE account_no=?",(amount,sender))
    con.execute("UPDATE accounts SET balance=balance+? WHERE account_no=?",(amount,receiver))
    t1=record_tx(con,sender,"TRANSFER",amount,receiver); t2=record_tx(con,receiver,"TRANSFER_CREDIT",amount,sender)
    con.commit(); new=con.execute("SELECT balance FROM accounts WHERE account_no=?",(sender,)).fetchone()["balance"]; con.close()
    return jsonify(message="Transfer successful",transaction_id=t1.id,balance=new)

@app.post("/api/change-pin")
def change_pin():
    data=request.json or {}; no=str(data.get("account_no","")); old=str(data.get("old_pin","")); new=str(data.get("new_pin",""))
    if len(new)!=4 or not new.isdigit(): return jsonify(error="PIN must be exactly 4 digits"),400
    con=db(); row=con.execute("SELECT * FROM accounts WHERE account_no=?",(no,)).fetchone()
    if not row: con.close(); return jsonify(error="Invalid account"),404
    if row["pin"]!=old: con.close(); return jsonify(error="Old PIN is incorrect"),400
    con.execute("UPDATE accounts SET pin=? WHERE account_no=?",(new,no)); con.commit(); con.close()
    return jsonify(message="PIN changed successfully")

@app.get("/api/statement/<account_no>")
def statement(account_no):
    con=db(); rows=con.execute("SELECT * FROM transactions WHERE account_no=? ORDER BY created_at DESC LIMIT 5",(account_no,)).fetchall(); con.close()
    return jsonify(transactions=[dict(x) for x in rows])

@app.get("/api/cash")
def cash():
    con=db(); rows=con.execute("SELECT * FROM atm_cash ORDER BY denomination").fetchall(); total=atm_total(con); con.close()
    return jsonify(notes=[dict(x) for x in rows],total=total)

if __name__=="__main__":
    init_db()
    app.run(host="127.0.0.1",port=5000,debug=False)
