import os
import httplib2

import configparser

config = configparser.ConfigParser()
config.read('config.ini')

from apiclient import discovery
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = config['DEFAULT']["SHEET_ID"]
SHEET_NAME = ['Sheet1', 'ExtraBite']

try:
    secret_file = os.path.join(os.getcwd(), 'client_secret.json')
    credentials = service_account.Credentials.from_service_account_file(secret_file, scopes=SCOPES)
    service = discovery.build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()

except OSError as e:
    print(e)

def edit_line(message_id, date, title, author, edit_link, solve_link, reactions, sheet_number=0):
    message_ids = []
    try:
        message_ids = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f'{SHEET_NAME[sheet_number]}!A1:A', majorDimension='COLUMNS').execute()['values'][0]
    except KeyError:
        pass

    index = len(message_ids)
    try:
        index = message_ids.index(str(message_id))
    except ValueError:
        pass

    values = [
        [str(message_id), date, title, author, edit_link, solve_link, *reactions],
    ]

    data = { 'values': values }
    sheet.values().update(spreadsheetId=SPREADSHEET_ID,
                          body=data,
                          range=f'{SHEET_NAME[sheet_number]}!A{index+1}:{chr(65+len(values)-1)}{index+1}',
                          valueInputOption='USER_ENTERED').execute()

def get_line(message_id, sheet_number=0):
    message_ids = []
    try:
        message_ids = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f'{SHEET_NAME[sheet_number]}!A1:A', majorDimension='COLUMNS').execute()['values'][0]
    except KeyError:
        pass

    if str(message_id) in message_ids:
        index = message_ids.index(str(message_id))
        return sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f'{SHEET_NAME[sheet_number]}!B{index+1}:F{index+1}').execute()['values'][0]
    else:
        return None

def del_line(message_id, sheet_number=0):
    message_ids = []
    try:
        message_ids = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f'{SHEET_NAME[sheet_number]}!A1:A', majorDimension='COLUMNS').execute()['values'][0]
    except KeyError:
        pass

    if str(message_id) in message_ids:
        index = message_ids.index(str(message_id))
        request_body = {
            "requests": [
                {
                    'deleteDimension': {
                        'range': {
                            'sheetId': 0,
                            'dimension': 'ROWS',
                            'startIndex': index,
                            'endIndex': index+1,
                        }
                    }
                },
            ]
        }
        sheet.batchUpdate(spreadsheetId=SPREADSHEET_ID,
                          body=request_body).execute()

if __name__ == '__main__':
    SPREADSHEET_ID = "1WN7qMfiCbdFmtrlhdsCTDqBk8yFDAreCvpt9347zDg0"
    del_line(10)