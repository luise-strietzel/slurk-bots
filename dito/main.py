# -*- coding: utf-8 -*-
# University of Potsdam
"""Commandline interface."""

import argparse
import logging
import os

from socketIO_client import SocketIO

from lib.dito_bot import DiToNamespace


# configure module logging
logging.basicConfig(format="%(levelname)s - %(asctime)s:%(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    level=logging.INFO)
LOG = logging.getLogger(__name__)


if __name__ == '__main__':
    LOG.info("DiTo bot started ...")

    # collect environment variables as defaults
    if 'TOKEN' in os.environ:
        token = {"default": os.environ["TOKEN"]}
    else:
        token = {"required": True}
    chat_host = {"default": os.environ.get("CHAT_HOST", "http://localhost")}
    chat_port = {"default": os.environ.get("CHAT_PORT")}
    task_id = {"default": os.environ.get("DITO_TASK_ID")}

    # configure commandline parser
    parser = argparse.ArgumentParser(
            description="DiTo Bot - Let's Spot the *Di*fference - *To*gether!",
            epilog="")

    parser.add_argument('-t', "--token",
                        help="authorization token with sufficient rights for all bot actions",
                        **token)
    parser.add_argument('-c', "--chat_host",
                        help="full URL (protocol, hostname) of chat server",
                        **chat_host)
    parser.add_argument('-p', "--chat_port",
                        type=int,
                        help="port of chat server",
                        **chat_port)
    parser.add_argument("--task_id",
                        type=int,
                        help="task the bot is involved in",
                        **task_id)

    args = parser.parse_args()

    uri = args.chat_host
    if args.chat_port:
        uri += f":{args.chat_port}"
    LOG.info(f"Running DiTo bot on {uri} with token {args.token}")
    uri += "/api/v2"

    DiToNamespace.task_id = args.task_id
    DiToNamespace.token = args.token
    DiToNamespace.uri = uri

    # passing token and name as additional information in request header
    socketIO = SocketIO(args.chat_host, args.chat_port,
                        headers={"Authorization": args.token, "Name": "DiTo Bot"},
                        Namespace=DiToNamespace)
    socketIO.wait()
