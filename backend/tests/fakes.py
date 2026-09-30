from typing import Self

from app.pihole.client import PiholeError


class FakePihole:
    def __init__(self, hosts: list[str] | None = None, *, fail: bool = False) -> None:
        self.hosts = list(hosts or [])
        self.fail = fail
        self.writes: list[tuple[str, str]] = []

    def __enter__(self) -> Self:
        if self.fail:
            raise PiholeError("Pi-hole unreachable: connection refused")
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def list_hosts(self) -> list[str]:
        if self.fail:
            raise PiholeError("Pi-hole unreachable: connection refused")
        return list(self.hosts)

    def add_host(self, line: str) -> None:
        self.writes.append(("add", line))
        self.hosts.append(line)

    def remove_host(self, line: str) -> None:
        self.writes.append(("remove", line))
        self.hosts.remove(line)

    def close(self) -> None:
        return None
