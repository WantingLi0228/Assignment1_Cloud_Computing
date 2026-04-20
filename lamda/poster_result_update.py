import json
import boto3
from datetime import datetime

s3 = boto3.client('s3', region_name='us-east-1')
S3_BUCKET = 'mini-project1-posters'

def lambda_handler(event, context):
    """
    Final status update and backup
    """
    submission_id = event.get('submission_id')
    status = event.get('status')
    note = event.get('note')

    if not submission_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing submission_id'})
        }

    try:
        # 1. Get record from S3
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

        # 4. Update main record in S3
        item['status'] = status
        item['note'] = note
        item['s3_backup'] = f"s3://{S3_BUCKET}/{backup_key}"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"submissions/{submission_id}.json",
            Body=json.dumps(item),
            ContentType='application/json'
        )

        print(f"Submission {submission_id} processing complete")
        print(f"   Final status: {status}")
        print(f"   Note: {note}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'submission_id': submission_id,
                'status': 'result_updated',
                'final_status': status,
                's3_backup': f"s3://{S3_BUCKET}/{backup_key}"
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
