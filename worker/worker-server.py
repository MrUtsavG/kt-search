#
# Worker server
#
import base64
import platform
import io
import os
import sys
import pika
import redis
import hashlib
import json

import moviepy.editor as mp

from urllib3 import request
from contextlib import closing


hostname = platform.node()

##
# Configure test vs. production
##
redisHost = os.getenv("REDIS_HOST") or "localhost"
rabbitMQHost = os.getenv("RABBITMQ_HOST") or "localhost"

print(f"Connecting to rabbitmq({rabbitMQHost}) and redis({redisHost})")

##
# Set up redis connections
##
db = redis.Redis(host=redisHost, db=1)

##
# Set up rabbitmq connection
##
rabbitMQ = pika.BlockingConnection(
    pika.ConnectionParameters(host=rabbitMQHost))
rabbitMQChannel = rabbitMQ.channel()

rabbitMQChannel.exchange_declare(exchange='toWorker', exchange_type='direct')

rabbitMQChannel.queue_declare(queue='toWorker')
rabbitMQChannel.exchange_declare(exchange='logs', exchange_type='topic')
infoKey = f"{platform.node()}.worker.info"
debugKey = f"{platform.node()}.worker.debug"


def log_debug(message, key=debugKey):
    print("DEBUG:", message, file=sys.stdout)
    rabbitMQChannel.basic_publish(
        exchange='logs', routing_key=key, body=message)


def log_info(message, key=infoKey):
    print("INFO:", message, file=sys.stdout)
    rabbitMQChannel.basic_publish(
        exchange='logs', routing_key=key, body=message)


rabbitMQChannel.queue_bind(
    exchange='toWorker', queue='toWorker', routing_key='upload')

#
# Upload video helper - To upload to Google Cloud Storage
#


def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"
    # The path to your file to upload
    # source_file_name = "local/path/to/file"
    # The ID of your GCS object
    # destination_blob_name = "storage-object-name"

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)

    print(
        "File {} uploaded to {}.".format(
            source_file_name, destination_blob_name
        )
    )


def download_blob(bucket_name, source_blob_name, destination_file_name):
    """Downloads a blob from the bucket."""
    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"

    # The ID of your GCS object
    # source_blob_name = "storage-object-name"

    # The path to which the file should be downloaded
    # destination_file_name = "local/path/to/file"

    storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)

    # Construct a client side representation of a blob.
    # Note `Bucket.blob` differs from `Bucket.get_blob` as it doesn't retrieve
    # any content from Google Cloud Storage. As we don't need additional data,
    # using `Bucket.blob` is preferred here.
    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(destination_file_name)

    print(
        "Downloaded storage object {} from bucket {} to local file {}.".format(
            source_blob_name, bucket_name, destination_file_name
        )
    )


def transcribe_audio(speech_file):
    """Transcribe the given audio file asynchronously and output the word time
    offsets."""
    from google.cloud import speech

    client = speech.SpeechClient()

    def encode_audio(audio_file):
        with open(audio_file, "rb") as audio:
            content = audio.read()

        return base64.b64encode(content)

    audio_content = encode_audio(speech_file)

    audio = speech.RecognitionAudio(content=audio_content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
        sample_rate_hertz=16000,
        language_code="en-US",
        enable_word_time_offsets=True,
    )

    operation = client.long_running_recognize(config=config, audio=audio)

    print("Waiting for operation to complete...")
    result = operation.result(timeout=90)

    for result in result.results:
        alternative = result.alternatives[0]
        print("Transcript: {}".format(alternative.transcript))
        print("Confidence: {}".format(alternative.confidence))

        for word_info in alternative.words:
            word = word_info.word
            start_time = word_info.start_time
            end_time = word_info.end_time

            print(
                f"Word: {word}, start_time: {start_time.total_seconds()}, end_time: {end_time.total_seconds()}"
            )


def callback(ch, method, properties, body):
    data = body.decode()
    print(" [x] %r:" % (method.routing_key))
    print("Callback data--- ", data)

    jsonData = json.loads(data)

    video_url = jsonData["video_url"]
    video_name = jsonData["video_name"]
    video_ext = jsonData["video_ext"]

    file_name = r"data/uploads/{}.{}".format(video_name, video_ext)

    with open(file_name, 'wb') as out_file:
        with closing(request.urlopen(video_url)) as fp:
            block_size = 1024 * 8
            while True:
                block = fp.read(block_size)
                if not block:
                    break
                out_file.write(block)

    clip = mp.VideoFileClip(file_name)

    audio_file = r"data/uploads/{}.wav".format(video_name)
    clip.audio.write_audiofile(audio_file)

    # transcribe_audio(audio_file)


rabbitMQChannel.basic_consume(
    queue='toWorker', on_message_callback=callback, auto_ack=True)

rabbitMQChannel.start_consuming()
