from github import Github
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from collections import defaultdict
import pandas as pd

# Load environment variables
load_dotenv()

def get_github_metrics(repo_name, token=None):
    """
    Get various metrics from a GitHub repository for multiple developers
    
    Args:
        repo_name (str): Repository name in format 'owner/repo'
        token (str, optional): GitHub personal access token
    """
    # Initialize GitHub client
    if token:
        g = Github(token)
    else:
        g = Github()
    
    try:
        repo = g.get_repo(repo_name)
        
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
        
        # Get all commits
        commits = list(repo.get_commits())
        total_commits = len(commits)
        
        # Process each commit
        for commit in commits:
            author = commit.author.login if commit.author else "Unknown"
            commit_date = commit.commit.author.date.date()
            
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
                    dev_metrics[author]['files_changed'].add(file.filename)
                    # Count lines added and removed for this file
                    if file.additions is not None:
                        dev_metrics[author]['lines_of_code'] += file.additions
                    if file.deletions is not None:
                        dev_metrics[author]['lines_of_code'] -= file.deletions
            except Exception as e:
                print(f"Error processing files in commit: {str(e)}")
                continue
        
        # Get current state of files
        try:
            contents = repo.get_contents("")
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    contents.extend(repo.get_contents(file_content.path))
                elif file_content.type == "file":
                    try:
                        content = repo.get_contents(file_content.path)
                        if content:
                            # Get the last commit that modified this file
                            commits = list(repo.get_commits(path=file_content.path))
                            if commits:
                                author = commits[0].author.login if commits[0].author else "Unknown"
                                lines = len(content.decoded_content.decode().split('\n'))
                                dev_metrics[author]['lines_of_code'] = max(dev_metrics[author]['lines_of_code'], lines)
                    except Exception as e:
                        print(f"Error processing file {file_content.path}: {str(e)}")
                        continue
        except Exception as e:
            print(f"Error getting repository contents: {str(e)}")
        
        # Print team-wide metrics
        total_lines = sum(metrics['lines_of_code'] for metrics in dev_metrics.values())
        all_coding_days = set()
        for metrics in dev_metrics.values():
            all_coding_days.update(metrics['coding_days'])
        
        print(f"\nTeam Metrics for repository: {repo_name}")
        print(f"Total lines of code: {total_lines}")
        print(f"Total commits: {total_commits}")
        print(f"Total coding days: {len(all_coding_days)}")
        print(f"Number of developers: {len(dev_metrics)}")
        
        # Print individual developer metrics
        print("\nIndividual Developer Metrics:")
        for author, metrics in dev_metrics.items():
            print(f"\nDeveloper: {author}")
            print(f"Lines of code: {metrics['lines_of_code']}")
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
                days_active = (metrics['last_commit'] - metrics['first_commit']).days + 1
                print(f"Days active: {days_active}")
            
            # Print last 7 days activity
            print("Last 7 days activity:")
            today = datetime.now().date()
            for i in range(7):
                date = today - timedelta(days=i)
                commits = metrics['commits_per_day'].get(date, 0)
                print(f"  {date}: {commits} commits")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    # Get repository name from environment variable or use default
    repo_name = os.getenv("GITHUB_REPO", "owner/repo")
    token = os.getenv("GITHUB_TOKEN")
    
    get_github_metrics(repo_name, token) 