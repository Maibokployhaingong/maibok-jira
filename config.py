import base64
from requests.auth import HTTPBasicAuth

# Paths to folders (you may need to adjust these based on your file structure)
TEMP_FOLDER = r".\cfg\Temp\Screenshots\2024-10"
TEST_RESULT_FOLDER = r".\cfg\Test_result"
BUG_FOLDER_BASE = r".\cfg\Bugs"
CANCEL_FOLDER_BASE = r".\cfg\Canceled"
ARCHIVE_FOLDER = r".\cfg\Archive"

# Global credentials variables
username = "jirawat.m@bam.co.th"
api_token = "ATATT3xFfGF0qSn1jb4ql4m8vS4pBurktW6IbLcSCwfqCOD0feW5EaTbOSZ5uPm4I9lZ-H8s6MJp6dmGoO2K-epMQrQdh3eA6APwLiWgbCc43KzvwUwgzTnpprGo-AlpROPlvmm57TNMpxCNiDNO3ledwmWJuhT8VrlGGB8Hqi75bWn3aOaib7Q=C9E02C3D"
ENCODED_CREDENTIALS = ""
AUTH = None

# Function to set credentials from the main program
def set_credentials(user, token):
    global username, api_token, ENCODED_CREDENTIALS, AUTH
    username = user
    api_token = token
    credentials = f"{username}:{api_token}"
    ENCODED_CREDENTIALS = base64.b64encode(credentials.encode()).decode("utf-8")
    AUTH = HTTPBasicAuth(username, api_token)

# Jira API configuration
JIRA_API_BASE = "https://bam-pmo.atlassian.net/rest/api/3/issue"
JIRA_URL_BASE = "https://bam-pmo.atlassian.net/rest/api/3"

# Custom field IDs
REMARK_FIELD_ID = "customfield_10058"
TBN_TEST_DATE_FIELD_ID = "customfield_10056"
TEST_STATUS_BY_TBN_FIELD_ID = "customfield_10057"
BAM_VERSION_TESTING_FIELD_ID = "customfield_10062"

# Slack webhook for notifications (optional)
SLACK_WEBHOOK_URL = ""

# Define headers for Jira requests
HEADERS = {
    "X-Atlassian-Token": "no-check",
    "Accept": "application/json",
}
