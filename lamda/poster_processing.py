import json
import boto3
from datetime import datetime

print("Loading Lambda function...")

s3 = boto3.client('s3', region_name='us-east-1')
lambda_client = boto3.client('lambda', region_name='us-east-1')
S3_BUCKET = 'mini-project1-posters'

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")

    submission_id = event.get('submission_id')
    print(f"submission_id: {submission_id}")

    if not submission_id:
        print("ERROR: Missing submission_id")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing submission_id'})
        }

    try:
        # 1. Get submission data from S3
        print(f"Getting item from S3: submissions/{submission_id}.json")
        response = s3.get_object(Bucket=S3_BUCKET, Key=f"submissions/{submission_id}.json")
        item = json.loads(response['Body'].read())
        print(f"S3 response: {json.dumps(item)}")

        if not item:
            print(f"ERROR: Submission {submission_id} not found in S3")
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Submission not found'})
            }

        title = item.get('title', '')
        description = item.get('description', '')
        filename = item.get('filename', '')
        print(f"Processing: title={title}, desc_len={len(description)}, filename={filename}")

        # 2. Validation logic
        if not title or not description or not filename:
            status = "INCOMPLETE"
            note = "Missing required fields."
        elif len(description) < 30:
            status = "NEEDS_REVISION"
            note = f"Description too short (min 30 chars). Current: {len(description)}"
        elif not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            status = "NEEDS_REVISION"
            note = "Invalid format. Only JPG/PNG allowed."
        else:
            status = "READY"
            note = "All checks passed. Poster is ready."

        print(f"Result: status={status}, note={note}")

        # 3. Update S3 with result
        item['status'] = status
        item['note'] = note
        item['updated_at'] = datetime.utcnow().isoformat()
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"submissions/{submission_id}.json",
            Body=json.dumps(item),
            ContentType='application/json'
        )
        print("S3 update successful")

        # 4. Trigger Result Update Function
        print(f"Invoking poster_result_update for {submission_id}")
        lambda_client.invoke(
            FunctionName='poster_result_update',
            InvocationType='Event',
            Payload=json.dumps({
                'submission_id': submission_id,
                'status': status,
                'note': note
            })
        )
        print("Result update invoked")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'submission_id': submission_id,
                'status': status,
                'note': note
            })
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
