import boto3
import telebot
from loguru import logger
import os
import time
from telebot.types import InputFile
import requests
import json

REGION_NAME = os.environ['REGION_NAME']
sqs_url = os.environ['SQS_QUEUE_URL']
BUCKET_NAME = os.environ['BUCKET_NAME']


class Bot:

    def __init__(self, token, telegram_chat_url):
        # create a new instance of the TeleBot class.
        # all communication with Telegram servers are done using self.telegram_bot_client
        self.telegram_bot_client = telebot.TeleBot(token)

        # remove any existing webhooks configured in Telegram servers
        self.telegram_bot_client.remove_webhook()
        time.sleep(0.5)

        # set the webhook URL
        self.telegram_bot_client.set_webhook(url=f'{telegram_chat_url}/{token}/', timeout=60)

        logger.info(f'Telegram Bot information\n\n{self.telegram_bot_client.get_me()}')

    def send_text(self, chat_id, text):
        self.telegram_bot_client.send_message(chat_id, text)

    def send_text_with_quote(self, chat_id, text, quoted_msg_id):
        self.telegram_bot_client.send_message(chat_id, text, reply_to_message_id=quoted_msg_id)

    def is_current_msg_photo(self, msg):
        return 'photo' in msg

    def download_user_photo(self, msg):
        """
        Downloads the photos that sent to the Bot to `photos` directory (should be existed)
        :return:
        """
        # could also be return non instead of run time error
        if not self.is_current_msg_photo(msg):
            raise RuntimeError(f'Message content of type \'photo\' expected')
        else:
            try:
                file_info = self.telegram_bot_client.get_file(msg['photo'][-1]['file_id'])
                data = self.telegram_bot_client.download_file(file_info.file_path)
                folder_name = file_info.file_path.split('/')[0]

                if not os.path.exists(folder_name):
                    os.makedirs(folder_name)

                with open(file_info.file_path, 'wb') as photo:
                    photo.write(data)

                return file_info.file_path
            except Exception as e:
                logger.error(f'Error Downloading Photo: {e}')
                return None

    def send_photo(self, chat_id, img_path):
        if not os.path.exists(img_path):
            raise RuntimeError("Image path doesn't exist")

        self.telegram_bot_client.send_photo(
            chat_id,
            InputFile(img_path)
        )

    def handle_message(self, msg):
        """Bot Main message handler"""
        logger.info(f'Incoming message: {msg}')
        self.send_text(msg['chat']['id'], f'Your original message: {msg["text"]}')


class ObjectDetectionBot(Bot):
    def handle_message(self, msg):

        logger.info(f'Incoming message: {msg}')

        if self.is_current_msg_photo(msg):
            photo_path = self.download_user_photo(msg)

            # TODO upload the photo to S3
            s3_client = boto3.client('s3')
            if 'caption' in msg:
                caption = msg['caption']
            else:
                msg['caption'] = 'no-caption' + "_" + time.time()
                caption = msg['caption']
            s3_client.upload_file(photo_path, BUCKET_NAME, caption)
            # TODO send message to the Telegram end-user (e.g. Your image is being processed. Please wait...)
            # TODO send a job to the SQS queue
            sqs_client = boto3.client('sqs', region_name = REGION_NAME)
            sqs_client.send_message(QueueUrl=sqs_url, DelaySeconds = 10, MessageBody = str(msg))

            chat_id = msg['from']['id']  # amir...
            self.send_text(chat_id, "Your image is being processed. Please wait...")
