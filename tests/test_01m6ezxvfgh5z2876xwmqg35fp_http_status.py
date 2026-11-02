"""Поле `http_status` результатов `forge.branch_pipeline`, `forge.pipeline_status`, `forge.protections` записи GitLab: код ответа берётся из `Reply.status` адаптера, не из текста причины; тексты `reason` прежние.

Группа: долгоживущий
Красен до реализации: у `forge.BranchPipeline`, `forge.PipelineStatus`, `forge.Protections` нет поля `http_status` — обращение к нему падает `AttributeError`, а `_read_all` адаптера теряет `Reply.status`.

Связка, которую держит файл: «запись `forge: gitlab` в `targets.yaml`
песочницы — `forge` — `gitlab_adapter.request` — транспорт». Песочница —
`initialized_tmp_root` (связка ключей — `tests.sandbox.fake_keychain_token`,
признак процесса роли снят). Сервер GitLab — подмена публичной точки
`gitlab_adapter.transport(method, url, headers, body, timeout)`: ответ
`(код, заголовки, тело bytes)`, таймаут — исключение `TimeoutError`; пауза
повтора — `tests.sandbox.TimeWithSleep`. Вторая половина — подмена
публичной `gitlab_adapter.request` готовым `gitlab_adapter.Reply`.

Имя проекта, группа, sha и id конвейера порождаются модулем `random` при
каждом запуске; зерно печатается и входит в текст провала.
"""
import json
import random
import re
import urllib.parse

import pytest

from orchestrator import config, forge, gitlab_adapter
from tests.sandbox import TimeWithSleep, artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"


def word(rng: random.Random, prefix: str, size: int = 7) -> str:
    return prefix + "".join(rng.choice(LETTERS) for _ in range(size))


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


class Server:
    """Поддельный GitLab: `fail` — {вид пути: код отказа}; `timeout` — таймаут
    на каждый запрос. Каждый вызов пишется в `calls`."""

    def __init__(self, rng: random.Random):
        self.pid = rng.randint(100, 900)
        self.sha = "%040x" % rng.getrandbits(160)
        self.fail: dict = {}
        self.timeout = False
        self.calls: list = []

    @staticmethod
    def reply(status: int, payload, total: int | None = None) -> tuple:
        head = {"Content-Type": "application/json"}
        if total is not None:
            head.update({"X-Total": str(total), "X-Total-Pages": "1", "X-Next-Page": ""})
        return status, head, json.dumps(payload).encode("utf-8")

    def transport(self, method, url, headers=None, body=None, timeout=None, *a, **k):
        path = urllib.parse.urlsplit(url).path
        self.calls.append((method, path))
        if self.timeout:
            raise TimeoutError("timed out")
        kind = ("jobs" if re.search(r"/pipelines/\d+/jobs$", path)
                else "pipelines" if path.endswith("/pipelines")
                else "protected_branches" if path.endswith("/protected_branches")
                else "protected_tags" if path.endswith("/protected_tags") else "")
        if kind in self.fail:
            return self.reply(self.fail[kind], {"message": f"{self.fail[kind]}"})
        if kind == "pipelines":
            items = [{"id": self.pid, "iid": 1, "sha": self.sha, "ref": config.MAIN_BRANCH,
                      "status": "success", "source": "push"}]
            return self.reply(200, items, 1)
        if kind == "jobs":
            return self.reply(200, [{"id": 1, "name": "tests", "stage": "test",
                                     "status": "success", "allow_failure": False}], 1)
        if kind in ("protected_branches", "protected_tags"):
            return self.reply(200, [{"name": "main"}], 1)
        return self.reply(404, {"message": "404 Not Found"})


class Scene:
    def __init__(self, seed: int):
        self.seed = seed
        self.rng = random.Random(seed)
        self.name = word(self.rng, "gl")
        group = word(self.rng, "grp", 4)
        text = "targets:\n" + artel_target_entry()
        text = text.rstrip("\n") + "\n" + (
            f"  {self.name}:\n    forge: gitlab\n"
            f"    url: https://localhost/{group}/{self.name}\n"
            f"    base: {config.MAIN_BRANCH}\n    token_slot: {self.name}-token\n"
            "    no_paths: []\n    project_skills: []\n    merge_gate: operator\n")
        config.TARGETS.write_text(text, encoding="utf-8")
        self.server = Server(self.rng)

    def results(self) -> dict:
        return {"branch_pipeline": forge.branch_pipeline(self.name, config.MAIN_BRANCH),
                "pipeline_status": forge.pipeline_status(self.name, self.server.sha),
                "protections": forge.protections(self.name)}

    def note(self, results, extra: str = "") -> str:
        return (f"зерно: {self.seed}; проект {self.name}; {extra}\n"
                + "\n".join(f"{k}: {v!r}" for k, v in results.items())
                + f"\nвызовы {self.server.calls}")


@pytest.fixture
def scene(initialized_tmp_root, monkeypatch, seed):
    made = Scene(seed)
    monkeypatch.setattr(gitlab_adapter, "transport", made.server.transport)
    monkeypatch.setattr(gitlab_adapter, "time", TimeWithSleep(lambda seconds: None))
    return made


def test_ac12_pipelines_403_sets_http_status(scene):
    """Ответ 403 на `GET /projects/:id/pipelines` — `http_status` 403 у `branch_pipeline` и `pipeline_status`, причина прежняя.

    Сценарий: сервер отвечает 403 на список конвейеров. У результатов
    `forge.branch_pipeline` и `forge.pipeline_status` `http_status` — 403,
    `reason` — прежний текст адаптера «доступ запрещён (403) на GET …».

    Ловит мутацию: `_read_all`/`branch_pipeline` теряют `Reply.status`
    (`http_status` `None`); код проведён только в одну из двух функций;
    вместе с полем изменён текст причины.
    """
    scene.server.fail = {"pipelines": 403}
    results = scene.results()
    note = scene.note(results, "403 на pipelines")
    for key in ("branch_pipeline", "pipeline_status"):
        assert results[key].http_status == 403, f"{key}; {note}"
        assert results[key].reason.startswith("доступ запрещён (403) на GET "), f"{key}; {note}"


def test_ac12_jobs_403_sets_http_status_of_branch_pipeline(scene):
    """Конвейеры прочитаны, задания — 403: `branch_pipeline` даёт `http_status` 403, причина прежняя.

    Сценарий: сервер отдаёт один конвейер ветки, а на `GET
    /projects/:id/pipelines/:n/jobs` отвечает 403. У `forge.branch_pipeline`
    `http_status` — 403, `reason` — «задания конвейера <n>: доступ запрещён
    (403) на GET …».

    Ловит мутацию: код отказа чтения заданий (`_pipeline_findings`) не
    проведён до результата — `http_status` `None`; причина собрана иначе.
    """
    scene.server.fail = {"jobs": 403}
    result = forge.branch_pipeline(scene.name, config.MAIN_BRANCH)
    note = scene.note({"branch_pipeline": result}, "403 на jobs")
    assert result.http_status == 403, note
    assert result.reason.startswith(
        f"задания конвейера {scene.server.pid}: доступ запрещён (403) на GET "), note


def test_ac12_protected_tags_403_sets_http_status(scene):
    """403 на `GET /projects/:id/protected_tags` — `forge.protections` даёт `http_status` 403, причина прежняя.

    Сценарий: защищённые ветки читаются, на теги сервер отвечает 403. У
    `forge.protections` `http_status` — 403, `reason` — «доступ запрещён
    (403) на GET …protected_tags…».

    Ловит мутацию: код проведён только для первого чтения (веток), не для
    тегов (`http_status` `None`); `protections` не заполняет поле вовсе.
    """
    scene.server.fail = {"protected_tags": 403}
    result = forge.protections(scene.name)
    note = scene.note({"protections": result}, "403 на protected_tags")
    assert result.http_status == 403, note
    assert result.reason.startswith("доступ запрещён (403) на GET "), note
    assert "protected_tags" in result.reason, note


def test_ac12_timeout_gives_none(scene):
    """Транспорт бросает `TimeoutError` — `http_status` `None` у всех трёх функций, причина «таймаут…» прежняя.

    Сценарий: каждый запрос к серверу — таймаут. У `branch_pipeline`,
    `pipeline_status`, `protections` `http_status` — `None`, `reason`
    начинается с «таймаут: GitLab не ответил».

    Ловит мутацию: отказ без ответа помечен кодом (например, 0 или 504) —
    строка `doctor` сочтёт его отказом правами или иным кодом.
    """
    scene.server.timeout = True
    results = scene.results()
    note = scene.note(results, "таймаут")
    for key, result in results.items():
        assert result.http_status is None, f"{key}; {note}"
        assert result.reason.startswith("таймаут: GitLab не ответил"), f"{key}; {note}"


@pytest.mark.parametrize("status,reason,expected", [
    (403, "отказ", 403),
    (None, "доступ запрещён (403) на GET /projects/x/pipelines", None),
], ids=["код без текста", "код только в тексте"])
def test_ac12_http_status_only_from_reply_status(scene, monkeypatch, status, reason, expected):
    """`http_status` берётся только из `Reply.status`: код без текста — 403, код только в тексте — `None`.

    Сценарий: подменённый `gitlab_adapter.request` на каждый запрос отдаёт
    `Reply(status=403, reason="отказ")` либо `Reply(status=None,
    reason="доступ запрещён (403) на GET …")`. У `branch_pipeline`,
    `pipeline_status`, `protections` `http_status` — 403 и `None`
    соответственно; `reason` результата — причина ответа.

    Ловит мутацию: код извлекается регулярным выражением из текста
    причины (во втором случае получится 403, в первом — `None`); поле
    заполняется только при известном тексте причины.
    """
    monkeypatch.setattr(gitlab_adapter, "request",
                        lambda *a, **k: gitlab_adapter.Reply(status=status, reason=reason))
    results = scene.results()
    note = scene.note(results, f"Reply(status={status!r}, reason={reason!r})")
    for key, result in results.items():
        assert result.http_status == expected, f"{key}; {note}"
        assert reason in result.reason, f"{key}; {note}"
