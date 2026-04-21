import json
import boto3
import os
import urllib.error
import urllib.request
from datetime import datetime

s3 = boto3.client('s3', region_name='us-east-1')
S3_BUCKET = os.environ.get('S3_BUCKET', 'mini-project1-posters')
DATA_SERVICE_URL = os.environ.get('DATA_SERVICE_URL')


def update_data_service(submission_id, status, note):
    if not DATA_SERVICE_URL:
        return False

    url = f"{DATA_SERVICE_URL.rstrip('/')}/submissions/{submission_id}"
    body = json.dumps({'status': status, 'note': note}).encode('utf-8')
    request = urllib.request.Request(
        url,
        data=body,
        headers={'Content-Type': 'application/json'},
        method='PUT'
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as e:
        print(f"Data-service HTTP error: {e.code}")
    except Exception as e:
        print(f"Data-service update failed: {str(e)}")

    return False

def lambda_handler(event, context):
    """
    Final status update and backup
    """
    submission_id = event.get('submission_id')
    status = event.get('status')
    note = event.get('note')
    item = event.get('item')

    if not submission_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing submission_id'})
        }

    if not status:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing status'})
        }

    try:
        # 1. Get record from S3, or use metadata passed by poster_processing.
        if not item:
            response = s3.get_object(Bucket=S3_BUCKET, Key=f"submissions/{submission_id}.json")
            item = json.loads(response['Body'].read())

        if not item:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Submission not found'})
            }

        # 2. Add completion timestamp
        item['completed_at'] = datetime.utcnow().isoformat()
        item['final_status'] = status
        item['final_note'] = note

        # 3. Backup to S3 (completed folder)
        backup_key = f"completed/{submission_id}.json"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=backup_key,
            Body=json.dumps(item, indent=2),
            ContentType='application/json'
        )

        print(f"Submission {submission_id} backed up to S3: {backup_key}")

        # 4. Update main record in S3 and data-service
        item['status'] = status
        item['note'] = note
        item['s3_backup'] = f"s3://{S3_BUCKET}/{backup_key}"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"submissions/{submission_id}.json",
            Body=json.dumps(item),
            ContentType='application/json'
        )

        data_service_updated = update_data_service(submission_id, status, note)

        print(f"Submission {submission_id} processing complete")
        print(f"   Final status: {status}")
        print(f"   Note: {note}")
        print(f"   Data service updated: {data_service_updated}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'submission_id': submission_id,
                'status': 'result_updated',
                'final_status': status,
                's3_backup': f"s3://{S3_BUCKET}/{backup_key}",
                'data_service_updated': data_service_updated
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
