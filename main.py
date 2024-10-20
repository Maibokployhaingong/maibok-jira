import os
import sys
import json
import time
import pandas as pd
from PyQt5 import QtWidgets
from requests.auth import HTTPBasicAuth
import requests
import config  # Import your config file for AUTH and other settings
import urllib
from processor.execute_card import process_test_case  # Import the execution function
from processor.create_card import process_sheet  # Import the create_card function
from processor.delete_card import delete_single_issue, delete_issues_by_range

# Global credentials variables
username = "jirawat.m@bam.co.th"
api_token = os.getenv('ATLASSIAN_API_TOKEN')
ENCODED_CREDENTIALS = ""
AUTH = None

# Define headers for Jira requests
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Basic {config.ENCODED_CREDENTIALS}'  # Use the dynamically set credentials
}

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

# Function to check if a Jira issue exists for the test case ID
def jira_issue_exists(test_case_id):
    # Define the JQL query
    jql_query = f'project = BTV AND summary ~ "{test_case_id}"'
    encoded_jql_query = urllib.parse.quote(jql_query)

    # Use the correct search URL
    url = f"{config.JIRA_URL_BASE}/search?jql={encoded_jql_query}"

    # Make the request
    response = requests.get(url, headers={'Accept': 'application/json'}, auth=config.AUTH)

    # Check the response
    if response.status_code == 200:
        issues = response.json().get('issues', [])
        if issues:
            return issues[0]['key']  # Return the issue key if it exists
    else:
        print(f"Failed to fetch issue details: {response.status_code}, {response.text}")
    
    return None  # Return None if no issue exists

# Function to create new Jira issues
def create_jira_issue(test_case_id, group, module, running_number):
    # Extract relevant information and sanitize
    first_row = group.iloc[0]
    
    test_case_description = sanitize_text(first_row.get('Test Case Description', 'No description available'))
    group_ball = sanitize_text(first_row.get('Group', 'Unknown'))

    test_status_by_tbn = sanitize_text(first_row.get('Test Script Status', 'Unknown'))
    tbn_test_date = sanitize_text(first_row.get('Test Date', 'Unknown'))

    # Generate the table for test script details in ADF format
    test_script_table_adf = create_test_script_table(group)

    # Format the running number
    running_str = f"{module}{str(running_number).zfill(3)}"

    # Jira summary
    summary = f"[{running_str}] {group_ball} - {test_case_id} - {test_case_description}"

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

    # Make the POST request to create the issue
    response = requests.post(f"{config.JIRA_URL_BASE}/issue", data=payload, headers=headers, auth=config.AUTH)
    if response.status_code == 201:
        print(f"Successfully created issue for {test_case_id}")
        return True
    else:
        print(f"Failed to create issue for {test_case_id}: {response.status_code}, {response.text}")
        return False

# Function to update existing Jira issue descriptions
def update_issue_description(test_case_id, group):
    issue_key = jira_issue_exists(test_case_id)
    if issue_key:
        # Extract relevant information and sanitize
        first_row = group.iloc[0]
        bam_test_script_status = sanitize_text(first_row.get('BAM Test Script Status', 'N/A'))

        # Generate the table for test script details in ADF format
        test_script_table_adf = create_test_script_table(group)

        # Create the updated description payload
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
                                        {
                                            "type": "text",
                                            "text": f"BAM Test Script Status: {bam_test_script_status}\n\nTest Script Details:"
                                        }
                                    ]
                                },
                                test_script_table_adf
                            ]
                        }
                    }
                ]
            }
        })

        # Send the update request to Jira
        url = f"{config.JIRA_URL_BASE}/issue/{issue_key}"
        response = requests.put(url, data=payload, headers=headers, auth=config.AUTH)
        if response.status_code == 204:
            print(f"Successfully updated description for {test_case_id}.")
            return True
        else:
            print(f"Failed to update description for {test_case_id}: {response.status_code}, {response.text}")
            return False
    else:
        print(f"Issue not found for Test Case ID: {test_case_id}")
        return False

# Function to get the last running number from existing Jira tasks
def get_last_running_number(module):
    jql_query = f'project = BTV AND issuetype = Task AND summary ~ "[{module}*" ORDER BY created DESC'
    encoded_jql_query = urllib.parse.quote(jql_query)

    url = f"{config.JIRA_URL_BASE}/search?jql={encoded_jql_query}&maxResults=1000"

    try:
        response = requests.get(url, headers={'Accept': 'application/json'}, auth=config.AUTH)

        if response.status_code == 200:
            issues = response.json().get('issues', [])

            if not issues:
                print(f"No issues found with {module} running numbers. Defaulting to 001.")
                return 1

            highest_running_number = 0

            for issue in issues:
                summary = issue['fields']['summary']

                try:
                    running_number_str = summary.split(f"[{module}")[1].split("]")[0].strip()
                    running_number = int(running_number_str)
                    if running_number > highest_running_number:
                        highest_running_number = running_number

                except (IndexError, ValueError) as e:
                    continue  # Skip if parsing fails

            next_running_number = highest_running_number + 1
            return next_running_number
        else:
            print(f"Failed to fetch issues: {response.status_code}, {response.text}")
            return 1  # Default to 1 if there's an error
    except Exception as e:
        print(f"Error during Jira request: {e}", flush=True)
        return 1  # Default to 1 if there's an error

# Function to process one sheet at a time for card creation
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
        
        # Create new Jira issue
        success = create_jira_issue(test_case_id, group, module, running_number)
        if success:
            running_number += 1  # Increment running number for the next issue

# Function to process one sheet at a time for updating existing cards
def process_sheet_with_updates(test_case_file, sheet_name):
    # Load the sheet into a DataFrame
    df = pd.read_excel(test_case_file, sheet_name=sheet_name)

    # Group by Test Case ID
    grouped_df = df.groupby('Test Case ID')

    # Loop through each unique test case
    for test_case_id, group in grouped_df:
        # Update Jira issue description
        update_issue_description(test_case_id, group)

# Function to delete a Jira issue by issue ID
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

# PyQt5 GUI setup
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Jira Automation Tool")
        central_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        self.create_button = QtWidgets.QPushButton("Start Card Creation")
        self.create_button.clicked.connect(self.open_create_window)
        layout.addWidget(self.create_button)

        self.update_button = QtWidgets.QPushButton("Update Existing Cards")
        self.update_button.clicked.connect(self.open_update_window)
        layout.addWidget(self.update_button)

        self.execute_button = QtWidgets.QPushButton("Start Execution Process")
        self.execute_button.clicked.connect(self.open_execute_window)
        layout.addWidget(self.execute_button)

        # Button for deleting a single issue
        self.delete_single_button = QtWidgets.QPushButton("Delete Single Jira Issue")
        self.delete_single_button.clicked.connect(self.open_delete_single_window)
        layout.addWidget(self.delete_single_button)

        # Button for deleting issues by range
        self.delete_range_button = QtWidgets.QPushButton("Delete Jira Issues by Range")
        self.delete_range_button.clicked.connect(self.open_delete_range_window)
        layout.addWidget(self.delete_range_button)

        # Button for closing the application
        self.close_button = QtWidgets.QPushButton("Exit")
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def open_create_window(self):
        self.create_window = CreateWindow(self)
        self.create_window.show()
        self.hide()

    def open_update_window(self):
        self.update_window = UpdateWindow(self)
        self.update_window.show()
        self.hide()

    def open_execute_window(self):
        self.execute_window = ExecuteWindow(self)
        self.execute_window.show()
        self.hide()

     # Open the window to delete a single issue
    def open_delete_single_window(self):
        self.delete_single_window = DeleteSingleIssueWindow(self)
        self.delete_single_window.show()
        self.hide()

    # Open the window to delete issues by range
    def open_delete_range_window(self):
        self.delete_range_window = DeleteIssuesRangeWindow(self)
        self.delete_range_window.show()
        self.hide()

class CreateWindow(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Jira Card Creation")

        layout = QtWidgets.QVBoxLayout()
        self.file_path_label = QtWidgets.QLabel("Test Case File Path:")
        self.file_path_input = QtWidgets.QLineEdit()
        layout.addWidget(self.file_path_label)
        layout.addWidget(self.file_path_input)

        self.sheet_name_label = QtWidgets.QLabel("Sheet Name:")
        self.sheet_name_input = QtWidgets.QLineEdit()
        layout.addWidget(self.sheet_name_label)
        layout.addWidget(self.sheet_name_input)

        self.module_label = QtWidgets.QLabel("Module Name (e.g., NPL):")
        self.module_input = QtWidgets.QLineEdit()
        layout.addWidget(self.module_label)
        layout.addWidget(self.module_input)

        self.start_button = QtWidgets.QPushButton("Create Cards")
        self.start_button.clicked.connect(self.start_card_creation)
        layout.addWidget(self.start_button)

        self.back_button = QtWidgets.QPushButton("Back")
        self.back_button.clicked.connect(self.go_back)
        layout.addWidget(self.back_button)

        self.setLayout(layout)

    def start_card_creation(self):
        test_case_file = self.file_path_input.text()
        sheet_name = self.sheet_name_input.text()
        module = self.module_input.text()

        try:
            process_sheet(test_case_file, sheet_name, module)
            QtWidgets.QMessageBox.information(self, "Success", f"Card Creation Completed.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def go_back(self):
        self.close()
        self.parent.show()

class UpdateWindow(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Update Existing Jira Cards")

        layout = QtWidgets.QVBoxLayout()
        self.file_path_label = QtWidgets.QLabel("Test Case File Path:")
        self.file_path_input = QtWidgets.QLineEdit()
        layout.addWidget(self.file_path_label)
        layout.addWidget(self.file_path_input)

        self.sheet_name_label = QtWidgets.QLabel("Sheet Name:")
        self.sheet_name_input = QtWidgets.QLineEdit()
        layout.addWidget(self.sheet_name_label)
        layout.addWidget(self.sheet_name_input)

        self.start_button = QtWidgets.QPushButton("Update Cards")
        self.start_button.clicked.connect(self.start_card_update)
        layout.addWidget(self.start_button)

        self.back_button = QtWidgets.QPushButton("Back")
        self.back_button.clicked.connect(self.go_back)
        layout.addWidget(self.back_button)

        self.setLayout(layout)

    def start_card_update(self):
        test_case_file = self.file_path_input.text()
        sheet_name = self.sheet_name_input.text()

        try:
            process_sheet_with_updates(test_case_file, sheet_name)
            QtWidgets.QMessageBox.information(self, "Success", f"Cards Updated Successfully.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def go_back(self):
        self.close()
        self.parent.show()

class ExecuteWindow(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Test Case Execution")

        layout = QtWidgets.QVBoxLayout()

        self.test_case_id_label = QtWidgets.QLabel("Test Case ID:")
        self.test_case_id_input = QtWidgets.QLineEdit()
        layout.addWidget(self.test_case_id_label)
        layout.addWidget(self.test_case_id_input)

        self.issue_key_label = QtWidgets.QLabel("Main Issue Key:")
        self.issue_key_input = QtWidgets.QLineEdit()
        layout.addWidget(self.issue_key_label)
        layout.addWidget(self.issue_key_input)

        self.test_status_label = QtWidgets.QLabel("Test Status (pass/fail/cancel):")
        self.test_status_input = QtWidgets.QLineEdit()
        layout.addWidget(self.test_status_label)
        layout.addWidget(self.test_status_input)

        self.test_date_label = QtWidgets.QLabel("Test Date (YYYY-MM-DD):")
        self.test_date_input = QtWidgets.QLineEdit()
        layout.addWidget(self.test_date_label)
        layout.addWidget(self.test_date_input)

        self.remark_label = QtWidgets.QLabel("Remark:")
        self.remark_input = QtWidgets.QLineEdit()
        layout.addWidget(self.remark_label)
        layout.addWidget(self.remark_input)

        self.start_button = QtWidgets.QPushButton("Execute Test Case")
        self.start_button.clicked.connect(self.start_execution)
        layout.addWidget(self.start_button)

        self.back_button = QtWidgets.QPushButton("Back")
        self.back_button.clicked.connect(self.go_back)
        layout.addWidget(self.back_button)

        self.setLayout(layout)

    def start_execution(self):
        test_case_id = self.test_case_id_input.text()
        main_issue_key = self.issue_key_input.text()
        test_status = self.test_status_input.text()
        test_date = self.test_date_input.text()
        remark = self.remark_input.text()

        try:
            result = process_test_case(test_case_id, main_issue_key, test_status, test_date, remark)  # Use your existing execution function
            QtWidgets.QMessageBox.information(self, "Success", f"Execution Completed: {result}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def go_back(self):
        self.close()
        self.parent.show()

    # Open the window to delete a single issue
    def open_delete_single_window(self):
        self.delete_single_window = DeleteSingleIssueWindow(self)
        self.delete_single_window.show()
        self.hide()

    # Open the window to delete issues by range
    def open_delete_range_window(self):
        self.delete_range_window = DeleteIssuesRangeWindow(self)
        self.delete_range_window.show()
        self.hide()

# Window to delete a single Jira issue by Issue ID
class DeleteSingleIssueWindow(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Delete Single Jira Issue")

        layout = QtWidgets.QVBoxLayout()

        # Input field for Issue ID
        self.issue_id_label = QtWidgets.QLabel("Issue ID:")
        self.issue_id_input = QtWidgets.QLineEdit()
        layout.addWidget(self.issue_id_label)
        layout.addWidget(self.issue_id_input)

        # Delete button
        self.delete_button = QtWidgets.QPushButton("Delete Issue")
        self.delete_button.clicked.connect(self.delete_issue)
        layout.addWidget(self.delete_button)

        # Back button
        self.back_button = QtWidgets.QPushButton("Back")
        self.back_button.clicked.connect(self.go_back)
        layout.addWidget(self.back_button)

        self.setLayout(layout)

    def delete_issue(self):
        issue_id = self.issue_id_input.text()

        try:
            delete_jira_issue(issue_id)
            QtWidgets.QMessageBox.information(self, "Success", f"Issue {issue_id} deleted successfully.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def go_back(self):
        self.close()
        self.parent.show()

# Window to delete Jira issues by a range of Issue IDs
class DeleteIssuesRangeWindow(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Delete Jira Issues by Range")

        layout = QtWidgets.QVBoxLayout()

        # Input field for Issue Prefix
        self.prefix_label = QtWidgets.QLabel("Issue Prefix (e.g., NPL):")
        self.prefix_input = QtWidgets.QLineEdit()
        layout.addWidget(self.prefix_label)
        layout.addWidget(self.prefix_input)

        # Input field for Start ID
        self.start_id_label = QtWidgets.QLabel("Start ID:")
        self.start_id_input = QtWidgets.QLineEdit()
        layout.addWidget(self.start_id_label)
        layout.addWidget(self.start_id_input)

        # Input field for End ID
        self.end_id_label = QtWidgets.QLabel("End ID:")
        self.end_id_input = QtWidgets.QLineEdit()
        layout.addWidget(self.end_id_label)
        layout.addWidget(self.end_id_input)

        # Delete button
        self.delete_button = QtWidgets.QPushButton("Delete Issues")
        self.delete_button.clicked.connect(self.delete_issues)
        layout.addWidget(self.delete_button)

        # Back button
        self.back_button = QtWidgets.QPushButton("Back")
        self.back_button.clicked.connect(self.go_back)
        layout.addWidget(self.back_button)

        self.setLayout(layout)

    def delete_issues(self):
        issue_prefix = self.prefix_input.text()
        start_id = int(self.start_id_input.text())
        end_id = int(self.end_id_input.text())

        try:
            delete_issues_by_range(issue_prefix, start_id, end_id)
            QtWidgets.QMessageBox.information(self, "Success", f"Issues {issue_prefix}-{start_id} to {issue_prefix}-{end_id} deleted successfully.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def go_back(self):
        self.close()
        self.parent.show()



# Bypass credentials input (if needed)
def bypass_credentials():
    global username, api_token
    config.set_credentials(username, api_token)

# Main execution
if __name__ == "__main__":
    bypass_credentials()  # Bypass username and API token input

    app = QtWidgets.QApplication(sys.argv)

    # Start with the main window
    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec_())
