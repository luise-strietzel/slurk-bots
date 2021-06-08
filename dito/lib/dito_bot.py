# -*- coding: utf-8 -*-

# University of Potsdam
"""DiTo bot logic including dialog and game phases."""

import configparser
import json
import functools
import logging
import os
import random
import string
from threading import Timer
from time import sleep

import requests
from socketIO_client import BaseNamespace

from lib.image_data import ImageData


LOG = logging.getLogger(__name__)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RoomTimers:
    """A number of timed events during the game.

    Attributes:
        ready_timer (Timer): Reminds both players 1min after
            having entered the task room that they have to send /ready
            to begin the game if none of them did so until then.
            If one already sent ready then the other player is
            reminded 30s later that they should do so too.
        game_timer (Timer): Triggered 3min after a new image pair
            was presented and the players did not yet end their
            discussion with /done to kindly ask them to do so.
        done_timer (Timer): Resets a sent /done command for one
            player if their partner did not agree within 30s.
        last_answer_timer (Timer): Used to end the game if one
            player did not receive an answer for 90s.
    """
    def __init__(self):
        self.ready_timer = None
        self.game_timer = None
        self.done_timer = None
        self.last_answer_timer = None


class DiToNamespace(BaseNamespace):
    """The ID of the task the bot is involved in."""
    task_id = None
    """The authentification token used to send requests."""
    token = None
    """Base address for requests."""
    uri = None

    def __init__(self, io, path):
        """Called once when the bot is started.

        Attributes:
            images_per_room (dict): Each room is mapped to a list
                of pairs with two image urls. Each participant
                is presented exactly one image per pair and round.
            timers_per_room (dict): Each room is mapped to
                an instance of RoomTimers.
            players_per_room (dict): Each room is mapped to a list of
                users. Each user is represented as a dict with the
                keys 'name' and 'id'.
            ready_per_room (dict): Each room is mapped to a set of
                user ids that have already sent the /ready command.
            done_per_room (dict): Each room is mapped to a set of
                user ids that have already sent the /done command.
                Resetted once a new image pair is shown.
            messages_per_room (dict): Each room is mapped to an integer
                indicating how many messages were sent in the running
                game round. Resetted once a new image pair is shown.
            last_message_from (dict): Each room is mapped to the user
                that has answered last. A user is represented as a
                dict with the keys 'name' and 'id'.
            waiting_timer (Timer): Only one user can be in the waiting
                room at a time because the concierge bot would move
                them once there are two. If this single user waits for
                longer than 5min we generate him an amt token.
            id (int): The user id of the bot.
        """
        super().__init__(io, path)
        LOG.info("DiTo bot at your command ^^>")

        config_file = os.path.join(ROOT, "data", "config.cfg")
        self.images_per_room = ImageData.from_config(config_file)
        self.timers_per_room = dict()
        self.players_per_room = dict()
        self.ready_per_room = dict()
        self.done_per_room = dict()
        self.messages_per_room = dict()
        self.last_message_from = dict()

        self.waiting_timer = None
        self.received_waiting_token = set()

        self.id = None
        self.config = configparser.ConfigParser()
        with open(config_file, 'r', encoding="utf-8") as conf:
            self.config.read_file(conf)
        # let the bot enter its initial room (i.e. waiting_room)
        self.emit("ready")

    def on_new_task_room(self, data):
        """Triggered after a new task room is created.

        An example scenario would be that the concierge
        bot emitted a room_created event once enough
        users for a task have entered the waiting room.

        Args:
            data (dict):
                {'room': <room_id_string>,
                'task': <task_id_int>,
                'users': <list of dicts
                    {'id': <user_id_int>,
                    'name': <user_name_string>}
                >}
        """
        LOG.info(f"A new task room was created with id: {data['task']}")
        LOG.info(f"This bot is looking for task id: {self.task_id}")

        if data["task"] == self.task_id:
            # the user does no longer wait
            self.waiting_timer.cancel()
            for usr in data['users']:
                if usr['id'] in self.received_waiting_token:
                    self.received_waiting_token.remove(usr['id'])

            # create image items for this room
            LOG.info("Create data for the new task room...")
            room = data["room"]

            self.images_per_room.get_image_pairs(room)
            self.players_per_room[room] = data["users"]
            self.ready_per_room[room] = set()
            self.done_per_room[room] = set()
            self.messages_per_room[room] = 0
            self.last_message_from[room] = None

            # register ready timer for this room
            self.timers_per_room[room] = RoomTimers()
            self.timers_per_room[room].ready_timer = Timer(
                self.config.getfloat("TIMERS", "ready")*60,
                self.emit, args=[
                    "text",
                    {"msg": "Are you ready? "
                            "Please type **/ready** to begin the game.",
                     "room": room,
                     "html": True}
                ]
            )
            self.timers_per_room[room].ready_timer.start()

            # let the bot in charge join this room
            self.emit("join_room", {"user": self.id, "room": room})

    def on_joined_room(self, data):
        """Triggered once after the bot joins a room.

        Args:
            data (dict):
                {'room': room.name,
                'user':  user.id}
        """
        room = data["room"]
        # let the bot know about its own user id
        if self.id is None:
            self.id = data["user"]

        if room != "waiting_room":
            LOG.info(f"I have joined a new task room: {room}")

            # read out the instruction file
            instr_f = os.path.join(ROOT, "data", "instructions.json")
            with open(instr_f, 'r', encoding="utf-8") as f:
                data = json.load(f)
                line = ""
                for line in data["greeting"]:
                    line = line.strip().replace("\\n", "\n")
                    self.emit(
                        "text",
                        {"msg": line,
                         "room": room,
                         "html": True}
                    )
                    sleep(.5)
                self.emit(
                    "set_text",
                    {"room": room,
                     "id": "instr_title",
                     "text": line}
                )

    def on_status(self, data):
        """Triggered if a user connects or disconnects while in a room.

        Args:
            data (dict):
                {'type': <'join'/'leave'>,
                'room': <room_id_string>,
                'user': {
                    'id': <user_id_int>,
                    'name': <user_name_string>,
                },
                'timestamp': <time_of_event>}
        """
        # check whether the user is eligible to join this task
        task = requests.get(
            f"{self.uri}/user/{data['user']['id']}/task",
            headers={'Authorization': f"Token {self.token}"}
        )
        sleep(.5)
        if (not task.ok or task.json() is None 
                or task.json()["id"] != self.task_id):
            return

        if data["type"] == "join":
            LOG.info(f"{data['user']['name']} has joined {data['room']}.")
            if data["room"] == "waiting_room":
                # a thread might need some time after cancel to die
                sleep(2)
                if (self.waiting_timer is None
                        or not self.waiting_timer.is_alive()):
                    LOG.info("This user has to wait.")
                    self.waiting_timer = Timer(
                        self.config.getfloat("TIMERS", "waiting")*60,
                        self._no_partner,
                        args=[
                            data["user"]["id"],
                            data["room"]
                        ]
                    )
                    self.waiting_timer.start()

            elif data["room"] in self.images_per_room:
                curr_usr, other_usr = self.players_per_room[data["room"]]
                if curr_usr["id"] != data["user"]["id"]:
                    curr_usr, other_usr = other_usr, curr_usr

                # inform game partner about the rejoin event
                self.emit(
                    "text",
                    {"msg": f"{curr_usr['name']} has rejoined the game. ",
                     "room": data["room"],
                     "receiver_id": other_usr["id"]}
                )

                users_ready = self.ready_per_room[data['room']]
                LOG.info(f"{len(users_ready)} users are ready in this room.")
                if len(users_ready) == 2:
                    # update the display for the joined user
                    # when the game is already running
                    rejoin_timer = Timer(
                        2*1,
                        self.show_item,
                        args=[data["room"]]
                    )
                    rejoin_timer.start()
                for usr in self.players_per_room[data["room"]]:
                    # otherwise remind users that they have to send /ready
                    if usr["id"] not in users_ready:
                        self.emit(
                            "text",
                            {"msg": "Type **/ready** to begin the game.",
                             "room": data["room"],
                             "receiver_id": usr["id"],
                             "html": True}
                        )

        # a player left the room
        if data["type"] == "leave":
            LOG.info(f"{data['user']['name']} has left {data['room']}.")
            if (data["room"] == "waiting_room"
                    and self.waiting_timer is not None):
                # cancel the waiting timer when the user disconnects
                self.waiting_timer.cancel()
            elif data["room"] in self.images_per_room:
                curr_usr, other_usr = self.players_per_room[data["room"]]
                if curr_usr["id"] != data["user"]["id"]:
                    curr_usr, other_usr = other_usr, curr_usr

                # send a message to the user that was left alone
                self.emit(
                    "text",
                    {"msg": f"{curr_usr['name']} has left the game. "
                            "Please wait a bit, your partner may rejoin.",
                     "room": data["room"],
                     "receiver_id": other_usr["id"]}
                )

    def on_text_message(self, data):
        """Triggered once a text message is sent (no leading /).

        Count user text messages.
        If encountering something that looks like a command
        then pass it on to be parsed as such.

        Args:
            data (dict):
                {'msg': <text string>,
                'room': <room_id_string>,
                'user': {
                    'id': <user_id_int>,
                    'name': <user_name_string>,
                },
                'room': room.name if room else None,
                'timestamp': <timestamp>,
                'private': <is_private_bool>,
                'html': <apply_format_bool>}
        """
        # filter irrelevant messages
        if (data["room"] not in self.images_per_room
                or data["user"]["id"] == self.id):
            return
        # the user accidently sent a command as a message
        if (data["msg"].startswith("ready")
                or data["msg"].startswith("done")
                or data["msg"] in {"noreply", "no reply"}):
            data["command"] = data["msg"]
            self.on_command(data)
        # the user sent a normal text message
        else:
            # reset the answer timer if the message was an answer
            if data["user"] != self.last_message_from[data["room"]]:
                LOG.info(f"{data['user']['name']} awaits an answer.")
                answ_tmr = self.timers_per_room[data["room"]].last_answer_timer
                if answ_tmr is not None:
                    self.timers_per_room[data["room"]].last_answer_timer.cancel()
                self.timers_per_room[data["room"]].last_answer_timer = Timer(
                    self.config.getfloat("TIMERS", "answer")*60,
                    self._noreply,
                    args=[data]
                )
                self.timers_per_room[data["room"]].last_answer_timer.start()
                # save the person that last left a message
                self.last_message_from[data["room"]] = data["user"]
            # if the message is part of the main discussion count it
            if len(self.ready_per_room[data['room']]) == 2:
                self.messages_per_room[data["room"]] += 1

    def on_command(self, data):
        """Parse user commands.

        Args:
            data (dict):
                {'command': <text string>,
                'room': <room_id_string>,
                'user': {
                    'id': <user_id_int>,
                    'name': <user_name_string>,
                },
                'room': room.name if room else None,
                'timestamp': <timestamp>,
                'private': <is_private_bool>}
        """
        if data["room"] in self.images_per_room:
            if data["command"].startswith("ready"):
                LOG.info("I have received a **/ready** command "
                         f"from {data['user']['name']}.")
                self._command_ready(data)
            elif data["command"].startswith("done"):
                LOG.info(f"I have received a **/done** command "
                         f"from {data['user']['name']}.")
                self._command_done(data)
            elif data["command"] in {"noreply", "no reply"}:
                LOG.info("I have received a **/noreply** command "
                         f"from {data['user']['name']}.")
                self.emit(
                    "text",
                    {"msg": "Please wait some more for an answer.",
                     "room": data["room"],
                     "receiver_id": data["user"]["id"]}
                )
            else:
                self.emit(
                    "text",
                    {"msg": "Sorry, but I do not understand this command.",
                     "room": data["room"],
                     "receiver_id": data["user"]["id"]}
                )

    def _command_ready(self, data):
        """Must be sent to begin a conversation."""
        room = data["room"]
        # identify the user that has not sent this event
        curr_usr, other_usr = self.players_per_room[room]
        if curr_usr["id"] != data["user"]["id"]:
            curr_usr, other_usr = other_usr, curr_usr

        # only one user has sent /ready repetitively
        if curr_usr["id"] in self.ready_per_room[room]:
            sleep(.5)
            self.emit(
                "text",
                {"msg": "You have already typed /ready.",
                 "receiver_id": curr_usr["id"],
                 "room": room}
            )
            return

        self.ready_per_room[room].add(curr_usr["id"])
        self.timers_per_room[room].ready_timer.cancel()
        # a first ready command was sent
        if len(self.ready_per_room[room]) == 1:
            sleep(.5)
            # give the user feedback that his command arrived
            self.emit(
                "text",
                {"msg": "Now, waiting for your partner to type /ready.",
                 "receiver_id": curr_usr["id"],
                 "room": room}
            )
            # give the other user 30sec before reminding him
            self.timers_per_room[room].ready_timer = Timer(
                (self.config.getfloat("TIMERS", "ready")/2)*60,
                self.emit,
                args=[
                    "text",
                    {"msg": "Your partner is ready. Please, type /ready!",
                     "room": room,
                     "receiver_id": other_usr["id"]}
                ]
            )
            self.timers_per_room[room].ready_timer.start()
        else:
            # both users are ready and the game begins
            self.emit(
                "text",
                {"msg": "Woo-Hoo! The game will begin now.",
                 "room": room}
            )
            self.show_item(room)
            # kindly ask the users to come to an end after 5minutes
            self.timers_per_room[room].game_timer = Timer(
                self.config.getfloat("TIMERS", "game")*60,
                self.emit,
                args=[
                    "text",
                    {"msg": "You both seem to be having a discussion "
                            "for a long time. Could you reach an "
                            "agreement and provide an answer?",
                     "room": room}
                ]
            )
            self.timers_per_room[room].game_timer.start()

    def _command_done(self, data):
        """Must be sent to end a game round."""
        room = data["room"]
        # identify the user that has not sent this event
        curr_usr, other_usr = self.players_per_room[room]
        if curr_usr["id"] != data["user"]["id"]:
            curr_usr, other_usr = other_usr, curr_usr
        # one can't be done before one is ready
        if len(self.ready_per_room[room]) != 2:
            self.emit(
                "text",
                {"msg": "The game has not started yet.",
                 "receiver_id": curr_usr["id"],
                 "room": room}
            )
        # we expect at least 5 messages alltogether for this round
        elif self.messages_per_room[room] < 5:
            self.emit(
                "text",
                {"msg": "Are you sure? Please discuss some more!",
                 "receiver_id": curr_usr["id"],
                 "room": room}
            )
        elif curr_usr["id"] not in self.done_per_room[room]:
            self.done_per_room[room].add(curr_usr["id"])
            # both user think they are done
            if len(self.done_per_room[room]) == 2:
                self.timers_per_room[data["room"]].done_timer.cancel()
                self.images_per_room[room].pop(0)
                # was this the last game round?
                if self.images_per_room[room] == []:
                    self.emit(
                        "text",
                        {"msg": "The game is over! Thank you for participating!",
                         "room": room}
                    )
                    sleep(1)
                    self.confirmation_code(room, "success")
                    sleep(1)
                    self.close_game(room)
                else:
                    self.emit(
                        "text",
                        {"msg": "Ok, let's get both of you the next image. "
                                f"{len(self.images_per_room[room])} to go!",
                         "room": room}
                    )
                    # reset attributes for the new round
                    self.done_per_room[room] = set()
                    self.messages_per_room[room] = 0
                    self.timers_per_room[room].game_timer.cancel()
                    self.timers_per_room[room].game_timer = Timer(
                        self.config.getfloat("TIMERS", "game")*60,
                        self.emit,
                        args=[
                            "text",
                            {"msg": "You both seem to be having a discussion "
                                    "for a long time. Could you reach an "
                                    "agreement and provide an answer?",
                             "room": room}
                        ]
                    )
                    self.timers_per_room[room].game_timer.start()

                    self.show_item(room)
            # only one user has sent done so far
            else:
                # a sent done is resetted if there is no done
                # from the other user for 30s
                self.timers_per_room[room].done_timer = Timer(
                    .5*60,
                    self._not_done,
                    args=[data]
                )
                self.timers_per_room[room].done_timer.start()
                self.emit(
                    "text",
                    {"msg": "Let's wait for your partner "
                            "to also type **/done**.",
                     "receiver_id": curr_usr["id"],
                     "room": room,
                     "html": True}
                )
                self.emit(
                    "text",
                    {"msg": "Your partner thinks that you "
                            "have found the difference. "
                            "Type **/done** if you agree with him.",
                     "receiver_id": other_usr["id"],
                     "room": room,
                     "html": True}
                )
        # this user alreasy typed run and it was not resetted
        else:
            sleep(.5)
            self.emit(
                "text",
                {"msg": "You have already typed **/done**.",
                 "receiver_id": curr_usr["id"],
                 "room": room,
                 "html": True}
            )

    def _not_done(self, data):
        """One of the two players was not done."""
        self.done_per_room[data["room"]] = set()
        self.emit(
            "text",
            {"msg": "Your partner seems to still want to discuss some more. "
                    "Send /done again once you two are really finished.",
             "receiver_id": data["user"]["id"],
             "room": data["room"]}
        )

    def show_item(self, room):
        """Update the image and task description of the players.

        Args:
            room: Unique room identifier as used by slurk.
        """
        LOG.info("Update the image and task description of the players.")
        # guarantee fixed user order - necessary for update due to rejoin
        users = sorted(self.players_per_room[room], key=lambda x: x.items())
        LOG.info(users)

        if self.images_per_room[room] != []:
            images = self.images_per_room[room][0]
            # show a different image to each user
            for usr, img in zip(users, images):
                self.emit(
                    "set_attribute",
                    {"id": "current-image",
                     "attribute": "src",
                     "value": img,
                     "room": room,
                     "receiver_id": usr["id"]}
                )
            instr_f = os.path.join(ROOT, "data", "instructions.json")
            with open(instr_f, 'r', encoding="utf-8") as f:
                data = json.load(f)
                # the task for both users is the same - no special receiver
                self.emit(
                    "set_text",
                    {"id": "instr_title",
                     "text": data["instr_title"],
                     "room": room}
                )
                self.emit(
                    "set_text",
                    {"id": "instr",
                     "text": data["instr"],
                     "room": room}
                )

    def _no_partner(self, user_id, room):
        """Handle the situation that a participant waits in vain.

        Args:
            room (string): The room where
            user_id (int): User that has waited for a specified time.
        """
        if user_id not in self.received_waiting_token:
            self.emit(
                "text",
                {"msg": "Unfortunately we could not find a partner for you!",
                 "room": "waiting_room", "receiver_id": user_id}
            )
            # create token and send it to user
            self.confirmation_code("waiting_room",
                                   "no_partner",
                                   receiver_id=user_id)
            sleep(5)
            self.emit(
                "text",
                {"msg": "You may also wait some more :)",
                 "room": room, "receiver_id": user_id}
             )
            # no need to cancel as the running out of this timer
            # triggered this event
            self.waiting_timer = Timer(
                self.config.getfloat("TIMERS", "waiting")*60,
                self._no_partner,
                args=[user_id, room]
            )
            self.waiting_timer.start()
            self.received_waiting_token.add(user_id)
        else:
            self.emit(
                "text",
                {"msg": "You won't be remunerated for further waiting time.",
                 "room": room, "receiver_id": user_id}
            )
            sleep(2)
            self.emit(
                "text",
                {"msg": "Please check back at another time of the day.",
                 "room": room, "receiver_id": user_id}
            )

    def _noreply(self, data):
        """One participant did not receive an answer for a while."""
        curr_usr, other_usr = self.players_per_room[data["room"]]
        if curr_usr["id"] != data["user"]["id"]:
            curr_usr, other_usr = other_usr, curr_usr

        room = data["room"]
        self.emit(
            "text",
            {"msg": "The game ended because you were gone for too long!",
             "room": room,
             "receiver_id": other_usr["id"]}
        )
        self.emit(
            "text",
            {"msg": "Your partner seems to be away for a long time!",
             "room": room,
             "receiver_id": curr_usr["id"]}
        )
        # create token and send it to user
        self.confirmation_code(room,
                               "no_reply",
                               receiver_id=curr_usr["id"])
        self.close_game(room)

    def confirmation_code(self, room, status, receiver_id=None):
        """Generate AMT token that will be sent to each player.

        Args:
            room (string): Unique room identifier.
            status (string): One out of 'success'/'no_partner'

        Returns:
            str: A six character long random code.
        """
        kwargs = dict()
        # either only for one user or for both
        if receiver_id is not None:
            kwargs["receiver_id"] = receiver_id

        amt_token = ''.join(random.choices(
            string.ascii_uppercase + string.digits, k=6
        ))
        self.emit(
            "log",
            {"room": room, "type": "confirmation_log",
             "amt_token": amt_token, "status_txt": status}
        )
        self.emit(
            "text",
            {"msg": "Please enter the following token into the field on "
                    "the HIT webpage, and close this browser window. ",
             "room": room, **kwargs}
        )
        self.emit(
            "text",
            {"msg": f"Here is your token: {amt_token}",
             "room": room, **kwargs}
        )
        return amt_token

    def close_game(self, room):
        """Hide the chat entry area from view.

        Args:
            room (str): Unique room identifier.
        """
        self.emit(
            "text",
            {"msg": "You will be moved out of this room in 30s.",
             "room": room}
        )
        sleep(2)
        self.emit(
            "text",
            {"msg": "Make sure to copy your token before that.",
             "room": room}
        )
        # set the room to read only
        response = requests.put(
            f"{self.uri}/room/{room}",
            headers={'Authorization': f"Token {self.token}"},
            json=dict(read_only=True)
        )
        # disable all timers
        for timer_name in {"ready_timer", "game_timer", "done_timer", "last_answer_timer"}:
            timer = getattr(self.timers_per_room[room], timer_name)
            if timer is not None:
                timer.cancel()

        sleep(15)
        for usr in self.players_per_room[room]:
            sleep(15)
            self.emit("join_room", {"user": usr["id"], "room": "waiting_room"})
            self.emit("leave_room", {"user": usr["id"], "room": room})

            self.emit(
                "text",
                {"msg": "Please refresh this page if you are interested in playing another round.",
                 "room": "waiting_room",
                 "receiver_id": usr["id"]}
            )

        self.rename_users(room)

        # remove any info only needed for a running game
        self.images_per_room.pop(room)
        self.timers_per_room.pop(room)
        self.players_per_room.pop(room)
        self.ready_per_room.pop(room)
        self.done_per_room.pop(room)
        self.messages_per_room.pop(room)

    def rename_users(self, room):
        response = requests.get(
                        f"{self.uri}/users",
                        headers={"Authorization": f"Token {self.token}"}
                    )
        user_names = {usr['name'] for usr in response.json()}

        names_f = os.path.join(ROOT, "data", "names.txt")
        with open(names_f, 'r', encoding="utf-8") as f:
            names = [line.rstrip() for line in f]
            for usr in self.players_per_room[room]:
                new_name = random.choice(names)
                if new_name in user_names:
                    suffix = 2
                    while f"{new_name}{suffix}" in user_names:
                        suffix += 1
                    new_name = f"{new_name}{suffix}"
                user_names.remove(usr['name'])
                user_names.add(new_name)
                requests.put(
                    f"{self.uri}/user/{usr['id']}",
                    json={'name': new_name},
                    headers={"Authorization": f"Token {self.token}"}
                )
