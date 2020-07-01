#!python3
# -*- coding: utf-8 -*-

import discord
from collections import OrderedDict
from threading import Semaphore
import time
import os
import re


TOKEN_FILE_NAME = "discord_token"


BOT = discord.Client()

TOKEN_ENV_VAR = "DISCORD_TOKEN"
ART_SOURCE = "art-gallery"
ART_TARGET = "art-discussion"

MAX_CACHE_SIZE = 50                 # 50 records per server
FOLLOW_UP_TTL = 5 * 60              # 5 minutes TTL for a follow-up

BOT_MSG_DELETION_EMOJI = "🚫"
LINK_DETECTION_REGEX = ".*(http:\\/\\/|www\\.|\\.com|\\.net|\\.org|\\.io|\\.eu|\\.gl).*"


class CachedMessageCopy:
    def __init__(self, discord_message: discord.Message, follow_up: bool) -> None:
        self.discord_message = discord_message
        self.follow_up = follow_up


class MessagesCache:
    def __init__(self, max_cache_size: int) -> None:
        assert max_cache_size > 0
        self._copies = OrderedDict()
        self._last_message = None
        self._last_message_timestamp = None
        self.max_cache_size = max_cache_size

    def get_last_message(self) -> tuple:
        return self._last_message, self._last_message_timestamp

    def get_cached_copy(self, orig_message_id: int) -> CachedMessageCopy:
        return self._copies.get(orig_message_id)

    def cache_message(self, message_orig: discord.Message, message_copy: discord.Message, follow_up: bool) -> None:
        if len(self._copies) >= self.max_cache_size:
            oldest = next(iter(self._copies.keys()))
            self._copies.pop(oldest)
        cache_entry = CachedMessageCopy(message_copy, follow_up)
        self._copies[message_orig.id] = cache_entry
        self._last_message = message_orig
        self._last_message_timestamp = time.time()


class BotState:
    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot
        self.last_art_origin = None
        self.last_art_copy = None

        self._server_cache_sem = Semaphore(1)
        self._server_cache_map = {}

    def get_cached_copy(self, message: discord.Message) -> CachedMessageCopy:
        self._server_cache_sem.acquire()
        try:
            server_cache = self._get_server_cache(message.guild.id)
            return server_cache.get_cached_copy(message.id)
        finally:
            self._server_cache_sem.release()

    def cache_message(self, message_orig: discord.Message, message_copy: discord.Message, follow_up: bool) -> None:
        self._server_cache_sem.acquire()
        try:
            server_cache = self._get_server_cache(message_orig.guild.id)
            server_cache.cache_message(message_orig, message_copy, follow_up)
        finally:
            self._server_cache_sem.release()

    def get_last_message(self, guild_id: int) -> tuple:
        self._server_cache_sem.acquire()
        try:
            server_cache = self._get_server_cache(guild_id)
            return server_cache.get_last_message()
        finally:
            self._server_cache_sem.release()
    
    def _get_server_cache(self, guild_id: int) -> MessagesCache:
        cache = self._server_cache_map.get(guild_id)
        if cache is None:
            cache = MessagesCache(MAX_CACHE_SIZE)
            self._server_cache_map[guild_id] = cache
        return cache

    def get_art_target_channel(self, guild: discord.Guild) -> discord.TextChannel or None:
        # TODO implement cache
        for channel in guild.text_channels:
            if channel.name == ART_TARGET:
                return channel
        return None

        
BOT_STATE = BotState(BOT)


@BOT.event
async def on_ready() -> None:
    print("Bot logged in as", BOT.user.name, "with ID:", BOT.user.id)
    print('------------------------------------------------')


def create_message_copy_content(message: discord.Message, follow_up: bool) -> str:
    urls = []
    for attachment in message.attachments:
        urls.append(attachment.url)
    
    if follow_up:
        prefix = ""
    else:
        prefix = "Post in " + ART_SOURCE + " by " + message.author.display_name + ":\n"
        
    content = prefix + message.content
    for url in urls:
        content += "\n" + url
    return content


def contains_link(message: discord.Message) -> bool:
    content_lower = message.content.lower()
    # TODO better link search
    return re.match(LINK_DETECTION_REGEX, content_lower) is not None


def is_follow_up(message: discord.Message) -> bool:
    last_message, last_timestamp = BOT_STATE.get_last_message(message.guild.id)
    if last_message is None:
        return False
    expired = (time.time() - last_timestamp) > FOLLOW_UP_TTL
    return last_message.author.id == message.author.id and not expired


@BOT.event
async def on_message(message: discord.Message) -> None:
    # Ignore bot's own messages
    if message.author == BOT.user:
        return

    if message.channel.name == ART_SOURCE:
        print(message.embeds, message.attachments)
        follow_up = is_follow_up(message)
        if (len(message.embeds) > 0 or
            len(message.attachments) > 0 or
            contains_link(message) or
            follow_up):
            content = create_message_copy_content(message, follow_up)

            target_channel = BOT_STATE.get_art_target_channel(message.channel.guild)
            if target_channel is None:
                print("Error: no target channel available (" + ART_TARGET + ")")
            else:
                message_copy = await target_channel.send(content)
                BOT_STATE.cache_message(message, message_copy, follow_up)

            
@BOT.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User) -> None:
    if reaction.message.author == BOT.user and reaction.emoji == BOT_MSG_DELETION_EMOJI:
            print("Message copy deletion initiated by", user.name)
            await reaction.message.delete()


@BOT.event
async def on_message_edit(message_before: discord.Message, message_after: discord.Message) -> None:
    if message_after.author == BOT.user or message_after.channel.name != ART_SOURCE:
        return

    cached_copy = BOT_STATE.get_cached_copy(message_after)
    if cached_copy is not None:
        new_content_copy = create_message_copy_content(message_after, cached_copy.follow_up)
        await cached_copy.discord_message.edit(content=new_content_copy)


@BOT.event
async def on_message_delete(message: discord.Message) -> None:
    # Ignore bot's own messages
    if message.author == BOT.user or message.channel.name != ART_SOURCE:
        return

    cached_copy = BOT_STATE.get_cached_copy(message)

    if cached_copy is not None:
        await cached_copy.discord_message.delete()


def load_token() -> str:
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


def run() -> None:
    BOT.run(load_token())
