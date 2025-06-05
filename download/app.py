import requests
import boto3
from datetime import datetime
import logging
import os
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BUCKET_NAME = 'examenfinalbigdata'
SITES ={'eltiempo': 'https://www.eltiempo.com','publimetro': 'https://www.publimetro.co'}

def download_and_save_to_s3(site_name, url):
    try:
        logger.info(f"Downloading data from {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        content = response.text


        s3 = boto3.client('s3')
        key = f'headlines/raw/{site_name}-{datetime.now().strftime("%Y-%m-%d")}.html'
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=content.encode('utf-8'),
            ContentType='text/html'
        )
        logger.info(f"Data saved to S3 bucket {BUCKET_NAME} at {key}")
        return True
    except Exception as e:
        logger.error(f"Error downloading or saving data: {e}")
        return False
    
def lambda_handler(event, context):
    results = {}
    for site_name, url in SITES.items():
        results[site_name] = download_and_save_to_s3(site_name, url)
    return {
        'statusCode': 200,
        'body': results
    }