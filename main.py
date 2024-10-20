# Global credentials variables
username = "jirawat.m@bam.co.th"
api_token = "ATATT3xFfGF0qSn1jb4ql4m8vS4pBurktW6IbLcSCwfqCOD0feW5EaTbOSZ5uPm4I9lZ-H8s6MJp6dmGoO2K-epMQrQdh3eA6APwLiWgbCc43KzvwUwgzTnpprGo-AlpROPlvmm57TNMpxCNiDNO3ledwmWJuhT8VrlGGB8Hqi75bWn3aOaib7Q=C9E02C3D"
ENCODED_CREDENTIALS = ""
AUTH = None

import sys
import base64
from PyQt5 import QtWidgets
from requests.auth import HTTPBasicAuth
import config  # Import config for Jira credentials
from processor.execute_card import process_test_case  # Import the execution function
from processor.create_card import process_sheet  # Import the create_card function

# print()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Jira Automation Tool")

        # Set up the central widget and layout
        central_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        # Button for "Card Creation"
        self.create_button = QtWidgets.QPushButton("Start Card Creation")
        self.create_button.clicked.connect(self.open_create_window)
        layout.addWidget(self.create_button)

        # Button for "Execution"
        self.execute_button = QtWidgets.QPushButton("Start Execution Process")
        self.execute_button.clicked.connect(self.open_execute_window)
        layout.addWidget(self.execute_button)

        # Set layout to central widget
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def open_create_window(self):
        self.create_window = CreateWindow(self)  # Pass the reference to the main window
        self.create_window.show()
        self.hide()

    def open_execute_window(self):
        self.execute_window = ExecuteWindow(self)  # Pass the reference to the main window
        self.execute_window.show()
        self.hide()

class CreateWindow(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Jira Card Creation")

        layout = QtWidgets.QVBoxLayout()

        # Input fields
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

        # Button to start card creation
        self.start_button = QtWidgets.QPushButton("Create Cards")
        self.start_button.clicked.connect(self.start_card_creation)
        layout.addWidget(self.start_button)

        # Button to go back to the main window
        self.back_button = QtWidgets.QPushButton("Back")
        self.back_button.clicked.connect(self.go_back)
        layout.addWidget(self.back_button)

        self.setLayout(layout)

    def start_card_creation(self):
        test_case_file = self.file_path_input.text()
        sheet_name = self.sheet_name_input.text()
        module = self.module_input.text()

        try:
            result = process_sheet(test_case_file, sheet_name, module)  # Use process_sheet
            QtWidgets.QMessageBox.information(self, "Success", f"Card Creation Completed: {result}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def go_back(self):
        self.close()
        self.parent.show()  # Show the main window again

class ExecuteWindow(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Test Case Execution")

        layout = QtWidgets.QVBoxLayout()

        # Input fields for test case execution
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

        # Button to start test case execution
        self.start_button = QtWidgets.QPushButton("Execute Test Case")
        self.start_button.clicked.connect(self.start_execution)
        layout.addWidget(self.start_button)

        # Button to go back to the main window
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
            result = process_test_case(test_case_id, main_issue_key, test_status, test_date, remark)  # Use process_test_case
            QtWidgets.QMessageBox.information(self, "Success", f"Execution Completed: {result}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def go_back(self):
        self.close()
        self.parent.show()  # Show the main window again

# Bypass credentials input
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
