from github import Github
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from collections import defaultdict
import pandas as pd
import sys
import json

# Load environment variables
load_dotenv()

def get_github_metrics(repo_name, token=None):
    """
    Get various metrics from a GitHub repository for multiple developers for the last week
    
    Args:
        repo_name (str): Repository name in format 'owner/repo'
        token (str, optional): GitHub personal access token
    """
    # Check if token is provided
    if not token:
        print("Error: GitHub token is required for private/internal repositories")
        print("Please set GITHUB_TOKEN in your .env file")
        sys.exit(1)
    
    try:
        # Initialize GitHub client with token
        g = Github(token)
        
        # Test token validity
        try:
            user = g.get_user()
            print(f"Authenticated as: {user.login}")
        except Exception as e:
            print(f"Authentication failed: {str(e)}")
            print("Please check your GitHub token")
            sys.exit(1)
        
        try:
            repo = g.get_repo(repo_name)
            print(f"Successfully accessed repository: {repo.full_name}")
            print(f"Repository visibility: {repo.private and 'Private' or 'Public'}")
        except Exception as e:
            error_data = json.loads(str(e).split(':', 1)[1]) if ':' in str(e) else {}
            if error_data.get('message', '').startswith('Resource protected by organization SAML enforcement'):
                print("\nError: Organization SAML SSO Access Required")
                print("Your Personal Access Token needs to be authorized for the organization.")
                print("\nTo fix this:")
                print("1. Go to GitHub.com → Settings → Developer Settings → Personal Access Tokens")
                print("2. Find your token and click on it")
                print("3. Look for 'Organization access' section")
                print("4. Click 'Grant' next to the organization")
                print("5. Complete the SAML SSO authorization")
                print("\nAfter authorizing, try running the script again.")
            else:
                print(f"Error accessing repository: {str(e)}")
                print("Please check:")
                print("1. Repository name is correct")
                print("2. You have access to the repository")
                print("3. Your token has the necessary permissions")
            sys.exit(1)
        
        # Initialize developer metrics
        dev_metrics = defaultdict(lambda: {
            'lines_of_code': 0,
            'commits': 0,
            'coding_days': set(),
            'commits_per_day': defaultdict(int),
            'files_changed': set(),
            'first_commit': None,
            'last_commit': None
        })
        
        # Calculate date range for last week
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        print(f"\nAnalyzing metrics from {start_date.date()} to {end_date.date()}")
        
        # Get all commits
        try:
            commits = list(repo.get_commits(since=start_date))
            total_commits = len(commits)
            print(f"Found {total_commits} commits in the last week")
        except Exception as e:
            print(f"Error getting commits: {str(e)}")
            sys.exit(1)
        
        # Process each commit
        for commit in commits:
            # Get author information with fallback options
            author = None
            if commit.author:
                author = commit.author.login
            elif commit.commit.author:
                author = commit.commit.author.name
            else:
                author = "Unknown"
            
            commit_date = commit.commit.author.date.date()
            
            # Only process commits from the last week
            if commit_date >= start_date.date():
                # Update commit metrics
                dev_metrics[author]['commits'] += 1
                dev_metrics[author]['coding_days'].add(commit_date)
                dev_metrics[author]['commits_per_day'][commit_date] += 1
                
                # Update first and last commit dates
                if not dev_metrics[author]['first_commit'] or commit_date < dev_metrics[author]['first_commit']:
                    dev_metrics[author]['first_commit'] = commit_date
                if not dev_metrics[author]['last_commit'] or commit_date > dev_metrics[author]['last_commit']:
                    dev_metrics[author]['last_commit'] = commit_date
                
                # Get files changed in this commit
                try:
                    files = commit.files
                    for file in files:
                        # Skip image files
                        if file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                            continue
                            
                        dev_metrics[author]['files_changed'].add(file.filename)
                        # Count lines added and removed for this file
                        if file.additions is not None:
                            dev_metrics[author]['lines_of_code'] += file.additions
                        if file.deletions is not None:
                            dev_metrics[author]['lines_of_code'] -= file.deletions
                except Exception as e:
                    print(f"Error processing files in commit: {str(e)}")
                    continue
        
        # Print team-wide metrics
        total_lines = sum(metrics['lines_of_code'] for metrics in dev_metrics.values())
        all_coding_days = set()
        for metrics in dev_metrics.values():
            all_coding_days.update(metrics['coding_days'])
        
        print(f"\nTeam Metrics for repository: {repo_name} (Last 7 days)")
        print(f"Total lines of code changed: {total_lines}")
        print(f"Total commits: {total_commits}")
        print(f"Total coding days: {len(all_coding_days)}")
        print(f"Number of active developers: {len(dev_metrics)}")
        
        # Print individual developer metrics
        print("\nIndividual Developer Metrics (Last 7 days):")
        for author, metrics in dev_metrics.items():
            print(f"\nDeveloper: {author}")
            print(f"Lines of code changed: {metrics['lines_of_code']}")
            print(f"Total commits: {metrics['commits']}")
            print(f"Coding days: {len(metrics['coding_days'])}")
            print(f"Files changed: {len(metrics['files_changed'])}")
            
            # Calculate average commits per day
            if metrics['commits_per_day']:
                avg_commits = sum(metrics['commits_per_day'].values()) / len(metrics['commits_per_day'])
                print(f"Average commits per day: {avg_commits:.2f}")
            
            # Print activity period
            if metrics['first_commit'] and metrics['last_commit']:
                print(f"Activity period: {metrics['first_commit']} to {metrics['last_commit']}")
            
            # Print daily activity for the last week
            print("Daily activity:")
            for i in range(7):
                date = (end_date - timedelta(days=i)).date()
                commits = metrics['commits_per_day'].get(date, 0)
                print(f"  {date}: {commits} commits")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Get repository name from environment variable or use default
    repo_name = os.getenv("GITHUB_REPO", "owner/repo")
    token = os.getenv("GITHUB_TOKEN")
    
    get_github_metrics(repo_name, token) 