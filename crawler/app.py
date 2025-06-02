import os
import boto3
import json

glue_client = boto3.client('glue')

# Configuration - will be set as Zappa environment variables
GLUE_CRAWLER_NAME = os.environ.get('GLUE_CRAWLER_NAME')

def lambda_handler(event, context):
    """
    Lambda function handler to start an AWS Glue Crawler.
    """
    print(f"Received event: {json.dumps(event)}")

    if not GLUE_CRAWLER_NAME:
        print("Error: GLUE_CRAWLER_NAME environment variable not set.")
        return {'statusCode': 500, 'body': json.dumps({'message': 'Glue Crawler name not configured'})}

    try:
        print(f"Starting Glue Crawler: {GLUE_CRAWLER_NAME}")
        response = glue_client.start_crawler(Name=GLUE_CRAWLER_NAME)
        print(f"Successfully started crawler: {response}")
        return {
            'statusCode': 200,
            'body': json.dumps(f'Successfully started Glue Crawler {GLUE_CRAWLER_NAME}')
        }
    except glue_client.exceptions.CrawlerRunningException:
        print(f"Crawler {GLUE_CRAWLER_NAME} is already running. Skipping start.")
        return {
            'statusCode': 200,
            'body': json.dumps(f'Crawler {GLUE_CRAWLER_NAME} is already running.')
        }
    except Exception as e:
        print(f"Error starting Glue Crawler {GLUE_CRAWLER_NAME}: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error starting Glue Crawler {GLUE_CRAWLER_NAME}: {str(e)}')
        }