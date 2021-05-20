#!/bin/bash

ADMIN=$1
TASK_NAME=$2
USERS=$3
TASK_ROOM_LAYOUT=$4

if [ "$#" -eq 4 ]
then
  curl -X POST \
         -H "Authorization: Token $ADMIN" \
         -H "Content-Type: application/json" \
         -H "Accept: application/json" \
         -d "{\"name\": \"$TASK_NAME\", \"num_users\": $USERS, \"layout\": $TASK_ROOM_LAYOUT}" \
         localhost/api/v2/task | jq .id
else
  echo "You need to specify the authorization token, a task name, the number of users and a layout."
  echo "Ex: 'sh $0 \$ADMIN_TOKEN \"Echo Task\" 2 \$ROOM_LAYOUT'"
fi
