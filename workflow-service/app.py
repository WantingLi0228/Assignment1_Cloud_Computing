from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import uuid
import os
import boto3
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

DATA_SERVICE_URL = os.environ.get('DATA_SERVICE_URL', 'http://localhost:5001')
S3_BUCKET = os.environ.get('S3_BUCKET', 'mini-project1-posters')

def get_lambda_client():
    return boto3.client('lambda', region_name='us-east-1')

def get_s3_client():
    return boto3.client('s3', region_name='us-east-1')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json()

    title = str(data.get('title', '')).strip()
    description = str(data.get('description', '')).strip()
    filename = str(data.get('filename', '')).strip()

    submission_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    payload = {
        'id': submission_id,
        'title': title,
        'description': description,
        'filename': filename,
        'status': 'PENDING',
        'note': '',
        'created_at': created_at
    }

    # 1. Save to data-service
    try:
        requests.post(f"{DATA_SERVICE_URL}/submissions", json=payload, timeout=10)
    except Exception as e:
        print(f"Data service error: {e}")

    # 2. Write metadata to S3
    try:
        s3 = get_s3_client()
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"submissions/{submission_id}.json",
            Body=json.dumps(payload),
            ContentType='application/json'
        )
    except Exception as e:
        print(f"S3 upload error: {e}")

    # 3. Trigger Lambda
    try:
        lambda_client = get_lambda_client()
        lambda_client.invoke(
            FunctionName='poster_submission_event',
            InvocationType='Event',
            Payload=json.dumps({'submission_id': submission_id})
        )
    except Exception as e:
        print(f"Lambda trigger error: {e}")

    return jsonify({
        'submission_id': submission_id,
        'status': 'PENDING',
        'message': 'Submission received and processing'
    }), 201

@app.route('/result/<submission_id>', methods=['GET'])
def get_result(submission_id):
    try:
        s3 = get_s3_client()
        s3_key = f"submissions/{submission_id}.json"
        response = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
        item = json.loads(response['Body'].read().decode('utf-8'))

        if item.get('final_status') and item['final_status'] != 'PENDING':
            return jsonify({
                'id': item.get('id'),
                'title': item.get('title'),
                'description': item.get('description'),
                'filename': item.get('filename'),
                'status': item.get('final_status'),
                'note': item.get('final_note', ''),
                'created_at': item.get('created_at')
            }), 200
    except Exception as e:
        print(f"S3 read error: {e}")

    # fallback
    try:
        resp = requests.get(f"{DATA_SERVICE_URL}/submissions/{submission_id}", timeout=10)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)