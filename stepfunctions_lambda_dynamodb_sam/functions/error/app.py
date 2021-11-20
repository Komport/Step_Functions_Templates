from datetime import datetime

def process_error(message, context):

    response = {}
    response['TransactionId'] = message['TransactionId']
    response['Type'] = message['Type']
    response['Timestamp'] = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    response['Message'] = 'Hello from lambda land inside the ProcessError function'

    return response
