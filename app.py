from datetime import datetime, timedelta
from pytz import utc
import discord
from discord.ext import tasks, commands
import json

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

schedule_file = "schedule.json"
users_pref_file = "prefs.json"

def reminder_message(url):
     return f"Reminder to post Snackdoku {url} today"

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

    async def on_ready(self):
        self.background_task.start()
        print(f'We have logged in as {client.user}')

    async def on_message(self, message):
        if message.author == client.user:
            return

        if message.channel.type == discord.ChannelType.private:
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

            if message.content.startswith('$schedule'):
                text = message.content.split("\n")
                for line in text[1:]:
                    values = line.split()
                    status = 'pending'
                    try:
                        date = datetime.fromisoformat(values[0])
                        if date < (datetime.now() - timedelta(days=1)):
                            status = 'past'
                    except ValueError:
                        await message.channel.send(f'Invalid date for line: **{line}**')
                        continue
                    member = None
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
                for sch in self.schedule:
                    if (datetime.fromisoformat(sch[0]) + timedelta(days=1)) > datetime.now():
                        await message.channel.send(f'{datetime.fromisoformat(sch[0]).date().isoformat()}: {sch[1]} {sch[2]} {sch[3]}')

    @tasks.loop(minutes=5)
    async def background_task(self):
         for i in range(len(self.schedule)):
              sch = self.schedule[i]
              if sch[3] != 'pending':
                  continue
              if datetime.fromisoformat(sch[0]).astimezone(utc) < datetime.now(utc):
                  reminder_time = self.user_list[sch[1]]['time']
                  if datetime.now().astimezone(utc).hour >= reminder_time:
                      user = self.get_user(self.user_list[sch[1]]['id'])
                      await user.send(reminder_message(sch[2]))
                      await self.get_channel(1338945636107550774).send(f'Reminder sent to {user.mention} for puzzle {sch[2]}.')
                      # remove pending flag
                      self.schedule[i][3] = f'sent at {datetime.now(utc).isoformat()}'
                      self.save_schedule()

client = Bot(intents=intents)

import configparser

config = configparser.ConfigParser()
config.read('config.ini')

client.run(config['DEFAULT']['DISCORD_TOKEN'])
