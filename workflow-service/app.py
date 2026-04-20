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

def get_dynamodb_table():
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    return dynamodb.Table('PosterSubmissions')

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

    # 2. Write to DynamoDB
    try:
        table = get_dynamodb_table()
        table.put_item(Item={
            'Id': submission_id,
            'title': title,
            'description': description,
            'filename': filename,
            'status': 'PENDING',
            'created_at': created_at
        })
    except Exception as e:
        print(f"DynamoDB write error: {e}")

    # 2.5 Upload file to S3
    if file:
        try:
            s3 = boto3.client('s3', region_name='us-east-1')
            s3_key = f"posters/{submission_id}/{filename}"
            s3.upload_fileobj(file, 'mini-project1-posters', s3_key)
        except Exception as e:
            print(f"S3 upload error: {e}")

    # 3. Trigger poster_processing Lambda (async)
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
        s3 = boto3.client('s3', region_name='us-east-1')
        s3_key = f"submissions/{submission_id}.json"
        response = s3.get_object(Bucket='mini-project1-posters', Key=s3_key)
        item = json.loads(response['Body'].read())
        if item.get('final_status') and item['final_status'] != 'PENDING':
            return jsonify({
                'Id': item.get('Id'),
                'title': item.get('title'),
                'description': item.get('description'),
                'filename': item.get('filename'),
                'status': item['final_status'],
                'note': item.get('final_note', ''),
                'created_at': item.get('created_at')
            }), 200
    except Exception as e:
        print(f"S3 read error: {e}")

    # Fallback to DynamoDB
    try:
        table = get_dynamodb_table()
        response = table.get_item(Key={'Id': submission_id})
        item = response.get('Item')
        if item and item.get('status') != 'PENDING':
            return jsonify(item), 200
    except Exception as e:
        print(f"DynamoDB read error: {e}")

    # Final fallback to data-service
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
