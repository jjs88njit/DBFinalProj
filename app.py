from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'term_project_key_v2'


def init_db():
    conn = sqlite3.connect('banking.db')
    with open('schema.sql', 'r') as f:
        conn.executescript(f.read())
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('banking.db')
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username'] 
        password = request.form['password']
        
        if username == 'admin' and password == 'admin123':
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))

        conn = get_db_connection()
        
        user = conn.execute('SELECT * FROM CUSTOMER WHERE CSSN = ? AND Password = ?', (username, password)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['CSSN'] # CSSN is the ID
            session['role'] = 'user'
            session['username'] = user['FName'] + " " + user['LName']
            return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid CSSN or Password', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        cssn = request.form['cssn']
        fname = request.form['fname']
        lname = request.form['lname']
        password = request.form['password']
        
        conn = get_db_connection()
        try:
        
            conn.execute("INSERT INTO CUSTOMER (CSSN, FName, LName, Password) VALUES (?, ?, ?, ?)", 
                         (cssn, fname, lname, password))
            
        
        
            max_id_row = conn.execute("SELECT MAX(AccountNum) as m FROM ACCOUNTS").fetchone()
            new_acc_id = (max_id_row['m'] or 500000) + 1
            
            conn.execute("INSERT INTO ACCOUNTS (AccountNum, Balance, AccountType, LastAccessBy) VALUES (?, ?, ?, ?)",
                         (new_acc_id, 0.0, 'Checking', cssn))
            conn.execute("INSERT INTO CHECKING (AccountNum, Overdrafts) VALUES (?, ?)", (new_acc_id, 0))
            
        
            conn.execute("INSERT INTO ACCOUNT_HOLDERS (AccountNum, CSSN) VALUES (?, ?)", (new_acc_id, cssn))
            
            conn.commit()
            flash(f'Registration successful! Your CSSN is {cssn}. Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/dashboard')
def user_dashboard():
    if 'user_id' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user_id = session['user_id']
    
    
    query = '''
        SELECT a.AccountNum, a.AccountType, a.Balance 
        FROM ACCOUNTS a
        JOIN ACCOUNT_HOLDERS ah ON a.AccountNum = ah.AccountNum
        WHERE ah.CSSN = ?
    '''
    
    
    search_bal = request.args.get('search_balance')
    if search_bal:
        query += ' AND a.Balance >= ' + search_bal

    accounts = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    return render_template('dashboard.html', accounts=accounts, user=session['username'])

@app.route('/transfer', methods=['POST'])
def transfer():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    from_acc_id = request.form['from_account']
    to_acc_id = request.form['to_account_id']
    amount = float(request.form['amount'])
    
    conn = get_db_connection()
    
    
    acc_check = conn.execute('''
        SELECT a.Balance FROM ACCOUNTS a 
        JOIN ACCOUNT_HOLDERS ah ON a.AccountNum = ah.AccountNum 
        WHERE a.AccountNum = ? AND ah.CSSN = ?
    ''', (from_acc_id, session['user_id'])).fetchone()
    
    if acc_check and acc_check['Balance'] >= amount:
    
        if conn.execute('SELECT 1 FROM ACCOUNTS WHERE AccountNum = ?', (to_acc_id,)).fetchone():
    
            conn.execute('UPDATE ACCOUNTS SET Balance = Balance - ? WHERE AccountNum = ?', (amount, from_acc_id))
            conn.execute('UPDATE ACCOUNTS SET Balance = Balance + ? WHERE AccountNum = ?', (amount, to_acc_id))
            
    
            max_code = conn.execute("SELECT MAX(Code) as m FROM TRANSACTIONS").fetchone()
            new_code = (max_code['m'] or 0) + 1
            now_date = datetime.now().strftime('%Y-%m-%d')
            now_time = datetime.now().strftime('%H:%M:%S')
            
            conn.execute('''INSERT INTO TRANSACTIONS (Code, Type, TransactionDate, Hour, Amount, AccntNum) 
                            VALUES (?, ?, ?, ?, ?, ?)''', 
                         (new_code, 'Transfer', now_date, now_time, amount, from_acc_id))
            
            conn.commit()
            flash('Transfer Successful!', 'success')
        else:
            flash('Destination Account ID not found.', 'danger')
    else:
        flash('Insufficient funds or Invalid Account.', 'danger')
        
    conn.close()
    return redirect(url_for('user_dashboard'))

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin': 
            return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    
    data = {
        'employees': conn.execute('SELECT * FROM EMPLOYEE').fetchall(),
        'branches': conn.execute('SELECT * FROM BRANCH').fetchall(),
        'customers': conn.execute('SELECT * FROM CUSTOMER').fetchall(),
        'accounts': conn.execute('SELECT * FROM ACCOUNTS').fetchall(),
        'savings': conn.execute('SELECT * FROM SAVINGS').fetchall(),
        'checking': conn.execute('SELECT * FROM CHECKING').fetchall(),
        'moneymarket': conn.execute('SELECT * FROM MONEYMARKET').fetchall(),
        'account_holders': conn.execute('SELECT * FROM ACCOUNT_HOLDERS').fetchall(),
        'loans': conn.execute('SELECT * FROM LOANS').fetchall(),
        'transactions': conn.execute('SELECT * FROM TRANSACTIONS').fetchall()
    }
    
    conn.close()
    return render_template('admin.html', data=data)

if __name__ == '__main__':
    try:
        init_db()
        print("Database initialized with provided schema.")
    except Exception as e:
        print(f"DB Error: {e}")
        
    app.run(debug=True)