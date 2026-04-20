import json
import boto3
import logging

# Initialize AWS SDK clients
s3 = boto3.client('s3')
lambda_client = boto3.client('lambda')

# Configure professional logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Define the S3 Bucket name
S3_BUCKET = 'mini-project1-posters'

def lambda_handler(event, context):
    """
    Core Processing Function:
    1. Fetches raw submission data from S3.
    2. Performs compliance validation on the poster metadata.
    3. Triggers the Result Update function for archiving and status synchronization.
    """
    logger.info(f"Received event: {json.dumps(event)}")

    # 1. Extract Submission ID
    # Handles direct ID input or IDs passed from upstream Lambda functions
    submission_id = event.get('submission_id')
    
    if not submission_id:
        logger.error("Validation Error: Missing submission_id in the event payload.")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing submission_id'})
        }

    try:
        # 2. Retrieve JSON metadata from S3
        # Replaces traditional DynamoDB queries with an S3-based object retrieval pattern
        file_key = f"submissions/{submission_id}.json"
        logger.info(f"Attempting to fetch S3 object: {file_key}")
        
        response = s3.get_object(Bucket=S3_BUCKET, Key=file_key)
        item = json.loads(response['Body'].read().decode('utf-8'))
        
        # 3. Extract required fields for validation
        title = item.get('title', '')
        description = item.get('description', '')
        filename = item.get('filename', '')
        
        logger.info(f"Processing submission metadata for ID: {submission_id}")

        # 4. Core Validation Logic
        # Default status is READY unless a rule violation is found
        status = "READY"
        note = "All compliance checks passed successfully."

        # Rule A: Check for mandatory field completeness
        if not title or not description or not filename:
            status = "INCOMPLETE"
            note = "Mandatory fields missing: title, description, or filename."
        
        # Rule B: Validate description length (minimum 30 characters)
        elif len(description) < 30:
            status = "NEEDS_REVISION"
            note = f"Description length ({len(description)}) is below the 30-character threshold."
        
        # Rule C: Validate file extension (Restriction: JPG, JPEG, PNG only)
        elif not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            status = "NEEDS_REVISION"
            note = f"Unsupported file format: {filename}. Authorized formats: JPG, JPEG, PNG."

        logger.info(f"Validation outcome - Status: {status}, Note: {note}")

        # 5. Asynchronous hand-off to the Result Update Lambda
        # This decouples the processing logic from the final archival/notification stage
        update_payload = {
            'submission_id': submission_id,
            'status': status,
            'note': note
        }
        
        lambda_client.invoke(
            FunctionName='poster_result_update',
            InvocationType='Event',  # Asynchronous execution for optimized performance
            Payload=json.dumps(update_payload)
        )
        
        logger.info(f"Asynchronous trigger sent to 'poster_result_update' for ID: {submission_id}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'submission_id': submission_id,
                'status': status,
                'note': note
            })
        }

    except s3.exceptions.NoSuchKey:
        logger.error(f"S3 Error: File not found at key {file_key}")
        return {'statusCode': 404, 'body': json.dumps({'error': 'Submission file not found in S3.'})}
    except Exception as e:
        logger.error(f"Internal System Error: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'An internal processing error occurred.'})}
