#!/bin/bash

ADMIN=$1
ROOM=$2

if [ "$#" -eq 2 ]
then
  curl -X POST \
        -H "Authorization: Token $ADMIN" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -d "{\"room\": \"$ROOM\", \"message_text\": true, \"room_update\": true, \"user_query\": true, \"user_room_join\": true}" \
        localhost/api/v2/token | sed 's/^"\(.*\)"$/\1/'
else
  echo "You need to specify the authorization token and a room identifier."
  echo "Ex: 'sh $0 \$ADMIN_TOKEN test_room'"
fi
