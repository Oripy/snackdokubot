import os
import httplib2

from apiclient import discovery
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1wsLo_FCTngxTke6MsP2RDdDvgh7vZdS-1B49rGqjV50"
SHEET_NAME = 'Sheet1'
DATA_RANGE = f'{SHEET_NAME}!A1:I1'

try:
    secret_file = os.path.join(os.getcwd(), 'client_secret.json')
    credentials = service_account.Credentials.from_service_account_file(secret_file, scopes=SCOPES)
    service = discovery.build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()

except OSError as e:
    print(e)

def edit_line(message_id, date, title, author, edit_link, solve_link, grn, yello, red):
    message_ids = []
    try:
        message_ids = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f'{SHEET_NAME}!A1:A', majorDimension='COLUMNS').execute()['values'][0]
    except KeyError:
        pass

    index = len(message_ids)
    try:
        index = message_ids.index(str(message_id))
    except ValueError:
        pass

    values = [
        [str(message_id), date, title, author, edit_link, solve_link, grn, yello, red],
    ]

    data = { 'values': values }
    sheet.values().update(spreadsheetId=SPREADSHEET_ID,
                          body=data,
                          range=f'{SHEET_NAME}!A{index+1}:I{index+1}',
                          valueInputOption='USER_ENTERED').execute()

def get_line(message_id):
    message_ids = []
    try:
        message_ids = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f'{SHEET_NAME}!A1:A', majorDimension='COLUMNS').execute()['values'][0]
    except KeyError:
        pass

    if str(message_id) in message_ids:
        index = message_ids.index(str(message_id))
        return sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f'{SHEET_NAME}!B{index+1}:I{index+1}').execute()['values'][0]
    else:
        return None
