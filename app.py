from datetime import datetime, timedelta
import functools
import asyncio
import re
from pytz import utc
import discord
from discord.ext import tasks, commands
import json

import sheet_tools
from puzzle_url_tools import get_image_and_rules, puzzle_desc

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

urls = re.compile(r'http[s]*\S+')

import configparser

config = configparser.ConfigParser()
config.read('config.ini')

schedule_file = "schedule.json"
users_pref_file = "prefs.json"
description_file = "description.md"
tracked_reactions = [['<:grn:951196965616644156>',
                     '<:yello:951196965708914769>',
                     '<:red:951196965713117224>'],
                     ['0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']]

fifo_queue = asyncio.Queue()
async def fifo_worker():
    while True:
        job = await fifo_queue.get()
        print(f"Got a job: (size of remaining queue: {fifo_queue.qsize()})")
        await job()

def to_thread(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper

class Bot(discord.Client):
    def __init__(self, *args, **kwargs):
        try:
            with open(users_pref_file, 'r') as f:
                self.user_list = json.load(f)
        except FileNotFoundError:
            self.user_list = {}
            self.save_users()
        try:
            with open(schedule_file, 'r') as f:
                self.schedule = json.load(f)
        except FileNotFoundError:
            self.schedule = []
            self.save_schedule()

        super().__init__(*args, **kwargs)

    def save_users(self):
        with open(users_pref_file, 'w') as f:
            json.dump(self.user_list, f)

    def save_schedule(self):
        with open(schedule_file, 'w') as f:
            json.dump(self.schedule, f)

    @to_thread
    def edit_sheet(self, message, before=None, sheet=0):
        message_urls = list(set(urls.findall(message.content)))
        skip_analysis = False
        message_date = message.created_at.isoformat()

        if before and len(message_urls) > 0:
            before_urls = list(set(urls.findall(message.content)))
            if before_urls == message_urls:
                skip_analysis = True

        data = sheet_tools.get_line(message.id, sheet)
        if data:
            if len(data) >= 4:
                if set([m for m in [data[3], data[4]] if m != ""]) == set(message_urls):
                    skip_analysis = True

        if skip_analysis:
            [title, author, edit_url, solve_url] = data[1:5]
        else:
            [title, author, edit_url, solve_url] = [None]*4
            for u in message_urls:
                try:
                    _, title, author, _, _, _ = get_image_and_rules(u)
                    if title:
                        solve_url = u
                        break
                except:
                    pass
            if solve_url:
                for u in message_urls:
                    if u != solve_url:
                        edit_url = u
                        break
            else:
                if len(message_urls) > 0:
                    solve_url = message_urls[0]
                if len(message_urls) > 1:
                    edit_url = message_urls[1]
        reactions = {str(r.emoji): r.count for r in message.reactions}
        for emoji in tracked_reactions[sheet]:
            if emoji not in reactions:
                reactions[emoji] = 0
        emojis = [reactions[e] for e in tracked_reactions[sheet]]
        sheet_tools.edit_line(int(message.id), message_date, title, author, edit_url, solve_url, emojis, sheet)

    async def on_ready(self):
        asyncio.create_task(fifo_worker())
        self.background_task.start()
        print(f'We have logged in as {client.user}')

    async def update_sheet(self, payload):
        if payload.channel_id == int(config['DEFAULT']['SUBMIT_CHANNEL0_ID']):
            sheet = 0
        elif payload.channel_id == int(config['DEFAULT']['SUBMIT_CHANNEL1_ID']):
            sheet = 1
        else:
            return
        guild = self.get_guild(payload.guild_id)
        if not guild:
            return
        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return
        message = await channel.fetch_message(payload.message_id)
        if message:
            await fifo_queue.put(lambda m=message: self.edit_sheet(m, None, sheet))
        return

    async def on_raw_reaction_add(self, payload):
        await self.update_sheet(payload)

    async def on_raw_reaction_remove(self, payload):
        await self.update_sheet(payload)

    async def on_raw_message_edit(self, payload):
        await self.update_sheet(payload)
    
    async def on_raw_message_delete(self, payload):
        return # disabled as it does not work properly (delete the line but then it prevent any other changes to the sheet)
        if payload.channel_id == int(config['DEFAULT']['SUBMIT_CHANNEL0_ID']):
            await fifo_queue.put(lambda m=payload.message_id: sheet_tools.del_line(m, 0))

        if payload.channel_id == int(config['DEFAULT']['SUBMIT_CHANNEL1_ID']):
            await fifo_queue.put(lambda m=payload.message_id: sheet_tools.del_line(m, 1))

    async def on_message(self, message):
        if message.author == client.user:
            return

        if message.channel.id == int(config['DEFAULT']['SUBMIT_CHANNEL0_ID']):
            await fifo_queue.put(lambda m=message: self.edit_sheet(m, None, 0))
            return

        if message.channel.id == int(config['DEFAULT']['SUBMIT_CHANNEL1_ID']):
            await fifo_queue.put(lambda m=message: self.edit_sheet(m, None, 1))
            return

        if message.content.startswith('$getinfo'):
            url = message.content.split()[1]
            if message.content.split()[1]:
                await self.send_puzzle(url, message.channel)
            return

        if message.content.startswith('$') and message.author.global_name not in self.user_list:
            await message.channel.send('User not in user list, can\'t send any commands.\nRequest user in list to add your name in the schedule to be added to user list.')
            return

        if message.channel.type == discord.ChannelType.private:
            if message.content.startswith('$gethistory'):
                try:
                    limit = int(message.content.split()[1])
                except:
                    limit = 50
                try:
                    channel_num = int(message.content.split()[2])
                except:
                    channel_num = 0
                channel = None
                for guild in self.guilds:
                    channel = guild.get_channel(int(config['DEFAULT'][f'SUBMIT_CHANNEL{channel_num}_ID']))
                    if channel:
                        messages = [m async for m in channel.history(limit=limit)]
                        for m in messages:
                            await fifo_queue.put(lambda m=m: self.edit_sheet(m, None, 0))
                        break
                return

            if message.content.startswith('$time'):
                try:
                    new_time = int(message.content.split()[1])
                    if new_time < 0 or new_time > 23:
                        raise ValueError('Out of range')
                    if message.author.global_name in self.user_list:
                        self.user_list[message.author.global_name]['time'] = new_time
                    else:
                        self.user_list[message.author.global_name] = {'id': message.author.id, 'time': new_time}
                    self.save_users()
                    await message.channel.send(f'The reminders will be sent around {new_time} GMT or <t:{new_time*3600}:t> your time.')
                except ValueError:
                    await message.channel.send(f'Invalid time!\nExample usage: type **$time 13** to receive a reminder around 13:00 GMT / <t:46800:t> your time.\nNote that the target is to post around 13:00 GMT / <t:46800:t> your time.')
                except IndexError:
                    cur_time = self.user_list[message.author.global_name]['time']
                    await message.channel.send(f'The reminders will be sent around {cur_time} GMT or <t:{cur_time*3600}:t> your time.')
                return

            if message.content.startswith('$schedule'):
                text = message.content.split("\n")
                full = False
                if len(text[0].split()) > 1:
                    if text[0].split()[1] == "full":
                        full = True
                for line in text[1:]:
                    values = line.split()
                    status = 'pending'
                    try:
                        date = datetime.fromisoformat(values[0])
                        if date.date() <= (datetime.now().date() - timedelta(days=1)):
                            status = 'past'
                    except ValueError:
                        await message.channel.send(f'Invalid date for line: **{line}**')
                        continue
                    member = None
                    if values[1] == 'delete':
                        for i in range(len(self.schedule)):
                            if datetime.fromisoformat(self.schedule[i][0]) == date:
                                self.schedule.pop(i)
                                await message.channel.send(f'schedule line for {date.date()} has been removed')
                                break
                    else:
                        for guild in self.guilds:
                            member_found = guild.get_member_named(values[1])
                            if member_found:
                                member = member_found
                                if member.global_name not in self.user_list:
                                    self.user_list[member.global_name] = {'id': member.id, 'time': 13}
                                    self.save_users()
                                break
                        if not member:
                            await message.channel.send(f'User not found for line: **{line}**')
                            continue
                        url = values[2]
                        found = False
                        for i in range(len(self.schedule)):
                            if datetime.fromisoformat(self.schedule[i][0]) == date:
                                self.schedule[i] = [date.isoformat(), member.global_name, url, status]
                                found = True
                                break
                        if not found:
                            self.schedule.append([date.isoformat(), member.global_name, url, status])
                    self.schedule.sort(key=lambda sch: sch[0])
                    self.save_schedule()
                cur_schedule = list(filter(lambda sch: datetime.fromisoformat(sch[0]).date() >= datetime.now().date(), self.schedule))
                if len(cur_schedule) == 0:
                    await message.channel.send(f'_The schedule is currently empty_')
                for i in range(len(cur_schedule)):
                    if not full and i >= 7:
                        if len(cur_schedule) > 7:
                            await message.channel.send(f'_Schedule truncated, for full schedule send **$schedule full**_')
                        break
                    sch = cur_schedule[i]
                    await message.channel.send(f'{datetime.fromisoformat(sch[0]).date().isoformat()}: {sch[1]} {sch[2]} {sch[3]}')
                return

            if message.content.startswith('$skip'):
                for i in range(len(self.schedule)):
                    if datetime.fromisoformat(self.schedule[i][0]).date() == datetime.now().date():
                        self.schedule[i][3] = "skipped"
                        await message.channel.send(f'schedule line for {self.schedule[i][0]} has been skipped')
                        self.save_schedule()
                        break
                return
            with open(description_file, "r") as f:
                await message.channel.send(f.read())

    async def send_puzzle(self, url, channel):
        message, image = puzzle_desc(url)
        if image:
            await channel.send(message, file=discord.File(fp=image, filename='screenshot.png'))
        else:
            await channel.send(message)

    async def send_reminder(self, url, channel):
        message, image = puzzle_desc(url)
        message = f"Target Times: 🦨  ≤ 2min < 🐿️  ≤ 5min <  🦔 so, please enjoy…\n\n{message}\n\n@Guest Series Solver - 1\n[new snackdoku]"
        if image:
            await channel.send(message, file=discord.File(fp=image, filename='screenshot.png'))
        else:
            await channel.send(message)

    @tasks.loop(minutes=5)
    async def background_task(self):
        for i in range(len(self.schedule)):
            sch = self.schedule[i]
            if sch[3] != 'pending':
                continue
            if datetime.fromisoformat(f"{sch[0][0:10]}T02:01:00").astimezone(utc) < datetime.now(utc):
                reminder_time = self.user_list[sch[1]]['time']
                if datetime.now().astimezone(utc).hour >= reminder_time:
                    user = self.get_user(self.user_list[sch[1]]['id'])
                    await user.send(f"Reminder to post Snackdoku today.")
                    await self.send_reminder(sch[2], user)
                    await self.get_channel(int(config['DEFAULT']['CHANNEL_ID'])).send(f'Reminder sent to {user.mention} for puzzle {sch[2]}.')
                    # remove pending flag
                    self.schedule[i][3] = f'sent at {datetime.now(utc).isoformat()}'
                    self.save_schedule()

client = Bot(intents=intents)

client.run(config['DEFAULT']['DISCORD_TOKEN'])
