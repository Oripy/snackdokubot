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

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
import io
from PIL import Image

def get_image_and_rules(url):
    options = Options()
    options.add_argument("--headless=new")

    service = Service('/usr/lib/chromium-browser/chromedriver')

    driver = webdriver.Chrome(options=options, service=service)
    driver.get(url)

    # Make sure the page is loaded properly
    WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CLASS_NAME, 'dialog')))
    WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.ID, 'svgrenderer')))

    # Hide SvenPeek so it does not appear on the screenshot
    driver.execute_script('document.getElementById("svenpeek").remove()')

    # Acknowledges the dialog
    dialog = driver.find_element(By.CLASS_NAME, 'dialog')
    dialog.find_element(By.CSS_SELECTOR, 'button').click()

    # Screenshot the puzzle image
    image_binary = driver.find_element(By.ID, 'svgrenderer').screenshot_as_png
    img = io.BytesIO(image_binary)

    # Get the rest of the data from the page
    title = driver.find_element(By.CLASS_NAME, 'puzzle-title').text
    author = driver.find_element(By.CLASS_NAME, 'puzzle-author').text
    rules = driver.find_element(By.CLASS_NAME, 'puzzle-rules').text

    driver.close()
    return title, author, rules, img

def puzzle_desc(url):
    title, author, rules, img = None, None, None, None
    try:
        title, author, rules, img = get_image_and_rules(url)
    except:
        pass
    if title:
        return f"**{title}** {author}\n\n**Rules:**\n{rules}\n\nSudokuPad: {url}", img
    else:
        return f"Link: {url}\n\n_Bot could not retreive more info... sorry_", img

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

        if message.content.startswith('$getinfo'):
            url = message.content.split()[1]
            if message.content.split()[1]:
                await self.send_puzzle(url, message.channel)
            return

        if message.content.startswith('$') and message.author.global_name not in self.user_list:
            await message.channel.send('User not in user list, can\'t send any commands.\nRequest user in list to add your name in the schedule to be added to user list.')
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
                except IndexError:
                    cur_time = self.user_list[message.author.global_name]['time']
                    await message.channel.send(f'The reminders will be sent around {cur_time} GMT or <t:{cur_time*3600}:t> your time.')
                return

            if message.content.startswith('$schedule'):
                text = message.content.split("\n")
                for line in text[1:]:
                    values = line.split()
                    status = 'pending'
                    try:
                        date = datetime.fromisoformat(values[0])
                        if date.date() < (datetime.now().date() - timedelta(days=1)):
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
                for sch in cur_schedule:
                    await message.channel.send(f'{datetime.fromisoformat(sch[0]).date().isoformat()}: {sch[1]} {sch[2]} {sch[3]}')
                return

            if message.content.startswith('$skip'):
                for i in range(len(self.schedule)):
                    if datetime.fromisoformat(self.schedule[i][0]).date() == datetime.now().date():
                        self.schedule[i][3] = "skipped"
                        await message.channel.send(f'schedule line for {date} has been skipped')
                        self.save_schedule()
                        break
                return

            await message.channel.send("""Hello!
I'm a bot to help Snackdoku posters to post in time. I can also help to write the post as I can gather info from puzzle links.

Send me the following commands in DM to manage the reminders and ask me for some help:

**Scheduling**
> $schedule
will list the current planned schedule (ignoring past dates)

> $schedule
> 2025-02-14 username http://sudokupad.app/somepuzzleid
will add/alter the reminder for 14th of February 2025. A message will be sent to _username_ on that date with the link and info.

> $schedule
> 2025-02-14 delete
will remove the scheduled line for that date

several lines can be added/modified/deleted on the same message

**User defined reminder time preference**
> $time 14
will define the reminder time as being around 14:00 UTC for the user sending the command. Other users reminder time is not affected.

**Skipping reminder**
> $skip
will skip todays reminder.
This is useful when the post has already been posted and don't want the reminder to trigger anymore.

**Asking for puzzle info**
> $getinfo http://sudokupad.app/somepuzzleid
will send a message with formatted info on the puzzle (Title, Author, Rules) as well as a screenshot of the puzzle.""")

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
            if datetime.fromisoformat(sch[0]).astimezone(utc) < datetime.now(utc):
                reminder_time = self.user_list[sch[1]]['time']
                if datetime.now().astimezone(utc).hour >= reminder_time:
                    user = self.get_user(self.user_list[sch[1]]['id'])
                    await user.send(f"Reminder to post Snackdoku today.")
                    await self.send_reminder(sch[2], user)
                    await self.get_channel(1127170273867730974).send(f'Reminder sent to {user.mention} for puzzle {sch[2]}.')
                    # remove pending flag
                    self.schedule[i][3] = f'sent at {datetime.now(utc).isoformat()}'
                    self.save_schedule()

client = Bot(intents=intents)

import configparser

config = configparser.ConfigParser()
config.read('config.ini')

client.run(config['DEFAULT']['DISCORD_TOKEN'])
