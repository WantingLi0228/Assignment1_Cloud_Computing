import json
import boto3
from datetime import datetime

print("Loading Lambda function...")

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('PosterSubmissions')
lambda_client = boto3.client('lambda', region_name='us-east-1')

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
        # 1. 从 DynamoDB 获取数据
        print(f"Getting item from DynamoDB with Id: {submission_id}")
        response = table.get_item(Key={'Id': submission_id})
        item = response.get('Item')
        print(f"DynamoDB response: {json.dumps(item)}")
        
        if not item:
            print(f"ERROR: Submission {submission_id} not found in DynamoDB")
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Submission not found'})
            }
        
        title = item.get('title', '')
        description = item.get('description', '')
        filename = item.get('filename', '')
        print(f"Processing: title={title}, desc_len={len(description)}, filename={filename}")
        
        # 2. 审核逻辑
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
        
        # 3. 更新 DynamoDB
        print(f"Updating DynamoDB for Id: {submission_id}")
        table.update_item(
            Key={'Id': submission_id},
            UpdateExpression='SET #status = :status, #note = :note, updated_at = :updated_at',
            ExpressionAttributeNames={
                '#status': 'status',
                '#note': 'note'
            },
            ExpressionAttributeValues={
                ':status': status,
                ':note': note,
                ':updated_at': datetime.utcnow().isoformat()
            }
        )
        print("DynamoDB update successful")
        
        # 4. 触发 Result Update Function
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