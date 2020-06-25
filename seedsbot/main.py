#!python3
# -*- coding: utf-8 -*-

import discord
import asyncio
import time
import os


TOKEN_FILE_NAME = "discord_token"


BOT = discord.Client()

TOKEN_ENV_VAR = "DISCORD_TOKEN"
ART_SOURCE = "art-gallery"
ART_TARGET = "art-discussion"
TARGET_CACHE_TTL = 60*60


class BotState:
    def __init__(self, bot):
        self.bot = bot
        self.last_art_origin = None
        self.last_art_copy = None

    def get_art_target_channel(self, guild):
        # TODO implement cache
        for channel in guild.text_channels:
            if channel.name == ART_TARGET:
                return channel
        return None

        
BOT_STATE = BotState(BOT)


@BOT.event
async def on_ready():
    print("Bot logged in as", BOT.user.name, "with ID:", BOT.user.id)
    print('------------------------------------------------')


@BOT.event
async def on_message(message):
    # Ignore bot's own messages
    if message.author == BOT.user:
        return

    if message.channel.name == ART_SOURCE:
        print(message.embeds, message.attachments)
        if len(message.embeds) > 0 or len(message.attachments) > 0:
            urls = []
            for attachment in message.attachments:
                urls.append(attachment.url)
            content = "Post in " + ART_SOURCE + " by " + message.author.display_name + ":\n" + message.content
            for url in urls:
                content += "\n" + url

            target_channel = BOT_STATE.get_art_target_channel(message.channel.guild)
            if target_channel is None:
                print("Error: no target channel available (" + ART_TARGET + ")")
            else:
                await target_channel.send(content)

            
@BOT.event
async def on_reaction_add(reaction, user):
    print(reaction, reaction.emoji)


@BOT.event
async def on_message_delete(message):
    # Ignore bot's own messages
    if message.author == BOT.user:
        return

    if BOT_STATE.last_art_origin is None or BOT_STATE.last_art_copy is None:
        return
    
    if message.id == BOT_STATE.last_art_origin.id:
        await BOT_STATE.last_art_copy.delete()
        BOT_STATE.last_art_origin = None
        BOT_STATE.last_art_copy = None


def load_token():
    env_token = os.getenv(TOKEN_ENV_VAR)
    if env_token is not None and len(env_token) > 3:
        return env_token
    try:
        token_file = open(TOKEN_FILE_NAME, "r")
        data = token_file.read()
        token_file.close()
        return data.strip()
    except Exception as ex:
        raise RuntimeError("No " + TOKEN_ENV_VAR + " variable set and failed to load token file, please check if it exists: " + str(TOKEN_FILE_NAME))


def run():
    BOT.run(load_token())
