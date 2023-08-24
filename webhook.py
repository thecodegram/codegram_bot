import requests
import re
from time import sleep

WEBHOOK_URL = "https://discord.com/api/webhooks/1142981991948636380/Za8RcTY1OrzC9gF2LQyQym1SVAOaXLz3ZL_UP1i8UPXLj-e8eZEAWRrsKkkTt81C6jg2"
USERNAMES = ["dannyliu0421", "shaygeko", "kiaancastillo"]  
reported_problems = {'dannyliu0421': {'single-number', 'middle-of-the-linked-list', 'find-customer-referee', 'search-a-2d-matrix', 'remove-element', 'fibonacci-number', 'maximum-subarray', 'max-consecutive-ones', 'maximum-average-subarray-i', 'sort-colors', 'palindrome-linked-list', 'big-countries', 'reverse-vowels-of-a-string', 'first-bad-version'}, 'shaygeko': {'powx-n', 'reverse-linked-list', 'symmetric-tree', 'deepest-leaves-sum', 'divide-chocolate', 'find-anagram-mappings', 'kth-largest-element-in-an-array', '01-matrix', 'minimize-the-maximum-difference-of-pairs', 'contains-duplicate-ii'}, 'kiaancastillo': {'create-hello-world-function', 'two-sum'}}
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
    print('Getting latest submits...')
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

def send_notification(username, title):
    print('Sending notification!')
    payload = {
        "content": f"{username} just solved {title} on LeetCode!"
    }
    requests.post(WEBHOOK_URL, json=payload)

def main():
    global reported_problems
    while True:
        for username in USERNAMES:
            submissions = getLatestAcceptedSubmits(username)
            if submissions:
                for submission in submissions:
                    problem_slug = submission['titleSlug']
                    if username not in reported_problems:
                        reported_problems[username] = set()
                    if problem_slug not in reported_problems[username]:
                        send_notification(username, submission['title'])
                        reported_problems[username].add(problem_slug)
        sleep(120)

if __name__ == "__main__":
    main()