"""Функция запроса `gitlab_adapter.request` и признак `forge.ci_by_pipeline` на подменённых записи и транспорте."""
import http.client
import io
import json

import pytest

from orchestrator import forge, gitlab_adapter, targets

TOKEN = "glpat-unit-test-token"


def entry(url: str, kind: str = "gitlab") -> dict:
    return {"forge": kind, "url": url, "base": "main", "token_slot": "slot",
            "no_paths": [], "project_skills": [], "merge_gate": "operator"}


@pytest.fixture
def calls(monkeypatch):
    sent = []
    records = {"gl": entry("https://localhost/grp/proj"),
               "scp": entry("git@localhost:grp/sub/proj.git"),
               "gh": entry("https://localhost/acme/proj", "github")}

    def target(name):
        if name not in records:
            raise targets.TargetsError(f"target '{name}' не объявлен")
        return records[name]

    def transport(method, url, headers, body, timeout):
        sent.append((method, url))
        return 200, {}, b'{"username": "robot"}'

    monkeypatch.setattr(targets, "target", target)
    monkeypatch.setattr("orchestrator.gitcmd.hosting_token", lambda name, e: (TOKEN, None))
    monkeypatch.setattr(gitlab_adapter, "transport", transport)
    return sent


def test_foreign_project_refused_before_transport(calls):
    """Разрешённая пара с `:id` чужого проекта — отказ без вызова транспорта.

    Ловит мутацию: шаблон `:id` таблицы пар принимает любой сегмент
    (`[^/]+`) вместо проекта записи — чтение чужого проекта уходит в
    транспорт.
    """
    reply = gitlab_adapter.request("gl", "GET", "/projects/other%2Fproj/pipelines?sha=abc")
    assert calls == []
    assert "other%2Fproj" in reply.reason


def test_scp_url_addresses_https_server(calls):
    """Адрес записи вида `git@<хост>:<путь>.git` — сервер по HTTPS на том же хосте, путь проекта с `%2F`.

    Ловит мутацию: `.git` не отрезается от пути проекта или `/`
    вложенной группы не кодируется — адрес запроса не тот.
    """
    reply = gitlab_adapter.request("scp", "GET", "/projects/grp%2Fsub%2Fproj")
    assert reply.reason == ""
    assert calls == [("GET", "https://localhost/api/v4/projects/grp%2Fsub%2Fproj")]


@pytest.mark.parametrize("name, expected", [("gl", True), ("gh", False), ("absent", False)])
def test_ci_by_pipeline_follows_registry(calls, name, expected):
    """Итог CI через конвейеры — только у хостинга, чья реализация это объявляет.

    Ловит мутацию: `ci_by_pipeline` отвечает `True` для любой
    разрешённой записи — GitHub-проект уходит мимо check runs `ci`;
    либо необъявленный проект роняет `TargetsError`.
    """
    assert forge.ci_by_pipeline(name) is expected


@pytest.fixture
def server(monkeypatch):
    """Подменённый транспорт с ответом по адресу: `routes` — функция
    (метод, адрес) -> (код, заголовки, тело); `sent` — отправленные запросы."""
    state = {"sent": [], "routes": None}
    records = {"gl": entry("https://localhost/grp/proj"),
               "plain": entry("http://localhost/grp/proj")}
    monkeypatch.setattr(targets, "target", lambda name: records[name])
    monkeypatch.setattr("orchestrator.gitcmd.hosting_token", lambda name, e: (TOKEN, None))

    def transport(method, url, headers, body, timeout):
        state["sent"].append((method, url, dict(headers)))
        return state["routes"](method, url)

    monkeypatch.setattr(gitlab_adapter, "transport", transport)
    return state


def test_redirect_reply_is_named_refusal(server):
    """Ответ 302 на чужой хост — причина «перенаправление запрещено: 302», второго запроса нет.

    Ловит мутацию: `request` считает 3xx успехом, повторяет его как
    429/5xx или уходит по адресу из `Location` — транспорт вызван больше
    одного раза либо причина пуста.
    """
    server["routes"] = lambda method, url: (
        302, {"Location": "https://127.0.0.1/api/v4/user"}, b"")
    reply = gitlab_adapter.request("gl", "GET", "/user")
    assert reply.reason.startswith("перенаправление запрещено: 302")
    assert [url for _m, url, _h in server["sent"]] == ["https://localhost/api/v4/user"]
    assert TOKEN not in reply.reason


class _FakeSocket:
    def __init__(self, raw: bytes):
        self.raw = raw

    def makefile(self, *args, **kwargs):
        return io.BytesIO(self.raw)


class _FakeConnection(http.client.HTTPConnection):
    """Подмена `http.client.HTTPSConnection` без сети (`request`/
    `getresponse` не открывают сокет): исходный хост отвечает 302 на другой
    хост, любой другой хост — 200."""
    opened: list = []

    def __init__(self, host, timeout=None, context=None, **kwargs):
        super().__init__(host, timeout=timeout)

    def request(self, method, url, body=None, headers=None, **kwargs):
        _FakeConnection.opened.append((self.host, method, url, dict(headers or {})))

    def getresponse(self):
        if self.host == "localhost":
            raw = (b"HTTP/1.1 302 Found\r\nLocation: https://127.0.0.1/api/v4/user\r\n"
                   b"Content-Length: 0\r\n\r\n")
        else:
            raw = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}"
        response = http.client.HTTPResponse(_FakeSocket(raw), method="GET")
        response.begin()
        return response

    def close(self):
        pass


def test_transport_does_not_follow_redirect(monkeypatch):
    """Настоящий `transport` на ответ 302 отдаёт код числом и не идёт по `Location`.

    Ловит мутацию: `transport` открывает запрос стандартным `urlopen` —
    обработчик перенаправлений повторяет запрос с `PRIVATE-TOKEN` на
    другой хост (второе соединение), а транспорт отдаёт 200.
    """
    _FakeConnection.opened = []
    monkeypatch.setattr(http.client, "HTTPSConnection", _FakeConnection)
    status, _headers, _body = gitlab_adapter.transport(
        "GET", "https://localhost/api/v4/user", {"PRIVATE-TOKEN": TOKEN}, None, 5)
    assert status == 302
    assert [host for host, *_rest in _FakeConnection.opened] == ["localhost"]


def test_plain_http_address_refused_before_transport(server):
    """Адрес записи не по https — именованный отказ до запроса: токен не уходит открытым текстом.

    Ловит мутацию: `_address` принимает схему `http` — запрос с токеном
    уходит в транспорт открытым текстом по схеме http.
    """
    server["routes"] = lambda method, url: (200, {}, b"{}")
    reply = gitlab_adapter.request("plain", "GET", "/user")
    assert server["sent"] == []
    assert "не https" in reply.reason


def test_allowed_pairs_exact_set():
    """Таблица пар — ровно перечень требования 4 SPEC, без лишних.

    Ловит мутацию: в `ALLOWED_PAIRS` дописана пара (например,
    `DELETE /projects/:id/merge_requests/:n`) или одна убрана.
    """
    assert set(gitlab_adapter.ALLOWED_PAIRS) == {
        ("GET", "/projects/:id"),
        ("GET", "/projects/:id/pipelines"),
        ("GET", "/projects/:id/pipelines/:n/jobs"),
        ("GET", "/projects/:id/pipelines/:n/test_report"),
        ("GET", "/projects/:id/merge_requests/:n"),
        ("GET", "/projects/:id/protected_branches"),
        ("GET", "/projects/:id/protected_tags"),
        ("GET", "/user"),
        ("GET", "/personal_access_tokens/self"),
        ("POST", "/projects/:id/merge_requests"),
        ("PUT", "/projects/:id/merge_requests/:n"),
    }
    assert len(gitlab_adapter.ALLOWED_PAIRS) == 11


@pytest.mark.parametrize("pipelines_total", [None, "١"])
def test_pipelines_without_x_total_unknown(server, pipelines_total):
    """Список конвейеров sha без числа `X-Total` (или с не-ASCII цифрой) — итог `unknown`, не `green`.

    Ловит мутацию: отсутствие `X-Total` считается полной выдачей или число
    сверяется через `isdigit` (принимает «١») — зелёное задание даёт `green`.
    """
    def routes(method, url):
        if "/jobs" in url:
            return (200, {"X-Total": "1"},
                    json.dumps([{"id": 5, "name": "test", "status": "success",
                                 "stage": "test", "allow_failure": False}]).encode())
        headers = {} if pipelines_total is None else {"X-Total": pipelines_total}
        return 200, headers, json.dumps([{"id": 1, "sha": "abc", "status": "success"}]).encode()

    server["routes"] = routes
    result = forge.pipeline_status("gl", "abc")
    assert result.verdict == forge.UNKNOWN
    assert "X-Total" in result.reason


@pytest.mark.parametrize("path", [
    "/projects/grp%2Fproj/pipelines?sha=abc&scope=all",
    "/projects/grp%2Fproj/merge_requests/٣",
    "/projects/grp%2Fproj/pipelines/١/jobs",
])
def test_extra_query_key_and_non_ascii_number_refused(server, path):
    """Лишний ключ строки запроса у чтения и не-ASCII цифры в `:n` — отказ до транспорта.

    Ловит мутацию: ключи строки запроса не сверяются с `QUERY_KEYS` или
    шаблон числа в пути — `\\d+` без `re.ASCII` (принимает «٣»).
    """
    server["routes"] = lambda method, url: (200, {}, b"{}")
    reply = gitlab_adapter.request("gl", "GET", path)
    assert server["sent"] == []
    assert "запрос не отправлен" in reply.reason
