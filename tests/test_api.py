from unittest.mock import Mock, patch
from excel2api.api import APIClient


@patch("excel2api.api.requests.Session.request")
def test_create(mock_request):
    response = Mock(ok=True, status_code=201)
    mock_request.return_value = response

    client = APIClient("https://example.com/api/patients")
    result = client.execute("CREATE", {"name": "John"})

    assert result.status_code == 201
    mock_request.assert_called_once()

@patch("excel2api.api.requests.Session.request")
def test_delete_has_no_json_body(mock_request):
    response = Mock(ok=True, status_code=204)
    mock_request.return_value = response

    client = APIClient("https://example.com/api/patients")
    client.execute("DELETE", {"name": "ignored"}, 101)

    kwargs = mock_request.call_args.kwargs
    assert "json" not in kwargs


def test_retry_configuration():
    client = APIClient("https://example.com/api", retries=2)
    adapter = client.session.get_adapter("https://")
    assert adapter.max_retries.total == 2
    assert "POST" not in adapter.max_retries.allowed_methods


def test_retry_create_configuration():
    client = APIClient("https://example.com/api", retries=2, retry_create=True)
    adapter = client.session.get_adapter("https://")
    assert "POST" in adapter.max_retries.allowed_methods
