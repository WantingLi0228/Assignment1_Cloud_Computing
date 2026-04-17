from flask import Flask, request, jsonify
import sqlite3
import uuid
import os
from datetime import datetime

app = Flask(__name__)

# 修复 Windows 路径问题
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'submissions.db')
os.makedirs(DB_DIR, exist_ok=True)

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表"""
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

# 启动时初始化数据库
init_db()

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok'})

@app.route('/submissions', methods=['POST'])
def create_submission():
    """创建新提交记录"""
    data = request.get_json()
    
    # 验证必填字段
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
    """查询提交记录"""
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
    """更新提交记录状态"""
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
    """删除提交记录（可选）"""
    conn = get_db()
    conn.execute('DELETE FROM submissions WHERE id = ?', (submission_id,))
    conn.commit()
    conn.close()
    return jsonify({'id': submission_id, 'deleted': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)