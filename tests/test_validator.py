from excel2api.schema import Field
from excel2api.validator import validate_and_convert


def test_required_field():
    field = Field(name="name", column="Name", required=True)
    record, errors = validate_and_convert({"Name": ""}, [field], 2)
    assert record == {}
    assert len(errors) == 1


def test_decimal_and_minimum():
    field = Field(name="amount", column="Amount", type="decimal", minimum=0)
    record, errors = validate_and_convert({"Amount": "125.50"}, [field], 2)
    assert record["amount"] == 125.5
    assert errors == []


def test_email_validation():
    field = Field(name="email", column="Email", type="email")
    _, errors = validate_and_convert({"Email": "bad-email"}, [field], 2)
    assert len(errors) == 1
