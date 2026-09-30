import json

import httpx
import pytest
import respx

from app.pihole.client import PiholeClient, PiholeError

BASE = "http://pihole.test"
LOGIN_OK = {"session": {"valid": True, "sid": "sid-1", "validity": 1800}}


def _client() -> PiholeClient:
    return PiholeClient(BASE, "secret")


@respx.mock(base_url=BASE)
def test_login_and_list_hosts(respx_mock):
    login = respx_mock.post("/api/auth").respond(json=LOGIN_OK)
    hosts = respx_mock.get("/api/config/dhcp/hosts").respond(
        json={"config": {"dhcp": {"hosts": ["00:00:5e:00:53:10,192.168.1.10,laptop-a,24h"]}}}
    )
    respx_mock.delete("/api/auth").respond(204)
    with _client() as client:
        assert client.list_hosts() == ["00:00:5e:00:53:10,192.168.1.10,laptop-a,24h"]
    assert json.loads(login.calls.last.request.content) == {"password": "secret"}
    assert hosts.calls.last.request.headers["X-FTL-SID"] == "sid-1"


@respx.mock(base_url=BASE)
def test_add_and_remove_host_url_encode_the_line(respx_mock):
    respx_mock.post("/api/auth").respond(json=LOGIN_OK)
    line = "00:00:5e:00:53:20,set:lanonly,192.168.1.120,plug-kitchen,24h"
    encoded = "00%3A00%3A5e%3A00%3A53%3A20%2Cset%3Alanonly%2C192.168.1.120%2Cplug-kitchen%2C24h"
    put = respx_mock.put(path__startswith="/api/config/dhcp/hosts/").respond(201)
    delete = respx_mock.delete(path__startswith="/api/config/dhcp/hosts/").respond(204)
    client = _client()
    client.add_host(line)
    client.remove_host(line)
    assert put.calls.last.request.url.raw_path.decode().endswith(encoded)
    assert delete.calls.last.request.url.raw_path.decode().endswith(encoded)


@respx.mock(base_url=BASE)
def test_reauth_on_401(respx_mock):
    respx_mock.post("/api/auth").mock(side_effect=[
        httpx.Response(200, json=LOGIN_OK),
        httpx.Response(200, json={"session": {"valid": True, "sid": "sid-2", "validity": 1800}}),
    ])
    route = respx_mock.get("/api/dhcp/leases").mock(side_effect=[
        httpx.Response(401, json={"error": {"key": "unauthorized"}}),
        httpx.Response(200, json={"leases": [{"ip": "192.168.1.243", "hwaddr": "00:00:5e:00:53:99"}]}),
    ])
    assert _client().list_leases() == [{"ip": "192.168.1.243", "hwaddr": "00:00:5e:00:53:99"}]
    assert route.calls.last.request.headers["X-FTL-SID"] == "sid-2"


@respx.mock(base_url=BASE)
def test_wrong_password_raises(respx_mock):
    respx_mock.post("/api/auth").respond(401, json={"session": {"valid": False}})
    with pytest.raises(PiholeError, match="login failed"):
        _client().list_hosts()


@respx.mock(base_url=BASE)
def test_unreachable_raises_pihole_error(respx_mock):
    respx_mock.post("/api/auth").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(PiholeError, match="unreachable"):
        _client().list_hosts()


@respx.mock(base_url=BASE)
def test_server_error_raises_with_status(respx_mock):
    respx_mock.post("/api/auth").respond(json=LOGIN_OK)
    respx_mock.delete("/api/dhcp/leases/192.168.1.243").respond(500, text="boom")
    with pytest.raises(PiholeError, match="HTTP 500"):
        _client().revoke_lease("192.168.1.243")


@respx.mock(base_url=BASE)
def test_close_logs_out(respx_mock):
    respx_mock.post("/api/auth").respond(json=LOGIN_OK)
    respx_mock.get("/api/config/dhcp/hosts").respond(json={"config": {"dhcp": {"hosts": []}}})
    logout = respx_mock.delete("/api/auth").respond(204)
    with _client() as client:
        client.list_hosts()
    assert logout.called
