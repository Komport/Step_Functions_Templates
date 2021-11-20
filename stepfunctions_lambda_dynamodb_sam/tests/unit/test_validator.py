from ... functions.validator import app


def test_validator():
    
    input_data = { "transactions": [
            {"Type": "PURCHASE"},
            {"Type": "REFUND"},
            {"Type": "PURCHASE"},
            {"Type": "REFUND"},
            {"Type": "PURCHASE"},
            {"Type": "FORERROR"},
            {"Type": "PURCHASE"},
            {"Type": "RAISEERROR"},
            {"Type": "PURCHASE"},
            {"Type": "REFUND"},
            {"Type": "REFUND"},
            {"Type": "PURCHASE"}
            ]
            }
    for tran in input_data['transactions']:
        data = app.validate_all(tran, "")

        assert "TransactionId" in data
        assert "Type" in data