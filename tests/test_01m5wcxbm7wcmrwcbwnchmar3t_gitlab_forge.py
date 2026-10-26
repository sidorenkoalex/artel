"""Адаптер хостинга `forge` и его реализация GitLab (`gitlab_adapter`) на подменённом транспорте; ветка `ci` для записи `forge: gitlab`.

Группа: долгоживущий
Красен до реализации: модулей `orchestrator.forge` и `orchestrator.gitlab_adapter` ещё нет — импорт файла падает `ImportError`, ни один тест не собирается.

Окружение (фикстура `lab`) — подмены публичных точек:
- `gitlab_adapter.transport(method, url, headers, body, timeout)` —
  поддельный сервер GitLab API v4 (`https://localhost/api/v4`, проект
  `grp/proj`, адрес — `url` записи). Ответ — `(код, заголовки, тело
  bytes)`; сеть недоступна — `urllib.error.URLError`, таймаут —
  `TimeoutError` (контракт транспорта — дефолт эскалации AC-1 планки
  задачи). Списки конвейеров и заданий отдаются постранично по `page`/
  `per_page` (по умолчанию 20, не больше 100) с заголовками `X-Total`,
  `X-Total-Pages`, `X-Next-Page`; конвейеры — по убыванию id, как у
  GitLab;
- `targets.target` — загрузчик записи проекта (плоская запись, как у
  `targets._flatten`); `gitcmd.hosting_token` — токен записи;
- `ci.check_runs` — чтение check runs GitHub; `ci.gh` — шпион `gh`;
- `time.sleep` — пауза повтора не ждёт.

Ветка `ci` (AC-14…AC-16) идёт через клон проекта
`tests.sandbox.make_project_repo` под `real_git` (песочница без шпиона
`subprocess.run`): голова ветки читается настоящим git клона, итог CI — с поддельного транспорта по её sha. Эта
связка «`ci` — `forge` — транспорт — локальный git клона» и есть
предмет тех тестов.

Результаты функций `forge` разбираются без привязки к их форме: итог
`pipeline_status` — единственное значение верхнего уровня результата
(элемент кортежа, значение словаря, поле), равное одному из `green`/
`red`/`running`/`none`/`unknown`; причины и разобранные поля ищутся среди
всех строк и значений результата на любой глубине.

Идентификаторы и порядок выдачи заданий и конвейеров там, где порядок не
предмет критерия, порождаются модулем `random` при каждом запуске; зерно
печатается и входит в текст провала.
"""
import dataclasses
import datetime
import enum
import inspect
import json
import math
import random
import re
import subprocess
import time
import urllib.error
import urllib.parse
from typing import NamedTuple

import pytest

from orchestrator import ci, config, forge, gitlab_adapter, store, targets
from tests.sandbox import make_project_repo

GL = "glproj"
GH = "ghproj"
API = "https://localhost/api/v4"
PID = "grp%2Fproj"
TOKEN = "glpat-FixtureToken-5u8Qz"
SHA = "4f1c2b7d9e0a3c5b8d6f1e2a4c7b9d0e3f5a6b8c"
MR = 37
MR_PATH = f"/projects/{PID}/merge_requests/{MR}"
MR_URL = "https://localhost/grp/proj/-/merge_requests/37"
TITLE = "Починка разбора отчёта"
VERDICTS = {"green", "red", "running", "none", "unknown"}
NO_PIPELINE = "конвейер не создан (ветка не под правилом workflow?)"
NETWORK_DOWN = "сеть недоступна:"
RUNNING_STATUSES = ["running", "pending", "waiting_for_resource", "preparing", "scheduled"]


def gl_entry(**extra) -> dict:
    entry = {"forge": "gitlab", "url": "https://localhost/grp/proj",
             "base": config.MAIN_BRANCH, "token_slot": "glproj-token",
             "no_paths": [], "project_skills": [], "merge_gate": "operator"}
    entry.update(extra)
    return entry


def gh_entry() -> dict:
    return {"forge": "github", "url": "https://localhost/acme/ghproj",
            "base": config.MAIN_BRANCH, "token_slot": "ghproj-token",
            "no_paths": [], "project_skills": [], "merge_gate": "operator"}


class Call(NamedTuple):
    method: str
    path: str
    query: dict
    headers: dict
    body: object


def _decode_body(body):
    if body is None or isinstance(body, (dict, list)):
        return body
    text = body.decode("utf-8") if isinstance(body, bytes) else str(body)
    try:
        return json.loads(text)
    except ValueError:
        return dict(urllib.parse.parse_qsl(text))


class Lab:
    """Поддельный GitLab, загрузчик записей, токен и шпионы `gh`/check runs."""

    def __init__(self):
        self.records = {GL: gl_entry(), GH: gh_entry()}
        self.calls: list[Call] = []
        self.pipelines: list[dict] = []
        self.jobs: dict[int, list] = {}
        self.reports: dict[int, tuple] = {}
        self.routes: dict[tuple, list] = {}
        self.total_bias = {"pipelines": 0, "jobs": 0}
        self.exc = None
        self.token = (TOKEN, None)
        self.target_calls: list[str] = []
        self.check_runs_answer = (None, "check runs в сценарии не заданы")
        self.check_runs_calls: list[tuple] = []
        self.gh_calls: list[tuple] = []
        self.sleeps: list = []

    # --- подменяемые точки ---

    def target(self, name: str) -> dict:
        self.target_calls.append(name)
        if name not in self.records:
            raise targets.TargetsError(f"target '{name}' не объявлен (сценарий теста)")
        return json.loads(json.dumps(self.records[name]))

    def hosting_token(self, name, entry):
        return self.token

    def check_runs(self, *args, **kwargs):
        self.check_runs_calls.append((args, kwargs))
        return self.check_runs_answer

    def gh(self, *args, **kwargs):
        self.gh_calls.append(args)
        return subprocess.CompletedProcess(["gh", *args], 1, "", "gh запрещён сценарием теста")

    def sleep(self, seconds) -> None:
        self.sleeps.append(seconds)

    def transport(self, method, url, headers=None, body=None, timeout=None, *args, **kwargs):
        parts = urllib.parse.urlsplit(url)
        raw = re.sub("%2f", "%2F", parts.path)
        path = raw[len("/api/v4"):] if f"{parts.scheme}://{parts.netloc}{raw}".startswith(API) else url
        query = dict(urllib.parse.parse_qsl(parts.query))
        self.calls.append(Call(str(method).upper(), path, query, dict(headers or {}),
                               _decode_body(body)))
        if self.exc is not None:
            raise self.exc
        return self._route(str(method).upper(), path, query)

    # --- ответы ---

    @staticmethod
    def _reply(status: int, payload, headers=None) -> tuple:
        head = {"Content-Type": "application/json"}
        head.update(headers or {})
        return status, head, json.dumps(payload).encode("utf-8")

    def _page(self, items: list, query: dict, bias: int) -> tuple:
        page = max(1, int(query.get("page") or 1))
        per = max(1, min(int(query.get("per_page") or 20), 100))
        pages = max(1, math.ceil(len(items) / per))
        chunk = items[(page - 1) * per: page * per]
        return self._reply(200, chunk, {
            "X-Total": str(len(items) + bias), "X-Total-Pages": str(pages),
            "X-Page": str(page), "X-Per-Page": str(per),
            "X-Next-Page": str(page + 1) if page < pages else ""})

    def _route(self, method: str, path: str, query: dict) -> tuple:
        if (method, path) in self.routes:
            seq = self.routes[(method, path)]
            answer = seq.pop(0) if len(seq) > 1 else seq[0]
            if isinstance(answer, BaseException):
                raise answer
            return self._reply(*answer)
        if method == "GET" and path == f"/projects/{PID}/pipelines":
            items = [p for p in self.pipelines
                     if p["sha"] == query.get("sha", p["sha"])
                     and p["ref"] == query.get("ref", p["ref"])]
            items.sort(key=lambda p: p["id"], reverse=query.get("sort") != "asc")
            return self._page(items, query, self.total_bias["pipelines"])
        found = re.fullmatch(rf"/projects/{re.escape(PID)}/pipelines/(\d+)/jobs", path)
        if method == "GET" and found and int(found.group(1)) in self.jobs:
            return self._page(self.jobs[int(found.group(1))], query, self.total_bias["jobs"])
        found = re.fullmatch(rf"/projects/{re.escape(PID)}/pipelines/(\d+)/test_report", path)
        if method == "GET" and found and int(found.group(1)) in self.reports:
            return self._reply(*self.reports[int(found.group(1))])
        return self._reply(404, {"message": "404 Not Found"})

    # --- сценарий ---

    def pipeline(self, pid: int, status: str, jobs: list, sha: str = SHA,
                 ref: str = config.MAIN_BRANCH, source: str = "push") -> None:
        self.pipelines.append({"id": pid, "iid": pid, "sha": sha, "ref": ref,
                               "status": status, "source": source,
                               "web_url": f"https://localhost/grp/proj/-/pipelines/{pid}"})
        self.jobs[pid] = jobs


def job(jid: int, name: str, status: str, stage: str = "test",
        allow_failure: bool = False) -> dict:
    return {"id": jid, "name": name, "stage": stage, "status": status,
            "allow_failure": allow_failure}


@pytest.fixture
def lab(monkeypatch):
    fake = Lab()
    monkeypatch.setattr(gitlab_adapter, "transport", fake.transport)
    monkeypatch.setattr(targets, "target", fake.target)
    # Подмена по пути: AC-3 называет точку подмены `gitcmd.hosting_token`.
    monkeypatch.setattr("orchestrator.gitcmd.hosting_token", fake.hosting_token)
    monkeypatch.setattr(ci, "check_runs", fake.check_runs)
    monkeypatch.setattr(ci, "gh", fake.gh)
    monkeypatch.setattr(time, "sleep", fake.sleep)
    return fake


@pytest.fixture
def rng():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return random.Random(value), value


@pytest.fixture
def gl_clone(real_git, lab):
    """Клон проекта `glproj` в области проектов песочницы: (путь, sha головы).

    Sha головы — из файла ссылки `refs/heads/<основная ветка>` свежего клона
    (ссылки ещё не упакованы), без вызова git."""
    repo = make_project_repo(GL)
    ref = repo / ".git" / "refs" / "heads" / config.MAIN_BRANCH
    return repo, ref.read_text(encoding="utf-8").strip()


# --- разбор результата без привязки к его форме ---

def _plain(value):
    return value.value if isinstance(value, enum.Enum) else value


def top_values(res) -> list:
    if isinstance(res, dict):
        return list(res.values())
    if dataclasses.is_dataclass(res) and not isinstance(res, type):
        return [getattr(res, f.name) for f in dataclasses.fields(res)]
    if isinstance(res, (tuple, list)):
        return list(res)
    if hasattr(res, "__dict__") and not isinstance(res, (str, bytes, int, float, enum.Enum)):
        return list(vars(res).values())
    return [res]


def leaves(res) -> list:
    """Все значения результата на любой глубине (ключи словарей — тоже)."""
    out, stack, seen = [], [res], set()
    while stack:
        item = _plain(stack.pop())
        if isinstance(item, (dict, list, tuple, set, frozenset)) or (
                dataclasses.is_dataclass(item) and not isinstance(item, type)) or (
                hasattr(item, "__dict__") and not isinstance(item, (str, bytes, int, float, type))
                and not callable(item)):
            if id(item) in seen:
                continue
            seen.add(id(item))
            if isinstance(item, dict):
                stack.extend(item.keys())
                stack.extend(item.values())
            elif isinstance(item, (list, tuple, set, frozenset)):
                stack.extend(item)
            else:
                stack.extend(top_values(item))
        else:
            out.append(item)
    return out


def texts(res) -> list[str]:
    return [x for x in leaves(res) if isinstance(x, str)]


def joined(res) -> str:
    return "\n".join(texts(res))


def verdicts(res) -> set:
    return {v for v in map(_plain, top_values(res)) if isinstance(v, str) and v in VERDICTS}


def mappings(res) -> list[dict]:
    out, stack = [], [res]
    while stack:
        item = _plain(stack.pop())
        if isinstance(item, dict):
            out.append(item)
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
        elif dataclasses.is_dataclass(item) and not isinstance(item, type):
            stack.extend(top_values(item))
    return out


def fixture_strings(fake: Lab) -> set:
    found = set(VERDICTS)
    for p in fake.pipelines:
        found |= {str(v) for v in p.values()}
    for jobs in fake.jobs.values():
        for j in jobs:
            found |= {str(v) for v in j.values()}
    return found


def reasons(res, fake: Lab) -> list[str]:
    """Непустые строки результата, которых нет в самой фикстуре (имена, статусы, sha)."""
    known = fixture_strings(fake)
    return [t for t in texts(res) if t.strip() and t not in known]


def calls_of(fake: Lab) -> list[tuple]:
    return [(c.method, c.path) for c in fake.calls]


def shuffled(gen: random.Random, items: list) -> list:
    items = list(items)
    gen.shuffle(items)
    return items


# Вызовы функций `forge` для записи `forge: gitlab` (параметр `target` — имя).
GL_CALLS = {
    "pipeline_status": lambda: forge.pipeline_status(GL, SHA),
    "job_result": lambda: forge.job_result(GL, SHA, "test"),
    "job_test_report": lambda: forge.job_test_report(GL, SHA, "test"),
    "open_mr": lambda: forge.open_mr(GL, "task/abc", config.MAIN_BRANCH, TITLE,
                                     "Описание", True, 42),
    "undraft_mr": lambda: forge.undraft_mr(GL, MR),
    "assign_mr": lambda: forge.assign_mr(GL, MR, 42),
    "mr_status": lambda: forge.mr_status(GL, MR),
    "token_user": lambda: forge.token_user(GL),
    "token_expiry": lambda: forge.token_expiry(GL),
    "protections": lambda: forge.protections(GL),
}
GL_CALL_NAMES = list(GL_CALLS)

# Те же функции, кроме `pipeline_status`, для записи `forge: github`.
GH_CALLS = {
    "job_result": lambda: forge.job_result(GH, SHA, "test"),
    "job_test_report": lambda: forge.job_test_report(GH, SHA, "test"),
    "open_mr": lambda: forge.open_mr(GH, "task/abc", config.MAIN_BRANCH, TITLE,
                                     "Описание", True, 42),
    "undraft_mr": lambda: forge.undraft_mr(GH, MR),
    "assign_mr": lambda: forge.assign_mr(GH, MR, 42),
    "mr_status": lambda: forge.mr_status(GH, MR),
    "token_user": lambda: forge.token_user(GH),
    "token_expiry": lambda: forge.token_expiry(GH),
    "protections": lambda: forge.protections(GH),
}


# --- AC-3 ---

@pytest.mark.parametrize("case, token", [
    ("пара (None, None)", (None, None)),
    ("пустой слот", (None, "слот glproj-token связки ключей пуст — операция хостинга "
                          "проекта glproj отказана (token_slot записи проекта)")),
    ("процесс роли", (None, "операция хостинга проекта glproj отказана: процесс роли — "
                            "токен хостинга проекта читается только в сессии Оператора")),
])
@pytest.mark.parametrize("name", GL_CALL_NAMES)
def test_ac3_no_token_no_request(lab, name, case, token):
    """Без полученного токена функция `forge` для GitLab отдаёт причину, транспорт не вызван.

    Сценарий: подменённый `gitcmd.hosting_token` отдаёт `(None, None)`,
    отказ пустого слота или отказ процесса роли; каждая функция `forge`
    зовётся по имени проекта `glproj` (`forge: gitlab`). Функция
    возвращает, а не бросает; в результате есть текст причины, для пары
    `(None, None)` — «токен не получен»; поддельный транспорт не получил
    ни одного вызова.

    Ловит мутацию: `(None, None)` читается как «прежняя авторизация», как
    у GitHub, и запрос уходит без заголовка `PRIVATE-TOKEN` — в журнале
    транспорта появляется вызов.
    """
    lab.token = token
    res = GL_CALLS[name]()
    assert calls_of(lab) == [], f"{name}, {case}: транспорт вызван без токена"
    assert any(t.strip() for t in texts(res)), f"{name}, {case}: нет причины в {res!r}"
    if token == (None, None):
        assert "токен не получен" in joined(res), f"{name}: {res!r}"


# --- AC-4 ---

@pytest.mark.parametrize("pipeline_status", ["success", "manual"])
def test_ac4_success_and_manual_jobs_green(lab, rng, pipeline_status):
    """Конвейер с заданиями `success` и `manual` (вне обязательных) — итог `green`.

    Сценарий: у sha один конвейер `success` или `manual`; задания —
    `build`/`test` `success` и `deploy` `manual`, запись без поля
    обязательных заданий; выдача заданий в случайном порядке.

    Ловит мутацию: задание `manual` считается незавершённым (`running`)
    — итог `running` вместо `green`.
    """
    gen, seed = rng
    lab.pipeline(500, pipeline_status, shuffled(gen, [
        job(11, "build", "success", "build"), job(12, "test", "success", "test"),
        job(13, "deploy", "manual", "deploy")]))
    res = forge.pipeline_status(GL, SHA)
    assert verdicts(res) == {"green"}, f"зерно: {seed}; {res!r}"


@pytest.mark.parametrize("status", ["created", "skipped"])
def test_ac4_created_or_skipped_after_manual_green(lab, rng, status):
    """Задание `created`/`skipped` стадией позже `manual`, вне обязательных, — `green`.

    Сценарий: конвейер `manual`: `build` `success` (стадия build),
    `approve` `manual` (стадия approve), `publish` `created`/`skipped`
    (стадия publish, id больше); обязательные задания записи — только
    `build`.

    Ловит мутацию: `created`/`skipped` за ручным заданием считается
    незавершённым или неизвестным — итог `running`/`unknown`.
    """
    gen, seed = rng
    lab.records[GL] = gl_entry(ci_required_jobs=["build"])
    lab.pipeline(501, "manual", shuffled(gen, [
        job(21, "build", "success", "build"), job(22, "approve", "manual", "approve"),
        job(23, "publish", status, "publish")]))
    res = forge.pipeline_status(GL, SHA)
    assert verdicts(res) == {"green"}, f"зерно: {seed}; {res!r}"


# --- AC-5 ---

def test_ac5_required_created_not_green(lab, rng):
    """Задание `created`, перечисленное в `ci_required_jobs`, — итог не `green`.

    Сценарий: конвейер `manual`: `build` `success`, `approve` `manual`
    ранней стадии, `publish` `created` поздней; `publish` — в
    обязательных заданиях записи.

    Ловит мутацию: правило «за ручным» не сверяется с
    `ci_required_jobs` — обязательное, но не исполненное задание даёт
    `green`.
    """
    gen, seed = rng
    lab.records[GL] = gl_entry(ci_required_jobs=["publish"])
    lab.pipeline(502, "manual", shuffled(gen, [
        job(31, "build", "success", "build"), job(32, "approve", "manual", "approve"),
        job(33, "publish", "created", "publish")]))
    res = forge.pipeline_status(GL, SHA)
    found = verdicts(res)
    assert len(found) == 1 and "green" not in found, f"зерно: {seed}; {res!r}"


@pytest.mark.parametrize("status, expected", [("created", "running"), ("skipped", "unknown")])
def test_ac5_without_earlier_manual(lab, rng, status, expected):
    """`created` без ручного задания раньше — `running`, `skipped` — `unknown`.

    Сценарий: конвейер `manual`: `build` `success` (стадия build, id 41),
    `publish` `created`/`skipped` (стадия publish, id 42), `approve`
    `manual` в стадии позже (id 43); обязательные — только `build`.

    Ловит мутацию: «за ручным» проверяется по наличию любого ручного
    задания в конвейере, а не в более ранней стадии, — итог `green`;
    либо `skipped` читается как `running` — итог не `unknown`.
    """
    gen, seed = rng
    lab.records[GL] = gl_entry(ci_required_jobs=["build"])
    lab.pipeline(503, "manual", shuffled(gen, [
        job(41, "build", "success", "build"), job(42, "publish", status, "publish"),
        job(43, "approve", "manual", "approve")]))
    res = forge.pipeline_status(GL, SHA)
    assert verdicts(res) == {expected}, f"зерно: {seed}; {res!r}"


def test_ac5_record_without_required_field_manual_green(lab, rng):
    """Запись без `ci_required_jobs`: задание `manual` при прочих `success` — `green`.

    Сценарий: в записи нет ключа `ci_required_jobs`; конвейер `manual`:
    `build`, `test` `success`, `deploy` `manual`.

    Ловит мутацию: поле читается как `entry["ci_required_jobs"]` без
    умолчания — `KeyError` вместо итога.
    """
    gen, seed = rng
    lab.records[GL] = gl_entry()
    lab.pipeline(504, "manual", shuffled(gen, [
        job(51, "build", "success", "build"), job(52, "test", "success", "test"),
        job(53, "deploy", "manual", "deploy")]))
    res = forge.pipeline_status(GL, SHA)
    assert verdicts(res) == {"green"}, f"зерно: {seed}; {res!r}"


# --- AC-6 ---

def test_ac6_failed_job_red(lab, rng):
    """Задание `failed` без права падать — итог `red`.

    Сценарий: конвейер `failed`: `build` `success`, `test` `failed` с
    `allow_failure: false`.

    Ловит мутацию: `allow_failure` читается с инверсией — упавшее
    обязательное задание пропускается, итог `green`.
    """
    gen, seed = rng
    lab.pipeline(505, "failed", shuffled(gen, [
        job(61, "build", "success", "build"), job(62, "test", "failed", "test")]))
    res = forge.pipeline_status(GL, SHA)
    assert verdicts(res) == {"red"}, f"зерно: {seed}; {res!r}"


def test_ac6_allowed_failure_green_with_mark(lab, rng):
    """Упавшее задание с `allow_failure` — `green` с пометкой, называющей задание.

    Сценарий: конвейер `success`: `build`, `test` `success`, задание со
    случайным именем `lint-…` `failed` с `allow_failure: true`. Итог
    `green`; среди строк результата есть пометка — строка, которая
    содержит имя задания и не сводится к самому имени.

    Ловит мутацию: `allow_failure` не читается — итог `red`; либо
    допустимое падение молча проглатывается — пометки с именем задания
    в результате нет.
    """
    gen, seed = rng
    name = "lint-" + "".join(gen.choice("abcdefghk") for _ in range(5))
    lab.pipeline(506, "success", shuffled(gen, [
        job(71, "build", "success", "build"), job(72, "test", "success", "test"),
        job(73, name, "failed", "test", allow_failure=True)]))
    res = forge.pipeline_status(GL, SHA)
    assert verdicts(res) == {"green"}, f"зерно: {seed}; {res!r}"
    assert [t for t in texts(res) if name in t and t != name], \
        f"зерно: {seed}; нет пометки о задании {name}: {res!r}"


# --- AC-7 ---

def test_ac7_two_pipelines_one_red(lab, rng):
    """У sha два конвейера (ветка и MR), один красный — итог `red`.

    Сценарий: конвейер ветки `success` с зелёными заданиями и конвейер
    MR `failed` с упавшим заданием на том же sha; id и порядок выдачи
    случайны.

    Ловит мутацию: итог берётся по первому (последнему) конвейеру
    выдачи — при зелёном первом итог `green`.
    """
    gen, seed = rng
    ids = gen.sample(range(600, 700), 2)
    lab.pipeline(ids[0], "success", [job(81, "test", "success")], source="push")
    lab.pipeline(ids[1], "failed", [job(82, "test", "failed")],
                 source="merge_request_event")
    res = forge.pipeline_status(GL, SHA)
    assert verdicts(res) == {"red"}, f"зерно: {seed}; {res!r}"


@pytest.mark.parametrize("pipeline_status", ["running", "success"])
@pytest.mark.parametrize("status", RUNNING_STATUSES)
def test_ac7_active_job_running(lab, rng, status, pipeline_status):
    """Задание `running`/`pending`/`waiting_for_resource`/`preparing`/`scheduled` без `failed` — `running`.

    Сценарий: конвейер `running` (и, для проверки правила самих заданий,
    `success`): `build` `success`, `test` с активным статусом.

    Ловит мутацию: статус задания `waiting_for_resource`/`preparing`/
    `scheduled` не входит в «идёт» — итог `unknown` или `green`.
    """
    gen, seed = rng
    lab.pipeline(507, pipeline_status, shuffled(gen, [
        job(91, "build", "success", "build"), job(92, "test", status, "test")]))
    res = forge.pipeline_status(GL, SHA)
    assert verdicts(res) == {"running"}, f"зерно: {seed}; {res!r}"


def test_ac7_no_pipeline_none_with_reason(lab):
    """У sha нет конвейеров — итог `none` с причиной про правило workflow.

    Сценарий: список конвейеров sha пуст (`X-Total: 0`).

    Ловит мутацию: пустой список читается как «упавших нет» — итог
    `green`; либо `none` без текста «конвейер не создан (ветка не под
    правилом workflow?)».
    """
    res = forge.pipeline_status(GL, SHA)
    assert verdicts(res) == {"none"}, repr(res)
    assert NO_PIPELINE in joined(res), repr(res)


# --- AC-8 ---

UNKNOWN_CASES = ["задание canceled", "конвейер canceled", "неизвестный статус задания",
                 "неизвестный статус конвейера", "X-Total заданий", "X-Total конвейеров"]


def unknown_case(fake: Lab, gen: random.Random, case: str) -> None:
    jobs = [job(101, "build", "success", "build"), job(102, "test", "success", "test")]
    status = "success"
    if case == "задание canceled":
        jobs[1] = job(102, "test", "canceled", "test")
    elif case == "конвейер canceled":
        status = "canceled"
    elif case == "неизвестный статус задания":
        jobs[1] = job(102, "test", "frobnicated", "test")
    elif case == "неизвестный статус конвейера":
        status = gen.choice(["skipped", "frobnicated"])
    elif case == "X-Total заданий":
        fake.total_bias["jobs"] = 1
    elif case == "X-Total конвейеров":
        fake.total_bias["pipelines"] = 1
    fake.pipeline(508, status, shuffled(gen, jobs))


@pytest.mark.parametrize("case", UNKNOWN_CASES)
def test_ac8_unknown_with_reason(lab, rng, case):
    """Шесть обстоятельств «статус не установлен» — итог `unknown` с причиной.

    Сценарий: конвейер `success` с зелёными заданиями, в котором ровно
    одно отклонение: задание `canceled`; конвейер `canceled`; статус
    задания вне известных; статус конвейера вне известных (`skipped` или
    выдуманный); `X-Total` заданий или конвейеров больше прочитанного.
    Итог `unknown`, в результате есть причина — строка, которой нет в
    самой фикстуре.

    Ловит мутацию: `X-Total` не сверяется или неизвестный статус
    пропускается как зелёный — итог `green`.
    """
    gen, seed = rng
    unknown_case(lab, gen, case)
    res = forge.pipeline_status(GL, SHA)
    assert verdicts(res) == {"unknown"}, f"зерно: {seed}; {case}: {res!r}"
    assert reasons(res, lab), f"зерно: {seed}; {case}: нет причины в {res!r}"


def test_ac8_failed_job_on_second_page_red(lab, rng):
    """Задание `failed` на последней странице выдачи заданий — итог `red`.

    Сценарий: конвейер `success` со 150 заданиями (больше предельной
    страницы 100); упавшее задание — последнее в выдаче. Итог `red`, а
    заданий прочитано столько страниц, сколько их при запрошенном
    `per_page`.

    Ловит мутацию: читается одна первая страница заданий — упавшее не
    видно, итог `green`; число вызовов транспорта к заданиям — один.
    """
    gen, seed = rng
    jobs = [job(1000 + i, f"job-{i}", "success", "test") for i in range(149)]
    jobs = shuffled(gen, jobs) + [job(2000, "job-red", "failed", "test")]
    lab.pipeline(509, "success", jobs)
    res = forge.pipeline_status(GL, SHA)
    job_calls = [c for c in lab.calls if c.path.endswith("/pipelines/509/jobs")]
    per = max(1, min(int((job_calls[0].query.get("per_page") if job_calls else None) or 20), 100))
    assert verdicts(res) == {"red"}, f"зерно: {seed}; {res!r}"
    assert len(job_calls) >= math.ceil(150 / per) >= 2, \
        f"зерно: {seed}; страниц заданий прочитано {len(job_calls)} при per_page {per}"


def test_ac8_red_pipeline_on_second_page_red(lab, rng):
    """Красный конвейер на последней странице списка конвейеров sha — итог `red`.

    Сценарий: у sha 120 конвейеров `success` с зелёным заданием и один
    `failed` с упавшим — с наименьшим id, то есть последним в выдаче по
    убыванию id. Список конвейеров читается больше чем одной страницей.

    Ловит мутацию: читается только первая страница конвейеров sha —
    красный не виден, итог `green`.
    """
    gen, seed = rng
    ids = shuffled(gen, list(range(3001, 3121)))
    for i, pid in enumerate(ids):
        lab.pipeline(pid, "success", [job(10000 + i, "test", "success")])
    lab.pipeline(3000, "failed", [job(9999, "test", "failed")])
    res = forge.pipeline_status(GL, SHA)
    list_calls = [c for c in lab.calls if c.path == f"/projects/{PID}/pipelines"]
    assert verdicts(res) == {"red"}, f"зерно: {seed}; {res!r}"
    assert len(list_calls) >= 2, f"зерно: {seed}; список конвейеров прочитан одной страницей"


# --- AC-9 ---

@pytest.mark.parametrize("name, expected, other", [
    ("test", "failed", "success"), ("build", "success", "failed")])
def test_ac9_job_result_requested_status(lab, rng, name, expected, other):
    """`job_result` отдаёт статус задания с запрошенным именем.

    Сценарий: в конвейере sha задания `build` `success` и `test`
    `failed` в случайном порядке; запрос по каждому имени даёт его
    статус, и статуса другого задания в результате нет.

    Ловит мутацию: отдаётся статус первого задания выдачи, а не
    задания с запрошенным именем, — в результате чужой статус.
    """
    gen, seed = rng
    lab.pipeline(510, "running", shuffled(gen, [
        job(111, "build", "success", "build"), job(112, "test", "failed", "test")]))
    res = forge.job_result(GL, SHA, name)
    found = texts(res)
    assert expected in found and other not in found, f"зерно: {seed}; {name}: {res!r}"


def test_ac9_missing_job_named_reason(lab, rng):
    """Задания с запрошенным именем нет — именованная причина, без чужих статусов.

    Сценарий: в конвейере `build` `success` и `test` `failed`; запрос
    задания `absent-job`. Функция возвращает причину; статусов `success`
    и `failed` среди значений результата нет.

    Ловит мутацию: при отсутствии имени отдаётся статус первого
    попавшегося задания — в результате `success` или `failed`.
    """
    gen, seed = rng
    lab.pipeline(511, "running", shuffled(gen, [
        job(121, "build", "success", "build"), job(122, "test", "failed", "test")]))
    res = forge.job_result(GL, SHA, "absent-job")
    found = texts(res)
    assert "success" not in found and "failed" not in found, f"зерно: {seed}; {res!r}"
    assert reasons(res, lab), f"зерно: {seed}; нет причины в {res!r}"


@pytest.mark.parametrize("first, last", [("failed", "success"), ("success", "failed")])
def test_ac9_last_attempt_wins(lab, rng, first, last):
    """У имени несколько попыток — статус последней (наибольший id).

    Сценарий: задание `test` дважды — попытка id 130 со статусом
    `first` и попытка id 135 со статусом `last`; порядок выдачи
    случаен.

    Ловит мутацию: берётся первая попытка или первая в выдаче — в
    результате статус `first`.
    """
    gen, seed = rng
    lab.pipeline(512, "running", shuffled(gen, [
        job(130, "test", first, "test"), job(135, "test", last, "test")]))
    res = forge.job_result(GL, SHA, "test")
    found = texts(res)
    assert last in found and first not in found, f"зерно: {seed}; {res!r}"


# --- AC-10 ---

def report(cases: list, suite: str = "pytest", **extra) -> dict:
    suite_body = {"name": suite, "total_count": len(cases), "test_cases": cases,
                  "suite_error": None}
    suite_body.update(extra)
    return {"total_count": len(cases), "test_suites": [suite_body]}


def case(classname: str, name: str, status: str) -> dict:
    return {"classname": classname, "name": name, "status": status, "execution_time": 0.1}


def test_ac10_report_keys_class_and_name(lab, rng):
    """Отчёт тестов задания разбирается в `<classname>::<name>` → исход.

    Сценарий: у конвейера sha задание `pytest`; отчёт тестов
    (`test_suites[].test_cases[]`) несёт два теста с одним `name` в
    разных `classname` и третий тест. Результат содержит отображение
    ровно из трёх ключей `<classname>::<name>` с исходами.

    Ловит мутацию: ключ строится только по `name` — два теста
    схлопываются в один, отображение из двух ключей.
    """
    gen, seed = rng
    lab.pipeline(513, "success", [job(140, "pytest", "success")])
    cases = shuffled(gen, [case("tests.test_a", "test_x", "success"),
                           case("tests.test_b", "test_x", "failed"),
                           case("tests.test_a", "test_y", "skipped")])
    lab.reports[513] = (200, report(cases))
    res = forge.job_test_report(GL, SHA, "pytest")
    expected = {"tests.test_a::test_x": "success", "tests.test_b::test_x": "failed",
                "tests.test_a::test_y": "skipped"}
    found = [{k: _plain(v) for k, v in m.items()} for m in mappings(res)]
    assert expected in found, f"зерно: {seed}; {res!r}"


def test_ac10_duplicate_key_ambiguous(lab, rng):
    """Совпадение ключей в одном отчёте — `None` с причиной «неоднозначный идентификатор».

    Сценарий: отчёт несёт два теста с одинаковыми `classname` и `name`
    (исходы разные). Среди значений верхнего уровня результата — `None`,
    в тексте — «неоднозначный идентификатор», отображения с ключами
    `…::…` нет.

    Ловит мутацию: второй тест молча перезаписывает первый — отдано
    отображение с одним ключом.
    """
    gen, seed = rng
    lab.pipeline(514, "success", [job(150, "pytest", "success")])
    lab.reports[514] = (200, report(shuffled(gen, [
        case("tests.test_a", "test_x", "success"), case("tests.test_a", "test_x", "failed"),
        case("tests.test_a", "test_y", "success")])))
    res = forge.job_test_report(GL, SHA, "pytest")
    assert None in top_values(res), f"зерно: {seed}; {res!r}"
    assert "неоднозначный идентификатор" in joined(res), f"зерно: {seed}; {res!r}"
    assert not any("::" in str(k) for m in mappings(res) for k in m), f"зерно: {seed}; {res!r}"


@pytest.mark.parametrize("kind", ["404", "нет набора задания", "истёк"])
def test_ac10_absent_or_expired_report_none(lab, kind):
    """Отчёта нет или он истёк — `None` с причиной.

    Сценарий: запрос отчёта конвейера отвечает 404; либо отчёт без
    набора задания (`test_suites: []`); либо набор задания с
    `suite_error` об истёкших артефактах и без тестов. Среди значений
    верхнего уровня — `None`, причина — строка, которой нет в фикстуре.

    Ловит мутацию: пустой или истёкший отчёт разбирается в пустое
    отображение `{}` — «тестов нет» вместо «отчёта нет».
    """
    lab.pipeline(515, "success", [job(160, "pytest", "success")])
    if kind == "нет набора задания":
        lab.reports[515] = (200, {"total_count": 0, "test_suites": []})
    elif kind == "истёк":
        lab.reports[515] = (200, report([], suite_error="Test report artifacts have expired"))
    res = forge.job_test_report(GL, SHA, "pytest")
    assert None in top_values(res), f"{kind}: {res!r}"
    assert reasons(res, lab), f"{kind}: нет причины в {res!r}"


# --- AC-11 ---

USER = ("GET", "/user")


@pytest.mark.parametrize("status", [401, 403, 404])
def test_ac11_client_errors_named_without_retry(lab, status):
    """401/403/404 — именованная причина без исключения и без повтора.

    Сценарий: `GET /user` отвечает кодом ошибки клиента; `token_user`
    возвращает причину, транспорт вызван ровно один раз.

    Ловит мутацию: повтор на любой код ошибки — транспорт вызван больше
    одного раза; либо `HTTPError` пробрасывается исключением.
    """
    lab.routes[USER] = [(status, {"message": f"{status} Forbidden"})]
    res = forge.token_user(GL)
    assert calls_of(lab) == [USER], f"{status}: {calls_of(lab)}"
    assert any(t.strip() for t in texts(res)), f"{status}: нет причины в {res!r}"


def test_ac11_timeout_named_without_retry(lab):
    """Таймаут транспорта — именованная причина без исключения и без повтора.

    Сценарий: транспорт поднимает `TimeoutError`; `token_user`
    возвращает причину, транспорт вызван ровно один раз.

    Ловит мутацию: таймаут попадает в ветку повтора 5xx — транспорт
    вызван несколько раз.
    """
    lab.exc = TimeoutError("timed out")
    res = forge.token_user(GL)
    assert len(lab.calls) == 1, calls_of(lab)
    assert any(t.strip() for t in texts(res)), f"нет причины в {res!r}"


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_ac11_server_errors_retried_bounded(lab, status):
    """429/5xx повторяются ограниченное число раз и дают именованную причину.

    Сценарий: `GET /user` всегда отвечает кодом `status`; транспорт
    вызван не меньше двух и не больше двадцати раз, `token_user`
    возвращает причину; паузы повтора подменены и не ждут.

    Ловит мутацию: повтора на 429/5xx нет — один вызов; либо повтор без
    предела — шаг висит до таймаута теста.
    """
    lab.routes[USER] = [(status, {"message": f"{status}"})]
    res = forge.token_user(GL)
    assert 2 <= len(lab.calls) <= 20, f"{status}: вызовов {len(lab.calls)}"
    assert any(t.strip() for t in texts(res)), f"{status}: нет причины в {res!r}"


@pytest.mark.parametrize("status", [429, 503])
def test_ac11_retry_then_success(lab, status):
    """После 429/5xx повтор, получивший ответ 200, отдаёт разобранный ответ.

    Сценарий: первый ответ `GET /user` — `status`, второй — 200 с
    пользователем `robot-pult`; транспорт вызван дважды, в результате —
    имя пользователя.

    Ловит мутацию: повтор отправляется, но итог берётся с первого
    (ошибочного) ответа — имени пользователя в результате нет.
    """
    lab.routes[USER] = [(status, {"message": "busy"}), (200, {"id": 7, "username": "robot-pult"})]
    res = forge.token_user(GL)
    assert len(lab.calls) == 2, calls_of(lab)
    assert "robot-pult" in texts(res), repr(res)


def test_ac11_reasons_are_distinct(lab):
    """Причины 401, 403, 404, 429, 5xx и таймаута различаются между собой.

    Сценарий: `token_user` зовётся шесть раз — на 401, 403, 404, 429,
    500 и таймаут транспорта; тексты результатов попарно разные.

    Ловит мутацию: все ошибки HTTP сведены в одну причину «запрос не
    удался» — тексты совпадают.
    """
    found = {}
    for status in (401, 403, 404, 429, 500, "таймаут"):
        lab.routes.clear()
        lab.exc = TimeoutError("timed out") if status == "таймаут" else None
        if status != "таймаут":
            lab.routes[USER] = [(status, {"message": "error"})]
        found[status] = joined(forge.token_user(GL))
    assert len(set(found.values())) == len(found), found


# --- AC-12 ---

def test_ac12_token_absent_from_reasons_and_journal(initialized_tmp_root, lab):
    """Фикстурный токен не встречается в причинах ошибок и в журнале шагов.

    Сценарий: в песочнице пульта после `init` (БД со схемой) функции `forge` для GitLab получают
    401, 403, 404, 500, таймаут и отказ сети; токен дошёл до транспорта
    (он есть среди заголовков вызовов), но ни в одной строке
    результатов, ни в одной строке таблицы `steps` БД песочницы его нет.

    Ловит мутацию: причина 401/403 включает заголовки запроса (с
    `PRIVATE-TOKEN`) — токен виден в тексте причины.
    """
    results = []
    for status in (401, 403, 404, 500):
        lab.exc = None
        lab.routes = {USER: [(status, {"message": f"{status} Unauthorized"})],
                      ("GET", MR_PATH): [(status, {"message": f"{status} Unauthorized"})],
                      ("GET", f"/projects/{PID}/pipelines"): [(status, {"message": "x"})]}
        results += [forge.token_user(GL), forge.mr_status(GL, MR),
                    forge.pipeline_status(GL, SHA)]
    for exc in (TimeoutError("timed out"),
                urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))):
        lab.exc = exc
        results += [forge.token_user(GL), forge.protections(GL)]
    sent = [str(v) for c in lab.calls for v in c.headers.values()]
    assert TOKEN in sent, "токен не дошёл до транспорта — проверка была бы пустой"
    leaked = [t for res in results for t in texts(res) if TOKEN in t]
    assert leaked == [], leaked
    rows = [" ".join(str(v) for v in tuple(r)) for r in store.db().execute("SELECT * FROM steps")]
    assert [r for r in rows if TOKEN in r] == []


# --- AC-13 ---

def run(name: str, status: str, conclusion) -> dict:
    return {"name": name, "status": status, "conclusion": conclusion}


GH_VERDICT_CASES = {
    "все завершены зелёными исходами": (
        [run("a", "completed", "success"), run("b", "completed", "skipped"),
         run("c", "completed", "neutral")], "green"),
    "failure": ([run("a", "completed", "success"), run("b", "completed", "failure")], "red"),
    "cancelled": ([run("a", "completed", "success"), run("b", "completed", "cancelled")], "red"),
    "timed_out": ([run("a", "completed", "success"), run("b", "completed", "timed_out")], "red"),
    "in_progress": ([run("a", "completed", "success"), run("b", "in_progress", None)], "running"),
    "queued": ([run("a", "completed", "success"), run("b", "queued", None)], "running"),
    "пусто": ([], "none"),
    "action_required": (
        [run("a", "completed", "success"), run("b", "completed", "action_required")], "unknown"),
}


@pytest.mark.parametrize("case", list(GH_VERDICT_CASES) + ["чтение не удалось"])
def test_ac13_github_verdict_from_check_runs(lab, rng, case):
    """`pipeline_status` для `forge: github` берёт итог из `ci.check_runs` по правилу требования 2.

    Сценарий: подменённый `ci.check_runs` отдаёт набор runs (в случайном
    порядке) либо `(None, причина)`; итог — по таблице: зелёные исходы —
    `green`, `failure`/`cancelled`/`timed_out` — `red`, `queued`/
    `in_progress` — `running`, пусто — `none`, `action_required` и сбой
    чтения — `unknown`. Чтение check runs получило этот sha; ни `gh`, ни
    транспорт GitLab не вызваны.

    Ловит мутацию: обёртка отдаёт `green` на любом непустом ответе — на
    `failure`/`in_progress`/`action_required` итог `green`.
    """
    gen, seed = rng
    if case == "чтение не удалось":
        lab.check_runs_answer, expected = (None, "gh не ответил: код 1"), "unknown"
    else:
        runs, expected = GH_VERDICT_CASES[case]
        lab.check_runs_answer = (shuffled(gen, runs), "")
    res = forge.pipeline_status(GH, SHA)
    assert verdicts(res) == {expected}, f"зерно: {seed}; {case}: {res!r}"
    assert any(SHA in args or SHA in kwargs.values() for args, kwargs in lab.check_runs_calls), \
        f"{case}: ci.check_runs не спрошен о sha"
    assert lab.calls == [] and lab.gh_calls == [], f"{case}: {calls_of(lab)} {lab.gh_calls}"


@pytest.mark.parametrize("name", list(GH_CALLS))
def test_ac13_github_other_functions_refuse(lab, name):
    """Прочие функции `forge` для `forge: github` — отказ «не реализовано для github».

    Сценарий: функция зовётся по имени проекта `ghproj` (`forge:
    github`); в результате — «не реализовано для github»; ни `gh`, ни
    транспорт GitLab не вызваны.

    Ловит мутацию: реестр отдаёт для github реализацию GitLab — вызов
    уходит в транспорт GitLab; либо функция зовёт `gh`.
    """
    res = GH_CALLS[name]()
    assert "не реализовано для github" in joined(res), f"{name}: {res!r}"
    assert lab.calls == [] and lab.gh_calls == [], f"{name}: {calls_of(lab)} {lab.gh_calls}"


# --- AC-14 ---

def ci_scenario(fake: Lab, sha: str, verdict: str) -> None:
    if verdict == "green":
        fake.pipeline(700, "success", [job(1, "build", "success", "build"),
                                       job(2, "test", "success", "test")], sha=sha)
    elif verdict == "red":
        fake.pipeline(700, "failed", [job(1, "build", "success", "build"),
                                      job(2, "test", "failed", "test")], sha=sha)
    elif verdict == "running":
        fake.pipeline(700, "running", [job(1, "build", "success", "build"),
                                       job(2, "test", "running", "test")], sha=sha)
    elif verdict == "unknown":
        fake.pipeline(700, "canceled", [job(1, "build", "success", "build"),
                                        job(2, "test", "canceled", "test")], sha=sha)


@pytest.mark.parametrize("verdict, kind, is_red, branch_ok, kind_note, fragment, names", [
    ("green", "VERIFYING_GREEN", False, True, None, None, set()),
    ("red", "VERIFYING_RED", True, False, "red", None, {"test"}),
    ("running", "VERIFYING_RUNNING", False, False, "running", "ещё идёт", set()),
    ("none", "VERIFYING_NONE", False, False, "unknown", "неизвестен", None),
    ("unknown", "VERIFYING_NONE", False, False, "unknown", "неизвестен", None),
])
def test_ac14_ci_views_follow_table(lab, gl_clone, verdict, kind, is_red, branch_ok,
                                    kind_note, fragment, names):
    """Итог `pipeline_status` GitLab отображается в виды `ci` по таблице требования 8.

    Сценарий: клон проекта `glproj` (`forge: gitlab`), голова `main`
    читается его git; поддельный транспорт отдаёт для этого sha
    конвейер с итогом `green`/`red`/`running`/`none`/`unknown`.
    `verifying_status`, `verifying_is_red`, `red_status_sha`,
    `branch_status`, `status_kind` и `failed_check_names` дают значения
    строки таблицы; `gh` не вызван.

    Ловит мутацию: `unknown` отображается в `VERIFYING_GREEN` или
    `branch_status` = `True`; либо `running` даёт `failed_check_names`
    = `(None, …)` вместо пустого множества.
    """
    repo, sha = gl_clone
    ci_scenario(lab, sha, verdict)
    vkind, note = ci.verifying_status(config.MAIN_BRANCH, repo)
    ok, bnote = ci.branch_status(config.MAIN_BRANCH, repo)
    found, why = ci.failed_check_names(sha, repo)
    assert vkind == getattr(ci, kind), f"{verdict}: {vkind} {note}"
    assert ci.verifying_is_red(note) is is_red, f"{verdict}: {note}"
    if verdict == "red":
        assert f"CI коммита {sha[:8]} не зелёный:" in note, note
        assert ci.red_status_sha(note) == sha[:8], note
    assert ok is branch_ok, f"{verdict}: {bnote}"
    if kind_note is not None:
        assert ci.status_kind(bnote) == kind_note, f"{verdict}: {bnote}"
    if fragment is not None:
        assert fragment in bnote, f"{verdict}: {bnote}"
    if names is None:
        assert found is None and why, f"{verdict}: {found} {why}"
    else:
        assert found == names, f"{verdict}: {found} {why}"
    assert lab.gh_calls == [], lab.gh_calls


def test_ac14_head_sha_local(lab, gl_clone):
    """`ci.head_sha` для `forge: gitlab` читает голову в клоне, транспорт не вызван.

    Сценарий: клон проекта `glproj`; `ci.head_sha("main", клон)` отдаёт
    sha из файла ссылки ветки клона; поддельный транспорт не
    получил ни одного вызова; первые параметры `head_sha` — прежние
    `branch` и `repo` с умолчанием `None`.

    Ловит мутацию: голова ветки gitlab-проекта спрашивается у API
    (`GET …/repository/branches/main`) — в журнале транспорта вызов.
    """
    repo, sha = gl_clone
    got, why = ci.head_sha(config.MAIN_BRANCH, repo)
    assert got == sha and sha, f"{got!r} {why}"
    assert lab.calls == [], calls_of(lab)
    params = list(inspect.signature(ci.head_sha).parameters.values())
    assert [p.name for p in params[:2]] == ["branch", "repo"]
    assert params[1].default is None


# --- AC-15 ---

GL_UNSUPPORTED = "не поддержано для gitlab"


@pytest.mark.parametrize("name", ["main_line_status", "trigger_rerun", "trigger_rerun по run_id",
                                  "find_run_id", "check_run_workflow_run"])
def test_ac15_unsupported_ci_functions_refuse(lab, gl_clone, name):
    """`main_line_status`/`trigger_rerun`/`find_run_id`/`check_run_workflow_run` для gitlab — отказ без `gh` и HTTP.

    Сценарий: клон проекта `glproj` (`forge: gitlab`). В отказе —
    «не поддержано для gitlab»; `main_line_status` — вид
    `ci.MAIN_UNKNOWN`; `trigger_rerun` (без id прогона и с ним) — текст
    с «не запущен», `ci.rerun_started` на нём `False`; `find_run_id` и
    `check_run_workflow_run` — `("", причина)`. Ни `gh`, ни транспорт
    не вызваны.

    Ловит мутацию: функция для gitlab идёт прежним путём `gh` — шпион
    `gh` записал вызов; либо отказ `trigger_rerun` без «не запущен» —
    `rerun_started` отдаёт `True`.
    """
    repo, sha = gl_clone
    if name == "main_line_status":
        res = ci.main_line_status(sha, repo)
        assert res.kind == ci.MAIN_UNKNOWN, repr(res)
        assert GL_UNSUPPORTED in joined(res), repr(res)
    elif name.startswith("trigger_rerun"):
        note = ci.trigger_rerun(config.MAIN_BRANCH, "4242" if "run_id" in name else "", repo)
        assert GL_UNSUPPORTED in note and "не запущен" in note, note
        assert ci.rerun_started(note) is False, note
    else:
        res = (ci.find_run_id(sha, repo) if name == "find_run_id"
               else ci.check_run_workflow_run("555", repo))
        assert res[0] == "" and GL_UNSUPPORTED in res[1], repr(res)
    assert lab.gh_calls == [] and lab.calls == [], f"{lab.gh_calls} {calls_of(lab)}"


# --- AC-16 ---

@pytest.mark.parametrize("pipeline_status, jobs, expected", [
    ("failed", [("build", "success", "build"), ("test", "success", "test")], "red"),
    ("manual", [("build", "success", "build"), ("deploy", "manual", "deploy")], "green"),
    ("running", [("build", "success", "build"), ("test", "success", "test")], "running"),
])
def test_ac16_pipeline_own_status_counts(lab, rng, pipeline_status, jobs, expected):
    """Итог учитывает статус самого конвейера, а не только видимые задания.

    Сценарий: конвейер `failed` при всех видимых заданиях `success` —
    `red`; конвейер `manual` с заданиями `success` и `manual` — `green`;
    конвейер `running` при всех видимых `success` — `running`.

    Ловит мутацию: итог считается только по заданиям — `failed` и
    `running` конвейеры с зелёными видимыми заданиями дают `green`.
    """
    gen, seed = rng
    lab.pipeline(800, pipeline_status,
                 shuffled(gen, [job(801 + i, n, s, st) for i, (n, s, st) in enumerate(jobs)]))
    res = forge.pipeline_status(GL, SHA)
    assert verdicts(res) == {expected}, f"зерно: {seed}; {res!r}"


def test_ac16_red_without_failed_job_names_none(lab, gl_clone):
    """Красный конвейер без упавшего задания: `failed_check_names` — `(None, «краснота без упавшего задания»)`.

    Сценарий: клон `glproj`; у sha головы конвейер `failed`, все видимые
    задания `success`. `ci.failed_check_names` отдаёт `None` с причиной,
    содержащей «краснота без упавшего задания», а не пустое множество.

    Ловит мутацию: имена упавших собираются по заданиям без учёта
    статуса конвейера — пустое множество, «пересечения нет» в пользу
    повтора.
    """
    repo, sha = gl_clone
    lab.pipeline(810, "failed", [job(811, "build", "success", "build"),
                                 job(812, "test", "success", "test")], sha=sha)
    found, why = ci.failed_check_names(sha, repo)
    assert found is None and "краснота без упавшего задания" in why, f"{found} {why}"


# --- AC-18 ---

@pytest.mark.parametrize("name", GL_CALL_NAMES)
def test_ac18_network_down_reason(lab, name):
    """Отказ соединения (`URLError`) — причина «сеть недоступна: …», не исключение.

    Сценарий: транспорт поднимает `URLError(ConnectionRefusedError)`;
    каждая функция `forge` для GitLab возвращает результат, среди строк
    которого есть начинающаяся с «сеть недоступна:»; у
    `pipeline_status` итог `unknown`.

    Ловит мутацию: `URLError` не ловится — исключение вылетает из
    функции; либо `pipeline_status` на отказе сети отдаёт `none`.
    """
    lab.exc = urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))
    res = GL_CALLS[name]()
    assert any(t.startswith(NETWORK_DOWN) for t in texts(res)), f"{name}: {res!r}"
    if name == "pipeline_status":
        assert verdicts(res) == {"unknown"}, repr(res)


# --- AC-19 ---

@pytest.mark.parametrize("required, expected", [(["deploy"], "running"), (["build"], "green")])
def test_ac19_required_manual_job_running(lab, rng, required, expected):
    """Обязательное задание `manual` — `running`; то же задание вне обязательных — `green`.

    Сценарий: конвейер `manual`: `build`, `test` `success`, `deploy`
    `manual`; в `ci_required_jobs` записи — `deploy` (итог `running`)
    либо только `build` (итог `green`).

    Ловит мутацию: `manual` допускается всегда, без сверки с
    `ci_required_jobs`, — обязательный ручной деплой даёт `green`.
    """
    gen, seed = rng
    lab.records[GL] = gl_entry(ci_required_jobs=required)
    lab.pipeline(900, "manual", shuffled(gen, [
        job(901, "build", "success", "build"), job(902, "test", "success", "test"),
        job(903, "deploy", "manual", "deploy")]))
    res = forge.pipeline_status(GL, SHA)
    assert verdicts(res) == {expected}, f"зерно: {seed}; {required}: {res!r}"


# --- AC-20 ---

@pytest.mark.parametrize("jobs, green", [
    ([job(31, "publish", "created", "aa-publish"), job(22, "approve", "manual", "zz-approve"),
      job(13, "build", "success", "mm-build")], True),
    ([job(31, "deploy", "manual", "aa-deploy"), job(22, "publish", "created", "zz-publish"),
      job(13, "build", "success", "mm-build")], False),
])
def test_ac20_stage_order_by_smallest_id(lab, jobs, green):
    """Порядок стадий — по наименьшему id задания стадии, не по выдаче и не по имени.

    Сценарий: выдача заданий идёт по убыванию id; имена стадий подобраны
    так, что их алфавитный порядок обратен порядку по id. `manual` в
    стадии с меньшими id и `created` в стадии с большими (вне
    обязательных) — `green`; `created` в стадии с меньшими id и
    `manual` с большими — не `green`.

    Ловит мутацию: стадии упорядочены по порядку выдачи API или по
    имени — оба исхода меняются местами.
    """
    lab.records[GL] = gl_entry(ci_required_jobs=["build"])
    lab.pipeline(950, "manual", list(jobs))
    res = forge.pipeline_status(GL, SHA)
    found = verdicts(res)
    assert len(found) == 1, repr(res)
    assert ("green" in found) is green, repr(res)


# --- AC-22 ---

PRECEDENCE_CASES = {
    "failed и canceled": ("red", [("success", ["failed", "canceled"])], 0),
    "конвейер running, failed": ("red", [("running", ["failed", "success"])], 0),
    "конвейер canceled, failed": ("red", [("canceled", ["failed"])], 0),
    "failed при неполной выдаче": ("unknown", [("success", ["failed", "success"])], 1),
    "canceled и running": ("unknown", [("success", ["canceled", "running"])], 0),
    "конвейеры red и unknown": ("red", [("failed", ["failed"]), ("canceled", ["success"])], 0),
    "конвейеры unknown и running": ("unknown", [("canceled", ["success"]),
                                                ("running", ["running"])], 0),
    "конвейеры running и green": ("running", [("running", ["running"]),
                                              ("success", ["success"])], 0),
}


@pytest.mark.parametrize("case", list(PRECEDENCE_CASES))
def test_ac22_verdict_precedence(lab, rng, case):
    """Сочетания статусов следуют старшинству `red` → `unknown` → `running` → `none` → `green`.

    Сценарий: один или два конвейера sha с заданиями без права падать в
    сочетаниях AC-22 (`failed`+`canceled`, конвейер `running`/`canceled`
    с `failed`, `failed` при `X-Total` больше прочитанного,
    `canceled`+`running`, пары конвейеров `red`/`unknown`,
    `unknown`/`running`, `running`/`green`); id и порядок выдачи
    случайны. Итог — старший по таблице.

    Ловит мутацию: `unknown` поставлен старше `red` (или `running`
    старше `unknown`) — итог сочетания другой.
    """
    gen, seed = rng
    expected, pipes, bias = PRECEDENCE_CASES[case]
    lab.total_bias["jobs"] = bias
    ids = gen.sample(range(1100, 1200), len(pipes))
    for n, (pid, (status, statuses)) in enumerate(zip(ids, pipes)):
        lab.pipeline(pid, status, shuffled(gen, [
            job(5000 + 10 * n + i, f"job-{i}", s, f"stage-{i}") for i, s in enumerate(statuses)]))
    res = forge.pipeline_status(GL, SHA)
    assert verdicts(res) == {expected}, f"зерно: {seed}; {case}: {res!r}"


# --- AC-23 ---

@pytest.mark.parametrize("with_key", [True, False])
def test_ac23_record_from_loader(lab, rng, with_key):
    """Запись проекта — из загрузчика `targets.target`; ключ `ci_required_jobs` плоской записи решает итог.

    Сценарий: подменённый `targets.target("glproj")` отдаёт плоскую
    запись `forge: gitlab` с ключом `ci_required_jobs: ["deploy"]` либо
    без ключа; функции передаётся только имя проекта. Конвейер `manual`,
    `build`/`test` `success`, `deploy` `manual`: с ключом — не `green`,
    без ключа — `green`; загрузчик спрошен об имени проекта.

    Ловит мутацию: поле читается из вложенного `entry["policy"]` или из
    словаря-аргумента, а не из плоской записи загрузчика, — с ключом
    итог `green`.
    """
    gen, seed = rng
    lab.records[GL] = gl_entry(ci_required_jobs=["deploy"]) if with_key else gl_entry()
    lab.pipeline(960, "manual", shuffled(gen, [
        job(961, "build", "success", "build"), job(962, "test", "success", "test"),
        job(963, "deploy", "manual", "deploy")]))
    res = forge.pipeline_status(GL, SHA)
    found = verdicts(res)
    assert GL in lab.target_calls, lab.target_calls
    assert len(found) == 1 and ("green" in found) is (not with_key), f"зерно: {seed}; {res!r}"


# --- AC-24 ---

@pytest.mark.parametrize("draft", [True, False])
def test_ac24_open_mr(lab, rng, draft):
    """`open_mr` делает ровно `POST /projects/:id/merge_requests` с полями из аргументов.

    Сценарий: ветка со случайным именем, база `main`, заголовок,
    описание, исполнитель 42; ответ — MR с `iid` 37 и адресом. Вызов
    транспорта один, это `POST` по пути проекта из `url` записи; среди
    значений тела — ветка, база, заголовок (с `Draft: ` при `draft=True`,
    без него иначе), описание и исполнитель; в результате — 37 и адрес.

    Ловит мутацию: префикс `Draft: ` ставится всегда (или никогда) —
    заголовок в теле не тот.
    """
    gen, seed = rng
    branch = "task/" + "".join(gen.choice("abcdefgh0123") for _ in range(8))
    path = f"/projects/{PID}/merge_requests"
    title = f"Draft: {TITLE}" if draft else TITLE
    lab.routes[("POST", path)] = [(201, {"iid": MR, "web_url": MR_URL, "title": title,
                                         "draft": draft, "state": "opened"})]
    res = forge.open_mr(GL, branch, config.MAIN_BRANCH, TITLE, "Описание изменения", draft, 42)
    assert calls_of(lab) == [("POST", path)], f"зерно: {seed}; {calls_of(lab)}"
    sent = leaves(lab.calls[0].body)
    for value in (branch, config.MAIN_BRANCH, title, "Описание изменения", 42):
        assert value in sent, f"зерно: {seed}; в теле нет {value!r}: {lab.calls[0].body}"
    if not draft:
        assert not [v for v in sent if isinstance(v, str) and v.startswith("Draft:")], \
            lab.calls[0].body
    assert MR in leaves(res) and MR_URL in texts(res), repr(res)


# --- AC-25 ---

def test_ac25_undraft_mr(lab):
    """`undraft_mr` правит MR `PUT` с одним заголовком без префикса `Draft: `.

    Сценарий: текущий MR 37 — «Draft: <заголовок>»; ответ правки — MR без
    признака черновика. Единственный не-`GET` вызов — `PUT
    /projects/:id/merge_requests/37` с телом ровно `{"title": <заголовок
    без префикса>}`; в результате нет значения `True` и нет строки с
    «Draft:».

    Ловит мутацию: в тело правки уходит ещё и `state_event`/`draft` или
    заголовок с префиксом — тело не то; либо признак черновика берётся
    из прежнего MR — в результате `True`.
    """
    lab.routes[("GET", MR_PATH)] = [(200, {"iid": MR, "title": f"Draft: {TITLE}", "draft": True,
                                           "work_in_progress": True, "state": "opened"})]
    lab.routes[("PUT", MR_PATH)] = [(200, {"iid": MR, "title": TITLE, "draft": False,
                                           "work_in_progress": False, "state": "opened"})]
    res = forge.undraft_mr(GL, MR)
    writes = [c for c in lab.calls if c.method != "GET"]
    assert [(c.method, c.path) for c in writes] == [("PUT", MR_PATH)], calls_of(lab)
    assert writes[0].body == {"title": TITLE}, writes[0].body
    assert not any(v is True for v in leaves(res)), repr(res)
    assert not [t for t in texts(res) if t.startswith("Draft:")], repr(res)


# --- AC-26 ---

def test_ac26_assign_mr(lab):
    """`assign_mr` правит MR `PUT` с одним полем исполнителя.

    Сценарий: исполнитель 42; ответ — MR с исполнителем `reviewer-bob`
    (id 42). Единственный не-`GET` вызов — `PUT
    /projects/:id/merge_requests/37`, в теле ровно одно поле, его
    значение — 42; исполнитель ответа есть в результате.

    Ловит мутацию: в тело правки попадает заголовок или иное поле
    рядом с исполнителем — в теле больше одного поля.
    """
    lab.routes[("PUT", MR_PATH)] = [(200, {
        "iid": MR, "title": TITLE, "assignee": {"id": 42, "username": "reviewer-bob"},
        "assignees": [{"id": 42, "username": "reviewer-bob"}]})]
    res = forge.assign_mr(GL, MR, 42)
    writes = [c for c in lab.calls if c.method != "GET"]
    assert [(c.method, c.path) for c in writes] == [("PUT", MR_PATH)], calls_of(lab)
    body = writes[0].body
    assert isinstance(body, dict) and len(body) == 1, body
    assert [v for v in leaves(body) if not isinstance(v, str)] == [42], body
    assert "reviewer-bob" in texts(res) or 42 in leaves(res), repr(res)


# --- AC-27 ---

@pytest.mark.parametrize("state, draft, assignee", [
    ("opened", True, {"id": 42, "username": "reviewer-bob"}), ("merged", False, None)])
def test_ac27_mr_status(lab, state, draft, assignee):
    """`mr_status` читает `GET /projects/:id/merge_requests/:iid` и разбирает состояние, черновик, исполнителя.

    Сценарий: MR в состоянии `opened`, черновик, исполнитель
    `reviewer-bob`; либо `merged`, не черновик, без исполнителя. Вызов
    один — `GET` MR 37; в результате состояние, признак черновика
    (`True` только у черновика) и исполнитель.

    Ловит мутацию: признак черновика читается из префикса заголовка
    вместо поля `draft` — у черновика без префикса в заголовке `True`
    пропадает.
    """
    lab.routes[("GET", MR_PATH)] = [(200, {"iid": MR, "title": TITLE, "state": state,
                                           "draft": draft, "work_in_progress": draft,
                                           "assignee": assignee})]
    res = forge.mr_status(GL, MR)
    assert calls_of(lab) == [("GET", MR_PATH)], calls_of(lab)
    assert state in texts(res), repr(res)
    assert any(v is True for v in leaves(res)) is draft, repr(res)
    if assignee:
        assert "reviewer-bob" in texts(res) or 42 in leaves(res), repr(res)


# --- AC-28 ---

def test_ac28_token_user(lab):
    """`token_user` читает `GET /user` и отдаёт имя пользователя.

    Сценарий: ответ — пользователь `robot-pult`; вызов один — `GET
    /user`; имя есть в результате.

    Ловит мутацию: спрашивается иной путь (`/users`, `/projects/:id`) —
    вызов не тот, имени нет.
    """
    lab.routes[USER] = [(200, {"id": 7, "username": "robot-pult", "name": "Robot"})]
    res = forge.token_user(GL)
    assert calls_of(lab) == [USER], calls_of(lab)
    assert "robot-pult" in texts(res), repr(res)


# --- AC-29 ---

@pytest.mark.parametrize("expires_at", ["2026-12-31", None])
def test_ac29_token_expiry(lab, expires_at):
    """`token_expiry` читает `GET /personal_access_tokens/self`: дата или признак «без срока».

    Сценарий: ответ — токен с `expires_at` «2026-12-31» либо `null`.
    Вызов один; с датой — она в результате (строкой или `date`); с
    `null` — в результате текст «без срока» и нет даты.

    Ловит мутацию: `null` разбирается как ошибка разбора даты — вместо
    признака «без срока» причина сбоя.
    """
    path = ("GET", "/personal_access_tokens/self")
    lab.routes[path] = [(200, {"id": 3, "name": "pult", "expires_at": expires_at,
                               "active": True, "scopes": ["api"]})]
    res = forge.token_expiry(GL)
    assert calls_of(lab) == [path], calls_of(lab)
    if expires_at:
        assert expires_at in texts(res) or datetime.date(2026, 12, 31) in leaves(res), repr(res)
    else:
        assert "без срока" in joined(res), repr(res)
        assert "2026" not in joined(res), repr(res)


# --- AC-30 ---

def test_ac30_protections(lab):
    """`protections` читает защищённые ветки и теги и отдаёт их имена.

    Сценарий: защищённые ветки `main` и `release/*`, тег `v*`. Вызваны
    `GET /projects/:id/protected_branches` и `GET
    /projects/:id/protected_tags`; все три имени — в результате.

    Ловит мутацию: читаются только ветки — пути тегов нет среди вызовов,
    имени `v*` нет в результате.
    """
    lab.routes[("GET", f"/projects/{PID}/protected_branches")] = [
        (200, [{"id": 1, "name": "main"}, {"id": 2, "name": "release/*"}],
         {"X-Total": "2", "X-Total-Pages": "1", "X-Next-Page": ""})]
    lab.routes[("GET", f"/projects/{PID}/protected_tags")] = [
        (200, [{"name": "v*", "create_access_levels": []}],
         {"X-Total": "1", "X-Total-Pages": "1", "X-Next-Page": ""})]
    res = forge.protections(GL)
    assert set(calls_of(lab)) == {("GET", f"/projects/{PID}/protected_branches"),
                                  ("GET", f"/projects/{PID}/protected_tags")}, calls_of(lab)
    for name in ("main", "release/*", "v*"):
        assert name in texts(res), f"{name}: {res!r}"
