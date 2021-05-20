#!/bin/bash

# remove running containers
docker kill $(docker ps -q)
docker rm $(docker ps -aq)

# build docker images for bots
cd ../slurk-bots
docker build --tag "slurk/dito-bot" -f dito/Dockerfile dito
docker build --tag "slurk/concierge-bot" -f concierge/Dockerfile concierge

# run slurk
cd ../slurk
docker build --tag="slurk/server" -f docker/slurk/Dockerfile .
source scripts/start_slurk_server.sh
sleep 5

# create admin token
source scripts/get_admin_token.sh
echo "This is your admin token:"
echo $ADMIN_TOKEN

# create waitingroom 
WAITING_ROOM_LAYOUT=$(sh scripts/push_room_layout.sh $ADMIN_TOKEN ../slurk-bots/dito/data/waiting_room_layout.json)
sh scripts/create_room_with_layout.sh $ADMIN_TOKEN waiting_room "Waiting Room" $WAITING_ROOM_LAYOUT

# create task
DITO_ROOM_LAYOUT=$(sh scripts/push_room_layout.sh $ADMIN_TOKEN ../slurk-bots/dito/data/task_room_layout.json)
TASK_ID=$(sh ../slurk-bots/dito/scripts/create_task_with_layout.sh $ADMIN_TOKEN "dito" 2 $DITO_ROOM_LAYOUT)

# create concierge bot
CONCIERGE_BOT_TOKEN=$(sh scripts/create_token.sh $ADMIN_TOKEN waiting_room --concierge)
docker run -e TOKEN=$CONCIERGE_BOT_TOKEN --net="host" slurk/concierge-bot &
sleep 5

# create cola bot
DITO_BOT_TOKEN=$(sh ../slurk-bots/dito/scripts/create_token_for_dito_bot.sh $ADMIN_TOKEN waiting_room)
docker run -e TOKEN=$DITO_BOT_TOKEN -e DITO_TASK_ID=$TASK_ID --net="host" slurk/dito-bot &
sleep 5

# create two users
sh ../slurk-bots/dito/scripts/create_token_for_dito_user.sh $ADMIN_TOKEN waiting_room $TASK_ID
sh ../slurk-bots/dito/scripts/create_token_for_dito_user.sh $ADMIN_TOKEN waiting_room $TASK_ID

cd ../slurk-bots
