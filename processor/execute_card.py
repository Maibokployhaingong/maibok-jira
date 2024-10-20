import os
import shutil
import requests
import logging
from tenacity import retry, wait_fixed, stop_after_attempt
import datetime
import config  # Import from the centralized config file
from logging.handlers import RotatingFileHandler
import urllib
import json

# Set up rotating log handler (creates new log files when the size limit is reached)
handler = RotatingFileHandler('test_results.log', maxBytes=5000000, backupCount=5)  # 5 MB max size per file, keep up to 5 backups
logging.basicConfig(filename='test_results.log', level=logging.INFO, 
                    format='%(asctime)s %(levelname)s %(funcName)s %(lineno)d: %(message)s')

# Retry mechanism for API calls
@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
def make_jira_request(url, payload):
    try:
        response = requests.post(url, json=payload, headers={'Accept': 'application/json'}, auth=config.AUTH)
        
        # Print the URL and payload for debugging purposes
        # print(f"Making request to: {url}", flush=True)
        # print(f"Payload: {json.dumps(payload, indent=2)}", flush=True)
        
        # Check the response status code
        if response.status_code != 201:
            # Print detailed response if the request fails
            print(f"Failed request. Status Code: {response.status_code}, Response: {response.text}", flush=True)
            raise Exception(f"Failed request with status code {response.status_code}")
        
        # Return the response if successful
        return response

    except Exception as e:
        # Print the exception details
        print(f"Exception occurred during Jira request: {str(e)}", flush=True)
        raise e


# Function to update custom fields (TBN Test Date, Test Status by TBN, BAM Version Testing)
def update_issue_with_custom_fields(issue_key, tbn_test_date, test_status_by_tbn, bam_version_testing):
    payload = {
        "fields": {
            config.TBN_TEST_DATE_FIELD_ID: tbn_test_date,
            config.TEST_STATUS_BY_TBN_FIELD_ID: {"value": test_status_by_tbn},
            config.BAM_VERSION_TESTING_FIELD_ID: bam_version_testing
        }
    }

    response = requests.put(f"{config.JIRA_API_BASE}/{issue_key}", json=payload, headers={'Accept': 'application/json'}, auth=config.AUTH)

    if response.status_code == 204:
        logging.info(f"Successfully updated custom fields for issue {issue_key}")
    else:
        logging.error(f"Failed to update custom fields for issue {issue_key}: {response.status_code}, {response.text}")

# Function to link the new Bug issue to the main issue
def link_bug_to_main_issue(main_issue_key, bug_issue_key):
    link_payload = {
        "type": {"name": "Relates"},  # Adjust the link type if necessary
        "inwardIssue": {"key": bug_issue_key},
        "outwardIssue": {"key": main_issue_key}
    }

    response = requests.post(f"{config.JIRA_URL_BASE}/issueLink", json=link_payload, headers={'Accept': 'application/json'}, auth=config.AUTH)

    if response.status_code == 201:
        logging.info(f"Successfully linked {bug_issue_key} to {main_issue_key}")
    else:
        logging.error(f"Failed to link issues: {response.status_code}, {response.text}")

def get_next_running_number():
    # Define the JQL query to specifically look for Bug issues with "TC_NPL" in the summary
    jql_query = 'project = BTV AND issuetype = Bug AND summary ~ "TC_NPL*" ORDER BY summary DESC'

    # URL encode the JQL query
    encoded_jql_query = urllib.parse.quote(jql_query)

    url = f"{config.JIRA_URL_BASE}/search?jql={encoded_jql_query}&maxResults=1000"

    try:
        # Make the request to Jira
        response = requests.get(url, headers={'Accept': 'application/json'}, auth=config.AUTH)

        # Print the response for debugging
        # print(f"Response URL: {response.url}", flush=True)
        # print(f"Response Status Code: {response.status_code}", flush=True)
        # print(f"Response Text: {response.text[:500]}", flush=True)  # Truncated response for readability

        # Check if the response is successful
        if response.status_code == 200:
            issues = response.json().get('issues', [])
            
            if not issues:
                print("No issues found with NPL running numbers. Defaulting to 001.")
                return "001"

            # Initialize variables to store the highest running number
            highest_running_number = 0

            # Process each issue and extract running number
            for issue in issues:
                summary = issue['fields']['summary']
                print(f"Processing issue summary: {summary}")

                try:
                    # Extract the running number between "NPL" and the closing square bracket "]"
                    running_number_str = summary.split("NPL")[1].split("]")[0].strip()
                    print(f"Extracted running number string: {running_number_str}")

                    # Convert extracted string to an integer
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


# Function to notify via Slack (optional)
def notify_slack(message):
    if config.SLACK_WEBHOOK_URL:
        slack_data = {'text': message}
        response = requests.post(config.SLACK_WEBHOOK_URL, json=slack_data)
        if response.status_code != 200:
            raise ValueError(f"Request to Slack returned an error {response.status_code}, the response is: {response.text}")
        logging.info(f"Sent notification to Slack: {message}")

def rename_and_move_images(test_case_id, destination_folder):
    # Check if the TEMP_FOLDER exists
    if not os.path.exists(config.TEMP_FOLDER):
        logging.error(f"TEMP_FOLDER {config.TEMP_FOLDER} does not exist.")
        return None

    # Check if there are files in TEMP_FOLDER
    files = os.listdir(config.TEMP_FOLDER)
    if not files:
        logging.error(f"No files found in TEMP_FOLDER: {config.TEMP_FOLDER}")
        return None

    # Check if destination folder exists, if not create it
    if os.path.exists(destination_folder):
        # Clear the folder by deleting all existing files
        for file in os.listdir(destination_folder):
            file_path = os.path.join(destination_folder, file)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)  # Remove the file
                    logging.info(f"Deleted existing file: {file_path}")
            except Exception as e:
                logging.error(f"Failed to delete {file_path}: {str(e)}")
    else:
        os.makedirs(destination_folder, exist_ok=True)  # Create the folder if it doesn't exist
        logging.info(f"Created destination folder: {destination_folder}")

    # Process image files in TEMP_FOLDER
    image_files = sorted(
        [f for f in files if f.endswith('.png') or f.endswith('.jpg')],
        key=lambda x: os.path.getctime(os.path.join(config.TEMP_FOLDER, x))
    )

    if not image_files:
        logging.info(f"No image files found for test case {test_case_id} in TEMP_FOLDER.")
        return None

    # Rename and move each image to the new folder
    for idx, filename in enumerate(image_files, start=1):
        old_file = os.path.join(config.TEMP_FOLDER, filename)
        new_filename = f"{test_case_id}_{idx:03}.png"  # Sequential naming
        new_file = os.path.join(destination_folder, new_filename)

        try:
            shutil.move(old_file, new_file)
            logging.info(f"Moved and renamed {filename} to {new_filename}")
        except Exception as e:
            logging.error(f"Failed to move {filename}: {str(e)}")

    return destination_folder  # Return the folder path for the test case


@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
def attach_images_to_jira(issue_key, case_folder, test_case_id):
    # List and sort image files that match the test_case_id
    image_files = sorted([f for f in os.listdir(case_folder) if f.startswith(test_case_id)], reverse=True)
    
    if not image_files:
        logging.info(f"No images found for {test_case_id}. Nothing to attach.")
        return
    
    # Iterate through the image files and attach each one to the Jira issue
    for image_filename in image_files:
        image_path = os.path.join(case_folder, image_filename)
        
        try:
            # Open the image file in binary mode
            with open(image_path, 'rb') as file:
                files = {'file': (image_filename, file, 'image/png')}  # You can change 'image/png' based on your image type
                
                # Perform the POST request to attach the file
                response = requests.post(
                    f"{config.JIRA_API_BASE}/{issue_key}/attachments",
                    headers={
                        'X-Atlassian-Token': 'no-check',  # Required by Jira for attachments
                        'Authorization': f'Basic {config.ENCODED_CREDENTIALS}'  # Auth must be encoded credentials
                    },
                    files=files,
                    auth=config.AUTH
                )
                
                # Check if the request was successful and print response details
                if response.ok:
                    print(f"Successfully attached {image_filename} to Jira issue {issue_key}")
                    logging.info(f"Successfully attached {image_filename} to Jira issue {issue_key}")
                else:
                    print(f"Failed to attach {image_filename}. Status: {response.status_code}, Response: {response.text}")
                    logging.error(f"Failed to attach {image_filename}: {response.status_code}, {response.text}")
                
                # # Print response for further investigation
                # print(f"url: {response.url}", flush=True)
                # print(f"Response Status: {response.status_code}", flush=True)
                # print(f"Response Text: {response.text}", flush=True)

        except Exception as e:
            # Catch and log any exceptions
            logging.error(f"Exception occurred while attaching {image_filename}: {str(e)}")
            print(f"Exception: {str(e)}", flush=True)

def create_bug_issue(test_case_id, running_number, remark):
    summary = f"[NPL{running_number}] - {test_case_id} - {remark.split(':')[0]}"
    
    payload = {
        "fields": {
            "project": {"key": "BTV"},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": remark}
                        ]
                    }
                ]
            },
            "issuetype": {"name": "Bug"}
        }
    }

    try:
        # Correct the URL here (remove the extra '/issue')
        response = make_jira_request(config.JIRA_API_BASE, payload)
        bug_issue_key = response.json()['key']
        logging.info(f"BUG issue created: {bug_issue_key}")
        return bug_issue_key
    except Exception as e:
        logging.error(f"Failed to create BUG issue: {str(e)}")
        return None


# Function to log test results in the Remark field
def log_test_results_to_remark(issue_key, test_status, test_date, remark):
    adf_remark = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": f"Test Status: {test_status}\nTest Date: {test_date}\nRemark: {remark}"}
                ]
            }
        ]
    }

    update_payload = {
        "fields": {
            config.REMARK_FIELD_ID: adf_remark  # Use the custom field ID for remarks
        }
    }

    url = f"{config.JIRA_API_BASE}/{issue_key}"
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f'Basic {config.ENCODED_CREDENTIALS}'  # Use encoded credentials
    }

    response = requests.put(url, json=update_payload, headers=headers, auth=config.AUTH)
    if response.status_code == 204:
        logging.info(f"Successfully logged test results to Remark for Jira issue {issue_key}")
    else:
        logging.error(f"Failed to log test results to Remark: {response.status_code}, {response.text}")

# Main function to process test cases
def process_test_case(test_case_id, issue_key, test_status, test_date, remark):
    if test_status == "pass":
        # For passing test cases, we don't need the running number
        case_folder = os.path.join(config.TEST_RESULT_FOLDER, test_case_id)
        rename_and_move_images(test_case_id, case_folder)
        attach_images_to_jira(issue_key, case_folder, test_case_id)
        log_test_results_to_remark(issue_key, test_status, test_date, remark)

    elif test_status == "fail":
        # Get the next running number for the bug issue
        running_number = get_next_running_number()

        bug_folder = os.path.join(config.BUG_FOLDER_BASE, f"NPL{running_number} - {test_case_id}")
        rename_and_move_images(test_case_id, bug_folder)
        bug_issue_key = create_bug_issue(test_case_id, running_number, remark)

        if bug_issue_key:
            attach_images_to_jira(bug_issue_key, bug_folder, test_case_id)
            link_bug_to_main_issue(issue_key, bug_issue_key)
            log_test_results_to_remark(issue_key, test_status, test_date, remark)
            notify_slack(f"BUG issue {bug_issue_key} created for test case {test_case_id}")

    elif test_status == "cancel":
        cancel_folder = os.path.join(config.CANCEL_FOLDER_BASE, test_case_id)
        rename_and_move_images(test_case_id, cancel_folder)
        attach_images_to_jira(issue_key, cancel_folder, test_case_id)
        log_test_results_to_remark(issue_key, test_status, test_date, remark)

# Function to archive old test results
def archive_old_results(days_old=30):
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_old)
    for folder in os.listdir(config.TEST_RESULT_FOLDER):
        folder_path = os.path.join(config.TEST_RESULT_FOLDER, folder)
        folder_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(folder_path))
        if folder_mtime < cutoff_date:
            shutil.move(folder_path, config.ARCHIVE_FOLDER)
            logging.info(f"Archived {folder}")

# # Example usage
# test_case_id = "TC_NPL01008"
# main_issue_key = "BTV-3100"
# test_status = "fail"  # pass, fail, or cancel
# test_date = datetime.date.today().isoformat()
# remark = "Import File Cancel: สามารถ export ไฟล์ไม่ถูกต้อง Cancel"

# tbn_test_date = "2024-10-12"
# test_status_by_tbn = "Pass"
# bam_version_testing = ""

# # Process the test case and automatically handle bug creation and running number
# process_test_case(test_case_id, main_issue_key, test_status, test_date, remark)
# update_issue_with_custom_fields(main_issue_key, tbn_test_date, test_status_by_tbn, bam_version_testing)

# # Optionally archive old results
# archive_old_results()
