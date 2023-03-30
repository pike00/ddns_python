#!/usr/bin/python3
import json
import os.path
import urllib.parse
import urllib.parse

import pushover
# Create JSON configuration if it doesn't exist
import requests

import logging
import sys

import argparse

parser = argparse.ArgumentParser(description="Use this command to update DNS entries in cloudflare")

parser.add_argument('--debug', help = "Show debug code", action="store_true")

args = parser.parse_args()

if args.debug:
    log_level = logging.DEBUG
else:
    log_level = logging.ERROR

logging.basicConfig(stream=sys.stderr,
                    level = log_level,
                    format='%(levelname)s: %(message)s')
#logging.basicConfig(stream=sys.stderr, level = logging.DEBUG)


logging.getLogger("requests").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


DDNS_FOLDER = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(DDNS_FOLDER, "config.json")

logging.debug("The DDNS Folder is located at %s",DDNS_FOLDER)
logging.debug("Config File exists? (%s) %s", CONFIG_FILE, str(os.path.exists(CONFIG_FILE)))

if not os.path.isfile(CONFIG_FILE):
    pushover_dict = dict()
    pushover_dict['key_user'] = input("Enter Pushover User Key: ")
    pushover_dict['key_app'] = input("Enter Pushover App Key: ")

    cloudflare_dict = dict()
    cloudflare_dict['url'] = "https://api.cloudflare.com/client/v4/"
    cloudflare_dict['api_token'] = input("Enter your Cloudflare API Token: ")
    cloudflare_dict['id_zone'] = input("Enter your Cloudflare Zone ID: ")
    cloudflare_dict['domain'] = input("Enter your Cloudflare Domain you'd like to update: ")

    dictionary = {
        "pushover": pushover_dict,
        "cloudflare": cloudflare_dict
    }

    with open(CONFIG_FILE, "w") as outfile:
        outfile.write(json.dumps(dictionary, indent=2))


# Load config from file
with open(CONFIG_FILE) as config_file:
    config = json.load(config_file)

logging.debug("Pushover Parameters: %s", config['pushover'])
logging.debug("Cloudflare Parameters: %s", config['cloudflare'])

# Initialize pushover
pushover.init(config['pushover']['key_app'])
pushover_client = pushover.Client(config['pushover']['key_user'])

list_data = {
    "type": "A",
    "name": config['cloudflare']['domain']
}


def urljoin(parts):
    if len(parts) > 1:
        parts = [urllib.parse.urljoin(parts[0], parts[1])] + parts[2:]
        return urljoin(parts)

    return parts[0]


# Get the URL ID
url_list = config['cloudflare']['url'] + \
           "zones/" + \
           config['cloudflare']['id_zone'] + "/" + \
           "dns_records?" + urllib.parse.urlencode(list_data)

logging.debug("URL List: " + url_list)

headers = {"Authorization": "Bearer " + config['cloudflare']['api_token'],
           "Content-Type": "application/json"}

data_list_req = requests.get(url_list, headers=headers)

list_json = data_list_req.json()

logging.debug(list_json)

message = ""

if list_json['result_info']['count'] == 0:
    message = "Did not find any DNS records for " + config['cloudflare']['domain']
elif list_json['result_info']['count'] > 1:
    message = "Found more than one DNS record for " + config['cloudflare']['domain']
if not list_json['success']:
    message = "Could not get ID for " + config['cloudflare']['url'] + ". " + \
              json.dumps(list_json['errors'])
else:  # Successfuly found ONE ID
    id_url = list_json['result'][0]['id']

# if the message isn't blank, there was a problem getting the ID
if message != "":
    pushover_client.send_message(message)
    exit(1)

# Get current IP
ip_req = requests.get("http://api.ipify.org")

if ip_req.status_code != 200:
    print("Unable to get IP. Exiting")
    exit(1)

ip = ip_req.text.strip()

# Create URL request
url_update = config['cloudflare']['url'] + \
             "zones/" + \
             config['cloudflare']['id_zone'] + \
             "/dns_records/" + \
             id_url

# Create data to send
data = {
    "type": "A",
    "name": config['cloudflare']['domain'],
    "content": ip,
    "ttl": 120
}


cloudflare_req = requests.put(url_update,
                              headers=headers,
                              data=json.dumps(data))

dns_json = cloudflare_req.json()

if dns_json['success']:
    logging.info("DNS successfully updated. %s now points to %s", config['cloudflare']['domain'], ip)
    exit(0)
else:
    pushover_client.send_message("DNS updated failed: " + json.dumps(dns_json['errors']))
