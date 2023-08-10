#!/bin/bash

while true; do
    screen -S open-workshop-discord-bot-executor python3 main.py
    sleep 60
done