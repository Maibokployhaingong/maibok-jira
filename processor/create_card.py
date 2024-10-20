import requests
import json
import time
import pandas as pd
import config  # Import your config file for AUTH and other settings
import urllib

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Basic {config.ENCODED_CREDENTIALS}'  # Use the dynamically set credentials
}

# Define the retry limit and delay
retry_limit = 3
delay = 2  # seconds


# Function to sanitize text
def sanitize_text(text):
    if isinstance(text, str):
        return text.replace('\n', ' ').replace('\r', ' ').strip()
    elif pd.isna(text):
        return ''
    else:
        return str(text).strip()

# Function to create an ADF table with test script details
def create_test_script_table(group):
    table_content = []

    # Add the header row
    header_row = {
        "type": "tableRow",
        "content": [
            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Test Script ID", "marks": [{"type": "strong"}]}]}]},
            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Test Script Name", "marks": [{"type": "strong"}]}]}]},
            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "TBN Test Script Status", "marks": [{"type": "strong"}]}]}]},
            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "BAM Test Script Status", "marks": [{"type": "strong"}]}]}]}
        ]
    }
    table_content.append(header_row)

    # Add each test script as a row
    for _, row in group.iterrows():
        table_row = {
            "type": "tableRow",
            "content": [
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": row['Test Script ID']}]}]},
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": sanitize_text(row.get('Test Script Name', 'N/A'))}]}]},
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": sanitize_text(row.get('Test Script Status', 'N/A'))}]}]},
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": sanitize_text(row.get('BAM Test Script Status', 'N/A'))}]}]}
            ]
        }
        table_content.append(table_row)

    # Return the table content in ADF format
    return {
        "type": "table",
        "attrs": {
            "isNumberColumnEnabled": False,
            "layout": "default"
        },
        "content": table_content
    }

# Function to get the last running number from existing Jira tasks
def get_last_running_number(module):
    # Add the body for the function
    jql_query = f'project = BTV AND issuetype = Task AND summary ~ "TC_{module}*" ORDER BY created DESC'

    # URL encode the JQL query
    encoded_jql_query = urllib.parse.quote(jql_query)

    url = f"{config.JIRA_URL_BASE}/search?jql={encoded_jql_query}&maxResults=1000"

    try:
        # Make the request to Jira
        response = requests.get(url, headers={'Accept': 'application/json'}, auth=config.AUTH)

        # Check the response
        if response.status_code == 200:
            issues = response.json().get('issues', [])

            if not issues:
                print(f"No issues found with {module} running numbers. Defaulting to 001.")
                return "001"

            # Initialize variables to store the highest running number
            highest_running_number = 0

            # Process each issue and extract the running number
            for issue in issues:
                summary = issue['fields']['summary']
                print(f"Processing issue summary: {summary}")

                try:
                    # Extract the running number between "[" and "]"
                    running_number_str = summary.split(f"[{module}")[1].split("]")[0].strip()
                    print(f"Extracted running number string: {running_number_str}")

                    # Convert the extracted string to an integer
                    running_number = int(running_number_str)
                    print(f"Converted running number: {running_number}")

                    # Update the highest running number
                    if running_number > highest_running_number:
                        highest_running_number = running_number

                except (IndexError, ValueError) as e:
                    print(f"Error extracting running number from summary '{summary}': {e}")
                    continue  # Skip if parsing fails

            # Increment the highest running number to get the next one
            next_running_number = f"{highest_running_number + 1:03}"
            print(f"Next running number: {next_running_number}")
            return next_running_number
        else:
            print(f"Failed to fetch issues: {response.status_code}, {response.text}")
            return "001"  # Default to "001" if there's an error
    except Exception as e:
        # Handle any errors during the request
        print(f"Error during Jira request: {e}", flush=True)
        return "001"  # Default to "001" if there's an error


# Function to check if a Jira issue exists for the test case ID
def jira_issue_exists(test_case_id):
    # Define the JQL query
    jql_query = f'project = BTV AND summary ~ "{test_case_id}"'
    encoded_jql_query = urllib.parse.quote(jql_query)

    # Use the correct search URL (no /issue/ in the path)
    url = f"{config.JIRA_URL_BASE}/search?jql={encoded_jql_query}"

    # Make the request
    response = requests.get(url, headers={'Accept': 'application/json'}, auth=config.AUTH)

    print(f"Checking Jira issue with URL: {url}")

    # Check the response
    if response.status_code == 200:
        issues = response.json().get('issues', [])
        if issues:
            print(f"Jira issue exists for {test_case_id}: {issues[0]['key']}")
            return issues[0]['key']  # Return the issue key if it exists
        else:
            print(f"No Jira issue found for {test_case_id}")
    else:
        print(f"Failed to fetch issue details: {response.status_code}, {response.text}")
    
    return None  # Return None if no issue exists

# Function to process one sheet at a time
def process_sheet(test_case_file, sheet_name, module):
    # Get the last running number
    running_number = get_last_running_number(module)

    # Load the sheet into a DataFrame
    df = pd.read_excel(test_case_file, sheet_name=sheet_name)
    
    # Group by Test Case ID
    grouped_df = df.groupby('Test Case ID')

    # Loop through each unique test case
    for test_case_id, group in grouped_df:
        # Check if the Jira issue already exists
        issue_key = jira_issue_exists(test_case_id)
        
        # If the issue already exists, skip creating a new one
        if issue_key:
            print(f"Skipping creation for {test_case_id} as it already exists.")
            continue  # Move to the next test case
        
        # Extract relevant information and sanitize
        first_row = group.iloc[0]
        
        # Fetch data with fallback values to avoid "Unknown" or "No description available" issues
        test_case_description = sanitize_text(first_row.get('Test Case Description', 'No description available'))
        group_ball = sanitize_text(first_row.get('Group', 'Unknown'))
        
        # Handle potential missing or empty data fields more gracefully
        test_status_by_tbn = sanitize_text(first_row.get('Test Script Status', 'Unknown'))
        tbn_test_date = sanitize_text(first_row.get('Test Date', 'Unknown'))
        
        # Generate the table for test script details in ADF format
        test_script_table_adf = create_test_script_table(group)

        # Format the running number
        running_str = f"{module}{str(running_number).zfill(3)}"

        # Jira summary
        summary = f"[{running_str}] {group_ball} - {test_case_id} - {test_case_description}"

        # Print the summary for debugging
        print(f"Creating issue with summary: {summary}")

        # Jira payload with ADF table in description
        payload = json.dumps({
            "fields": {
                "project": {
                    "key": "BTV"
                },
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Test Status by TBN: {test_status_by_tbn}\nTBN Test Date: {tbn_test_date}\n\nTest Script Details:"
                                }
                            ]
                        },
                        test_script_table_adf
                    ]
                },
                "issuetype": {
                    "name": "Task"
                }
            }
        })

        # Retry logic (with the correct headers)
        for attempt in range(retry_limit):
            response = requests.post(f"{config.JIRA_URL_BASE}/issue", data=payload, headers=headers, auth=config.AUTH)
            if response.status_code == 201:
                print(f"Successfully created issue for {test_case_id} in {sheet_name}")
                # Update the running_number for the next one
                running_number = int(running_number) + 1
                break
            else:
                print(f"Failed to create issue for {test_case_id} in {sheet_name}, attempt {attempt + 1}: {response.status_code}, {response.text}")
                if attempt < retry_limit - 1:
                    time.sleep(delay)
                else:
                    print(f"Giving up on {test_case_id} after {retry_limit} attempts.")

