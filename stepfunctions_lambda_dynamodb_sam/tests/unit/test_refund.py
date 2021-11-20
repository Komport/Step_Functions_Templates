from ... functions.refund import app


def test_refund():
    payload = {"TransactionId":"One","Type":"REFUND"}
    data = app.process_refund(payload, "")
    assert "TransactionId" in data
    assert "Type" in data
    assert "Timestamp" in data
    assert "Message" in data
