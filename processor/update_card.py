import pandas as pd
import requests
import json
import urllib
import config  # Import config for Jira credentials

# Define headers for Jira requests
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Basic {config.ENCODED_CREDENTIALS}'  # Use the dynamically set credentials
}

# Function to sanitize text input
def sanitize_text(text):
    if isinstance(text, str):
        return text.replace('\n', ' ').replace('\r', ' ').strip()
    elif pd.isna(text):
        return ''
    else:
        return str(text).strip()

# Function to create an ADF table for test script details
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
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": sanitize_text(row.get('Test Script ID', 'N/A'))}]}]},
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

# Function to check if a Jira issue exists based on the test case ID
def jira_issue_exists(test_case_id):
    jql_query = f'project = BTV AND summary ~ "{test_case_id}"'
    encoded_jql_query = urllib.parse.quote(jql_query)
    url = f"{config.JIRA_URL_BASE}/search?jql={encoded_jql_query}"

    response = requests.get(url, headers={'Accept': 'application/json'}, auth=config.AUTH)

    if response.status_code == 200:
        issues = response.json().get('issues', [])
        if issues:
            return issues[0]['key']
    return None

# Function to update the Jira issue description with the new data from the Excel file
def update_issue_description(test_case_id, group):
    issue_key = jira_issue_exists(test_case_id)
    
    if issue_key:
        first_row = group.iloc[0]
        bam_test_script_status = sanitize_text(first_row.get('BAM Test Script Status', 'N/A'))
        test_script_table_adf = create_test_script_table(group)

        payload = json.dumps({
            "update": {
                "description": [
                    {
                        "set": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"type": "text", "text": f"Updated BAM Test Script Status: {bam_test_script_status}\n\nTest Script Details:"}
                                    ]
                                },
                                test_script_table_adf
                            ]
                        }
                    }
                ]
            }
        })

        url = f"{config.JIRA_URL_BASE}/issue/{issue_key}"
        response = requests.put(url, data=payload, headers=headers, auth=config.AUTH)

        if response.status_code == 204:
            print(f"Successfully updated description for {test_case_id}.")
        else:
            print(f"Failed to update description for {test_case_id}: {response.status_code}, {response.text}")
    else:
        print(f"Issue not found for Test Case ID: {test_case_id}")

# Function to process a sheet from the Excel file and update Jira cards
def process_sheet_with_updates(test_case_file, sheet_name):
    df = pd.read_excel(test_case_file, sheet_name=sheet_name)
    grouped_df = df.groupby('Test Case ID')

    for test_case_id, group in grouped_df:
        update_issue_description(test_case_id, group)
