from typing import Any, Self
from urllib.parse import quote

import httpx


class PiholeError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status

    @property
    def rejected(self) -> bool:
        return self.status is not None and 400 <= self.status < 500


class PiholeClient:
    def __init__(self, base_url: str, password: str, *, http: httpx.Client | None = None) -> None:
        self._http = http or httpx.Client(base_url=base_url, timeout=10.0)
        self._password = password
        self._sid: str | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _login(self) -> None:
        try:
            response = self._http.post("/api/auth", json={"password": self._password})
        except httpx.HTTPError as exc:
            raise PiholeError(f"Pi-hole unreachable: {exc}") from exc
        try:
            session = response.json().get("session", {})
        except ValueError:
            session = {}
        if response.status_code != 200 or not session.get("valid"):
            raise PiholeError(f"Pi-hole login failed: HTTP {response.status_code}")
        self._sid = session["sid"]

    def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._http.request(method, path, headers={"X-FTL-SID": self._sid or ""}, **kwargs)
        except httpx.HTTPError as exc:
            raise PiholeError(f"Pi-hole unreachable: {exc}") from exc

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if self._sid is None:
            self._login()
        response = self._send(method, path, **kwargs)
        if response.status_code == 401:
            self._login()
            response = self._send(method, path, **kwargs)
        if response.status_code >= 400:
            raise PiholeError(
                f"{method} {path} failed: HTTP {response.status_code} {response.text[:200]}", status=response.status_code
            )
        return response

    def list_hosts(self) -> list[str]:
        return self._request("GET", "/api/config/dhcp/hosts").json()["config"]["dhcp"]["hosts"]

    def add_host(self, line: str) -> None:
        self._request("PUT", "/api/config/dhcp/hosts/" + quote(line, safe=""))

    def remove_host(self, line: str) -> None:
        self._request("DELETE", "/api/config/dhcp/hosts/" + quote(line, safe=""))

    def list_leases(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/dhcp/leases").json()["leases"]

    def list_queries(
        self, client_ip: str, since: int, until: int, length: int = 5000, disk: bool = False
    ) -> tuple[list[dict[str, Any]], int]:
        params: dict[str, Any] = {"client_ip": client_ip, "from": since, "until": until, "length": length}
        if disk:
            params["disk"] = "true"
        body = self._request("GET", "/api/queries", params=params).json()
        queries = body["queries"]
        return queries, int(body.get("recordsFiltered", len(queries)))

    def revoke_lease(self, ip: str) -> None:
        self._request("DELETE", f"/api/dhcp/leases/{ip}")

    def close(self) -> None:
        if self._sid is not None:
            try:
                self._http.delete("/api/auth", headers={"X-FTL-SID": self._sid})
            except httpx.HTTPError:
                pass
            self._sid = None
        self._http.close()
