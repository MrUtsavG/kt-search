#!/usr/bin/env python3

import requests
import json
import sys


##
# Use localhost & port 5000 if not specified by environment variable REST
##
REST = "34.149.160.137"


##
# The following routine makes a JSON REST query of the specified type
# and if a successful JSON reply is made, it pretty-prints the reply
##
def mkReq(reqmethod, endpoint, data, params=None):
    print(f"Response to http://{REST}/{endpoint} request is")
    jsonData = json.dumps(data)

    if params:
        response = reqmethod(f"http://{REST}/{endpoint}", params=params)
    else:
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
          "bucket_name": "kt-search-dump",
          "source_name": "Screen Recording 2.mov"
      }
      )

# Wait for operation to complete before searching for keywords.

'''

mkReq(requests.get, "apiv1/search", params={"q": "Liverpool"}, data=None)

'''

sys.exit(0)
