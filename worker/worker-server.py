#
# Worker server
#
import platform
import os
import sys
import json
import pika
import redis
import yake
import ffmpeg

import moviepy.editor as mp

from google.cloud import storage

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


##
# rabbitMQ declarations
##
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


##
# Method to extract keywords out of the audio transcript
##
def extract_keywords(transcript):
    language = "en"
    max_ngram_size = 2
    deduplication_threshold = 0.9

    # Use the yake Keyword Extraction model
    custom_kw_extractor = yake.KeywordExtractor(
        lan=language, n=max_ngram_size, dedupLim=deduplication_threshold, features=None)

    keywords = custom_kw_extractor.extract_keywords(transcript)
    keywords_set = set()

    for kw in keywords:
        keywords_set.add(kw[0])

    return keywords_set


##
# Method to transcribe audio to text using Google Speech Recognition.
# Only accepts '.wav' audio file types.
##
def transcribe_audio(audio_uri, video_name):
    from google.cloud import speech

    client = speech.SpeechClient()

    audio = speech.RecognitionAudio(uri=audio_uri)
    config = speech.RecognitionConfig(
        language_code="en-US",
        enable_word_time_offsets=True,
    )

    # Run Google Speech Recognition
    operation = client.long_running_recognize(
        config=config, audio=audio)

    print("Waiting for operation to complete...")
    result = operation.result()  # timeout=90
    # print(result)

    # Create database pipeline to update multiple keywords
    db_pipe = db.pipeline()

    for result in result.results:
        alternative = result.alternatives[0]
        print("Transcript: {}".format(alternative.transcript))
        print("Confidence: {}".format(alternative.confidence))

        # Extract keywords using yake
        keywords = extract_keywords(alternative.transcript)

        for word_info in alternative.words:
            word = word_info.word
            start_time = word_info.start_time
            end_time = word_info.end_time

            if word in keywords:
                word_res = db.get(word)
                print("word_res before-- ", word_res)
                if word_res:
                    word_result = word_res.decode("utf-8")
                    word_result += ";{}: T({}s)".format(
                        video_name, start_time.total_seconds())
                else:
                    word_result = "{}: T({}s)".format(
                        video_name, start_time.total_seconds())
                print("word_result after-- ", word_result)

                db_pipe.set(word, word_result)

            print(
                f"Word: {word}, start_time: {start_time.total_seconds()}, end_time: {end_time.total_seconds()}"
            )

    db_pipe.execute()

    print("Database updated.")


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

    return f"gs://{bucket_name}/{destination_blob_name}"


##
# Convert audio to mono channel audio if not already
##
def decode_audio(audio_filepath, filename):
    if audio_filepath and filename:
        audio_data = ffmpeg.probe(audio_filepath)
        print("audio_data --- ", audio_data)

        # Get audio channels
        audio_channel = audio_data['streams'][0]['channels']

        output_filename = ''

        # 1 = "mono"
        # 2 = "stereo"
        if audio_channel != 1:
            if audio_channel == 2:
                output_filename = filename.split(".wav")[0] + "_mono.wav"

                output_filepath = audio_filepath.split(".wav")[0] + "_mono.wav"
                ffmpeg.input(audio_filepath).output(
                    output_filepath, ac=1).run()
        else:
            output_filename = filename

        return output_filename


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

    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(destination_file_name)

    print(
        "Downloaded storage object {} from bucket {} to local file {}.".format(
            source_blob_name, bucket_name, destination_file_name
        )
    )


def callback(ch, method, properties, body):
    data = body.decode()

    jsonData = json.loads(data)

    bucket_name = jsonData["bucket_name"]
    source_name = jsonData["source_name"]

    upload_path = "data/uploads/"
    file_name = upload_path + source_name

    download_blob(bucket_name, source_name, file_name)

    # Extract audio out of the video in '.wav' audio format
    clip = mp.VideoFileClip(file_name)
    audio_file = upload_path + "{}.wav".format(source_name.split(".")[0])
    clip.audio.write_audiofile(audio_file)
    print("Extracted Audio")

    # Decode and save the audio to the local file system
    final_audio_filename = decode_audio(audio_file, source_name.split(".")[0])
    gcs_uri = upload_blob(bucket_name, upload_path +
                          final_audio_filename, final_audio_filename)

    # Perform speech recognition and save updated keywords to database
    transcribe_audio(gcs_uri, source_name.split(".")[0])


rabbitMQChannel.basic_consume(
    queue='toWorker', on_message_callback=callback, auto_ack=True)

rabbitMQChannel.start_consuming()
