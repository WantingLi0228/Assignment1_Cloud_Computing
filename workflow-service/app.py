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
S3_BUCKET = 'mini-project1-posters'

def get_s3_client():
    return boto3.client('s3', region_name='us-east-1')

def get_lambda_client():
    return boto3.client('lambda', region_name='us-east-1')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/submit', methods=['POST', 'OPTIONS'])
def submit():
    if request.method == 'OPTIONS':
        return '', 200

    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    file = request.files.get('file')

    filename = file.filename if file else ''
    submission_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    # 1. Save to data-service as PENDING
    payload = {
        'id': submission_id,
        'title': title,
        'description': description,
        'filename': filename,
        'status': 'PENDING',
        'note': '',
        'created_at': created_at
    }

    try:
        requests.post(f"{DATA_SERVICE_URL}/submissions", json=payload, timeout=10)
    except Exception as e:
        print(f"Data service error: {e}")

    # 2. Save submission metadata to S3
    try:
        s3 = get_s3_client()
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"submissions/{submission_id}.json",
            Body=json.dumps(payload),
            ContentType='application/json'
        )
    except Exception as e:
        print(f"S3 write error: {e}")

    # 3. Upload poster file to S3
    if file:
        try:
            s3_key = f"posters/{submission_id}/{filename}"
            s3.upload_fileobj(file, S3_BUCKET, s3_key)
        except Exception as e:
            print(f"S3 upload error: {e}")

    # 4. Trigger Lambda chain
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
    # Try S3 first
    try:
        s3 = get_s3_client()
        response = s3.get_object(Bucket=S3_BUCKET, Key=f"submissions/{submission_id}.json")
        item = json.loads(response['Body'].read())
        if item.get('status') and item['status'] != 'PENDING':
            return jsonify(item), 200
    except Exception as e:
        print(f"S3 read error: {e}")

    # Fallback to data-service
    try:
        resp = requests.get(
            f"{DATA_SERVICE_URL}/submissions/{submission_id}",
            timeout=10
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'error': f'Service error: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
