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
            'lines_added': 0,
            'lines_removed': 0,
            'commits': 0,
            'coding_days': set(),
            'commits_per_day': defaultdict(int),
            'files_changed': set(),
            'first_commit': None,
            'last_commit': None,
            'pr_branch_commits': 0,  # Commits in PR branches
            'pr_branch_days': set(),  # Days with PR branch activity
            'master_commits': 0,      # Commits in master
            'master_days': set()      # Days with master activity
        })
        
        # Calculate date range for last week
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        print(f"\nAnalyzing metrics from {start_date.date()} to {end_date.date()}")
        
        # Get all branches
        try:
            branches = list(repo.get_branches())
            print(f"Found {len(branches)} branches")
        except Exception as e:
            print(f"Error getting branches: {str(e)}")
            sys.exit(1)
        
        # Process commits from each branch
        for branch in branches:
            try:
                commits = list(repo.get_commits(sha=branch.commit.sha, since=start_date))
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
                        
                        # Track PR branch vs master commits
                        if branch.name == 'master':
                            dev_metrics[author]['master_commits'] += 1
                            dev_metrics[author]['master_days'].add(commit_date)
                        else:
                            dev_metrics[author]['pr_branch_commits'] += 1
                            dev_metrics[author]['pr_branch_days'].add(commit_date)
                        
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
                                    dev_metrics[author]['lines_added'] += file.additions
                                if file.deletions is not None:
                                    dev_metrics[author]['lines_removed'] += file.deletions
                        except Exception as e:
                            print(f"Error processing files in commit: {str(e)}")
                            continue
            except Exception as e:
                print(f"Error processing branch {branch.name}: {str(e)}")
                continue
        
        # Print team-wide metrics
        total_lines_added = sum(metrics['lines_added'] for metrics in dev_metrics.values())
        total_lines_removed = sum(metrics['lines_removed'] for metrics in dev_metrics.values())
        all_coding_days = set()
        for metrics in dev_metrics.values():
            all_coding_days.update(metrics['coding_days'])
        
        print(f"\nTeam Metrics for repository: {repo_name} (Last 7 days)")
        print(f"Total lines of code added: {total_lines_added}")
        print(f"Total lines of code removed: {total_lines_removed}")
        print(f"Net lines changed: {total_lines_added - total_lines_removed}")
        print(f"Total commits: {sum(metrics['commits'] for metrics in dev_metrics.values())}")
        print(f"Total coding days: {len(all_coding_days)}")
        print(f"Number of active developers: {len(dev_metrics)}")
        
        # Print individual developer metrics
        print("\nIndividual Developer Metrics (Last 7 days):")
        for author, metrics in dev_metrics.items():
            print(f"\nDeveloper: {author}")
            print(f"Lines of code added: {metrics['lines_added']}")
            print(f"Lines of code removed: {metrics['lines_removed']}")
            print(f"Net lines changed: {metrics['lines_added'] - metrics['lines_removed']}")
            print(f"Total commits: {metrics['commits']}")
            print(f"PR branch commits: {metrics['pr_branch_commits']}")
            print(f"Master branch commits: {metrics['master_commits']}")
            print(f"Coding days: {len(metrics['coding_days'])}")
            print(f"Files changed: {len(metrics['files_changed'])}")
            
            # Calculate average commits per day based on activity period
            if metrics['first_commit'] and metrics['last_commit']:
                activity_days = (metrics['last_commit'] - metrics['first_commit']).days + 1
                avg_commits = metrics['commits'] / activity_days
                print(f"Average commits per day: {avg_commits:.2f}")
                print(f"Activity period: {metrics['first_commit']} to {metrics['last_commit']} ({activity_days} days)")
            else:
                print("Average commits per day: N/A")
            
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