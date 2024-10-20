import requests
import config  # Import config for Jira credentials

# Define headers for Jira requests
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Basic {config.ENCODED_CREDENTIALS}'  # Use the dynamically set credentials
}

# Function to delete a Jira issue by issue ID (single issue deletion)
def delete_jira_issue(issue_id):
    url = f"{config.JIRA_URL_BASE}/issue/{issue_id}"

    response = requests.delete(url, headers=headers, auth=config.AUTH)

    if response.status_code == 204:
        print(f"Successfully deleted issue: {issue_id}")
        return True
    else:
        print(f"Failed to delete issue {issue_id}: {response.status_code}, {response.text}")
        return False

# Function to delete Jira issues within a range of issue IDs
def delete_issues_by_range(issue_prefix, start_id, end_id):
    for issue_id in range(start_id, end_id + 1):
        issue_key = f"{issue_prefix}-{issue_id}"
        success = delete_jira_issue(issue_key)
        if not success:
            print(f"Failed to delete issue: {issue_key}")

# Function to delete a single issue by Issue ID provided
def delete_single_issue(issue_id):
    success = delete_jira_issue(issue_id)
    if success:
        print(f"Successfully deleted issue {issue_id}.")
    else:
        print(f"Failed to delete issue {issue_id}.")
