import os
import sys
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify

# .exe फाइल के लिए टेम्प्लेट फोल्डर का सही रास्ता खोजना
if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    app = Flask(__name__, template_folder=template_folder)
else:
    app = Flask(__name__)

DB_FILE = 'local_database.db'

# डेटाबेस कनेक्शन फंक्शन
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# पहली बार रन होने पर टेबल्स (Tables) बनाना
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT,
            role TEXT,
            password TEXT,
            is_approved INTEGER DEFAULT 0,
            totalLinks INTEGER DEFAULT 0,
            successCount INTEGER DEFAULT 0,
            failCount INTEGER DEFAULT 0,
            joinedAt TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            url TEXT,
            status TEXT,
            addedBy TEXT,
            addedByName TEXT,
            claimedBy TEXT,
            claimedByName TEXT,
            timestamp TEXT,
            claimedAt TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ================= ROUTES (APIs) =================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user_id = data['id']
    name = data['name']
    role = data['role']
    password = data['password']
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if not user:
        # Naya user request
        conn.execute('INSERT INTO users (id, name, role, password, is_approved, joinedAt) VALUES (?, ?, ?, ?, 0, ?)',
                     (user_id, name, role, password, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({"status": "pending_approval", "message": "Request Owner ke paas bhej di gayi hai. Approval ka wait karein."})
    else:
        # User exist karta hai - Password match check karo
        if user['password'] != password:
            conn.close()
            return jsonify({"status": "error", "message": "Incorrect Password! Kripya sahi password dalein."})
        
        # Approval check karo
        if user['is_approved'] == 0:
            conn.close()
            return jsonify({"status": "pending_approval", "message": "Aapki ID abhi pending hai. Owner se accept karwayein."})
        
        # Agar sab sahi hai
        user_data = dict(conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone())
        conn.close()
        return jsonify({"status": "success", "user": user_data})

@app.route('/api/data', methods=['GET'])
def get_all_data():
    conn = get_db_connection()
    users = [dict(row) for row in conn.execute('SELECT * FROM users').fetchall()]
    links = [dict(row) for row in conn.execute('SELECT * FROM links ORDER BY timestamp ASC').fetchall()]
    conn.close()
    
    users_dict = {u['id']: u for u in users}
    return jsonify({"users": users_dict, "links": links})

@app.route('/api/approve_user', methods=['POST'])
def approve_user():
    user_id = request.json['userId']
    conn = get_db_connection()
    conn.execute('UPDATE users SET is_approved = 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/reject_user', methods=['POST'])
def reject_user():
    user_id = request.json['userId']
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# Links wale baaki routes same rahenge
@app.route('/api/add_link', methods=['POST'])
def add_link():
    data = request.json
    conn = get_db_connection()
    conn.execute('''INSERT INTO links (text, url, status, addedBy, addedByName, timestamp) 
                    VALUES (?, ?, ?, ?, ?, ?)''', 
                 (data['text'], data['url'], 'pending', data['addedBy'], data['addedByName'], datetime.now().isoformat()))
    
    conn.execute('UPDATE users SET totalLinks = totalLinks + 1 WHERE id = ?', (data['addedBy'],))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/claim_link', methods=['POST'])
def claim_link():
    data = request.json
    user_id = data['userId']
    user_name = data['userName']
    
    conn = get_db_connection()
    link = conn.execute("SELECT * FROM links WHERE status = 'pending' ORDER BY timestamp ASC LIMIT 1").fetchone()
    
    if not link:
        conn.close()
        return jsonify({"error": "No available links!"}), 400
        
    conn.execute("UPDATE links SET status = 'claimed', claimedBy = ?, claimedByName = ?, claimedAt = ? WHERE id = ?",
                 (user_id, user_name, datetime.now().isoformat(), link['id']))
    conn.execute('UPDATE users SET totalLinks = totalLinks + 1 WHERE id = ?', (user_id,))
    conn.commit()
    
    claimed_link = dict(conn.execute('SELECT * FROM links WHERE id = ?', (link['id'],)).fetchone())
    conn.close()
    return jsonify({"success": True, "link": claimed_link})

@app.route('/api/update_status', methods=['POST'])
def update_status():
    data = request.json
    link_id = data['linkId']
    status = data['status']
    user_id = data['userId']
    
    conn = get_db_connection()
    conn.execute('UPDATE links SET status = ? WHERE id = ?', (status, link_id))
    
    if status == 'success':
        conn.execute('UPDATE users SET successCount = successCount + 1 WHERE id = ?', (user_id,))
    else:
        conn.execute('UPDATE users SET failCount = failCount + 1 WHERE id = ?', (user_id,))
        
    conn.commit()
    conn.close()
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)