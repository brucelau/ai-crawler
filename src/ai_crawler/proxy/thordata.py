from __future__ import annotations

import time
import uuid
from typing import Iterator


class ThorDataSession:
    def __init__(
        self,
        username: str,
        password: str,
        proxy_host: str = "pr.thordata.net",
        proxy_port: int = 9999,
        country: str = "us",
        state: str | None = None,
        city: str | None = None,
        sticky: bool = True,
        session_duration: int = 180,
    ):
        self.base_username = username
        self.password = password
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.country = country
        self.state = state
        self.city = city
        self.sticky = sticky
        self.session_duration = session_duration
        self._session_id = self._generate_session_id()
        self._session_start = time.time()

    def _generate_session_id(self) -> str:
        return f"sessid-{uuid.uuid4().hex[:10]}"

    def _build_username(self) -> str:
        parts = [f"td-customer-{self.base_username}"]
        if self.sticky:
            if self.country:
                parts.append(f"country-{self.country}")
            if self.state:
                parts.append(f"state-{self.state}")
            if self.city:
                parts.append(f"city-{self.city}")
            parts.append(self._session_id)
            parts.append(f"sesstime-{self.session_duration}")
        return "-".join(parts)

    def proxy_url(self, scheme: str = "http") -> str:
        username = self._build_username()
        auth = f"{username}:{self.password}"
        return f"{scheme}://{auth}@{self.proxy_host}:{self.proxy_port}"

    def rotate(self) -> None:
        self._session_id = self._generate_session_id()
        self._session_start = time.time()
        self._current_ip = None

    def should_rotate(self) -> bool:
        if not self.sticky:
            return True
        return (time.time() - self._session_start) > (self.session_duration * 60)


class ThorDataPool:
    def __init__(
        self,
        username: str,
        password: str,
        proxy_host: str = "pr.thordata.net",
        country: str = "us",
        state: str | None = None,
        city: str | None = None,
        pool_size: int = 5,
        sticky: bool = True,
        session_duration: int = 180,
    ):
        self.username = username
        self.password = password
        self.proxy_host = proxy_host
        self.country = country
        self.state = state
        self.city = city
        self.pool_size = pool_size
        self.sticky = sticky
        self.session_duration = session_duration
        self._sessions: list[ThorDataSession] = []
        self._active_index = 0
        self._enabled = bool(username and password)
        if self._enabled:
            self._build_pool()

    def _build_pool(self) -> None:
        for _ in range(self.pool_size):
            session = ThorDataSession(
                username=self.username,
                password=self.password,
                proxy_host=self.proxy_host,
                country=self.country,
                state=self.state,
                city=self.city,
                sticky=self.sticky,
                session_duration=self.session_duration,
            )
            self._sessions.append(session)

    def __len__(self) -> int:
        return len(self._sessions)

    def __iter__(self) -> Iterator[ThorDataSession]:
        return iter(self._sessions)

    def get_session(self) -> ThorDataSession:
        if not self._sessions:
            raise RuntimeError("No proxy sessions available")
        return self._sessions[self._active_index]

    def rotate(self) -> None:
        self._active_index = (self._active_index + 1) % len(self._sessions)
        self._sessions[self._active_index].rotate()


class ThorDataManager:
    def __init__(
        self,
        username: str,
        password: str,
        proxy_host: str = "pr.thordata.net",
        country: str = "us",
        state: str | None = None,
        city: str | None = None,
        pool_size: int = 5,
        sticky: bool = True,
        session_duration: int = 180,
    ):
        self.username = username
        self.password = password
        self.country = country
        self.state = state
        self.city = city
        self.pool_size = pool_size
        self.sticky = sticky
        self.session_duration = session_duration
        self._pool = ThorDataPool(
            username=username,
            password=password,
            proxy_host=proxy_host,
            country=country,
            state=state,
            city=city,
            pool_size=pool_size,
            sticky=sticky,
            session_duration=session_duration,
        )
        self._enabled = bool(username and password)

    def get_proxy_url(self) -> str | None:
        if not self._enabled:
            return None
        return self._pool.get_session().proxy_url()

    def rotate(self) -> None:
        self._pool.rotate()

    @property
    def enabled(self) -> bool:
        return self._enabled
