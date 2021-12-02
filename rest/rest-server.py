##
import logging
from flask import Flask, request, Response
import os
import sys
import pika
import redis
import json
import jsonpickle

##
# Configure test vs. production
##
redisHost = os.getenv("REDIS_HOST") or "localhost"
rabbitMQHost = os.getenv("RABBITMQ_HOST") or "localhost"

print("Connecting to rabbitmq({}) and redis({})".format(rabbitMQHost, redisHost))

db = redis.Redis(host=redisHost, db=1)

app = Flask(__name__)

log = logging.getLogger('werkzeug')
log.setLevel(logging.DEBUG)

#
# Main page
#


@app.route('/')
def root():
    return "<h1>KT Search Server</h1>"


#
# Upload endpoint - To upload KT videos
#
@app.route('/apiv1/upload', methods=['POST'])
def upload():
    # Establish a new RabbitMQ connection
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=rabbitMQHost))
    channel = connection.channel()
    try:
        jsonData = request.get_json()
        print(jsonData)

        channel.exchange_declare(exchange='toWorker', exchange_type='direct')

        message = json.dumps(jsonData)
        channel.basic_publish(
            exchange='toWorker', routing_key='upload', body=message)

        resp = {"action": "completed"}
    except:
        resp = {"action": "Exception occured"}

    connection.close()

    sys.stdout.flush()

    response_pickled = jsonpickle.encode(resp)
    return Response(response=response_pickled, status=200, mimetype="application/json")


#
# Search endpoint - To search for words mentioned in the uploaded videos
#
@app.route('/apiv1/search', methods=['GET'])
def search():
    query = request.args.get("q")

    value = db.get(query)

    result = []

    for vid, timestamp in value:
        result.append((vid, timestamp))

    if len(result) > 0:
        data = {"result": result}
    else:
        data = {"result": "No results found."}

    sys.stdout.flush()

    response_pickled = jsonpickle.encode(data)
    return Response(response=response_pickled, status=200, mimetype="application/json")


# start flask app
app.run(host="0.0.0.0", port=5000)
