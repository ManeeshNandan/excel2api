from unittest.mock import Mock, patch
from excel2api.api import APIClient


@patch("excel2api.api.requests.Session.request")
def test_custom_endpoint_template(mock_request):
    response = Mock(ok=True, status_code=200)
    mock_request.return_value = response
    client = APIClient("https://example.com/api")
    client.execute("PATCH", {"name": "John"}, 101, endpoints={"PATCH": {"method": "POST", "path": "/patients/{id}/details"}})
    args, kwargs = mock_request.call_args
    assert args[0] == "POST"
    assert args[1] == "https://example.com/api/patients/101/details"


@patch("excel2api.api.requests.Session.request")
def test_endpoint_template_can_use_record_fields(mock_request):
    response = Mock(ok=True, status_code=200)
    mock_request.return_value = response
    client = APIClient("https://example.com/api")
    client.execute("CREATE", {"department": "cardiology"}, endpoints={"CREATE": {"method": "POST", "path": "/departments/{department}/patients"}})
    assert mock_request.call_args.args[1].endswith("/departments/cardiology/patients")
