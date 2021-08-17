'''slurk link generator'''

import random
import configparser
import requests
import json


LINKS_LIST = []

CONFIG = configparser.ConfigParser()
CONFIG.read('config.ini')

with open('adj.txt', 'r') as adj_file:
    ADJ = adj_file.read().splitlines()


def insert_names_and_tokens(n_hits):
    '''generate slurk tokens for players'''
    for item in range(n_hits):
        # generate random name for the turker
        full_name = random.choice(ADJ)

        # header stays the same for all requests
        TOKEN = CONFIG['slurk']['admin_token']
        headers = {
            'Accept': 'application/json',
            'Authorization': f"Bearer {TOKEN}",
            'Content-Type': 'application/json',
        }

        # first set permissions
        data = open('dito_user_permissions.json').read()
        url = CONFIG['link_generator']['permissions_url']
        response = requests.post(url, headers=headers, data=data).json()
        permissions_id = response['id']

        # then get the token
        data = {
            "permissions_id": permissions_id,
            "room_id": int(CONFIG['slurk']['room_id']),
            "task_id": int(CONFIG['slurk']['task_id'])
        }
        url = CONFIG['link_generator']['token_url']
        response = requests.post(url, headers=headers, data=json.dumps(data)).json()
        login_token = response['id']

        # finally construct the url link
        uris = CONFIG['login']['url']+'/login?name={}&token={}'.format(full_name, login_token)
        LINKS_LIST.append(uris)

    return LINKS_LIST


if __name__ == '__main__':
    GENER_LINKS = insert_names_and_tokens(2)
    print(GENER_LINKS)

