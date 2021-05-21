#!/bin/bash

# replace placeholder with actual Discord token
export DISCORD_TOKEN=1234

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
/usr/bin/python3 $SCRIPT_DIR/runbot.py
