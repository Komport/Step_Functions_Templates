from uuid import uuid4


def validate_all(message, context):

    response = {}
    transactionType = message['Type']
    transactionId = uuid4()
    response['TransactionId'] = str(transactionId)
    if transactionType in ['PURCHASE','REFUND']:
        response['Type'] = transactionType
    else:
        response['Type'] = 'ERROR'

    return response
