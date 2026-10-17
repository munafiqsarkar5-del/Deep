import os, sqlite3, secrets, re
from pathlib import Path
from functools import wraps
from urllib.parse import quote
from flask import Flask, request, redirect, url_for, session, flash, render_template_string, abort, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

ROOT=Path(__file__).resolve().parent
UPLOADS=Path(os.environ.get('UPLOAD_FOLDER', str(ROOT/'static'/'uploads')))
UPLOADS.mkdir(parents=True,exist_ok=True)
DB_PATH=Path(os.environ.get('DATABASE_PATH',str(ROOT/'store.db')))
DB_PATH.parent.mkdir(parents=True,exist_ok=True)
app=Flask(__name__)
app.secret_key=os.environ.get('SECRET_KEY',secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH']=4*1024*1024
ADMIN_USER=os.environ.get('ADMIN_USERNAME','admin')
ADMIN_PASS=os.environ.get('ADMIN_PASSWORD','fankarx')
WHATSAPP=''.join(x for x in os.environ.get('WHATSAPP_NUMBER','033303257478') if x.isdigit())
if WHATSAPP.startswith('0'): WHATSAPP='92'+WHATSAPP[1:]
DISCORD=os.environ.get('DISCORD_USERNAME','mahijuti001')
DISCORD_URL=os.environ.get('DISCORD_URL','https://discord.com/app')
ALLOWED={'jpg','jpeg','png','webp'}

def connect():
    c=sqlite3.connect(DB_PATH,timeout=10); c.row_factory=sqlite3.Row
    c.execute('PRAGMA busy_timeout=5000'); return c

with connect() as c:
    c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, coins INTEGER NOT NULL DEFAULT 10, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    user_cols={row['name'] for row in c.execute('PRAGMA table_info(users)').fetchall()}
    if 'coins' not in user_cols: c.execute('ALTER TABLE users ADD COLUMN coins INTEGER NOT NULL DEFAULT 10')
    c.execute('CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, price TEXT NOT NULL, coin_cost INTEGER NOT NULL DEFAULT 1, description TEXT DEFAULT "", image_url TEXT DEFAULT "", image_file TEXT DEFAULT "", sold_out INTEGER DEFAULT 0)')
    product_cols={row['name'] for row in c.execute('PRAGMA table_info(products)').fetchall()}
    if 'coin_cost' not in product_cols: c.execute('ALTER TABLE products ADD COLUMN coin_cost INTEGER NOT NULL DEFAULT 1')
    c.execute('CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, order_key TEXT UNIQUE NOT NULL, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, product_name TEXT NOT NULL, product_price TEXT NOT NULL, coin_cost INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    order_cols={row['name'] for row in c.execute('PRAGMA table_info(orders)').fetchall()}
    if 'coin_cost' not in order_cols: c.execute('ALTER TABLE orders ADD COLUMN coin_cost INTEGER NOT NULL DEFAULT 0')

STYLE = '''
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 10% 0%,#260b17,transparent 38%),radial-gradient(ellipse at 90% 5%,#08242c,transparent 30%),#07080c;color:#f5f7fb;font-family:Arial,sans-serif;min-height:100vh}
.wrap{width:min(1080px,92%);margin:auto}.top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:21px 0;border-bottom:1px solid #252c3a;flex-wrap:wrap}.logo{font-size:25px;font-weight:1000;letter-spacing:2px}.logo b{color:#ff2448}.tag,.eyebrow{color:#45f3ff;font-size:10px;letter-spacing:3px;font-weight:900;margin-top:5px}.nav,.actions{display:flex;gap:8px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;padding:10px 13px;border-radius:8px;border:1px solid #394252;background:#171c26;color:white;font-weight:800;font-size:12px;cursor:pointer;text-decoration:none}.red{background:linear-gradient(135deg,#ff2448,#a40025);border-color:#ff2448}.cyan{color:#45f3ff;border-color:#45f3ff}.muted{color:#9ba6b8;line-height:1.6}
.hero{padding:38px 0 25px;display:grid;grid-template-columns:1.4fr 1fr;gap:22px;align-items:center}.hero h1{font-size:clamp(37px,6vw,62px);line-height:.98;margin:12px 0}.hero h1 em{font-style:normal;color:#ff2448}.terminal,.formbox{background:#10131b;border:1px solid #30394a;border-radius:13px;padding:18px}.termline{font:13px monospace;color:#a8ffb7;margin:11px 0}.termline b{color:#45f3ff}
.sectionhead{display:flex;align-items:end;justify-content:space-between;gap:12px;margin:24px 0 16px}.sectionhead h2{margin:5px 0;font-size:24px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px;padding-bottom:35px}.product{border:1px solid #252c3a;border-radius:12px;overflow:hidden;background:#10141c}.product img,.noimg{width:100%;height:175px;object-fit:cover;background:#0b0e14}.noimg{display:grid;place-items:center;color:#667085;font-size:12px}.pbody{padding:14px}.pbody h3{margin:0 0 8px;overflow-wrap:anywhere}.desc{font-size:13px;color:#9ba6b8;line-height:1.5;min-height:38px;white-space:pre-wrap;overflow-wrap:anywhere}.pfoot{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:13px}.price{font-size:17px;font-weight:900;color:#45f3ff}.sold{font-size:10px;color:#ff8a9d;border:1px solid #ff244866;border-radius:7px;padding:8px;font-weight:bold}
.flash{margin:14px 0;padding:11px;border-radius:8px;background:#35121b;border:1px solid #ff244866}.field{display:block;margin:13px 0}.field span{display:block;font-size:12px;color:#b6c0d0;margin-bottom:7px}.field input,.field textarea{width:100%;padding:11px;border:1px solid #30394a;border-radius:8px;background:#080b11;color:white}.field textarea{min-height:75px}.hint{font-size:12px;color:#9ba6b8;line-height:1.5}.formbox{margin:22px 0}.adminlist{display:grid;gap:9px;margin-bottom:35px}.adminrow{display:grid;grid-template-columns:58px 1fr auto;align-items:center;gap:11px;background:#111620;border:1px solid #252c3a;border-radius:10px;padding:10px}.adminrow img{width:58px;height:55px;object-fit:cover;border-radius:6px}.adminrow p{margin:4px 0;color:#9ba6b8;font-size:12px}footer{border-top:1px solid #252c3a;padding:20px 0 28px;color:#748094;font-size:12px;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
@media(max-width:720px){.hero{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.adminrow{grid-template-columns:50px 1fr}.adminrow img{width:50px;height:50px}.adminrow .actions{grid-column:1/-1}}@media(max-width:430px){.grid{grid-template-columns:1fr}.product img,.noimg{height:205px}}
'''
HOME = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DEEP WEB</title><style>'''+STYLE+'''</style></head><body><div class="wrap">
<header class="top"><a href="/" style="color:inherit;text-decoration:none"><div class="logo">DEEP <b>WEB</b><div class="tag">/// DIGITAL MARKETPLACE</div></div></a><nav class="nav"><a class="btn cyan" href="#products">STORE</a>{% if username %}<span class="btn">Hi, {{ username }} · 🪙 {{ coins }} coins</span><a class="btn" href="/logout">LOG OUT</a>{% else %}<a class="btn" href="/signup">CREATE ACCOUNT</a><a class="btn" href="/login">LOGIN</a>{% endif %}</nav></header>
<section class="hero"><div><div class="eyebrow">[ SIMPLE • SECURE • FAST ]</div><h1>BUY SMART.<br><em>SELL BOLD.</em></h1><p class="muted">Create an account, browse products, and contact the seller. Lightweight marketplace for mobile.</p><a class="btn red" href="#products">VIEW PRODUCTS ↘</a></div><div class="terminal"><div class="muted">root@deepweb:~ — status</div><div class="termline">[<b>OK</b>] Store online</div><div class="termline">[<b>OK</b>] Accounts enabled</div><div class="termline">[<b>LIVE</b>] Listings: {{ products|length }}</div><div class="termline">[<b>READY</b>] Welcome to the market_</div></div></section>
{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}{% endwith %}
<div id="products" class="sectionhead"><div><div class="eyebrow">THE CATALOG</div><h2>Latest Products</h2></div><span class="muted">{{ products|length }} listing(s)</span></div>
{% if products %}<section class="grid">{% for p in products %}<article class="product">{% if p.image_file %}<img src="{{ '/uploads/'+p.image_file }}" alt="{{ p.name }}">{% elif p.image_url %}<img src="{{ p.image_url }}" alt="{{ p.name }}" loading="lazy">{% else %}<div class="noimg">NO IMAGE</div>{% endif %}<div class="pbody"><h3>{{ p.name }}</h3><div class="desc">🪙 {{ p.coin_cost }} coins required</div><div class="pfoot"><span class="price">{{ p.price }}</span>{% if p.sold_out %}<span class="sold">SOLD OUT</span>{% else %}<form method="post" action="/buy/{{ p.id }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="btn red" type="submit">BUY NOW ↗</button></form>{% endif %}</div></div></article>{% endfor %}</section>{% else %}<div class="terminal" style="text-align:center;margin-bottom:35px"><h3>No products yet</h3><p class="muted">Admin will add listings soon.</p></div>{% endif %}
<footer><span>© DEEP WEB · MARKETPLACE</span><span>Discord: {{ discord }}</span></footer></div></body></html>'''
AUTH = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }}</title><style>'''+STYLE+'''</style></head><body><div class="wrap"><header class="top"><div class="logo">DEEP <b>WEB</b><div class="tag">/// ACCOUNT ACCESS</div></div><a class="btn" href="/">← STORE</a></header><main class="formbox" style="max-width:520px;margin:35px auto"><div class="eyebrow">MEMBER ACCESS</div><h1>{{ title }}</h1><p class="muted">{{ subtitle }}</p>{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}{% endwith %}<form method="post"><input type="hidden" name="csrf" value="{{ csrf }}"><label class="field"><span>USERNAME</span><input name="username" required minlength="3" maxlength="24" pattern="[A-Za-z0-9_]+" autocomplete="username"></label><label class="field"><span>PASSWORD (minimum 8 characters)</span><input name="password" type="password" required minlength="8" maxlength="128" autocomplete="{{ 'new-password' if signup else 'current-password' }}"></label><button class="btn red" style="width:100%" type="submit">{{ 'CREATE ACCOUNT' if signup else 'LOGIN' }} →</button></form><p class="hint">{% if signup %}Already registered? <a href="/login" style="color:#45f3ff">Login</a>{% else %}New here? <a href="/signup" style="color:#45f3ff">Create account</a>{% endif %}</p></main></div></body></html>'''
ADMIN = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin Panel</title><style>'''+STYLE+'''</style></head><body><div class="wrap"><header class="top"><div class="logo">DEEP <b>WEB</b><div class="tag">/// CONTROL PANEL</div></div><nav class="nav"><a class="btn cyan" href="/">VIEW STORE</a><a class="btn" href="/admin/logout">LOG OUT</a></nav></header><div style="padding:24px 0 5px"><div class="eyebrow">OWNER CONSOLE</div><h1>Product Manager</h1><p class="muted">Add, edit, delete and mark products sold out.</p></div>{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}{% endwith %}
<section class="formbox"><h2>{{ 'Edit Product' if edit else 'Add New Product' }}</h2><form method="post" enctype="multipart/form-data" action="{{ '/admin/edit/'+(edit.id|string) if edit else '/admin/add' }}"><input type="hidden" name="csrf" value="{{ csrf }}"><label class="field"><span>PRODUCT NAME *</span><input name="name" required maxlength="100" value="{{ edit.name if edit else '' }}"></label><label class="field"><span>PRICE *</span><input name="price" required maxlength="50" value="{{ edit.price if edit else '' }}" placeholder="Rs. 1500"></label><label class="field"><span>COIN COST *</span><input name="coin_cost" type="number" required min="0" max="1000000" value="{{ edit.coin_cost if edit else 1 }}"></label><label class="field"><span>DESCRIPTION</span><textarea name="description" maxlength="500">{{ edit.description if edit else '' }}</textarea></label><label class="field"><span>IMAGE URL (OPTIONAL)</span><input name="image_url" type="url" maxlength="1000" value="{{ edit.image_url if edit else '' }}" placeholder="https://example.com/image.jpg"></label><label class="field"><span>OR UPLOAD IMAGE (max 4 MB)</span><input name="image_file" type="file" accept=".png,.jpg,.jpeg,.webp,image/jpeg,image/png,image/webp"></label>{% if edit %}<label class="field"><span><input type="checkbox" name="sold_out" value="1" {% if edit.sold_out %}checked{% endif %} style="width:auto"> SOLD OUT</span></label>{% endif %}<button class="btn red" type="submit">{{ 'SAVE CHANGES' if edit else 'ADD PRODUCT +' }}</button> {% if edit %}<a class="btn" href="/admin">CANCEL</a>{% endif %}</form></section>
<div class="sectionhead"><div class="eyebrow"><h2>Inventory ({{ products|length }})</h2></div></div>{% if products %}<section class="adminlist">{% for p in products %}<article class="adminrow">{% if p.image_file %}<img src="{{ '/uploads/'+p.image_file }}" alt="">{% elif p.image_url %}<img src="{{ p.image_url }}" alt="">{% else %}<div class="noimg" style="height:50px">—</div>{% endif %}<div><b>{{ p.name }}</b><p>{{ p.price }} · {{ p.coin_cost }} coins · {{ 'SOLD OUT' if p.sold_out else 'AVAILABLE' }}</p></div><div class="actions"><a class="btn cyan" href="/admin/edit/{{ p.id }}">EDIT</a><form method="post" action="/admin/toggle/{{ p.id }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="btn" type="submit">{{ 'RESTOCK' if p.sold_out else 'SOLD OUT' }}</button></form><form method="post" action="/admin/delete/{{ p.id }}" onsubmit="return confirm('Delete this listing?')"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="btn" type="submit">DELETE</button></form></div></article>{% endfor %}</section>{% else %}<p class="muted">No products yet.</p>{% endif %}<footer><span>ADMIN CONSOLE</span><span>Discord: {{ discord }}</span></footer></div></body></html>'''

ORDER_PAGE = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Order Key — DEEP WEB</title><style>'''+STYLE+'''</style></head><body><div class="wrap"><header class="top"><a href="/" style="color:inherit;text-decoration:none"><div class="logo">DEEP <b>WEB</b><div class="tag">/// ORDER SYSTEM</div></div></a><a class="btn" href="/">BACK TO STORE</a></header><main class="formbox" style="max-width:680px;margin:35px auto"><div class="eyebrow">[ ORDER CREATED ]</div><h1>Order Key Generated</h1><p class="muted">Your unique order key is ready. Send it to the seller through WhatsApp or open Discord to contact them.</p><div class="terminal"><div class="muted">YOUR ORDER KEY</div><h2 id="orderKey" style="font-family:monospace;color:#45f3ff;overflow-wrap:anywhere">{{ order.order_key }}</h2><button class="btn cyan" type="button" onclick="navigator.clipboard.writeText(document.getElementById('orderKey').innerText).then(()=>{this.innerText='KEY COPIED ✓'}).catch(()=>{this.innerText='Long-press the key to copy'})">COPY ORDER KEY</button><p class="termline">[<b>PRODUCT</b>] {{ order.product_name }}</p><p class="termline">[<b>PRICE</b>] {{ order.product_price }}</p><p class="termline">[<b>COINS USED</b>] {{ order.coin_cost }}</p><p class="termline">[<b>COINS LEFT</b>] {{ coins_left }}</p><p class="hint">Keep this key. Include it when contacting the seller.</p></div><div class="actions" style="margin-top:16px"><a class="btn red" style="flex:1" href="{{ whatsapp_url(order.product_name, order.order_key) }}" target="_blank" rel="noopener">🟢 WhatsApp Seller</a><a class="btn cyan" style="flex:1" href="{{ discord_url }}" target="_blank" rel="noopener">🔵 Open Discord</a></div><p class="hint" style="margin-top:14px">Discord username: <b>{{ discord }}</b>. If Discord opens but doesn't show the profile, search this username inside Discord.</p></main><footer><span>© DEEP WEB</span><span>ORDER SYSTEM · KEY SAVED</span></footer></div></body></html>'''

def csrf_check():
    t=request.form.get('csrf','')
    if not t or not secrets.compare_digest(t,session.get('csrf','')): abort(400,'Invalid form token. Reload and try again.')
@app.before_request
def ensure_csrf(): session.setdefault('csrf',secrets.token_urlsafe(24))
def admin_only(fn):
    @wraps(fn)
    def w(*a,**k):
        if not session.get('admin'): return redirect('/admin/login')
        return fn(*a,**k)
    return w
@app.context_processor
def helpers():
    def whatsapp_url(name, key):
        message='Hi, I want to buy: '+name+'\nOrder Key: '+key
        return 'https://wa.me/'+WHATSAPP+'?text='+quote(message)
    return {'csrf':session.get('csrf',''),'discord':DISCORD,'discord_url':DISCORD_URL,'whatsapp_url':whatsapp_url}

@app.get('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOADS, filename)

@app.get('/')
def home():
    with connect() as c: products=c.execute('SELECT * FROM products ORDER BY id DESC LIMIT 100').fetchall()
    coins=0
    if session.get('user_id'):
        with connect() as c:
            u=c.execute('SELECT coins FROM users WHERE id=?',(session['user_id'],)).fetchone()
            coins=u['coins'] if u else 0
    return render_template_string(HOME,products=products,username=session.get('username'),coins=coins)


@app.post('/buy/<int:pid>')
def buy(pid):
    csrf_check()
    if not session.get('user_id'):
        flash('Create an account or log in before buying.')
        return redirect('/login')
    with connect() as c:
        product=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
        if not product: abort(404)
        if product['sold_out']:
            flash('This product is sold out.')
            return redirect('/#products')
        user=c.execute('SELECT coins FROM users WHERE id=?',(session['user_id'],)).fetchone()
        if not user:
            session.clear()
            flash('Please log in again.')
            return redirect('/login')
        cost=max(0,int(product['coin_cost'] or 0))
        if user['coins'] < cost:
            flash(f'Not enough coins. You have {user["coins"]}; this product needs {cost}.')
            return redirect('/#products')
        # Atomic deduction prevents users from spending the same coins twice.
        cur=c.execute('UPDATE users SET coins=coins-? WHERE id=? AND coins>=?',(cost,session['user_id'],cost))
        if cur.rowcount != 1:
            flash('Not enough coins.'); return redirect('/#products')
        key='DWP-'+secrets.token_hex(3).upper()+'-'+secrets.token_hex(2).upper()
        c.execute('INSERT INTO orders(order_key,user_id,product_id,product_name,product_price,coin_cost) VALUES(?,?,?,?,?,?)',
                  (key,session['user_id'],pid,product['name'],product['price'],cost))
        order=c.execute('SELECT * FROM orders WHERE order_key=?',(key,)).fetchone()
        coins_left=c.execute('SELECT coins FROM users WHERE id=?',(session['user_id'],)).fetchone()['coins']
    return render_template_string(ORDER_PAGE,order=order,coins_left=coins_left)

@app.route('/signup',methods=['GET','POST'])
def signup():
    if session.get('user_id'): return redirect('/')
    if request.method=='POST':
        csrf_check(); username=request.form.get('username','').strip(); password=request.form.get('password','')
        if not re.fullmatch(r'[A-Za-z0-9_]{3,24}',username): flash('Username must be 3–24 letters, numbers or underscores.')
        elif len(password)<8 or len(password)>128: flash('Password must be at least 8 characters.')
        else:
            try:
                with connect() as c: cur=c.execute('INSERT INTO users(username,password_hash,coins) VALUES(?,?,10)',(username,generate_password_hash(password))); uid=cur.lastrowid
                session.clear(); session['user_id']=uid; session['username']=username; session['csrf']=secrets.token_urlsafe(24)
                flash('Account created. Welcome!'); return redirect('/')
            except sqlite3.IntegrityError: flash('That username is already taken.')
    return render_template_string(AUTH,title='Create Account',subtitle='Create your marketplace account.',signup=True)

@app.route('/login',methods=['GET','POST'])
def member_login():
    if session.get('user_id'): return redirect('/')
    if request.method=='POST':
        csrf_check(); username=request.form.get('username','').strip(); password=request.form.get('password','')
        with connect() as c: u=c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        if u and check_password_hash(u['password_hash'],password):
            session.clear(); session['user_id']=u['id']; session['username']=u['username']; session['csrf']=secrets.token_urlsafe(24); return redirect('/')
        flash('Username or password is incorrect.')
    return render_template_string(AUTH,title='Member Login',subtitle='Log in to your account.',signup=False)
@app.get('/logout')
def member_logout(): session.clear(); return redirect('/')

@app.route('/admin/login',methods=['GET','POST'])
def admin_login():
    if session.get('admin'): return redirect('/admin')
    if request.method=='POST':
        csrf_check()
        if not ADMIN_PASS: flash('Set ADMIN_PASSWORD in hosting environment first.')
        elif secrets.compare_digest(request.form.get('username',''),ADMIN_USER) and secrets.compare_digest(request.form.get('password',''),ADMIN_PASS):
            session.clear(); session['admin']=True; session['csrf']=secrets.token_urlsafe(24); return redirect('/admin')
        else: flash('Wrong admin username or password.')
    return render_template_string(AUTH,title='Admin Login',subtitle='Owner-only product management.',signup=False)
@app.get('/admin/logout')
def admin_logout(): session.clear(); return redirect('/')
@app.get('/admin')
@admin_only
def admin():
    with connect() as c: products=c.execute('SELECT * FROM products ORDER BY id DESC LIMIT 100').fetchall()
    return render_template_string(ADMIN,products=products,edit=None)
def save_image():
    f=request.files.get('image_file')
    if not f or not f.filename: return ''
    if '.' not in f.filename or f.filename.rsplit('.',1)[1].lower() not in ALLOWED: raise ValueError('Use JPG, PNG or WEBP only.')
    name=secrets.token_hex(8)+'_'+secure_filename(f.filename); f.save(UPLOADS/name); return name
@app.post('/admin/add')
@admin_only
def add():
    csrf_check(); name=request.form.get('name','').strip()[:100]; price=request.form.get('price','').strip()[:50]; desc=request.form.get('description','').strip()[:500]; url=request.form.get('image_url','').strip()[:1000]
    try: coin_cost=int(request.form.get('coin_cost','1'))
    except ValueError: coin_cost=-1
    if coin_cost < 0 or coin_cost > 1000000: flash('Coin cost must be between 0 and 1000000.'); return redirect('/admin')
    if not name or not price: flash('Name and price are required.'); return redirect('/admin')
    try: image=save_image()
    except ValueError as e: flash(str(e)); return redirect('/admin')
    if image: url=''
    with connect() as c: c.execute('INSERT INTO products(name,price,coin_cost,description,image_url,image_file) VALUES(?,?,?,?,?,?)',(name,price,coin_cost,desc,url,image))
    flash('Product added.'); return redirect('/admin')
@app.route('/admin/edit/<int:pid>',methods=['GET','POST'])
@admin_only
def edit(pid):
    with connect() as c: p=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
    if not p: abort(404)
    if request.method=='POST':
        csrf_check(); name=request.form.get('name','').strip()[:100]; price=request.form.get('price','').strip()[:50]; desc=request.form.get('description','').strip()[:500]; url=request.form.get('image_url','').strip()[:1000]; sold=1 if request.form.get('sold_out')=='1' else 0
        try: coin_cost=int(request.form.get('coin_cost','1'))
        except ValueError: coin_cost=-1
        if coin_cost < 0 or coin_cost > 1000000: flash('Coin cost must be between 0 and 1000000.'); return redirect(f'/admin/edit/{pid}')
        if not name or not price: flash('Name and price are required.'); return redirect(f'/admin/edit/{pid}')
        image=p['image_file']
        try: new=save_image()
        except ValueError as e: flash(str(e)); return redirect(f'/admin/edit/{pid}')
        if new:
            if image: (UPLOADS/image).unlink(missing_ok=True)
            image=new; url=''
        elif url and image: (UPLOADS/image).unlink(missing_ok=True); image=''
        with connect() as c: c.execute('UPDATE products SET name=?,price=?,coin_cost=?,description=?,image_url=?,image_file=?,sold_out=? WHERE id=?',(name,price,coin_cost,desc,url,image,sold,pid))
        flash('Product updated.'); return redirect('/admin')
    with connect() as c: products=c.execute('SELECT * FROM products ORDER BY id DESC LIMIT 100').fetchall()
    return render_template_string(ADMIN,products=products,edit=p)
@app.post('/admin/toggle/<int:pid>')
@admin_only
def toggle(pid):
    csrf_check()
    with connect() as c:
        p=c.execute('SELECT sold_out FROM products WHERE id=?',(pid,)).fetchone()
        if p: c.execute('UPDATE products SET sold_out=? WHERE id=?',(0 if p['sold_out'] else 1,pid))
    return redirect('/admin')
@app.post('/admin/delete/<int:pid>')
@admin_only
def delete(pid):
    csrf_check()
    with connect() as c:
        p=c.execute('SELECT image_file FROM products WHERE id=?',(pid,)).fetchone()
        if p:
            c.execute('DELETE FROM products WHERE id=?',(pid,))
            if p['image_file']: (UPLOADS/p['image_file']).unlink(missing_ok=True)
    return redirect('/admin')
@app.errorhandler(413)
def too_large(e): return 'Image too large. Maximum upload is 4 MB.',413
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')),debug=False)
