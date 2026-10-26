"""Строки `doctor` для записи `forge: gitlab` (сверка базовой ветки, срок токена) и команда `artel.py forge-probe` на подменённом транспорте `gitlab_adapter`.

Группа: долгоживущий
Красен до реализации: `check_base_branch` для gitlab отдаёт `skip` «сверка не реализована» без запроса к API, строки срока токена у `doctor` нет, команды `forge-probe` нет в диспетчере `artel.py` (вывод — справка, транспорт не вызван), а в `check_base_branch` стоит литерал `"github"`; сверка базы без токена (`skip`, транспорт не вызван) зелена с рождения — сегодняшний `skip` для gitlab к транспорту не ходит.

Связка, которую держит файл: «запись проекта в `targets.yaml` песочницы —
`doctor`/`artel.py` — `forge` — `gitlab_adapter.request` — транспорт». Песочница — `initialized_tmp_root`
(пути `config` во временном каталоге, БД со схемой, связка ключей —
`tests.sandbox.fake_keychain_token`, признак роли снят); внешние процессы,
кроме локальных, получают отказ запуска (тот же приём, что у долгоживущего
теста строки `project-support-<проект>`). Сервер GitLab — подмена
публичной точки `gitlab_adapter.transport(method, url, headers, body,
timeout)` (контракт части 1): ответ `(код, заголовки, тело bytes)`, сеть
недоступна — `urllib.error.URLError`; пауза повтора адаптера не ждёт
(ссылка адаптера на `time` — `tests.sandbox.TimeWithSleep`).

Строка `doctor` о сроке токена находится поведением, без имени: из двух
прогонов `doctor.all_checks` (срок через 1 день и через 200 дней) это
строка, которая `warn` только в первом. «Сегодня» реализации может
считаться по местному времени или по UTC — сроки у порога отсчитываются так,
чтобы ожидание держалось при любом из двух.

Имена проектов, ветки, пользователи, уровни доступа, задания и счётчики
порождаются модулем `random` при каждом запуске; зерно печатается и входит
в текст провала.
"""
import ast
import collections
import contextlib
import datetime
import importlib
import inspect
import io
import json
import math
import os
import random
import re
import subprocess
import sys
import urllib.error
import urllib.parse
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (artel, config, doctor, forge, gitlab_adapter, idgen,
                          keychain, store)
from tests.sandbox import TimeWithSleep, artel_target_entry, fake_keychain_token

LETTERS = "abcdefghijkmnopqrstuvwxyz"
NETWORK_GIT = {"clone", "fetch", "push", "pull", "ls-remote"}
LEVEL_NAMES = {10: "guest", 20: "reporter", 30: "developer", 40: "maintainer",
               50: "owner"}
NOT_KILLED = ["in_dev", "review", "tests_writing", "done", "escalated", "spec_audit"]


# --- окружение сценария ---

def word(rng: random.Random, prefix: str, size: int = 7) -> str:
    return prefix + "".join(rng.choice(LETTERS) for _ in range(size))


def flat_entry(name: str, record: dict) -> str:
    lines = [f"  {name}:"]
    lines += [f"    {key}: {value}" for key, value in record.items()]
    lines += ["    no_paths: []", "    project_skills: []", "    merge_gate: operator"]
    return "\n".join(lines) + "\n"


def write_targets(records: dict) -> None:
    """`targets.yaml` песочницы: артель и плоские записи `records`."""
    text = "targets:\n" + artel_target_entry()
    text = text.rstrip("\n") + "\n" + "".join(flat_entry(n, r) for n, r in records.items())
    config.TARGETS.write_text(text, encoding="utf-8")


def local_command(argv) -> bool:
    """Локальный процесс песочницы: `ps`, интерпретатор Python, git без сети."""
    if not isinstance(argv, (list, tuple)) or not argv:
        return False
    words = [os.fsdecode(a) for a in argv]
    name = Path(words[0]).name
    if name == "git":
        return not NETWORK_GIT & set(words[1:])
    return name == "ps" or name.startswith("python") or words[0] == sys.executable


class Api:
    """Поддельный GitLab API v4 одного проекта: записывает каждый вызов."""

    def __init__(self, project_path: str, rng: random.Random):
        self.pid = urllib.parse.quote(project_path, safe="")
        self.calls: list = []
        self.user = word(rng, "u_")
        self.level = rng.choice(sorted(LEVEL_NAMES))
        self.default_branch = config.MAIN_BRANCH
        self.expires_at: str | None = None
        self.status: int | None = None
        self.exc: BaseException | None = None
        self.branches: list = []
        self.tags: list = []
        self.pipelines: list = []
        self.jobs: dict = {}
        self.reports: dict = {}

    def sleep(self, seconds) -> None:
        """Пауза повтора адаптера — без ожидания."""

    def transport(self, method, url, headers=None, body=None, timeout=None, *args, **kwargs):
        parts = urllib.parse.urlsplit(url)
        path = re.sub("%2f", "%2F", parts.path)
        if path.startswith("/api/v4"):
            path = path[len("/api/v4"):]
        query = dict(urllib.parse.parse_qsl(parts.query))
        self.calls.append((str(method).upper(), path, query, dict(headers or {})))
        if self.exc is not None:
            raise self.exc
        if self.status is not None:
            extra = {"Location": "https://localhost/elsewhere"} if 300 <= self.status < 400 else {}
            return self.reply(self.status, {"message": f"{self.status}"}, extra)
        return self.route(str(method).upper(), path, query)

    @staticmethod
    def reply(status: int, payload, headers=None) -> tuple:
        head = {"Content-Type": "application/json"}
        head.update(headers or {})
        return status, head, json.dumps(payload).encode("utf-8")

    def page(self, items: list, query: dict) -> tuple:
        number = max(1, int(query.get("page") or 1))
        per = max(1, min(int(query.get("per_page") or 20), 100))
        pages = max(1, math.ceil(len(items) / per))
        return self.reply(200, items[(number - 1) * per: number * per], {
            "X-Total": str(len(items)), "X-Total-Pages": str(pages),
            "X-Next-Page": str(number + 1) if number < pages else ""})

    def route(self, method: str, path: str, query: dict) -> tuple:
        project = f"/projects/{self.pid}"
        if method != "GET":
            return self.reply(405, {"message": "405 Method Not Allowed"})
        if path == "/user":
            return self.reply(200, {"id": 7, "username": self.user})
        if path == "/personal_access_tokens/self":
            return self.reply(200, {"id": 3, "name": "pult", "active": True,
                                    "expires_at": self.expires_at})
        if path == project:
            return self.reply(200, {"id": 11, "default_branch": self.default_branch,
                                    "permissions": {"project_access": {"access_level": self.level},
                                                    "group_access": None}})
        if path == f"{project}/protected_branches":
            return self.page([{"id": i, "name": n} for i, n in enumerate(self.branches, 1)], query)
        if path == f"{project}/protected_tags":
            return self.page([{"name": n} for n in self.tags], query)
        if path == f"{project}/pipelines":
            items = [p for p in self.pipelines
                     if p["sha"] == query.get("sha", p["sha"])
                     and p["ref"] == query.get("ref", p["ref"])]
            items.sort(key=lambda p: p["id"], reverse=query.get("sort") != "asc")
            return self.page(items, query)
        found = re.fullmatch(rf"{re.escape(project)}/pipelines/(\d+)/(jobs|test_report)", path)
        if found and found.group(2) == "jobs" and int(found.group(1)) in self.jobs:
            return self.page(self.jobs[int(found.group(1))], query)
        if found and found.group(2) == "test_report" and int(found.group(1)) in self.reports:
            return self.reply(200, self.reports[int(found.group(1))])
        return self.reply(404, {"message": "404 Not Found"})

    def pipeline(self, pid: int, sha: str, ref: str, status: str, jobs: list) -> None:
        self.pipelines.append({"id": pid, "iid": pid, "sha": sha, "ref": ref,
                               "status": status, "source": "push"})
        self.jobs[pid] = jobs


class Scene:
    """Проект `forge: gitlab` в песочнице: имя, слот токена, записи, сервер."""

    def __init__(self, rng: random.Random, seed: int):
        self.rng = rng
        self.seed = seed
        self.name = word(rng, "gl")
        group = word(rng, "grp", 4)
        self.slot = f"{self.name}-token"
        self.token = fake_keychain_token(self.slot)
        self.records = {self.name: {"forge": "gitlab",
                                    "url": f"https://localhost/{group}/{self.name}",
                                    "base": config.MAIN_BRANCH,
                                    "token_slot": self.slot}}
        self.api = Api(f"{group}/{self.name}", rng)
        self.save()

    def save(self) -> None:
        write_targets(self.records)

    def entry(self) -> dict:
        return dict(self.records[self.name])


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def pult(initialized_tmp_root):
    """Песочница с проинициализированным корнем; внешние процессы не запускаются."""
    real_run, real_popen = subprocess.run, subprocess.Popen

    def run(argv, *args, **kwargs):
        if local_command(argv):
            return real_run(argv, *args, **kwargs)
        empty = b"" if not (kwargs.get("text") or kwargs.get("encoding")
                            or kwargs.get("universal_newlines")) else ""
        return subprocess.CompletedProcess(argv, 127, empty, empty)

    def popen(argv, *args, **kwargs):
        if local_command(argv):
            return real_popen(argv, *args, **kwargs)
        raise FileNotFoundError(f"песочница: внешний процесс {argv!r} не запускается")

    with mock.patch.object(subprocess, "run", run), \
            mock.patch.object(subprocess, "Popen", popen):
        yield initialized_tmp_root


@pytest.fixture
def scene(pult, monkeypatch, seed):
    """Запись `forge: gitlab` объявлена, транспорт и пауза адаптера подменены."""
    made = Scene(random.Random(seed), seed)
    monkeypatch.setattr(gitlab_adapter, "transport", made.api.transport)
    monkeypatch.setattr(gitlab_adapter, "time", TimeWithSleep(made.api.sleep))
    return made


def cli(*args: str) -> tuple[str, int]:
    """`artel.py <args>`: (весь вывод вместе с текстом выхода, код выхода)."""
    buf = io.StringIO()
    code = 0
    with mock.patch.object(sys, "argv", ["artel.py", *args]), \
            contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            artel.main()
        except SystemExit as exc:
            code = exc.code or 0
            if isinstance(code, str):
                buf.write(f"\n{code}")
                code = 1
    return buf.getvalue(), code


def shown(checks) -> str:
    return "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks)


def today_bounds() -> tuple[datetime.date, datetime.date]:
    """(раньшее, позднее) из местной даты и даты UTC."""
    local = datetime.date.today()
    utc = datetime.datetime.now(datetime.timezone.utc).date()
    return min(local, utc), max(local, utc)


def expiry_line_names(sc: Scene) -> list:
    """Имена строк `doctor`, которые `warn` при сроке токена через 1 день и не
    `warn` при сроке через 200 дней, — строка срока токена."""
    early, late = today_bounds()
    sc.api.expires_at = (early + datetime.timedelta(days=1)).isoformat()
    near = collections.Counter(c.name for c in doctor.all_checks(store.db())
                               if c.status == "warn")
    sc.api.expires_at = (late + datetime.timedelta(days=200)).isoformat()
    far = collections.Counter(c.name for c in doctor.all_checks(store.db())
                              if c.status == "warn")
    return sorted(n for n in near if near[n] > far.get(n, 0))


def add_tasks(target: str, count: int, rng: random.Random, state: str | None = None) -> None:
    conn = store.db()
    for _ in range(count):
        task_id = idgen.new_task_id()
        store.insert_task(conn, task_id, "Задача сценария", state or rng.choice(NOT_KILLED),
                          f"task/{task_id.lower()}-x", target, config.DEFAULT_BUDGET_USD)


# --- AC-1 ---

FAILURES = ["ответ получен", "401", "сеть недоступна"]


def set_failure(api: Api, kind: str) -> None:
    if kind == "401":
        api.status = 401
    elif kind == "сеть недоступна":
        api.exc = urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))


@pytest.mark.parametrize("kind", FAILURES)
def test_ac1_token_absent_from_doctor_and_forge_probe_output(scene, kind):
    """Токен песочницы, ушедший в заголовке запроса, не печатается ни `doctor`, ни `forge-probe`.

    Сценарий: запись `forge: gitlab` со слотом токена; связка ключей
    песочницы отдаёт `fake_keychain_token(<слот>)`. Сервер отвечает
    успешно, кодом 401 или сеть недоступна. `artel.py doctor` и
    `artel.py forge-probe <проект> --job <имя>` отрабатывают; хотя бы один
    вызов транспорта за каждую команду нёс этот токен (значит, команда его
    получила), а в выводе команды (stdout и stderr) значения токена нет.

    Ловит мутацию: `forge-probe` печатает заголовки запроса или запись с
    токеном; строка `doctor` о сроке токена/сверке базы собирает причину
    из заголовков (`PRIVATE-TOKEN`) — токен появится в выводе; `doctor` или
    `forge-probe` не ходит в GitLab вовсе — транспорт не увидит токена.
    """
    sc = scene
    sc.api.expires_at = (datetime.date.today() + datetime.timedelta(days=90)).isoformat()
    sc.api.pipeline(5, "a" * 40, config.MAIN_BRANCH, "success",
                    [{"id": 50, "name": "test", "stage": "test", "status": "success",
                      "allow_failure": False}])
    set_failure(sc.api, kind)
    for args in (("doctor",), ("forge-probe", sc.name, "--job", "test")):
        start = len(sc.api.calls)
        out, code = cli(*args)
        note = f"зерно: {sc.seed}; {kind}; {' '.join(args)}; код {code}\n{out}"
        sent = [c for c in sc.api.calls[start:] if sc.token in c[3].values()]
        assert sent, note
        assert sc.token not in out, note


# --- AC-2 ---

@pytest.mark.parametrize("same", [True, False], ids=["совпадает", "расходится"])
def test_ac2_base_branch_compared_with_default_branch(scene, same):
    """База записи сверяется с `default_branch` проекта: совпадение — `ok`, расхождение — `warn`.

    Сценарий: запись `forge: gitlab` со случайной базой; сервер на
    `GET /projects/:id` отдаёт `default_branch`, равный базе либо другой
    случайной ветке. `doctor.check_base_branch(<проект>, <запись>)` даёт
    `ok` или `warn` соответственно, а транспорт получил запрос сведений
    именно этого проекта.

    Ловит мутацию: для gitlab остался `skip` «сверка не реализована»;
    сравнение перевёрнуто (`==` вместо `!=`) — статусы поменяются местами;
    сверка берёт `config.MAIN_BRANCH` вместо `base` записи или ветку
    защиты вместо `default_branch` — исход не зависит от ответа сервера.
    """
    sc = scene
    base = word(sc.rng, "base-")
    sc.records[sc.name]["base"] = base
    sc.save()
    sc.api.default_branch = base if same else word(sc.rng, "trunk-")
    check = doctor.check_base_branch(sc.name, sc.entry())
    note = f"зерно: {sc.seed}; база {base}; у сервера {sc.api.default_branch}; {check}"
    assert check.status == ("ok" if same else "warn"), note
    assert ("GET", f"/projects/{sc.api.pid}") in [c[:2] for c in sc.api.calls], note


# Слот токена в связке ключей пуст: пустая строка или `None` (поле
# `token_slot` у записи внешнего проекта обязательно — без него запись не
# читается вовсе).
NO_TOKEN = {"слот пуст": "", "слота нет в связке": None}


@pytest.mark.parametrize("how", list(NO_TOKEN))
def test_ac2_base_branch_without_token_skips_without_transport(scene, monkeypatch, how):
    """Без токена сверка базы — `skip` с непустой причиной, транспорт не вызван.

    Сценарий: слот токена записи `forge: gitlab` в связке ключей песочницы
    пуст (`""` либо `None`). `doctor.check_base_branch` возвращает `skip`,
    его текст непуст, поддельный сервер не получил ни одного вызова.

    Ловит мутацию: запрос уходит без заголовка токена (транспорт вызван);
    отсутствие токена превращено в `warn`/`fail` или `ok` с пустой причиной.
    """
    sc = scene
    monkeypatch.setattr(keychain, "token", lambda slot: NO_TOKEN[how])
    check = doctor.check_base_branch(sc.name, sc.entry())
    note = f"зерно: {sc.seed}; {how}; {check}; вызовы {sc.api.calls}"
    assert check.status == "skip", note
    assert check.detail.strip(), note
    assert sc.api.calls == [], note


# --- AC-3 ---

def expiry_line(sc: Scene) -> tuple[list, str]:
    """(имена строк срока токена, текст провала со всеми строками `doctor`)."""
    names = expiry_line_names(sc)
    note = (f"зерно: {sc.seed}; строки срока токена: {names}\n"
            f"{shown(doctor.all_checks(store.db()))}")
    return names, note


def test_ac3_expiry_within_threshold_warns(scene):
    """Срок токена через `TOKEN_EXPIRY_WARN_DAYS` дней или меньше — `warn`, в том числе ровно на пороге.

    Сценарий: сервер на `GET /personal_access_tokens/self` отдаёт
    `expires_at` ровно через порог и через случайное число дней от 1 до
    порога. Строка срока токена `doctor` в обоих случаях — `warn`.

    Ловит мутацию: строгое `<` вместо `<=` — срок ровно на пороге даст не
    `warn`; порог зашит иным числом, меньшим константы адаптера.
    """
    sc = scene
    early, _late = today_bounds()
    days = gitlab_adapter.TOKEN_EXPIRY_WARN_DAYS
    names, note = expiry_line(sc)
    assert len(names) == 1, note
    for ahead in (days, sc.rng.randint(1, days)):
        sc.api.expires_at = (early + datetime.timedelta(days=ahead)).isoformat()
        line = [c for c in doctor.all_checks(store.db()) if c.name == names[0]]
        note = f"{note}\nсрок через {ahead} дн.: {line}"
        assert len(line) == 1 and line[0].status == "warn", note


def test_ac3_expiry_beyond_threshold_not_warn(scene):
    """Срок токена дальше `TOKEN_EXPIRY_WARN_DAYS` дней — строка не `warn`.

    Сценарий: `expires_at` через порог + 1 день и через случайное число
    дней дальше порога. Строка срока токена есть и не `warn`.

    Ловит мутацию: сравнение перевёрнуто или порог завышен (например, 30
    дней) — дальний срок даст `warn`.
    """
    sc = scene
    _early, late = today_bounds()
    days = gitlab_adapter.TOKEN_EXPIRY_WARN_DAYS
    names, note = expiry_line(sc)
    assert len(names) == 1, note
    for ahead in (days + 1, sc.rng.randint(days + 2, days + 400)):
        sc.api.expires_at = (late + datetime.timedelta(days=ahead)).isoformat()
        line = [c for c in doctor.all_checks(store.db()) if c.name == names[0]]
        assert len(line) == 1 and line[0].status != "warn", f"{note}\nсрок через {ahead} дн.: {line}"


# (задач проекта не-killed, killed задач проекта, задач артели, ждём warn)
def no_expiry_counts(kind: str, rng: random.Random, limit: int) -> tuple:
    if kind == "порог - 1":
        return limit - 1, 0, 0, False
    if kind == "меньше порога":
        return rng.randint(0, limit - 1), 0, 0, False
    if kind == "ровно порог":
        return limit, 0, 0, True
    if kind == "не меньше порога":
        return rng.randint(limit, limit + 15), 0, 0, True
    if kind == "killed не в счёт":
        mine = rng.randint(0, limit - 1)
        return mine, rng.randint(limit - mine, limit - mine + 5), 0, False
    mine = rng.randint(0, limit - 1)
    return mine, 0, rng.randint(limit - mine, limit - mine + 5), False


@pytest.mark.parametrize("kind", ["порог - 1", "меньше порога", "ровно порог",
                                  "не меньше порога", "killed не в счёт",
                                  "другой проект не в счёт"])
def test_ac3_no_expiry_depends_on_project_task_count(scene, kind):
    """Токен без срока: `warn` от `TOKEN_NO_EXPIRY_TASKS_WARN` задач проекта (не `killed`), иначе информационная строка `ok`.

    Сценарий: сервер отдаёт `expires_at: null`. В БД пульта — задачи
    проекта в состояниях кроме `killed` (порог − 1, случайно меньше
    порога, ровно порог, случайно не меньше порога), либо меньше порога
    живых задач проекта и столько `killed`-задач проекта, что вместе с ними
    набирается порог, либо меньше порога задач проекта и столько задач
    артели, что всех задач не меньше порога. Строка срока токена — `warn`
    ровно в случаях «не меньше порога» задач проекта не-`killed`, иначе
    `ok` (информационная).

    Ловит мутацию: строгое `>` вместо `>=` (ровно порог — не `warn`);
    счёт всех задач без фильтра проекта или вместе с `killed` (информационная
    строка станет `warn`); токен без срока даёт `warn` всегда или никогда.
    """
    sc = scene
    limit = gitlab_adapter.TOKEN_NO_EXPIRY_TASKS_WARN
    mine, killed, other, warns = no_expiry_counts(kind, sc.rng, limit)
    names, note = expiry_line(sc)
    assert len(names) == 1, note
    add_tasks(sc.name, mine, sc.rng)
    add_tasks(sc.name, killed, sc.rng, state="killed")
    add_tasks(config.DEFAULT_TARGET, other, sc.rng)
    sc.api.expires_at = None
    line = [c for c in doctor.all_checks(store.db()) if c.name == names[0]]
    note = (f"{note}\nбез срока; задач проекта {mine}, killed {killed}, "
            f"артели {other}: {line}")
    assert len(line) == 1, note
    assert line[0].status == ("warn" if warns else "ok"), note


@pytest.mark.parametrize("how", list(NO_TOKEN))
def test_ac3_no_token_skips_with_reason(scene, monkeypatch, how):
    """Без токена строка срока токена — `skip` с непустой причиной.

    Сценарий: строка найдена прогоном с токеном; затем слот токена записи
    в связке ключей песочницы становится пустым (`""` либо `None`). Строка
    срока токена — `skip`, её текст непуст.

    Ловит мутацию: отсутствие токена даёт `warn`/`fail` или `ok`
    (например, «без срока» по пустому ответу); строка без токена пропадает.
    """
    sc = scene
    names, note = expiry_line(sc)
    assert len(names) == 1, note
    monkeypatch.setattr(keychain, "token", lambda slot: NO_TOKEN[how])
    line = [c for c in doctor.all_checks(store.db()) if c.name == names[0]]
    note = f"{note}\n{how}: {line}"
    assert len(line) == 1 and line[0].status == "skip", note
    assert line[0].detail.strip(), note


ERRORS = ["сеть недоступна", "401", "403", "404", "429", "500", "502", "503",
          "301", "302", "не https"]


@pytest.mark.parametrize("kind", ERRORS)
def test_ac3_request_error_skips_with_adapter_reason(scene, kind):
    """Ошибка запроса с токеном — строка срока токена `skip` с причиной адаптера, не `warn` и не `fail`.

    Сценарий: строка найдена прогоном с рабочим сервером; затем сервер
    недоступен (`URLError`), отвечает кодом 401/403/404, 429 или 5xx на
    каждую попытку, перенаправлением 301/302, либо схема адреса записи —
    не https.
    Строка срока токена — `skip`, и в её тексте — причина, которую на тот
    же запрос даёт `forge.token_expiry(<проект>)`.

    Ловит мутацию: ошибка запроса превращена в `warn` или `fail`; ответ
    без срока по ошибке принят за «токен без срока» (`ok`/`warn`); причина
    адаптера заменена общим текстом без неё.
    """
    sc = scene
    names, note = expiry_line(sc)
    assert len(names) == 1, note
    if kind == "сеть недоступна":
        sc.api.exc = urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))
    elif kind == "не https":
        sc.records[sc.name]["url"] = sc.records[sc.name]["url"].replace("https://", "http://")
        sc.save()
    else:
        sc.api.status = int(kind)
    expected = forge.token_expiry(sc.name).reason
    line = [c for c in doctor.all_checks(store.db()) if c.name == names[0]]
    note = f"{note}\n{kind}: причина адаптера {expected!r}; {line}"
    assert expected, note
    assert len(line) == 1 and line[0].status == "skip", note
    assert expected in line[0].detail, note


def test_ac3_github_record_has_no_expiry_line(scene):
    """У записи `forge: github` строки срока токена нет.

    Сценарий: рядом с записью `forge: gitlab` объявлена запись
    `forge: github` со случайным именем и слотом токена. Строка срока
    токена gitlab-проекта найдена; строк с тем же именем ровно одна, и нет
    строки того же имени с проектом github на месте проекта gitlab.

    Ловит мутацию: строка срока токена строится для каждой записи — у
    github она появится (`skip` «не реализовано для github» или иная).
    """
    sc = scene
    gh = word(sc.rng, "gh")
    sc.records[gh] = {"forge": "github", "url": f"https://localhost/acme/{gh}",
                      "base": config.MAIN_BRANCH, "token_slot": f"{gh}-token"}
    sc.save()
    names = expiry_line_names(sc)
    checks = doctor.all_checks(store.db())
    note = f"зерно: {sc.seed}; github {gh}; строки срока токена: {names}\n{shown(checks)}"
    assert len(names) == 1, note
    assert [c.name for c in checks].count(names[0]) == 1, note
    if sc.name in names[0]:
        assert names[0].replace(sc.name, gh) not in [c.name for c in checks], note


# --- AC-4 ---

def probe_scene(sc: Scene) -> dict:
    """Конвейеры, задания и отчёт для `forge-probe`: два конвейера базовой
    ветки (последний — наибольший id) и более свежий конвейер чужой ветки."""
    rng, api = sc.rng, sc.api
    job = word(rng, "job-", 5)
    others = [word(rng, "j-", 5) for _ in range(rng.randint(1, 3))]
    old_sha, last_sha, foreign_sha = ("%040x" % rng.getrandbits(160) for _ in range(3))
    old_id = rng.randint(100, 500)
    last_id = old_id + rng.randint(1, 50)
    red = rng.random() < 0.5

    def jobs(first: int, failing: bool) -> list:
        names = [job, *others]
        return [{"id": first + i, "name": n, "stage": "test",
                 "status": "failed" if failing and n == others[0] else "success",
                 "allow_failure": False} for i, n in enumerate(names)]

    api.pipeline(old_id, old_sha, config.MAIN_BRANCH, "success", jobs(old_id * 10, False))
    api.pipeline(last_id, last_sha, config.MAIN_BRANCH, "failed" if red else "success",
                 jobs(last_id * 10, red))
    api.pipeline(last_id + 7, foreign_sha, word(rng, "feature-"), "success",
                 jobs((last_id + 7) * 10, False))
    # Счётчики не кратны 10 — не совпадают с числом уровня доступа.
    counts = dict(zip(["success", "failed", "skipped", "error"],
                      rng.sample([n for n in range(11, 60) if n % 10], 4)))
    cases = [{"classname": f"suite.{outcome}", "name": f"t{i}", "status": outcome}
             for outcome, n in counts.items() for i in range(n)]
    api.reports[last_id] = {"test_suites": [{"name": job, "test_cases": cases}]}
    old_cases = [{"classname": "old", "name": f"t{i}", "status": "success"} for i in range(3)]
    api.reports[old_id] = {"test_suites": [{"name": job, "test_cases": old_cases}]}
    api.branches = [word(rng, "rel-", 4) for _ in range(rng.randint(1, 3))]
    api.tags = [word(rng, "v-", 4) for _ in range(rng.randint(1, 3))]
    level = re.compile(rf"\b{api.level}\b")
    expiry = datetime.date.today() + datetime.timedelta(days=rng.randint(30, 700))
    # Дата срока без числа уровня доступа — иначе уровень «найдётся» в дате.
    while level.search(expiry.isoformat()) or level.search(expiry.strftime("%d.%m.%Y")):
        expiry += datetime.timedelta(days=1)
    api.expires_at = expiry.isoformat()
    return {"job": job, "jobs": [job, *others], "old_sha": old_sha,
            "last_sha": last_sha, "counts": counts, "expiry": expiry}


def test_ac4_forge_probe_prints_hosting_summary(scene):
    """`forge-probe <проект> --job <имя>` печатает пользователя, доступ, срок, защиты, последний конвейер базы и сводку отчёта по его sha.

    Сценарий: запись `forge: gitlab` (хостинг вне `SUPPORTED_FORGES`).
    Сервер отдаёт пользователя токена, уровень доступа, срок токена,
    защищённые ветки и теги, два конвейера базовой ветки и более свежий
    конвейер чужой ветки; у задания есть отчёты тестов в обоих конвейерах
    базы. Команда выходит с кодом 0; в выводе — имя пользователя, уровень
    доступа (числом или названием роли), дата срока, имена защищённых веток
    и тегов, sha, итог и задания конвейера, который вернул
    `forge.branch_pipeline`, число тестов каждого исхода из отчёта
    последнего конвейера. Отчёт запрошен по sha последнего конвейера
    базы, по sha прежнего — нет. Все вызовы транспорта — `GET`.

    Ловит мутацию: отчёт читается по sha головы ветки клона или по первому
    конвейеру в выдаче (прежний sha в запросах); `forge-probe` не печатает
    защиты или сводку; команда отказывает записи неподдержанного хостинга
    (код выхода не 0); проба зовёт меняющий метод (`POST`/`PUT`).
    """
    sc = scene
    plan = probe_scene(sc)
    out, code = cli("forge-probe", sc.name, "--job", plan["job"])
    pipeline = forge.branch_pipeline(sc.name, config.MAIN_BRANCH)
    note = (f"зерно: {sc.seed}; код {code}; конвейер {pipeline}; план {plan}\n"
            f"вызовы {[c[:3] for c in sc.api.calls]}\n{out}")
    assert code == 0, note
    assert pipeline.sha == plan["last_sha"], note
    assert sc.api.user in out, note
    level = sc.api.level
    assert (re.search(rf"\b{level}\b", out)
            or LEVEL_NAMES[level] in out.lower()), note
    expiry = plan["expiry"]
    assert expiry.isoformat() in out or expiry.strftime("%d.%m.%Y") in out, note
    for name in sc.api.branches + sc.api.tags:
        assert name in out, note
    assert pipeline.sha[:8] in out, note
    assert re.search(rf"\b{pipeline.verdict}\b", out), note
    for name in plan["jobs"]:
        assert name in out, note
    for outcome, n in plan["counts"].items():
        assert re.search(rf"\b{outcome}\b\W{{0,4}}{n}\b|\b{n}\W{{0,4}}{outcome}\b", out), \
            f"{outcome}={n}; {note}"
    sha_queries = {c[2].get("sha") for c in sc.api.calls if c[2].get("sha")}
    assert plan["last_sha"] in sha_queries, note
    assert plan["old_sha"] not in sha_queries, note
    assert sc.api.calls and {c[0] for c in sc.api.calls} == {"GET"}, note


def test_ac4_forge_probe_without_base_pipeline_names_reason(scene):
    """У базовой ветки нет конвейера — вместо сводки отчёта `forge-probe --job` печатает именованную причину.

    Сценарий: у сервера есть только конвейер чужой ветки. Команда
    `forge-probe <проект> --job <имя>` не запрашивает отчёт тестов, а в
    выводе — причина `forge.branch_pipeline` для базы (или слова «нет
    конвейер…»). Все вызовы транспорта — `GET`.

    Ловит мутацию: без конвейера базы отчёт берётся по последнему
    конвейеру любой ветки (запрос `test_report` есть); причина не
    печатается — сводка молча пропущена.
    """
    sc = scene
    plan = probe_scene(sc)
    sc.api.pipelines = [p for p in sc.api.pipelines if p["ref"] != config.MAIN_BRANCH]
    out, code = cli("forge-probe", sc.name, "--job", plan["job"])
    reason = forge.branch_pipeline(sc.name, config.MAIN_BRANCH).reason
    note = (f"зерно: {sc.seed}; код {code}; причина {reason!r}\n"
            f"вызовы {[c[:3] for c in sc.api.calls]}\n{out}")
    assert reason, note
    assert reason in out or re.search(r"нет конвейер", out), note
    assert not [c for c in sc.api.calls if c[1].endswith("/test_report")], note
    assert sc.api.calls and {c[0] for c in sc.api.calls} == {"GET"}, note


# --- AC-6 ---

EXPIRY_MARKS = {"token_expiry", "TOKEN_EXPIRY_WARN_DAYS", "TOKEN_NO_EXPIRY_TASKS_WARN"}


def misc_functions() -> list:
    """Функции верхнего уровня `orchestrator/doctor/misc_checks.py`."""
    module = importlib.import_module("orchestrator.doctor.misc_checks")
    tree = ast.parse(Path(inspect.getsourcefile(module)).read_text(encoding="utf-8"))
    return [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def mentions_expiry(fn) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and node.attr in EXPIRY_MARKS:
            return True
        if isinstance(node, ast.Name) and node.id in EXPIRY_MARKS:
            return True
    return False


def test_ac6_no_forge_literals_in_doctor_forge_lines():
    """В `check_base_branch` и функции строки срока токена нет литералов `"github"`/`"gitlab"` и обращения к `FORGES`.

    Сценарий: разбор `ast` файла `misc_checks.py`; функция строки срока
    токена — функция модуля, обращающаяся к `token_expiry` или к порогам
    `TOKEN_EXPIRY_WARN_DAYS`/`TOKEN_NO_EXPIRY_TASKS_WARN`. Такая функция
    есть; ни в ней, ни в `check_base_branch` нет строковой константы, равной
    `"github"` или `"gitlab"`, и атрибута `FORGES`.

    Ловит мутацию: прежнее `entry.get("forge") != "github"` оставлено;
    строка срока токена выбирает хостинг сравнением с `"gitlab"` или по
    `targets.FORGES`; строка срока токена не в `misc_checks.py`.
    """
    functions = misc_functions()
    base = [f for f in functions if f.name == "check_base_branch"]
    expiry = [f for f in functions if mentions_expiry(f)]
    assert len(base) == 1, [f.name for f in functions]
    assert expiry, [f.name for f in functions]
    found = []
    for fn in base + expiry:
        for node in ast.walk(fn):
            if isinstance(node, ast.Constant) and node.value in ("github", "gitlab"):
                found.append(f"{fn.name}:{node.lineno}: {node.value!r}")
            if isinstance(node, ast.Attribute) and node.attr == "FORGES":
                found.append(f"{fn.name}:{node.lineno}: .FORGES")
    assert found == [], found
