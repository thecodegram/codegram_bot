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

from datetime import datetime, timedelta

def days_since_last_activity(username):
    submissions = getLatestAcceptedSubmits(username, limit=1)
    if not submissions:
        return None

    # Ensure the timestamp is an integer
    latest_submission_timestamp = submissions[0]['timestamp']
    if isinstance(latest_submission_timestamp, str):
        latest_submission_timestamp = int(latest_submission_timestamp)
    latest_submission_date = datetime.fromtimestamp(latest_submission_timestamp)

    # Calculating the difference in days
    difference = datetime.utcnow() - latest_submission_date
    return difference.days



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

@CodegramBot.command(name="activity")
async def user_activity(ctx, username: str):
    try:
        days = days_since_last_activity(username)
        if days is None:
            await ctx.send(f"{username} has no accepted submissions on LeetCode.")
        else:
            await ctx.send(f"{username} has not solved a problem in {days} days.")
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

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


@CodegramBot.command(name="grindset")
async def grindset(ctx, username: str):
    try:
        average = calculate_average_solved_per_day(username)
        if average is None:
            await ctx.send(f"Couldn't fetch data for {username}. They might not have solved any problems on LeetCode.")
            return
        await ctx.send(f"{username} solves an average of {average:.2f} problem(s) per day.")
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")


def calculate_average_solved_per_day(username):
    # Fetch the earliest submission
    submissions = getLatestAcceptedSubmits(username, limit=1000)  # Assuming no one solves more than 1000 problems in a day
    if not submissions:
        return None

    first_submission_timestamp = min([submission['timestamp'] for submission in submissions])
    if isinstance(first_submission_timestamp, str):
        first_submission_timestamp = int(first_submission_timestamp)

    first_submission_date = datetime.fromtimestamp(first_submission_timestamp)
    difference = datetime.utcnow() - first_submission_date
    days_difference = difference.days

    # Get total problems solved
    stats = getSubmitStats(username)
    if not stats:
        return None
    total_solved = sum([d['count'] for d in stats['submitStats']['acSubmissionNum']])
    
    # Calculate the average
    average = total_solved / days_difference
    return average

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
def display_user_stats(username):
    stats = getSubmitStats(username)
    if not stats:
        return f"Username {username} is invalid or not found."
    
    total_solved = sum([d['count'] for d in stats['submitStats']['acSubmissionNum']])
    
    # Formatting the data for output
    stats_str = f"Statistics for {username}:\n"
    stats_str += f"Total Problems Solved: {total_solved}\n"
    
    for difficulty_stat in stats['submitStats']['acSubmissionNum']:
        stats_str += f"{difficulty_stat['difficulty']} Problems Solved: {difficulty_stat['count']} out of {difficulty_stat['submissions']} submissions\n"
    
    return stats_str

bot.remove_command('help')

@CodegramBot.command(name='help')
async def custom_help(ctx):
    help_str = "List of available commands under `CodegramBot`:\n"
    
    for command in CodegramBot.walk_commands():
        help_str += f"!CodegramBot {command.name}\n"

    await ctx.send(help_str)


@CodegramBot.command(name="stats")
async def user_stats(ctx, username: str):
    try:
        stats_message = display_user_stats(username)
        await ctx.send(stats_message)
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

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
