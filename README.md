# GitHub Repository Metrics

This script fetches various metrics from a GitHub repository including:
- Total lines of code
- Average commits per day
- Total coding days
- Commits per day for the last 7 days

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the same directory with your GitHub credentials:
```
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_REPO=owner/repo_name
```

You can create a GitHub Personal Access Token by going to:
- GitHub Settings → Developer Settings → Personal Access Tokens → Tokens (classic)
- Generate new token with 'repo' scope

## Usage

Run the script:
```bash
python github_metrics.py
```

The script will output:
- Total lines of code in the repository
- Average number of commits per day
- Total number of days with commits
- Commits per day for the last 7 days

## Notes
- The script uses the GitHub API which has rate limits
- Using a personal access token increases the rate limit
- The lines of code count includes all files in the repository 