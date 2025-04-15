from github import Github
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
from collections import defaultdict
import pandas as pd
import sys
import json

# Load environment variables
load_dotenv()

def get_branches(repo):
    """Get all branches in the repository."""
    try:
        print("Fetching branches from repository...")
        
        # Get branches using pagination
        branches = []
        page = 1
        per_page = 100  # Maximum allowed by GitHub API
        
        while True:
            # Get a page of branches
            try:
                branch_page = list(repo.get_branches().get_page(page))
                if not branch_page:
                    print(f"No more branches found on page {page}")
                    break
                
                print(f"\nProcessing page {page} with {len(branch_page)} branches")
                
                for branch in branch_page:
                    try:
                        branch_name = branch.name
                        print(f"Found branch: {branch_name}")
                        branches.append(branch_name)
                        
                        # If we've found enough branches, we can stop
                        if len(branches) >= 1000:  # GitHub API limit
                            print("Warning: Reached maximum branch limit of 1000")
                            break
                    except Exception as e:
                        print(f"Warning: Could not process branch: {str(e)}")
                        continue
                
                # If we've reached the limit or no more branches, stop
                if len(branches) >= 1000 or len(branch_page) < per_page:
                    break
                    
                page += 1
                
            except Exception as e:
                print(f"Warning: Error getting branch page {page}: {str(e)}")
                break
        
        print(f"\nFound {len(branches)} branches")
        return branches
    except Exception as e:
        print(f"Error getting branches: {str(e)}")
        return []

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
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)
        print(f"\nAnalyzing metrics from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Get branches created in the last 90 days
        branches = get_branches(repo)
        
        # Create a mapping of commit SHA to branch name
        commit_branch_map = {}
        for branch_name in branches:
            try:
                branch = repo.get_branch(branch_name)
                commits = repo.get_commits(sha=branch.commit.sha, since=start_date, until=end_date)
                for commit in commits:
                    commit_branch_map[commit.sha] = branch_name
            except Exception as e:
                print(f"Warning: Could not get commits for branch {branch_name}: {str(e)}")
                continue
        
        # Get all commits across all branches
        all_commits = []
        for branch_name in branches:
            try:
                commits = repo.get_commits(sha=branch_name, since=start_date, until=end_date)
                all_commits.extend(commits)
            except Exception as e:
                print(f"Warning: Could not get commits for branch {branch_name}: {str(e)}")
                continue
        
        print(f"Found {len(all_commits)} commits in the specified date range")
        
        # Process commits from each branch
        for commit in all_commits:
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
                branch_name = commit_branch_map.get(commit.sha, 'Unknown')
                if branch_name == 'master':
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
        
        # Create output directory if it doesn't exist
        output_dir = "metrics_output"
        os.makedirs(output_dir, exist_ok=True)
        
        # Create team metrics DataFrame
        team_data = {
            'Metric': [
                'Total Lines Added',
                'Total Lines Removed',
                'Net Lines Changed',
                'Total Commits',
                'Total Coding Days',
                'Active Developers'
            ],
            'Value': [
                sum(metrics['lines_added'] for metrics in dev_metrics.values()),
                sum(metrics['lines_removed'] for metrics in dev_metrics.values()),
                sum(metrics['lines_added'] - metrics['lines_removed'] for metrics in dev_metrics.values()),
                sum(metrics['commits'] for metrics in dev_metrics.values()),
                len(set().union(*(metrics['coding_days'] for metrics in dev_metrics.values()))),
                len(dev_metrics)
            ]
        }
        team_df = pd.DataFrame(team_data)
        
        # Create developer metrics DataFrame
        dev_data = []
        for author, metrics in dev_metrics.items():
            activity_days = (metrics['last_commit'] - metrics['first_commit']).days + 1 if metrics['first_commit'] and metrics['last_commit'] else 0
            avg_commits = metrics['commits'] / activity_days if activity_days > 0 else 0
            
            dev_data.append({
                'Developer': author,
                'Lines Added': metrics['lines_added'],
                'Lines Removed': metrics['lines_removed'],
                'Net Lines Changed': metrics['lines_added'] - metrics['lines_removed'],
                'Total Commits': metrics['commits'],
                'PR Branch Commits': metrics['pr_branch_commits'],
                'Master Commits': metrics['master_commits'],
                'Coding Days': len(metrics['coding_days']),
                'Files Changed': len(metrics['files_changed']),
                'Avg Commits/Day': f"{avg_commits:.2f}",
                'Activity Period': f"{metrics['first_commit']} to {metrics['last_commit']}" if metrics['first_commit'] and metrics['last_commit'] else "N/A"
            })
        
        dev_df = pd.DataFrame(dev_data)
        
        # Create daily activity DataFrame
        daily_data = []
        for author, metrics in dev_metrics.items():
            for i in range(7):
                date = (end_date - timedelta(days=i)).date()
                commits = metrics['commits_per_day'].get(date, 0)
                daily_data.append({
                    'Developer': author,
                    'Date': date,
                    'Commits': commits
                })
        daily_df = pd.DataFrame(daily_data)
        
        # Save DataFrames to CSV files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        team_df.to_csv(f"{output_dir}/team_metrics_{timestamp}.csv", index=False)
        dev_df.to_csv(f"{output_dir}/developer_metrics_{timestamp}.csv", index=False)
        daily_df.to_csv(f"{output_dir}/daily_activity_{timestamp}.csv", index=False)
        
        print(f"\nMetrics have been saved to CSV files in the '{output_dir}' directory:")
        print(f"- team_metrics_{timestamp}.csv")
        print(f"- developer_metrics_{timestamp}.csv")
        print(f"- daily_activity_{timestamp}.csv")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

def main():
    # Load environment variables
    load_dotenv()
    
    # Get GitHub token and repository from environment variables
    token = os.getenv('GITHUB_TOKEN')
    repo_name = os.getenv('GITHUB_REPO')
    
    if not token:
        print("Error: GITHUB_TOKEN not found in .env file")
        return
    
    if not repo_name:
        print("Error: GITHUB_REPO not found in .env file")
        return
    
    # Initialize GitHub client
    g = Github(token)
    
    try:
        # Test token validity and get repository
        user = g.get_user()
        print(f"Successfully authenticated as {user.login}")
        
        try:
            repo = g.get_repo(repo_name)
            print(f"Successfully accessed repository: {repo_name}")
            print(f"Repository visibility: {repo.private and 'Private' or 'Public'}")
            print(f"Default branch: {repo.default_branch}")
        except Exception as e:
            print(f"Error accessing repository: {str(e)}")
            print("Please check if:")
            print("1. The repository name is correct (format: owner/repo)")
            print("2. You have access to the repository")
            print("3. The token has the necessary permissions")
            return
        
        # Set date range for analysis (last 7 days)
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)
        
        print(f"\nAnalyzing repository from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Initialize metrics
        team_metrics = {
            'total_lines_added': 0,
            'total_lines_removed': 0,
            'total_commits': 0,
            'total_coding_days': set(),
            'active_developers': set()
        }
        
        developer_metrics = defaultdict(lambda: {
            'lines_added': 0,
            'lines_removed': 0,
            'commits': 0,
            'coding_days': set(),
            'files_changed': set(),
            'pr_branch_commits': 0,
            'master_commits': 0,
            'first_commit': None,
            'last_commit': None
        })
        
        daily_activity = defaultdict(lambda: defaultdict(int))
        
        # Get commits from the default branch
        try:
            print(f"Getting commits from default branch ({repo.default_branch})")
            commits = repo.get_commits(since=start_date, until=end_date)
            
            # Process each commit
            for commit in commits:
                # Get author information
                author = None
                if commit.author:
                    author = commit.author.login
                elif commit.commit.author:
                    author = commit.commit.author.name
                else:
                    author = "Unknown"
                
                commit_date = commit.commit.author.date.date()
                print(f"Processing commit {commit.sha[:7]} by {author} on {commit_date}")
                
                # Update team metrics
                team_metrics['total_commits'] += 1
                team_metrics['total_coding_days'].add(commit_date)
                team_metrics['active_developers'].add(author)
                
                # Update developer metrics
                dev_metrics = developer_metrics[author]
                dev_metrics['commits'] += 1
                dev_metrics['coding_days'].add(commit_date)
                
                # Track branch type (all commits are from default branch)
                dev_metrics['master_commits'] += 1
                
                # Update first and last commit dates
                if not dev_metrics['first_commit'] or commit_date < dev_metrics['first_commit']:
                    dev_metrics['first_commit'] = commit_date
                if not dev_metrics['last_commit'] or commit_date > dev_metrics['last_commit']:
                    dev_metrics['last_commit'] = commit_date
                
                # Update daily activity
                daily_activity[author][commit_date] += 1
                
                # Process files in commit
                try:
                    files = commit.files
                    for file in files:
                        # Skip image files
                        if file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                            continue
                        
                        dev_metrics['files_changed'].add(file.filename)
                        if file.additions is not None:
                            dev_metrics['lines_added'] += file.additions
                            team_metrics['total_lines_added'] += file.additions
                        if file.deletions is not None:
                            dev_metrics['lines_removed'] += file.deletions
                            team_metrics['total_lines_removed'] += file.deletions
                except Exception as e:
                    print(f"Error processing files in commit: {str(e)}")
                    continue
                    
        except Exception as e:
            print(f"Error getting commits: {str(e)}")
            return
        
        print(f"\nProcessed {team_metrics['total_commits']} commits")
        
        # Create output directory if it doesn't exist
        os.makedirs('metrics_output', exist_ok=True)
        
        # Generate timestamp for filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save team metrics
        team_data = {
            'Metric': [
                'Total Lines Added',
                'Total Lines Removed',
                'Net Lines Changed',
                'Total Commits',
                'Total Coding Days',
                'Active Developers'
            ],
            'Value': [
                team_metrics['total_lines_added'],
                team_metrics['total_lines_removed'],
                team_metrics['total_lines_added'] - team_metrics['total_lines_removed'],
                team_metrics['total_commits'],
                len(team_metrics['total_coding_days']),
                len(team_metrics['active_developers'])
            ]
        }
        pd.DataFrame(team_data).to_csv(f'metrics_output/team_metrics_{timestamp}.csv', index=False)
        
        # Save developer metrics
        dev_data = []
        for author, metrics in developer_metrics.items():
            activity_days = (metrics['last_commit'] - metrics['first_commit']).days + 1 if metrics['first_commit'] and metrics['last_commit'] else 0
            avg_commits = metrics['commits'] / activity_days if activity_days > 0 else 0
            
            dev_data.append({
                'Developer': author,
                'Lines Added': metrics['lines_added'],
                'Lines Removed': metrics['lines_removed'],
                'Net Lines Changed': metrics['lines_added'] - metrics['lines_removed'],
                'Total Commits': metrics['commits'],
                'PR Branch Commits': metrics['pr_branch_commits'],
                'Master Commits': metrics['master_commits'],
                'Coding Days': len(metrics['coding_days']),
                'Files Changed': len(metrics['files_changed']),
                'Avg Commits/Day': f"{avg_commits:.2f}",
                'Activity Period': f"{metrics['first_commit']} to {metrics['last_commit']}" if metrics['first_commit'] and metrics['last_commit'] else "N/A"
            })
        pd.DataFrame(dev_data).to_csv(f'metrics_output/developer_metrics_{timestamp}.csv', index=False)
        
        # Save daily activity
        daily_data = []
        for author, daily_commits in daily_activity.items():
            for date in sorted(daily_commits.keys()):
                daily_data.append({
                    'Developer': author,
                    'Date': date,
                    'Commits': daily_commits[date]
                })
        pd.DataFrame(daily_data).to_csv(f'metrics_output/daily_activity_{timestamp}.csv', index=False)
        
        print(f"\nMetrics have been saved to CSV files in the 'metrics_output' directory:")
        print(f"- team_metrics_{timestamp}.csv")
        print(f"- developer_metrics_{timestamp}.csv")
        print(f"- daily_activity_{timestamp}.csv")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        if "Bad credentials" in str(e):
            print("Please check your GitHub token in the .env file")
        elif "rate limit exceeded" in str(e).lower():
            print("GitHub API rate limit exceeded. Please try again later.")
        else:
            print("An unexpected error occurred. Please check your configuration and try again.")

if __name__ == "__main__":
    main() 