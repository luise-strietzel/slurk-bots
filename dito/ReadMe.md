### Modifications
In the `data` folder of the `dito` bot
you can find an `instructions.json` file.
The *greetings* key maps to a list of strings.
Each string will be printed as one speech bubble
after both users have entered the task room.
If you want to use linebreaks in messages write
a single backslash followed by an n twice.
The *instr_title* key maps to a string.
This string is used as the header of the task
box on the right, while a game round is running.
The *instr* key maps to the task description that will
be displayed under this header.  
  
See the `config.cfg` in the same folder for further configuration
options.  
Image pairs for the task should be specified one pair per line
in the `image_data.csv`. The components of a pair are separated by
a comma followed by no whitespace.

### To run locally
Download the resources from GitHub. Both of them should end up being located in the same folder:
```sh
git clone -b development git@github.com:wencke-lm/slurk-bots.git
git clone git@github.com:clp-research/slurk.git
```
Navigate into the `slurk-bots` repository:
```sh
cd slurk-bots
```
Start the server, run the bots and create two user tokens:
```sh 
source dito/setup.sh
```
The output you get should be prefixed only by INFO or DEBUG.  
Finally, enter http://localhost/ into a private browser window.
And use one of the generated tokens to log in.
You can also open a second different private browser and enter the second token to start a chat with yourself.
```sh 
% Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   121  100    39  100    82   5571  11714 --:--:-- --:--:-- --:--:-- 17285
35621c65-9142-480d-983e-a5e57e35a33c <-- THIS IS ONE EXAMPLE TOKEN

% Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   121  100    39  100    82   5571  11714 --:--:-- --:--:-- --:--:-- 17285
29c3cdb9-81a0-41a8-9df3-6dac4a99306a <-- THIS IS ANOTHER EXAMPLE TOKEN
```