#!/usr/bin/env python3

import requests
import json
import time
import sys


#
# Use localhost & port 5000 if not specified by environment variable REST
#
REST = "<Enter Ingress Address Here>"

##
# The following routine makes a JSON REST query of the specified type
# and if a successful JSON reply is made, it pretty-prints the reply
##


def mkReq(reqmethod, endpoint, data):
    print(f"Response to http://{REST}/{endpoint} request is")
    jsonData = json.dumps(data)
    response = reqmethod(f"http://{REST}/{endpoint}", data=jsonData,
                         headers={'Content-type': 'application/json'})
    if response.status_code == 200:
        print(response)
        jsonResponse = json.dumps(response.json(), indent=4, sort_keys=True)
        print(jsonResponse)
        return
    else:
        print(
            f"response code is {response.status_code}, raw response is {response.text}")
        return response.text


mkReq(requests.post, "apiv1/upload",
      data={
          "video_url": "https://storage.cloud.google.com/kt-search-dump/Screen%20Recording%201.mov?authuser=1",
          "video_name": "Screen Recording Test1",
          "video_ext": "mov"
      }
      )

'''
print('Waiting for action to complete...')

time.sleep(80)

print('Action completed...')

mkReq(requests.get, "apiv1/cache/sentiment", data=None)

mkReq(requests.get, "apiv1/sentence",
      data={
          "model": "sentiment",
          "sentences": [
                    "I think this is a good thing",
                    "This thing sucks",
                    "I don't like that one I guess"
          ]
      }
      )
'''
sys.exit(0)
