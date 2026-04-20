import json
import boto3

lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    """
    接收 Workflow Service 的触发，调用 Processing Function
    """
    submission_id = event.get('submission_id')
    
    if not submission_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing submission_id'})
        }
    
    # 异步调用 Processing Function
    lambda_client.invoke(
        FunctionName='poster_processing',
        InvocationType='Event',  # 异步，不等待结果
        Payload=json.dumps({'submission_id': submission_id})
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'status': 'processing_started',
            'submission_id': submission_id
        })
    }