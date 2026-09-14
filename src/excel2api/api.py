from dataclasses import dataclass
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class APIResult:
    row: int
    operation: str
    success: bool
    status_code: int | None = None
    response: Any = None
    error: str | None = None
    sheet: str | None = None


class APIClient:
    RETRY_STATUS_CODES = (408, 429, 500, 502, 503, 504)

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        timeout: int = 30,
        retries: int = 0,
        retry_create: bool = False,
        headers: dict[str, str] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        if headers:
            self.session.headers.update(headers)

        if retries > 0:
            allowed_methods = {"PUT", "PATCH", "DELETE", "GET", "HEAD", "OPTIONS"}
            if retry_create:
                allowed_methods.add("POST")

            retry = Retry(
                total=retries,
                connect=retries,
                read=retries,
                status=retries,
                backoff_factor=0.5,
                status_forcelist=self.RETRY_STATUS_CODES,
                allowed_methods=allowed_methods,
                respect_retry_after_header=True,
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

    def request(self, method: str, path: str = "", **kwargs):
        url = f"{self.base_url}/{path.lstrip('/')}" if path else self.base_url
        return self.session.request(method, url, timeout=self.timeout, **kwargs)

    def execute(self, operation: str, record: dict, identifier=None, endpoints: dict[str, object] | None = None):
        operation = operation.upper()
        endpoints = endpoints or {}
        default = {
            "CREATE": {"method": "POST", "path": ""},
            "UPDATE": {"method": "PUT", "path": "/{id}"},
            "PATCH": {"method": "PATCH", "path": "/{id}"},
            "DELETE": {"method": "DELETE", "path": "/{id}"},
        }
        if operation not in default and operation not in endpoints:
            raise ValueError(f"Unsupported operation: {operation}")
        spec = endpoints.get(operation, default.get(operation))
        if isinstance(spec, str):
            spec = {"method": default.get(operation, {"method": "POST"})["method"], "path": spec}
        spec = spec or {}
        method = str(spec.get("method", default.get(operation, {}).get("method", "POST"))).upper()
        path_template = str(spec.get("path", default.get(operation, {}).get("path", "")))
        if "{id}" in path_template or "{identifier}" in path_template:
            if identifier is None:
                raise ValueError(f"{operation} requires an identifier")
        values = dict(record)
        values.update({"id": identifier, "identifier": identifier})
        try:
            path = path_template.format(**values)
        except KeyError as exc:
            raise ValueError(f"Missing endpoint template field: {exc.args[0]}") from exc
        if method == "DELETE":
            return self.request(method, path)
        return self.request(method, path, json=record)
