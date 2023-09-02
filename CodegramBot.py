import discord
from discord.ext import commands, tasks
import requests
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import re

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.presences = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

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
    
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandInvokeError):
        await ctx.send(f"An error occurred while processing your command: {error.original}")
    else:
        await ctx.send(f"An error occurred: {error}")

channel_ids = {}

@bot.group()
async def CodegramBot(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send('Please specify a valid subcommand. For example: track <username>.')

@CodegramBot.command()
async def track(ctx, username: str):
    if username not in USERNAMES:
        USERNAMES.append(username)
        channel_ids[username] = ctx.channel.id
        await ctx.send(f"Now tracking LeetCode submissions for {username}!")
        await check_for_updates(username, ctx.channel.id)
    else:
        await ctx.send(f"{username} is already being tracked!")

@CodegramBot.command(name="whoIsBetter")
async def who_is_better(ctx, username1: str, username2: str):
    try:
        result = compare_users_stats(username1, username2)
        await ctx.send(result)
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

def compare_users_stats(username1, username2):
    stats1 = getSubmitStats(username1)
    stats2 = getSubmitStats(username2)
    if not stats1 and not stats2:
        return f"Both usernames {username1} and {username2} are invalid or not found."
    if not stats1:
        return f"Username {username1} is invalid or not found."
    if not stats2:
        return f"Username {username2} is invalid or not found."

    solved1 = sum([d['count'] for d in stats1['submitStats']['acSubmissionNum']])
    solved2 = sum([d['count'] for d in stats2['submitStats']['acSubmissionNum']])

    if solved1 > solved2:
        return f"{username1} has solved more problems than {username2} ({solved1} vs {solved2})."
    elif solved1 < solved2:
        return f"{username2} has solved more problems than {username1} ({solved2} vs {solved1})."
    else:
        return f"{username1} and {username2} have solved the same number of problems ({solved1})."

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
                if username not in reported_problems:
                    reported_problems[username] = set()
                if problem_slug not in reported_problems[username]:
                    channel = bot.get_channel(channel_ids[username])
                    await channel.send(f"{username} just solved {submission['title']} on LeetCode!")
                    reported_problems[username].add(problem_slug)

bot.run(TOKEN)
