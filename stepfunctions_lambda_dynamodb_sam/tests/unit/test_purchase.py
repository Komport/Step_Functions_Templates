from ... functions.purchase import app


def test_purchase():
    payload = {"TransactionId":"One","Type":"PURCHASE"}
    data = app.process_purchase(payload, "")
    assert "TransactionId" in data
    assert "Type" in data
    assert "Timestamp" in data
    assert "Message" in data
