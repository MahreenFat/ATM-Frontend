let session = null, account = null;

// Automatically detect local environment vs live hosting (PythonAnywhere)
const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? (window.location.port === '5000' ? '' : 'http://127.0.0.1:5000')
  : '';

const api = p => `${API_BASE}/api${p}`;

async function call(path, options = {}) {
  try {
    const r = await fetch(api(path), {
      headers: { 'Content-Type': 'application/json' },
      ...options
    });
    const text = await r.text();
    let d = {};
    try { 
      d = text ? JSON.parse(text) : {}; 
    } catch (_) { 
      throw new Error('Backend returned an invalid response.'); 
    }
    if (!r.ok) throw new Error(d.error || 'Request failed');
    return d;
  } catch (e) {
    if (e instanceof TypeError || String(e.message).toLowerCase().includes('failed to fetch')) {
      throw new Error('Cannot connect to ATM backend. Please check server status or connection.');
    }
    throw e;
  }
}

function show(id) {
  document.querySelectorAll('.screen').forEach(x => x.classList.add('hidden'));
  document.getElementById(id).classList.remove('hidden');
}

function modal(html) {
  document.getElementById('modalContent').innerHTML = html;
  document.getElementById('modal').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modal').classList.add('hidden');
}

function money(x) {
  return `Rs. ${Number(x).toLocaleString('en-PK', { maximumFractionDigits: 2 })}`;
}

async function login() {
  try {
    const d = await call('/login', {
      method: 'POST',
      body: JSON.stringify({
        card_no: document.getElementById('cardNo').value,
        pin: document.getElementById('pin').value
      })
    });
    session = d; 
    account = d.accounts[0]; 
    render(); 
    show('menuView');
  } catch (e) {
    alert(e.message); 
    if (e.message.toLowerCase().includes('blocked')) {
      document.getElementById('pin').value = '';
    }
  }
}

function render() {
  document.getElementById('customerName').textContent = `Welcome, ${session.customer.name}`;
  document.getElementById('accountLabel').textContent = `${account.account_type} Account • ${account.account_no}`;
  document.getElementById('balance').textContent = money(account.balance);
  document.getElementById('accountButtons').innerHTML = session.accounts.map(a => `<button onclick="selectAccount('${a.account_no}')">${a.account_type} • ${a.account_no}</button>`).join('');
}

async function selectAccount(no) {
  account = session.accounts.find(x => x.account_no === no);
  const d = await call(`/account/${no}`);
  account = d.account;
  render();
}

function balance() {
  modal(`<h2>Current Balance</h2><div style="font-size:32px;font-weight:800">${money(account.balance)}</div><p>${account.account_type} Account — ${account.account_no}</p>`);
}

function form(title, fields, submit) {
  modal(`<h2>${title}</h2>${fields.map(f => `<label>${f.label}</label><input id="f_${f.id}" ${f.type === 'password' ? 'type="password"' : ''} placeholder="${f.placeholder || ''}">`).join('')}<button class="action" onclick="${submit}">Continue</button>`);
}

async function deposit() {
  form('Deposit', [{ id: 'amount', label: 'Amount (Rs.)' }], "doDeposit()");
}

async function doDeposit() {
  try {
    const d = await call('/deposit', {
      method: 'POST',
      body: JSON.stringify({
        account_no: account.account_no,
        amount: Number(document.getElementById('f_amount').value)
      })
    });
    account.balance = d.balance;
    closeModal();
    render();
    alert(`${d.message}\n${money(d.balance)}\nTransaction: ${d.transaction_id}`);
  } catch (e) {
    alert(e.message);
  }
}

async function withdraw() {
  form('Withdraw', [{ id: 'amount', label: 'Amount (Rs.)', placeholder: '500 - 50,000' }], "doWithdraw()");
}

async function doWithdraw() {
  try {
    const d = await call('/withdraw', {
      method: 'POST',
      body: JSON.stringify({
        account_no: account.account_no,
        amount: Number(document.getElementById('f_amount').value)
      })
    });
    account.balance = d.balance;
    closeModal();
    render();
    alert(`${d.message}\n${money(d.balance)}\nTransaction: ${d.transaction_id}`);
  } catch (e) {
    alert(e.message);
  }
}

async function transfer() {
  form('Transfer', [{ id: 'to', label: 'Receiver Account' }, { id: 'amount', label: 'Amount (Rs.)' }], "doTransfer()");
}

async function doTransfer() {
  try {
    const d = await call('/transfer', {
      method: 'POST',
      body: JSON.stringify({
        from_account: account.account_no,
        to_account: document.getElementById('f_to').value,
        amount: Number(document.getElementById('f_amount').value)
      })
    });
    account.balance = d.balance;
    closeModal();
    render();
    alert(`${d.message}\n${money(d.balance)}`);
  } catch (e) {
    alert(e.message);
  }
}

function changePin() {
  form('Change PIN', [{ id: 'old', label: 'Old PIN', type: 'password' }, { id: 'new', label: 'New 4-digit PIN', type: 'password' }], "doPin()");
}

async function doPin() {
  try {
    const d = await call('/change-pin', {
      method: 'POST',
      body: JSON.stringify({
        account_no: account.account_no,
        old_pin: document.getElementById('f_old').value,
        new_pin: document.getElementById('f_new').value
      })
    });
    closeModal();
    alert(d.message);
  } catch (e) {
    alert(e.message);
  }
}

async function statement() {
  try {
    const d = await call(`/statement/${account.account_no}`);
    let s = d.transactions.map(t => `${t.created_at.replace('T', ' ')} | ${t.type.padEnd(15)} | Rs.${Number(t.amount).toLocaleString()}${t.destination_account ? ' -> ' + t.destination_account : ''}`).join('\n');
    modal(`<h2>Mini Statement</h2><div class="statement">${s || 'No transactions yet.'}\n\nCurrent Balance: ${money(account.balance)}</div>`);
  } catch (e) {
    alert(e.message);
  }
}

async function cash() {
  try {
    const d = await call('/cash');
    modal(`<h2>ATM Cash</h2>${d.notes.map(n => `<p>Rs. ${n.denomination.toLocaleString()} × ${n.quantity}</p>`).join('')}<hr><b>Total: ${money(d.total)}</b>`);
  } catch (e) {
    alert(e.message);
  }
}

function logout() {
  session = null;
  account = null;
  document.getElementById('pin').value = '';
  show('loginView');
}

document.getElementById('modal').addEventListener('click', e => {
  if (e.target.id === 'modal') closeModal();
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});