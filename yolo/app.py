import time
from pathlib import Path
import requests
from detect import run
import yaml
from loguru import logger
import os
import boto3
import json


images_bucket = os.environ['BUCKET_NAME']
queue_name = os.environ['SQS_QUEUE_NAME']
#queue_url = os.environ['SQS_QUEUE_URL']
REGION_NAME = os.environ['REGION_NAME']
DYNAMO_TABLE = os.environ['DYNAMO_TABLE']


sqs_client = boto3.client('sqs', region_name=REGION_NAME)
s3 = boto3.client('s3')
s3_client = boto3.client('s3', region_name=REGION_NAME)
dynamo_client = boto3.client('dynamodb', region_name = REGION_NAME)


# Use this code snippet in your app.
# If you need more information about configurations
# or implementing the sample code, visit the AWS docs:
# https://aws.amazon.com/developer/language/python/

import boto3
from botocore.exceptions import ClientError


def get_secret():
    secret_name = "shermanawsproject"
    region_name = "eu-north-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    secret = get_secret_value_response['SecretString']
    return json.loads(secret)


# load TELEGRAM_TOKEN value from Secret Manager
secrets = get_secret()
TELEGRAM_TOKEN = secrets["TELEGRAM_TOKEN"]  # os.environ['TELEGRAM_TOKEN']
APP_URL = secrets["app_url"]  # os.environ['TELEGRAM_APP_URL']

with open("data/coco128.yaml", "r") as stream:
    names = yaml.safe_load(stream)['names']


def consume():
    while True:
        response = sqs_client.receive_message(QueueUrl=queue_name, MaxNumberOfMessages=1, WaitTimeSeconds=5)
        if 'Messages' in response:
            message = response['Messages'][0]['Body']
            receipt_handle = response['Messages'][0]['ReceiptHandle']

            # Use the ReceiptHandle as a prediction UUID
            prediction_id = response['Messages'][0]['MessageId']
            logger.info(f'prediction: {prediction_id}. start processing')

            # Receives a URL parameter representing the image to download from S3
            message_replace1 = message.replace("'", '"')
            message_replace2 = message_replace1.replace("False", '"False"')
            message_dict = json.loads(message_replace2)
            image_name = message_dict['caption']# TODO extract from message
            chat_id = message_dict['from']['id']
            original_img_path = (f'/usr/src/app/{image_name}')
            s3_client.download_file(images_bucket, image_name, original_img_path)  # TODO download img_name from S3,

            logger.info(f'prediction: {prediction_id}/{original_img_path}. Download img completed')

            # Predicts the objects in the image
            run(
                weights='yolov5s.pt',
                data='data/coco128.yaml',
                source=original_img_path,
                project='static/data',
                name=prediction_id,
                save_txt=True
            )

            logger.info(f'prediction: {prediction_id}/{original_img_path}. done')

            # This is the path for the predicted image with labels
            # The predicted image typically includes bounding boxes drawn around the detected objects, along with class labels and possibly confidence scores.
            predicted_img_path = Path(f'static/data/{prediction_id}/{image_name}')

            # TODO Uploads the predicted image (predicted_img_path) to S3 (be careful not to override the original image).
            s3_client.upload_file(predicted_img_path, images_bucket, image_name.split(".")[0] + "." +  image_name.split(".")[1] + "_predict.jpeg")

            # Parse prediction labels and create a summary
            #pred_summary_path = f'static/data/{prediction_id}/labels/{image_name.split(".")[0] + "." +  image_name.split(".")[1]}_predict.jpeg.txt'
            #pred_summary_path = f'static/data/{prediction_id}/labels/{image_name}'
            #pred_summary_path = f'static/data/{prediction_id}/labels/{image_name.split(".")[0] + "." + image_name.split(".")[1]}_predict.txt'
            pred_summary_path = f'static/data/{prediction_id}/labels/{image_name.split(".")[0] + "." + image_name.split(".")[1]}.txt'
            if pred_summary_path:
                with open(pred_summary_path) as f:
                    labels = f.read().splitlines()
                    labels = [line.split(' ') for line in labels]
                    labels = [{
                        'class': names[int(l[0])],
                        'cx': float(l[1]),
                        'cy': float(l[2]),
                        'width': float(l[3]),
                        'height': float(l[4]),
                    } for l in labels]

                logger.info(f'prediction: {prediction_id}/{original_img_path}. prediction summary:\n\n{labels}')

                prediction_summary = {
                    'prediction_id': prediction_id,
                    'original_img_path': str(original_img_path),
                    'predicted_img_path': str(predicted_img_path),
                    'labels': str(labels),
                    'time': str(time.time())
                }
                # TODO store the prediction_summary in a DynamoDB table
                try:
                    response = dynamo_client.put_item(
                        TableName=DYNAMO_TABLE,
                        Item = {
                            'prediction_id': {'S': prediction_summary['prediction_id']},
                            'chat_id': {'S': str(chat_id)},
                            'prediction_summary': {'S': str(prediction_summary)}

                    },
                    )
                except:
                    raise Exception(f'The response is: {response} and the prediction_summary is:{prediction_summary}  and prediction_id is: {prediction_id} and chat_id is {chat_id}')
                # TODO perform a GET request to Polybot to `/results` endpoint
            #requests.get(f'https://amirawsrecored.devops-int-college.com:8443/results/?prediction_id={prediction_id}&chat_id={chat_id}')
            #requests.get(f'http://amirawsroute.devops-int-college.com:80/results/?predictionId={prediction_id}&chatId={chat_id}')
            try:
                requests.get(f'http://polyservice:8443/results/?prediction_id={prediction_id}&chat_id={chat_id}')
            except Exception as e:
                raise e
                return f'Error: {str(e)}'

            # Delete the message from the queue as the job is considered as DONE
            sqs_client.delete_message(QueueUrl=queue_name, ReceiptHandle=receipt_handle)


if __name__ == "__main__":
    consume()
