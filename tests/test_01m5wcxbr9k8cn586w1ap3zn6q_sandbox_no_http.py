"""Песочница `tests/sandbox.py::isolate_keychain_and_role` не пускает адаптер GitLab в сеть: подменённый по умолчанию транспорт отказывает соединению, а транспорт, подменённый самим тестом, имеет приоритет при любом порядке подмены.

Группа: долгоживущий
Красен до реализации: `isolate_keychain_and_role` транспорт `gitlab_adapter` не подменяет — запрос с токеном песочницы идёт настоящим `urllib` и доходит до `socket.create_connection` (подмена теста записывает вызов); два теста приоритета транспорта теста зелены с рождения — подмены песочницы ещё нет, перекрывать нечего, они держат приоритет после её появления.

Связка, которую держит файл: «песочница `tmp_root` (`TmpRootTest.setUp` →
`isolate_keychain_and_role`) — запись `forge: gitlab` в `targets.yaml`
песочницы — токен из связки ключей песочницы —
`gitlab_adapter.request` — транспорт». Сетевое соединение наблюдается
подменой `socket.create_connection`, которая записывает вызов и отказывает
(настоящего соединения нет ни при какой реализации).

Имена проектов и групп порождаются модулем `random` при каждом запуске;
зерно печатается и входит в текст провала.
"""
import json
import random
import socket
import urllib.parse

import pytest

from orchestrator import config, doctor, gitlab_adapter, keychain, targets
from tests.sandbox import artel_target_entry, fake_keychain_token

LETTERS = "abcdefghijkmnopqrstuvwxyz"


def word(rng: random.Random, prefix: str, size: int = 7) -> str:
    return prefix + "".join(rng.choice(LETTERS) for _ in range(size))


class Connections:
    """Подмена `socket.create_connection`: записывает адрес и отказывает."""

    def __init__(self):
        self.calls: list = []

    def __call__(self, address, *args, **kwargs):
        self.calls.append(address)
        raise ConnectionRefusedError(61, "соединение запрещено тестом")


class OwnTransport:
    """Транспорт, подменённый самим тестом: отвечает на `GET /user`."""

    def __init__(self, user: str):
        self.user = user
        self.calls: list = []

    def __call__(self, method, url, headers=None, body=None, timeout=None, *args, **kwargs):
        self.calls.append((str(method).upper(), urllib.parse.urlsplit(url).path))
        return 200, {"Content-Type": "application/json"}, json.dumps(
            {"id": 1, "username": self.user}).encode("utf-8")


class Project:
    """Запись `forge: gitlab` со слотом токена в `targets.yaml` песочницы."""

    def __init__(self, seed: int):
        rng = random.Random(seed)
        self.seed = seed
        self.name = word(rng, "gl")
        self.group = word(rng, "grp", 4)
        self.slot = f"{self.name}-token"
        self.user = word(rng, "u_")
        self.pid = urllib.parse.quote(f"{self.group}/{self.name}", safe="")

    def declare(self) -> None:
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry().rstrip("\n") + "\n"
            f"  {self.name}:\n    forge: gitlab\n"
            f"    url: https://localhost/{self.group}/{self.name}\n"
            f"    base: {config.MAIN_BRANCH}\n    token_slot: {self.slot}\n"
            f"    no_paths: []\n    project_skills: []\n    merge_gate: operator\n",
            encoding="utf-8")


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def connections(monkeypatch):
    spy = Connections()
    monkeypatch.setattr(socket, "create_connection", spy)
    return spy


@pytest.fixture
def own_before(monkeypatch, seed):
    """Транспорт теста подменён ДО включения песочницы (как фикстура `lab`
    раньше `gl_clone` → `real_git` в тестах части 1)."""
    own = OwnTransport(Project(seed).user)
    monkeypatch.setattr(gitlab_adapter, "transport", own)
    return own


@pytest.fixture
def sandbox_after_own(own_before, tmp_root):
    """Песочница `tmp_root`, включённая после подмены транспорта тестом."""
    return own_before


def test_ac5_sandbox_request_opens_no_connection(tmp_root, connections, seed):
    """Под песочницей запрос адаптера с токеном песочницы не открывает соединения и возвращает причину; сверка базы — `skip`.

    Сценарий: в `tmp_root` объявлена запись `forge: gitlab` (схема https,
    слот токена); связка ключей отдаёт по слоту токен песочницы
    `fake_keychain_token(<слот>)`; тест транспорт сам не подменял.
    `gitlab_adapter.request(<проект>, "GET", "/user")` возвращает непустую
    причину, `socket.create_connection` не вызван ни разу;
    `doctor.check_base_branch` этой записи — `skip`, и соединения снова нет.

    Ловит мутацию: песочница не подменяет транспорт (запрос уходит в
    `urllib` и зовёт `socket.create_connection`); подмена песочницы
    возвращает успешный ответ вместо отказа соединения (причина пуста).
    """
    pr = Project(seed)
    pr.declare()
    entry = targets.target(pr.name)
    note = f"зерно: {seed}; проект {pr.name}; соединения {connections.calls}"
    assert keychain.token(entry["token_slot"]) == fake_keychain_token(pr.slot), note
    reply = gitlab_adapter.request(pr.name, "GET", "/user")
    note = f"{note}; ответ {reply!r}"
    assert reply.reason, note
    assert connections.calls == [], note
    check = doctor.check_base_branch(pr.name, entry)
    note = f"{note}; {check}; соединения {connections.calls}"
    assert check.status == "skip", note
    assert connections.calls == [], note


def test_ac5_own_transport_set_after_sandbox_wins(tmp_root, connections, monkeypatch, seed):
    """Транспорт, подменённый тестом после включения песочницы, вызывается вместо подмены песочницы.

    Сценарий: `tmp_root` включён, затем тест подменяет
    `gitlab_adapter.transport` своим; запрос `GET /user` к записи
    `forge: gitlab` доходит до транспорта теста и возвращает его
    пользователя без причины; `socket.create_connection` не вызван.

    Ловит мутацию: песочница подменяет не атрибут модуля, а саму функцию
    `request`/место вызова транспорта — подмена теста не вызывается.
    """
    pr = Project(seed)
    pr.declare()
    own = OwnTransport(pr.user)
    monkeypatch.setattr(gitlab_adapter, "transport", own)
    reply = gitlab_adapter.request(pr.name, "GET", "/user")
    note = f"зерно: {seed}; ответ {reply!r}; вызовы {own.calls}; соединения {connections.calls}"
    assert own.calls == [("GET", "/api/v4/user")], note
    assert reply.reason == "" and reply.data.get("username") == pr.user, note
    assert connections.calls == [], note


def test_ac5_own_transport_set_before_sandbox_wins(sandbox_after_own, connections, seed):
    """Транспорт, подменённый тестом до включения песочницы, не перекрывается подменой песочницы.

    Сценарий: фикстура теста подменила `gitlab_adapter.transport` раньше,
    чем `tmp_root` вызвал `isolate_keychain_and_role`. Запрос `GET /user`
    к записи `forge: gitlab` доходит до транспорта теста и возвращает его
    пользователя без причины; `socket.create_connection` не вызван.

    Ловит мутацию: песочница ставит свою подмену безусловно поверх уже
    подменённого транспорта — транспорт теста не вызван, ответ — отказ
    соединения.
    """
    own = sandbox_after_own
    pr = Project(seed)
    pr.declare()
    reply = gitlab_adapter.request(pr.name, "GET", "/user")
    note = f"зерно: {seed}; ответ {reply!r}; вызовы {own.calls}; соединения {connections.calls}"
    assert own.calls == [("GET", "/api/v4/user")], note
    assert reply.reason == "" and reply.data.get("username") == pr.user, note
    assert connections.calls == [], note
