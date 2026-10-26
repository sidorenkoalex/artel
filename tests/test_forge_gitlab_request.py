"""Функция запроса `gitlab_adapter.request` и признак `forge.ci_by_pipeline` на подменённых записи и транспорте."""
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
