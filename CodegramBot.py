import discord
from discord.ext import commands, tasks
import requests
import os
from dotenv import load_dotenv
import re

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.presences = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load .env variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

USERNAMES = []

reported_problems = {}

def isValidUsername(userId):
    return bool(re.match("^[A-Za-z0-9_]*$", userId))

def getSubmitStats(userId):
    if not isValidUsername(userId):
        print("invalid username")
        return None

    query = """
    {
        matchedUser(username: "%s")
        {
            username
            submitStats: submitStatsGlobal
            {
                acSubmissionNum
                {
                    difficulty
                    count
                    submissions
                }
            }
        }
    }
    """ % userId

    try:
        response = requests.post("https://leetcode.com/graphql", json={"query": query})
        data = response.json()
        
        if data.get("data", {}).get("matchedUser") is None:
            raise Exception(f"Leetcode username {userId} was not found")
        
        return data["data"]["matchedUser"]
    except Exception as error:
        print(f"Error fetching data for user ID {userId}: {error}")
        raise error

def getLatestAcceptedSubmits(userId, limit=10):
    if not isValidUsername(userId):
        print("invalid username")
        return None
    
    query = """
    {
        recentAcSubmissionList(username: "%s", limit: %d) {
            title
            titleSlug
            timestamp
            lang
        }
    }
    """ % (userId, limit)

    try:
        response = requests.post("https://leetcode.com/graphql", json={"query": query})
        data = response.json()
        return data["data"]["recentAcSubmissionList"]
    except Exception as error:
        print(f"Error fetching data for user ID {userId}: {error}")
        raise error

@bot.event
async def on_ready():
    print(f'Bot has logged in as {bot.user.name}({bot.user.id})')
    check_leetcode_updates.start()

channel_ids = {}

@bot.command()
async def CodegramBot(ctx, username: str):
    if username not in USERNAMES:
        USERNAMES.append(username)
        channel_ids[username] = ctx.channel.id
        await ctx.send(f"Now tracking LeetCode submissions for {username}!")
        # Now, instantly check for the user's recent submissions
        await check_for_updates(username, ctx.channel.id)
    else:
        await ctx.send(f"{username} is already being tracked!")

async def check_for_updates(username, channel_id):
    submissions = getLatestAcceptedSubmits(username)
    if submissions:
        for submission in submissions:
            problem_slug = submission['titleSlug']
            if username not in reported_problems:
                reported_problems[username] = set()
            if problem_slug not in reported_problems[username]:
                channel = bot.get_channel(channel_id)
                await channel.send(f"{username} just solved {submission['title']} on LeetCode!")
                reported_problems[username].add(problem_slug)



@tasks.loop(minutes=2)
async def check_leetcode_updates():
    for username in USERNAMES:
        submissions = getLatestAcceptedSubmits(username)
        if submissions:
            for submission in submissions:
                problem_slug = submission['titleSlug']

                # If the user hasn't been recorded before, initialize a set for them
                if username not in reported_problems:
                    reported_problems[username] = set()

                # If the problem hasn't been reported before, send a message and add to the set
                if problem_slug not in reported_problems[username]:
                    channel = bot.get_channel(channel_ids[username])
                    await channel.send(f"{username} just solved {submission['title']} on LeetCode!")
                    reported_problems[username].add(problem_slug)




bot.run(TOKEN)
