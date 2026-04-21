from flask import Flask, request, jsonify
import sqlite3
import uuid
import os
from datetime import datetime

app = Flask(__name__)

# Define database directory and path
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'submissions.db')
os.makedirs(DB_DIR, exist_ok=True)

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database table"""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            filename TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

# Initialize database when service starts
init_db()

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

@app.route('/submissions', methods=['POST'])
def create_submission():
    """Create a new submission record"""
    data = request.get_json()
    
    # Validate required fields
    required = ['id', 'title', 'description', 'filename']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing field: {field}'}), 400
    
    conn = get_db()
    conn.execute('''
        INSERT INTO submissions (id, title, description, filename, status, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['id'],
        data['title'],
        data['description'],
        data['filename'],
        'PENDING',
        '',
        data.get('created_at', datetime.utcnow().isoformat())
    ))
    conn.commit()
    conn.close()
    
    return jsonify({'id': data['id'], 'status': 'created'}), 201

@app.route('/submissions/<submission_id>', methods=['GET'])
def get_submission(submission_id):
    """Retrieve submission record"""
    conn = get_db()
    row = conn.execute(
        'SELECT id, title, description, filename, status, note, created_at FROM submissions WHERE id = ?',
        (submission_id,)
    ).fetchone()
    conn.close()
    
    if row:
        return jsonify(dict(row))
    return jsonify({'error': 'Submission not found'}), 404

@app.route('/submissions/<submission_id>', methods=['PUT'])
def update_submission(submission_id):
    """Update submission status and note"""
    data = request.get_json()
    
    conn = get_db()
    conn.execute(
        'UPDATE submissions SET status = ?, note = ? WHERE id = ?',
        (data.get('status', 'UNKNOWN'), data.get('note', ''), submission_id)
    )
    conn.commit()
    conn.close()
    
    return jsonify({'id': submission_id, 'status': data.get('status')})

@app.route('/submissions/<submission_id>', methods=['DELETE'])
def delete_submission(submission_id):
    """Delete a submission record (optional)"""
    conn = get_db()
    conn.execute('DELETE FROM submissions WHERE id = ?', (submission_id,))
    conn.commit()
    conn.close()
    return jsonify({'id': submission_id, 'deleted': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)