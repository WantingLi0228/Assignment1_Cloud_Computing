import json
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
table = dynamodb.Table('PosterSubmissions')

# S3 桶名（需要先创建）
S3_BUCKET = 'mini-project1-posters'  # 改成你的桶名

def lambda_handler(event, context):
    """
    最终状态更新，并备份到 S3
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
        # 1. 从 DynamoDB 获取完整记录
        response = table.get_item(Key={'Id': submission_id})
        item = response.get('Item')
        
        if not item:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Submission not found'})
            }
        
        # 2. 添加完成时间戳
        item['completed_at'] = datetime.utcnow().isoformat()
        item['final_status'] = status
        item['final_note'] = note
        
        # 3. 备份到 S3
        backup_key = f"submissions/{submission_id}.json"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=backup_key,
            Body=json.dumps(item, indent=2),
            ContentType='application/json'
        )
        
        print(f"提交 {submission_id} 已备份到 S3: {backup_key}")
        
        # 4. 更新 DynamoDB 的完成时间
        table.update_item(
            Key={'Id': submission_id},
            UpdateExpression='SET completed_at = :completed_at, s3_backup = :s3_backup',
            ExpressionAttributeValues={
                ':completed_at': datetime.utcnow().isoformat(),
                ':s3_backup': f"s3://{S3_BUCKET}/{backup_key}"
            }
        )
        
        print(f"提交 {submission_id} 处理完成")
        print(f"   最终状态: {status}")
        print(f"   说明: {note}")
        
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
        print(f"错误: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }