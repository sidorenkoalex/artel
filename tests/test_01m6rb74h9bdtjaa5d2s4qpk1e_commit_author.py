"""Автор коммитов пульта проекта GitLab: автопоиск `machine.commit_author` в `doctor --fix`, сторож `project-commit-author-<проект>` в `doctor`, отказ `new` и `epic draft promote` при его `fail`.

Группа: долгоживущий
Красен до реализации: строки `project-commit-author-<проект>` в `doctor` нет (поиск строки сторожа падает), `doctor --fix` поле `machine.commit_author` не пишет (ни копии слоя, ни строки журнала) и причин отказа не называет, а `new` и `epic draft promote` проекта без поля заводят задачу.

Провалидировано временным стабом реализации (удалён, не закоммичен): все
методы зелёные.

Связка, которую держит файл: «локальный слой `targets.local_path()`
песочницы — `doctor.all_checks`/`doctor.cmd_doctor(fix=True)` — адаптер
GitLab — журнал пульта» и «тот же слой — `artel.py new`/`epic draft
promote` — БД задач — ссылка документов». Песочница — `initialized_tmp_root`
(пути `config` во временном каталоге, БД со схемой, связка ключей —
`tests.sandbox.fake_keychain_token`, признак процесса роли снят). Запись
проекта — в трёх разделах локального слоя, `forge: gitlab`, `merge_gate:
target-human`, `token_slot`; `targets.yaml` репозитория песочницы — одна
запись артели. Ответ `GET /user` — подменённый `gitlab_adapter.transport`
(в сеть запрос не уходит; прочие запросы API получают 404); отказ API —
`URLError` транспорта или код 401. Прогоны `doctor` идут с подменой
`subprocess.run`/`Popen`: внешние процессы, кроме локальных (git без сети,
интерпретатор, `ps`), получают отказ запуска. Команды `new`/`promote` идут
по песочнице как есть (`SpyRun` песочницы, клон проекта —
`tests.sandbox.make_project_repo`); запись ссылки документов видна в
журнале подмены git (`update-ref refs/artifacts/…`).

Логины, имена, адреса и имена проектов порождаются модулем `random` при
каждом запуске; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import json
import os
import random
import subprocess
import sys
import urllib.error
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import artel, config, doctor, epics, gitlab_adapter, runner, store, targets
from orchestrator import yamlmini
from tests.sandbox import artel_target_entry, fake_keychain_token, make_project_repo

LETTERS = "abcdefghijkmnopqrstuvwxyz"
NETWORK_GIT = {"clone", "fetch", "push", "pull", "ls-remote"}
NOT_OVERWRITTEN = ("doctor --fix не перезаписывает — правка поля "
                   "machine.commit_author локального слоя Оператором")
WRITE_CHECK_FAILED = "сверка до записи не прошла"
CHECK_LINE = ("[ok]", "[WARN]", "[FAIL]", "[skip]")


def word(rng: random.Random, prefix: str, size: int = 7) -> str:
    return prefix + "".join(rng.choice(LETTERS) for _ in range(size))


def local_command(argv) -> bool:
    """Локальный процесс песочницы: `ps`, интерпретатор Python, git без сети."""
    if not isinstance(argv, (list, tuple)) or not argv:
        return False
    words = [os.fsdecode(a) for a in argv]
    name = Path(words[0]).name
    if name == "git":
        return not NETWORK_GIT & set(words[1:])
    return name == "ps" or name.startswith("python") or words[0] == sys.executable


@contextlib.contextmanager
def no_external_processes():
    """`subprocess.run`/`Popen` без внешних процессов: им — отказ запуска."""
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
        yield


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


class Api:
    """Подменённый транспорт GitLab: ответ `GET /user` задаёт тест.

    `user` — тело ответа (словарь) либо `None` — отказ соединения;
    `status` — код ответа; `user_calls` — число запросов `GET /user`,
    `tokens` — значения заголовка `PRIVATE-TOKEN` всех запросов."""

    def __init__(self):
        self.user = None
        self.status = 200
        self.user_calls = 0
        self.tokens = set()

    def transport(self, method, url, headers, body, timeout):
        self.tokens.add(str(headers.get("PRIVATE-TOKEN", "")))
        if not url.endswith("/api/v4/user"):
            return 404, {}, b""
        self.user_calls += 1
        if self.user is None:
            raise urllib.error.URLError(ConnectionRefusedError(
                111, "песочница: GitLab не отвечает"))
        return self.status, {}, json.dumps(self.user).encode("utf-8")


@pytest.fixture
def api(initialized_tmp_root, monkeypatch):
    fake = Api()
    monkeypatch.setattr(gitlab_adapter, "transport", fake.transport)
    monkeypatch.setattr(runner, "in_role_environment", lambda env=None: False)
    return fake


class Scene:
    """Запись проекта GitLab в локальном слое песочницы и наблюдения за ней."""

    def __init__(self, seed: int, api: Api, gate: str = "target-human"):
        self.seed = seed
        self.rng = random.Random(seed)
        self.api = api
        self.name = word(self.rng, "p")
        self.gate = gate
        self.slot = f"{self.name}-token"
        self.username = word(self.rng, "bot-")
        self.display = "Бот " + word(self.rng, "", 6)
        self.address = f"{word(self.rng, 'bot-')}@localhost"
        self.other_address = f"{word(self.rng, 'other-')}@localhost"
        config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")

    # --- запись и ответ API ---

    def write(self, author: dict | None) -> None:
        """Локальный слой с записью проекта; `author` — `machine.commit_author` либо его нет."""
        lines = ["targets:", f"  {self.name}:", "    description:",
                 f"      base: {config.MAIN_BRANCH}", "      test_profile:",
                 "        command: [python3, -m, pytest]",
                 "        long_lived_dir: tests",
                 "        long_lived_name: test_<id>_<name>.py", "    policy:",
                 "      no_paths: []", "      project_skills: []",
                 f"      merge_gate: {self.gate}",
                 "      weakening_scope: [tests/**/*.py]",
                 "      mutation_claim_scope: [tests/test_*.py]",
                 "    machine:", "      forge: gitlab",
                 f"      url: https://localhost/team/{self.name}",
                 f"      token_slot: {self.slot}"]
        if author is not None:
            lines += ["      commit_author:", f"        name: {author['name']}",
                      f"        email: {author['email']}"]
        path = targets.local_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def reply(self, *, commit_email: bool = True, email: bool = True,
              username: str | None = None) -> None:
        """Ответ `GET /user`: логин (по умолчанию `username` сцены), имя, адреса."""
        body = {"id": self.rng.randrange(1, 10 ** 6),
                "username": self.username if username is None else username,
                "name": self.display}
        if commit_email:
            body["commit_email"] = self.address
        if email:
            body["email"] = self.address if not commit_email else self.other_address
        self.api.user = body

    def layer_bytes(self) -> bytes:
        return targets.local_path().read_bytes()

    def layer_author(self):
        data = yamlmini.mapping(targets.local_path().read_text(encoding="utf-8"))
        return data["targets"][self.name].get("machine", {}).get("commit_author")

    def token(self) -> str:
        return fake_keychain_token(self.slot)

    # --- doctor ---

    def checks(self) -> list:
        with no_external_processes():
            return doctor.all_checks(store.db())

    def guard(self):
        """Строка `project-commit-author-<проект>` из `doctor.all_checks`."""
        checks = self.checks()
        found = [c for c in checks if c.name == f"project-commit-author-{self.name}"]
        assert len(found) == 1, self.note(
            "строк сторожа: " + str(len(found)) + "\n"
            + "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks))
        return found[0]

    def doctor_fix(self) -> str:
        out = io.StringIO()
        with no_external_processes(), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out), contextlib.suppress(SystemExit):
            doctor.cmd_doctor(fix=True)
        return out.getvalue()

    def journal_rows(self) -> list:
        return [tuple(r) for r in store.db().execute(
            "SELECT id, target, action, detail FROM steps ORDER BY id").fetchall()]

    def backups(self) -> dict:
        if not config.LOGS.is_dir():
            return {}
        return {p: p.read_bytes() for p in config.LOGS.rglob("*") if p.is_file()}

    def note(self, extra) -> str:
        return f"зерно: {self.seed}; проект {self.name}; {extra}"


def author_rows(rows: list, name: str) -> list:
    """Строки журнала о записи `commit_author` проекта `name`."""
    return [r for r in rows if r[1] == name
            and "commit_author" in f"{r[2]} {r[3]}"]


# --- AC-2 ---

def test_ac2_fix_writes_username_and_commit_email(api, seed):
    """`doctor --fix` пишет `{name: username, email: commit_email}`, копию прежнего слоя и строку журнала; повтор слой не меняет.

    Сценарий: запись GitLab без `commit_author`; ответ `GET /user` —
    `username`, отличное от него `name`, `commit_email` и другой `email`.
    После `doctor.cmd_doctor(fix=True)` в разобранном слое
    `machine.commit_author` = `{name: <username>, email: <commit_email>}`;
    в `config.LOGS` появился файл, побайтно равный прежнему слою; в
    журнале пульта — новая строка проекта, называющая `commit_author`.
    Второй `doctor --fix` оставляет слой побайтно тем же.

    Ловит мутацию: в `name` пишется отображаемое `name` вместо `username`;
    адрес берётся из `email` прежде `commit_email`; запись мимо пути
    `target-set` (без копии в `config.LOGS` или без строки журнала);
    повторный `--fix` перезаписывает уже заданное поле (слой меняется —
    например, порядком ключей или повторной пересборкой с новой копией).
    """
    sc = Scene(seed, api)
    sc.write(None)
    sc.reply()
    before, backups, rows = sc.layer_bytes(), sc.backups(), sc.journal_rows()
    out = sc.doctor_fix()
    note = sc.note(f"ответ {api.user}\n{out}")
    assert sc.layer_author() == {"name": sc.username, "email": sc.address}, note
    copies = [p for p, data in sc.backups().items()
              if p not in backups and data == before]
    assert copies, note
    assert author_rows(sc.journal_rows()[len(rows):], sc.name), note
    written = sc.layer_bytes()
    out = sc.doctor_fix()
    assert sc.layer_bytes() == written, sc.note(f"повторный --fix\n{out}")


# --- AC-3 ---

def test_ac3_fix_falls_back_to_email(api, seed):
    """Ответ без `commit_email`, но с `email`: `doctor --fix` пишет `email`.

    Сценарий: запись GitLab без `commit_author`; ответ `GET /user` —
    `username`, `name`, `email`, поля `commit_email` нет. После
    `doctor --fix` в слое `machine.commit_author` = `{name: <username>,
    email: <email>}`.

    Ловит мутацию: автопоиск читает только `commit_email` и при его
    отсутствии поле не пишет; адаптер не берёт запасной `email`.
    """
    sc = Scene(seed, api)
    sc.write(None)
    sc.reply(commit_email=False)
    out = sc.doctor_fix()
    assert sc.layer_author() == {"name": sc.username, "email": sc.address}, \
        sc.note(f"ответ {api.user}\n{out}")


@pytest.mark.parametrize("how", ["без адреса", "отказ соединения", "401"])
def test_ac3_no_address_or_api_refusal_keeps_layer(api, seed, how):
    """Ответ без обоих адресов или отказ API: слой побайтно прежний, строка `doctor` называет причину.

    Сценарий: запись GitLab без `commit_author`; ответ `GET /user` —
    `username` и `name` без `commit_email`/`email`, либо отказ соединения
    транспорта, либо код 401. После `doctor --fix` файл слоя побайтно
    прежний; в выводе — строка с именем
    проекта, называющая причину: отсутствие адреса («адрес»/«email») либо
    отказ API (текст адаптера: «сеть недоступна» с текстом отказа
    соединения, «401»).

    Ловит мутацию: при пустом адресе пишется `email: ""`, `None` или
    `username` (слой меняется); отказ API принят за пустой ответ и запись
    идёт с пустыми значениями; причина не выводится ни одной строкой.
    """
    sc = Scene(seed, api)
    sc.write(None)
    if how == "без адреса":
        sc.reply(commit_email=False, email=False)
        markers = ("адрес", "email")
    elif how == "отказ соединения":
        api.user = None
        markers = ("сеть недоступна",)
    else:
        sc.reply()
        api.status = 401
        markers = ("401",)
    before = sc.layer_bytes()
    out = sc.doctor_fix()
    note = sc.note(f"{how}\n{out}")
    assert sc.layer_bytes() == before, note
    lines = [line for line in out.splitlines() if sc.name in line]
    assert any(m in line for line in lines for m in markers), note


def test_ac3_write_check_refusal_keeps_layer_and_doctor_goes_on(api, seed):
    """Пробельный `username` при годном `commit_email`: «сверка до записи не прошла», слой побайтно прежний, строки прочих проверок — после строки отказа.

    Сценарий: запись GitLab без `commit_author`; ответ `GET /user` —
    `username` из одних пробелов (их число случайно) и годный
    `commit_email`. После `doctor --fix` в выводе — строка с причиной
    «сверка до записи не прошла»; слой побайтно прежний; после этой строки
    выведены строки проверок `doctor` (`[ok]`/`[WARN]`/`[FAIL]`/`[skip]`)
    и итог `DOCTOR:`. Код выхода не проверяется.

    Ловит мутацию: запись идёт без сверки `targets.merge_local` (в слой
    попадает пробельное имя); отказ сверки завершает процесс `sys.exit`
    хелпера `target-set` (строк проверок после отказа нет, итога
    `DOCTOR:` нет); причина отказа — текст `target-set` вместо «сверка до
    записи не прошла».
    """
    sc = Scene(seed, api)
    sc.write(None)
    sc.reply(username=" " * sc.rng.randrange(1, 6))
    before = sc.layer_bytes()
    out = sc.doctor_fix()
    note = sc.note(f"ответ {api.user}\n{out}")
    lines = out.splitlines()
    refusal = [i for i, line in enumerate(lines) if WRITE_CHECK_FAILED in line]
    assert refusal, note
    assert sc.layer_bytes() == before, note
    tail = lines[refusal[0] + 1:]
    assert any(line.strip().startswith(CHECK_LINE) for line in tail), note
    assert any(line.startswith("DOCTOR:") for line in tail), note


# --- AC-4 ---

def guard_case(sc: Scene, case: str) -> str:
    """Готовит слой и ответ API случая `case`; возвращает ожидаемый статус."""
    use_commit_email = sc.rng.choice([True, False])
    good = {"name": sc.username, "email": sc.address}
    if case == "ok":
        sc.write(good)
        sc.reply(commit_email=use_commit_email)
        return "ok"
    if case == "адрес другой":
        sc.write({"name": sc.username, "email": f"{word(sc.rng, 'x-')}@localhost"})
        sc.reply(commit_email=use_commit_email)
        return "fail"
    if case == "имя — name":
        sc.write({"name": sc.display, "email": sc.address})
        sc.reply(commit_email=use_commit_email)
        return "fail"
    if case == "имя другое":
        sc.write({"name": word(sc.rng, "someone-"), "email": sc.address})
        sc.reply(commit_email=use_commit_email)
        return "fail"
    if case == "поля нет, адрес есть":
        sc.write(None)
        sc.reply(commit_email=use_commit_email)
        return "fail"
    if case == "поле есть, API не ответил":
        sc.write(good)
        sc.api.user = None
        return "warn"
    if case == "поля нет, API не ответил":
        sc.write(None)
        sc.api.user = None
        return "warn"
    if case == "поле есть, адреса нет":
        sc.write(good)
        sc.reply(commit_email=False, email=False)
        return "warn"
    if case == "поля нет, адреса нет":
        sc.write(None)
        sc.reply(commit_email=False, email=False)
        return "warn"
    raise AssertionError(case)


GUARD_CASES = ["ok", "адрес другой", "имя — name", "имя другое", "поля нет, адрес есть",
               "поле есть, API не ответил", "поля нет, API не ответил",
               "поле есть, адреса нет", "поля нет, адреса нет"]


@pytest.mark.parametrize("case", GUARD_CASES)
def test_ac4_guard_status_by_case(api, seed, case):
    """Статус строки `project-commit-author-<проект>` по случаю AC-4; значение токена в тексте не встречается.

    Сценарий: запись GitLab с `token_slot`; `username` и `name` ответа
    различны, адрес токена — `commit_email` либо (случайно) только
    `email`. Случаи: совпадение имени и адреса — `ok`; другой адрес,
    имя = `name` ответа, иное имя, поля нет при ответе с адресом —
    `fail`; API не ответил или не дал адреса, с полем и без него —
    `warn`. Ни в одном случае в тексте строки нет токена слота.

    Ловит мутацию: имя сверяется с отображаемым `name` (случай «имя —
    name» даст `ok`, «ok» — `fail`); сверяется только адрес или только
    имя; адрес токена берётся только из `commit_email` (случай с одним
    `email` — `warn`/`fail` вместо `ok`); отсутствие адреса при
    отсутствии поля даёт `fail`; отказ API даёт `fail` или `ok`; в текст
    попадает токен слота.
    """
    sc = Scene(seed, api)
    expected = guard_case(sc, case)
    line = sc.guard()
    note = sc.note(f"{case}; ответ {api.user}; строка [{line.status}] {line.detail}")
    assert line.status == expected, note
    assert sc.token() not in line.detail, note
    for token in api.tokens:
        assert not token or token not in line.detail, note


@pytest.mark.parametrize("case", ["адрес другой", "имя — name", "имя другое"])
def test_ac4_mismatch_text_and_fix_keeps_field(api, seed, case):
    """`fail` несовпадения называет записанное и значение токена, содержит текст о правке Оператором; `doctor --fix` поле не меняет.

    Сценарий: запись GitLab с `commit_author`, расходящимся с владельцем
    токена адресом либо именем (в том числе равным отображаемому `name`).
    Текст строки сторожа: при другом адресе — записанный адрес и адрес
    токена; при другом имени — записанное имя и `username`; в обоих —
    «doctor --fix не перезаписывает — правка поля machine.commit_author
    локального слоя Оператором». После `doctor --fix` слой побайтно
    прежний; токен слота нет ни в строке, ни в выводе `doctor --fix`.

    Ловит мутацию: автопоиск перезаписывает заданное поле (слой меняется);
    текст называет только одно из двух значений либо значение другого
    поля; нет подсказки о правке Оператором.
    """
    sc = Scene(seed, api)
    guard_case(sc, case)
    written = sc.layer_author()
    line = sc.guard()
    note = sc.note(f"{case}; ответ {api.user}; строка [{line.status}] {line.detail}")
    assert line.status == "fail", note
    assert NOT_OVERWRITTEN in line.detail, note
    if case == "адрес другой":
        assert written["email"] in line.detail, note
        assert sc.address in line.detail, note
    else:
        assert written["name"] in line.detail, note
        assert sc.username in line.detail, note
    before = sc.layer_bytes()
    out = sc.doctor_fix()
    assert sc.layer_bytes() == before, sc.note(f"{case}\n{out}")
    assert sc.token() not in out, sc.note(f"{case}: токен в выводе\n{out}")


def test_ac4_missing_field_fail_hints_fix(api, seed):
    """Поля нет, API ответил с адресом: `fail` с подсказкой `doctor --fix`.

    Сценарий: запись GitLab без `commit_author`; ответ `GET /user` с
    `username` и `commit_email`. Строка сторожа — `fail`, в тексте
    «doctor --fix», нет токена слота.

    Ловит мутацию: отсутствие поля даёт `warn` (проект без автора проходит
    в `new`); текст без подсказки `doctor --fix`.
    """
    sc = Scene(seed, api)
    sc.write(None)
    sc.reply()
    line = sc.guard()
    note = sc.note(f"строка [{line.status}] {line.detail}")
    assert line.status == "fail", note
    assert "doctor --fix" in line.detail, note
    assert sc.token() not in line.detail, note


def test_ac4_role_process_skips_and_fix_does_not_call_api(api, monkeypatch, seed):
    """В процессе роли строка сторожа — `skip`; `doctor --fix` поле не пишет и `GET /user` не запрашивает.

    Сценарий: запись GitLab без `commit_author`, ответ API с адресом;
    признак процесса роли выставлен (`runner.in_role_environment`
    истинно). Строка `project-commit-author-<проект>` — `skip`; после
    `doctor --fix` слой побайтно прежний, транспорт не видел ни одного
    запроса `GET /user`.

    Ловит мутацию: сторож не смотрит признак роли (`fail` вместо `skip`,
    запрос `GET /user` есть); автопоиск `--fix` в роли зовёт `token_user`
    и пишет поле.
    """
    sc = Scene(seed, api)
    sc.write(None)
    sc.reply()
    monkeypatch.setattr(runner, "in_role_environment", lambda env=None: True)
    line = sc.guard()
    assert line.status == "skip", sc.note(f"строка [{line.status}] {line.detail}")
    before = sc.layer_bytes()
    out = sc.doctor_fix()
    note = sc.note(f"запросов GET /user: {api.user_calls}\n{out}")
    assert sc.layer_bytes() == before, note
    assert api.user_calls == 0, note


# --- AC-5, AC-6 ---

def cli(*args: str) -> tuple:
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


def project_scene(seed: int, api: Api, gate: str = "target-human") -> Scene:
    """Сцена с клоном проекта (`make_project_repo`): запись артели в
    `targets.yaml` репозитория, запись проекта — только в локальном слое."""
    sc = Scene(seed, api, gate=gate)
    make_project_repo(sc.name, origin=True)
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    return sc


def task_ids() -> set:
    return {row["id"] for row in store.all_tasks(store.db())}


def docs_ref_writes(spy) -> int:
    """Записи ссылок документов (`update-ref refs/artifacts/…`) в журнале подмены git."""
    return sum(1 for call in spy.calls if "update-ref" in call
               and any(str(a).startswith("refs/artifacts/") for a in call))


@pytest.mark.parametrize("case", ["поля нет, адрес есть", "адрес другой", "имя — name"])
def test_ac5_new_refused_by_guard_fail(api, initialized_tmp_root, seed, case):
    """`fail` сторожа: `new --target` отказывает текстом проверки, задачи и ссылки документов нет.

    Сценарий: клон проекта заведён, запись GitLab `target-human` в
    локальном слое; поле не задано при ответе API с адресом либо
    расходится с владельцем токена. Строка сторожа в `doctor` — `fail`;
    `artel.py new "<название>" --target <проект>` выходит ненулевым кодом,
    в выводе — текст этой строки; строк `tasks` не прибавилось, записи
    `update-ref refs/artifacts/…` нет.

    Ловит мутацию: отказ поставлен только в `doctor` (`new` заводит
    задачу); отказ — после заведения строки задачи или ссылки документов;
    текст отказа — общий, без текста проверки.
    """
    sc = project_scene(seed, api)
    guard_case(sc, case)
    line = sc.guard()
    assert line.status == "fail", sc.note(f"{case}: [{line.status}] {line.detail}")
    spy = initialized_tmp_root.git_spy
    before, refs = task_ids(), docs_ref_writes(spy)
    out, code = cli("new", "Задача проекта gitlab", "--target", sc.name)
    note = sc.note(f"{case}; код {code}; строка {line.detail}\n{out}")
    assert code != 0, note
    assert line.detail in out, note
    assert task_ids() == before, note
    assert docs_ref_writes(spy) == refs, note


def test_ac5_epic_draft_promote_refused_by_guard_fail(api, initialized_tmp_root, seed):
    """`fail` сторожа: `epic draft promote` черновика эпика проекта отказывает, задачи и ссылки документов нет.

    Сценарий: клон проекта заведён, запись GitLab без `commit_author`,
    ответ API с адресом (сторож — `fail`); эпик проекта и черновик
    заведены в БД. `artel.py epic draft promote <адрес черновика>` выходит
    ненулевым кодом, строк `tasks` не прибавилось, черновик остался
    `draft`, записи `update-ref refs/artifacts/…` нет.

    Ловит мутацию: отказ поставлен в CLI-обёртку `new`, а не в
    `catalog.cmd_new` (`promote` зовёт `cmd_new` в обход неё и заводит
    задачу).
    """
    sc = project_scene(seed, api)
    guard_case(sc, "поля нет, адрес есть")
    conn = store.db()
    epic_id = epics.new_epic_id()
    store.insert_epic(conn, epic_id, sc.name, "Эпик", "цель", None)
    number = store.insert_draft(conn, epic_id, "Черновик", "ТЗ черновика", None, None, None)
    conn.commit()
    spy = initialized_tmp_root.git_spy
    before, refs = task_ids(), docs_ref_writes(spy)
    out, code = cli("epic", "draft", "promote", epics.draft_address(epic_id, number))
    note = sc.note(f"код {code}\n{out}")
    assert code != 0, note
    assert task_ids() == before, note
    assert store.get_draft(store.db(), epic_id, number)["state"] == epics.DRAFT, note
    assert docs_ref_writes(spy) == refs, note


def test_ac5_unsupported_project_keeps_old_refusal(api, initialized_tmp_root, seed):
    """Неподдержанный проект (`gitlab` + `operator`) без `commit_author`: отказ `new` — прежний текст `unsupported_reason`.

    Сценарий: запись GitLab `merge_gate: operator` в локальном слое без
    поля, ответ API с адресом. `new --target` выходит ненулевым кодом, в
    выводе — «new: проект <имя>: <причина unsupported_reason> — задача не
    заведена», текста строки сторожа в выводе нет.

    Ловит мутацию: проверка сторожа поставлена до `unsupported_reason`
    (отказ называет автора коммитов, а не неподдержанную пару).
    """
    sc = project_scene(seed, api, gate="operator")
    guard_case(sc, "поля нет, адрес есть")
    reason = targets.unsupported_reason(sc.name)
    assert reason, sc.note("пара gitlab + operator поддержана")
    line = sc.guard()
    out, code = cli("new", "Задача проекта gitlab", "--target", sc.name)
    note = sc.note(f"код {code}; строка [{line.status}] {line.detail}\n{out}")
    assert code != 0, note
    assert f"new: проект {sc.name}: {reason} — задача не заведена" in out, note
    assert line.detail not in out, note


def test_ac6_new_with_guard_warn_creates_task_and_warns(api, initialized_tmp_root, seed):
    """`warn` сторожа (поля нет, API не ответил): `new --target` заводит задачу, в выводе — предупреждение.

    Сценарий: клон проекта заведён, запись GitLab `target-human` без
    `commit_author`, транспорт отказывает соединением. Строка сторожа —
    `warn`; `new --target` выходит кодом 0, прибавилась одна строка
    `tasks` проекта; в выводе есть предупреждение об авторе коммитов
    (имя строки сторожа, «commit_author» или «автор коммитов»).

    Ловит мутацию: `warn` принят за `fail` (задача не заведена);
    предупреждение не выводится.
    """
    sc = project_scene(seed, api)
    guard_case(sc, "поля нет, API не ответил")
    line = sc.guard()
    assert line.status == "warn", sc.note(f"[{line.status}] {line.detail}")
    before = task_ids()
    out, code = cli("new", "Задача проекта gitlab", "--target", sc.name)
    created = [r for r in store.all_tasks(store.db()) if r["id"] not in before]
    note = sc.note(f"код {code}\n{out}")
    assert code == 0, note
    assert len(created) == 1 and created[0]["target"] == sc.name, note
    lowered = out.lower()
    assert (f"project-commit-author-{sc.name}" in out or "commit_author" in out
            or "автор коммитов" in lowered), note
