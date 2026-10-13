"""Порог справочника ядра из настройки проекта, вход без задачи и команда `reference <проект>`.

Группа: долгоживущий
Красен до реализации: порог сборки и сверки кэша — константа `config.CORE_REFERENCE_MIN_USES` (подполе `min_uses` отказывает как неизвестное), входа без задачи в `reference_cache` нет, команды `reference` в диспетчере нет («Неизвестная команда»), `target-init` справочник не собирает — красны AC-3, AC-4, AC-6 (вход), AC-7, AC-8–AC-14, AC-16, AC-17; AC-5, прежнее поведение `get_reference` в AC-6 и отказ роли AC-15 (белый список закрыт по умолчанию) зелены с рождения и сторожат, что новая проверка, общий вход и новая команда их не сломают. Проверено временным стабом реализации: все методы зелены, десять мутаций стаба пойманы.

Каждый тест держит связку «`targets.yaml` — клон проекта в области
проектов — git-объекты коммита — файл кэша — журнал и алерты БД» (а тесты
команды — ещё и диспетчер `artel.main`). Песочница — `ConnRealGitSandbox`:
`config.TARGETS`, `config.PROJECTS` и `config.DB` во временном каталоге,
клон проекта — `make_project_repo` (настоящий git), настоящий
`targets.yaml` и боевая область проектов не читаются и не пишутся.

Запуски процессов считаются подменой `subprocess.Popen` подклассом
настоящего (через него идут и `subprocess.run`, и прямой `Popen`),
процесс остаётся настоящим. Команда вызывается диспетчером с подменой
`sys.argv`; окружение процесса на время вызова — окружение Оператора
(без маркера роли, HOME — каталог песочницы), кроме теста отказа роли.

Вход без задачи SPEC разрешает назвать как угодно при форме
`(conn, target, *, reason, sha, task_id=None)`: тест находит его среди
публичных функций `reference_cache` по этой форме. Форму значения
справочника SPEC называет полями `text`, `note`, `state`; тест читает их
атрибутом или ключом.
"""
import contextlib
import inspect
import io
import os
import random
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import alerts, artel, config, reference_cache, store, targets
from tests.sandbox import ConnRealGitSandbox, artel_target_entry, make_project_repo

PROJECT = "proj"
TASK = "T901"
BRANCH = "task/t901-reference"

OVER = "больше предела — в бриф не попадёт"
WARN = "больше 90% предела — бриф поднимет предупреждение"
WITHIN = "в пределе"
VERDICTS = (OVER, WARN, WITHIN)
NO_DB = "журнал недоступен — сначала init"
INIT_NO_DB = "справочник ядра: журнал недоступен — сначала init"
INIT_OFF = "справочник ядра: выключен (нет поля core_reference)"
ROLE_REFUSAL = "недоступна процессу роли"

CORE = '''"""Ядро проекта: справочный модуль<PAD>."""


def engine(v: int, scale: float = 1.0) -> float:
    """Двигатель проекта."""
    return v * scale


def rare(v: int) -> int:
    """Редкая функция проекта."""
    return v
'''
SETTINGS = '''"""Настройки проекта."""

LIMIT_A = 4242  # предел проекта
'''
ENGINE = "engine(v: int, scale: float = 1.0) -> float"
RARE = "rare(v: int) -> int"
SETTING = {"modules": ["lib/core.py", "conf/settings.py"],
           "constants_module": "conf/settings.py", "constants": ["LIMIT_A"]}
MISSING_MODULE_SETTING = {"modules": ["lib/core.py", "lib/missing.py"]}

ENTRY_FIELDS = (("forge", "github"), ("url", "file:///nonexistent/{name}"),
                ("base", "{base}"), ("token_slot", "{name}-token"),
                ("no_paths", "[]"), ("project_skills", "[]"),
                ("merge_gate", "operator"))


def project_files(engine_users: int, rare_users: int, pad: str = "") -> dict:
    """Модуль с `engine` (в `engine_users` файлах) и `rare` (в `rare_users`)."""
    files = {"lib/core.py": CORE.replace("<PAD>", pad), "conf/settings.py": SETTINGS}
    files.update({f"use/e{i}.py": "from lib import core\ncore.engine(1)\n"
                  for i in range(engine_users)})
    files.update({f"use/r{i}.py": "from lib import core\ncore.rare(1)\n"
                  for i in range(rare_users)})
    return files


def yaml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return f"[{', '.join(str(x) for x in value)}]"
    if isinstance(value, str) and (value.isdigit() or not value):
        return f'"{value}"'
    return str(value)


def entry_yaml(name: str, setting: dict | None, omit: tuple = ()) -> str:
    lines = [f"  {name}:"]
    for key, value in ENTRY_FIELDS:
        if key not in omit:
            lines.append(f"    {key}: "
                         + value.format(name=name, base=config.MAIN_BRANCH))
    if setting is not None:
        lines.append("    core_reference:")
        lines += [f"      {key}: {yaml_value(value)}" for key, value in setting.items()]
    return "\n".join(lines) + "\n"


def field(result, name: str):
    return result[name] if isinstance(result, dict) else getattr(result, name)


def squeeze(text: str) -> str:
    return "".join(text.split())


def has_signature(text: str, signature: str) -> bool:
    wanted = squeeze(signature)
    return any(wanted in squeeze(line) for line in text.split("\n"))


def has_number(text: str, number) -> bool:
    return re.search(rf"(?<![\d.]){number}(?![\d])", text) is not None


def verdicts(text: str) -> set:
    return {verdict for verdict in VERDICTS if verdict in text}


def paths_snapshot(root: Path) -> set:
    """Все пути дерева песочницы (каталоги и файлы), кроме git-объектов и БД."""
    found = set()
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if ".git" in rel.parts or path.name.startswith("state.db"):
            continue
        found.add(str(rel))
    return found


def refuse(*_args, **_kwargs):
    raise OSError("замена файла запрещена тестом")


@contextlib.contextmanager
def replace_fails():
    """Замена файла (`os.replace`/`os.rename`) отказывает `OSError`."""
    with mock.patch.object(os, "replace", refuse), \
            mock.patch.object(os, "rename", refuse):
        yield


def target_entries() -> list:
    """Публичные функции `reference_cache` формы `(a, b, *, reason, sha, task_id=None)`."""
    kinds = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    found = []
    for name, fn in inspect.getmembers(reference_cache, inspect.isfunction):
        if (name.startswith("_") or name == "get_reference"
                or fn.__module__ != reference_cache.__name__):
            continue
        params = list(inspect.signature(fn).parameters.values())
        positional = [p for p in params if p.kind in kinds]
        keyword = {p.name: p for p in params
                   if p.kind == inspect.Parameter.KEYWORD_ONLY}
        if (len(positional) >= 2
                and all(p.default is inspect.Parameter.empty for p in positional[:2])
                and {"reason", "sha", "task_id"} <= set(keyword)
                and keyword["task_id"].default is None):
            found.append(fn)
    found.sort(key=lambda fn: fn.__name__ != "get_reference_for_target")
    return found


class ReferenceSandbox(ConnRealGitSandbox):
    """Проекты с полем `core_reference`, их клоны, счёт запусков, вызов команды."""

    def setUp(self):
        super().setUp()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.entries = {}
        self.clones = {}
        self.runs = []
        self.recording = False
        self.operator_home = self.root / ".artel" / "operator-home"
        self.operator_home.mkdir(parents=True, exist_ok=True)
        sandbox = self
        real_popen = subprocess.Popen

        class SpyPopen(real_popen):
            def __init__(self, args, *rest, **kwargs):
                if sandbox.recording:
                    argv = ([str(a) for a in args]
                            if isinstance(args, (list, tuple)) else [str(args)])
                    sandbox.runs.append(argv)
                super().__init__(args, *rest, **kwargs)

        patcher = mock.patch.object(subprocess, "Popen", SpyPopen)
        patcher.start()
        self.addCleanup(patcher.stop)

    def why(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    # --- мир ----------------------------------------------------------------

    def write_targets(self) -> None:
        text = "targets:\n" + artel_target_entry() + "".join(self.entries.values())
        config.TARGETS.write_text(text, encoding="utf-8")

    def declare(self, name: str = PROJECT, setting: dict | None = SETTING,
                omit: tuple = ()) -> None:
        self.entries[name] = entry_yaml(name, setting, omit)
        self.write_targets()

    def add_project(self, name: str = PROJECT, setting: dict | None = SETTING,
                    files: dict | None = None) -> str:
        """Проект с записью, клоном и коммитом `files` на базовой ветке; sha коммита."""
        self.declare(name, setting)
        self.clones[name] = make_project_repo(name, origin=False)
        return self.commit(name, project_files(3, 1) if files is None else files)

    def add_task(self, name: str = PROJECT, task: str = TASK,
                 branch: str = BRANCH) -> str:
        """Задача проекта на своей ветке с ещё одним коммитом; sha головы ветки."""
        self.git("-C", str(self.clones[name]), "checkout", "-q", "-b", branch)
        store.insert_task(self.conn, task, "Задача", "in_dev", branch, name, 25.0)
        return self.commit(name, {"extra/branch_only.py": "BRANCH_ONLY = 1\n"})

    def commit(self, name: str, files: dict, message: str = "правка") -> str:
        clone = self.clones[name]
        for rel, content in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "--allow-empty", "-m", message)
        return self.git("-C", str(clone), "rev-parse", "HEAD").strip()

    def cache_path(self, name: str = PROJECT) -> Path:
        return config.PROJECTS / name / "knowledge" / "derived" / "core-reference.md"

    def cache_bytes(self, name: str = PROJECT) -> bytes:
        return self.cache_path(name).read_bytes()

    def drop_db(self) -> None:
        for suffix in ("", "-wal", "-shm", "-journal"):
            path = Path(str(config.DB) + suffix)
            if path.exists():
                path.unlink()

    # --- вызовы и наблюдения ------------------------------------------------

    def entry(self):
        found = target_entries()
        self.assertTrue(found, "в reference_cache нет входа формы "
                               "(conn, target, *, reason, sha, task_id=None)")
        return found[0]

    def get(self, task: str = TASK, reason: str = "brief", sha: str | None = None):
        self.runs, self.recording = [], True
        try:
            return reference_cache.get_reference(self.conn, task, reason=reason, sha=sha)
        finally:
            self.recording = False

    def get_for_target(self, target: str = PROJECT, reason: str = "reference",
                       sha: str | None = None):
        fn = self.entry()
        self.runs, self.recording = [], True
        try:
            return fn(self.conn, target, reason=reason, sha=sha)
        finally:
            self.recording = False

    def env_operator(self) -> dict:
        env = {"HOME": str(self.operator_home), "PATH": os.environ.get("PATH", "")}
        for key in ("TMPDIR", "LANG", "LC_ALL"):
            if key in os.environ:
                env[key] = os.environ[key]
        return env

    def run_cmd(self, *argv: str, env: dict | None = None) -> tuple[int, str]:
        """(код выхода, stdout+stderr+текст SystemExit) вызова `artel.py <argv>`."""
        out, err = io.StringIO(), io.StringIO()
        code = 0
        self.runs, self.recording = [], True
        try:
            with mock.patch.dict(os.environ, env or self.env_operator(), clear=True), \
                    mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    artel.main()
                except SystemExit as exc:
                    if exc.code in (None, 0):
                        code = 0
                    elif isinstance(exc.code, int):
                        code = exc.code
                    else:
                        code = 1
                        err.write(f"\n{exc.code}\n")
        finally:
            self.recording = False
        return code, out.getvalue() + err.getvalue()

    def git_runs(self) -> list:
        return [argv for argv in self.runs if argv and Path(argv[0]).name == "git"]

    def all_alerts(self) -> list:
        return [tuple(row) for row in
                self.conn.execute("SELECT * FROM alerts ORDER BY id").fetchall()]

    def new_alerts(self, since: int, target: str = PROJECT) -> list:
        return [row for row in alerts.open_alerts(self.conn)
                if row["id"] > since and row["target"] == target]

    def ack_all(self) -> None:
        for row in alerts.open_alerts(self.conn):
            alerts.ack(self.conn, row["id"], "test", "снят тестом")

    def rows_of(self, action: str, since: int = 0) -> list:
        return self.conn.execute(
            "SELECT * FROM steps WHERE action=? AND id>? ORDER BY id",
            (action, since)).fetchall()

    def max_step(self) -> int:
        return store.journal_maxima(self.conn)[0]

    def assert_state(self, result, state: str) -> None:
        self.assertEqual(state, field(result, "state"),
                         self.why(f"note: {field(result, 'note')!r}"))


# === AC-3, AC-4: порог настройки в сборке и в сверке кэша ======================


class ThresholdTest(ReferenceSandbox):

    def test_ac3_generator_threshold_from_setting_or_config_default(self):
        """Порог сборки — подполе `min_uses`, без него — `config.CORE_REFERENCE_MIN_USES`.

        Сценарий: `config.CORE_REFERENCE_MIN_USES` подменён случайным k;
        `engine` используется ровно в k файлах, `rare` — в k−1: без подполя
        `engine` в справочнике, `rare` нет. Затем подполе `min_uses` = m
        (случайное, ≠ k), `engine` — в m файлах, `rare` — в m−1: снова
        `engine` есть, `rare` нет, хотя по порогу `config` вышло бы иначе.
        Повторный вызов на том же sha — `cached`: сверка кэша считает тот
        же порог, что сборка.

        Ловит мутацию: порог из настройки не передан генератору (взят из
        `config` — при m > k войдёт `rare`, при m < k пропадёт `engine`),
        умолчание зашито литералом 3 вместо `config.CORE_REFERENCE_MIN_USES`,
        либо сверка `_read_cache` зовётся с порогом `config` (повтор — не
        `cached`, а снова `fresh`).
        """
        k = self.rng.randint(2, 9)
        m = self.rng.choice([v for v in range(2, 12) if v != k])
        with mock.patch.object(config, "CORE_REFERENCE_MIN_USES", k):
            sha = self.add_project(files=project_files(k, k - 1))
            self.add_task()
            result = self.get(sha=sha)
            self.assert_state(result, "fresh")
            text = field(result, "text")
            self.assertTrue(has_signature(text, ENGINE), self.why(f"k={k}: engine пропал"))
            self.assertFalse(has_signature(text, RARE), self.why(f"k={k}: rare вошёл"))

            self.declare(setting=dict(SETTING, min_uses=m))
            self.git("-C", str(self.clones[PROJECT]), "rm", "-r", "-q", "use")
            sha = self.commit(PROJECT, project_files(m, m - 1))
            result = self.get(sha=sha)
            self.assert_state(result, "fresh")
            text = field(result, "text")
            self.assertTrue(has_signature(text, ENGINE),
                            self.why(f"k={k}, m={m}: engine пропал — порог не из настройки"))
            self.assertFalse(has_signature(text, RARE),
                             self.why(f"k={k}, m={m}: rare вошёл — порог не из настройки"))
            self.assert_state(self.get(sha=sha), "cached")

    def test_ac4_cache_with_other_threshold_is_rebuilt_same_threshold_is_cached(self):
        """Кэш, собранный с другим порогом, пересобирается; с тем же порогом настройки — `cached`.

        Сценарий на одном sha: сборка без подполя (умолчание) — `fresh`;
        подполе `min_uses` = m (≠ умолчанию) — `fresh`, не `cached`; повтор
        с тем же m — `cached`; подполе m2 ≠ m — снова `fresh`; подполе
        убрано (умолчание ≠ m2) — `fresh`.

        Ловит мутацию: порог не участвует в сверке кэша (кэш с другим
        порогом засчитан годным — `cached` вместо `fresh`) либо сверка
        всегда считает кэш с порогом настройки негодным (повтор с тем же
        m — `fresh` вместо `cached`).
        """
        default = config.CORE_REFERENCE_MIN_USES
        m = self.rng.choice([v for v in range(1, 40) if v != default])
        m2 = self.rng.choice([v for v in range(1, 40) if v not in (default, m)])
        sha = self.add_project()
        self.add_task()
        self.assert_state(self.get(sha=sha), "fresh")
        steps = ((dict(SETTING, min_uses=m), "fresh"),
                 (dict(SETTING, min_uses=m), "cached"),
                 (dict(SETTING, min_uses=m2), "fresh"),
                 (SETTING, "fresh"))
        for setting, expected in steps:
            with self.subTest(min_uses=setting.get("min_uses"), expected=expected):
                self.declare(setting=setting)
                self.assert_state(self.get(sha=sha), expected)


# === AC-5: неверное min_uses при брифе и мерже ================================


class WrongThresholdTest(ReferenceSandbox):

    def test_ac5_wrong_min_uses_gives_absent_with_alert_without_raising(self):
        """Неверное `min_uses` (0, 1001, `true`, строка) — `absent` с алертом повода, без исключения.

        Сценарий: для поводов `brief` и `merge` и каждого неверного
        значения `get_reference` по задаче возвращает `absent` с пометкой,
        поднят новый открытый алерт проекта с источником повода
        (`brief.core_reference` / `fsm.core_reference_regen`), кэш не
        записан, исключение наружу не вышло.

        Ловит мутацию: проверка записи принимает неверное `min_uses` (0,
        1001, `true` или строку) — сборка идёт, состояние `fresh` вместо
        `absent`; либо `TargetsError` настройки пробрасывается из
        `get_reference` и роняет бриф или шаг мержа.
        """
        sources = {"brief": "brief.core_reference", "merge": "fsm.core_reference_regen"}
        sha = self.add_project()
        self.add_task()
        for value in (0, 1001, True, "abc", "4"):
            for reason, source in sources.items():
                with self.subTest(min_uses=value, reason=reason):
                    self.ack_all()
                    self.declare(setting=dict(SETTING, min_uses=value))
                    since = store.max_alert_id(self.conn)
                    try:
                        result = self.get(reason=reason, sha=sha)
                    except Exception as exc:  # noqa: BLE001 — предмет теста
                        self.fail(self.why(f"{reason}, min_uses={value!r}: исключение {exc!r}"))
                    self.assert_state(result, "absent")
                    raised = [row["source"] for row in self.new_alerts(since)]
                    self.assertIn(source, raised, self.why(f"min_uses={value!r}"))
                    self.assertFalse(self.cache_path().exists(), self.why("кэш записан"))


# === AC-6: общий вход без задачи и прежний get_reference ======================


class TargetEntryTest(ReferenceSandbox):

    def test_ac6_target_entry_with_documented_form_exists(self):
        """В `reference_cache` есть публичный вход `(conn, target, *, reason, sha, task_id=None)`.

        Сценарий: среди публичных функций модуля, кроме `get_reference`,
        есть функция с двумя обязательными позиционными параметрами и
        ключевыми `reason`, `sha`, `task_id` (умолчание `None`); вызов её
        для проекта (без задачи) с поводом `reference` на sha коммита даёт
        `fresh` и текст с `built_at_sha` этого коммита.

        Ловит мутацию: общий вход не заведён (сборка осталась только по
        задаче) либо `task_id` у него обязательный — вызов без задачи
        невозможен, функции такой формы нет.
        """
        sha = self.add_project()
        result = self.get_for_target(sha=sha)
        self.assert_state(result, "fresh")
        self.assertIn(sha, field(result, "text"), self.why("sha коммита нет в тексте"))

    def test_ac6_get_reference_by_task_keeps_default_sha_alerts_and_task_journal(self):
        """`get_reference` по задаче: sha по умолчанию — голова ветки, журнал и алерты — по задаче.

        Сценарий: для поводов `brief` и `merge` — без `sha` справочник
        собран на голове ветки задачи (не базовой ветки клона), запись
        «построен» есть в журнале задачи с её поводом; со сломанным `sha`
        — `absent`, запись «сбой» в журнале задачи, новый алерт проекта с
        источником повода.

        Ловит мутацию: `get_reference` сведён к общему входу без передачи
        своего `task_id` (записи журнала брифа/мержа уходят без задачи) или
        без головы ветки задачи (sha по умолчанию — база клона либо
        `absent`), либо источник алерта повода подменён — прежний
        результат `get_reference` по задаче изменился.
        """
        sources = {"brief": "brief.core_reference", "merge": "fsm.core_reference_regen"}
        base_sha = self.add_project()
        head = self.add_task()
        self.assertNotEqual(base_sha, head)
        for reason, source in sources.items():
            with self.subTest(reason=reason):
                reference_cache_file = self.cache_path()
                if reference_cache_file.exists():
                    reference_cache_file.unlink()
                since_step = self.max_step()
                result = self.get(reason=reason)
                self.assert_state(result, "fresh")
                text = field(result, "text")
                self.assertIn(f"built_at_sha: {head}", text, self.why(reason))
                built = [row for row in store.task_steps(self.conn, TASK)
                         if row["id"] > since_step
                         and row["action"] == reference_cache.BUILT_ACTION]
                self.assertEqual(1, len(built), self.why(f"{reason}: запись «построен»"))
                self.assertIn(f"повод={reason}", built[0]["detail"])

                self.ack_all()
                since_alert = store.max_alert_id(self.conn)
                since_step = self.max_step()
                result = self.get(reason=reason, sha="не-sha")
                self.assert_state(result, "absent")
                failed = [row for row in store.task_steps(self.conn, TASK)
                          if row["id"] > since_step
                          and row["action"] == reference_cache.FAILED_ACTION]
                self.assertEqual(1, len(failed), self.why(f"{reason}: запись «сбой»"))
                self.assertIn(source, [row["source"] for row in self.new_alerts(since_alert)],
                              self.why(reason))


# === AC-7: повод reference — без алертов =======================================


class ReferenceReasonAlertsTest(ReferenceSandbox):

    def test_ac7_reference_reason_neither_raises_nor_acks_alerts(self):
        """Сборка с поводом `reference` не трогает алерты ни в одном исходе; исход — в результате и журнале.

        Сценарий: до сборок открыты алерты проекта с источниками
        `brief.core_reference` и `fsm.core_reference_regen`. Вход без задачи
        с поводом `reference`: успешная сборка (`fresh`, запись
        «построен»); сбой сборки — несуществующий 40-значный sha (`absent`
        с пометкой, запись «сбой»); недостатки — модуль настройки не найден
        в коммите (`fresh` с пометкой); незаписанный кэш — замена файла
        отказывает (`fresh` с пометкой). После каждой — таблица алертов
        целиком та же, что до неё (ни новых, ни подтверждённых).

        Ловит мутацию: повод `reference` поднимает алерт (неизвестный повод
        уходит в источник `brief.core_reference` по умолчанию `ALERT_SOURCES`)
        на сбое, недостатке или незаписанном кэше, либо успешная сборка
        снимает открытый алерт брифа.
        """
        sha = self.add_project()
        alerts.raise_alert(self.conn, PROJECT, "incident", "brief.core_reference",
                           "справочник ядра: прежний сбой брифа")
        alerts.raise_alert(self.conn, PROJECT, "incident", "fsm.core_reference_regen",
                           "справочник ядра: прежний сбой мержа")
        missing = "".join(self.rng.choice("0123456789abcdef") for _ in range(40))

        def success():
            return self.get_for_target(sha=sha)

        def failure():
            return self.get_for_target(sha=missing)

        def problems():
            self.declare(setting=MISSING_MODULE_SETTING)
            try:
                return self.get_for_target(sha=self.commit(PROJECT, {"x/a.py": "A = 1\n"}))
            finally:
                self.declare(setting=SETTING)

        def unwritten():
            new_sha = self.commit(PROJECT, {"x/b.py": "B = 2\n"})
            with replace_fails():
                return self.get_for_target(sha=new_sha)

        cases = (("успех", success, "fresh", reference_cache.BUILT_ACTION, False),
                 ("сбой", failure, "absent", reference_cache.FAILED_ACTION, True),
                 ("недостатки", problems, "fresh", reference_cache.BUILT_ACTION, True),
                 ("кэш не записан", unwritten, "fresh", reference_cache.BUILT_ACTION, True))
        for label, call, state, action, noted in cases:
            with self.subTest(case=label):
                before = self.all_alerts()
                since = self.max_step()
                result = call()
                self.assert_state(result, state)
                self.assertEqual(before, self.all_alerts(),
                                 self.why(f"{label}: таблица алертов изменилась"))
                if noted:
                    self.assertTrue(field(result, "note"), self.why(f"{label}: пометки нет"))
                self.assertTrue(self.rows_of(action, since),
                                self.why(f"{label}: записи «{action}» в журнале нет"))


# === AC-8 … AC-14: команда reference ===========================================


class CommandRefusalTest(ReferenceSandbox):

    def test_ac8_unknown_project_refused_listing_projects_without_side_effects(self):
        """Неизвестный проект: ненулевой код, перечень проектов, ни каталогов, ни кэша, ни git.

        Сценарий: объявлены `artel`, `proj` и `other_<случайное>`; вызов
        `reference ghost_<случайное>` — ненулевой код, вывод называет все
        объявленные проекты; дерево песочницы (каталоги и файлы) то же, git
        не запускался.

        Ловит мутацию: на неизвестном проекте команда сначала заводит
        каталоги/кэш (`init_project`, запись кэша) или вызывает git (клон,
        rev-parse) и только потом сверяет имя, либо отказ не перечисляет
        проекты.
        """
        self.add_project()
        other = f"other_{self.rng.randrange(1 << 20):x}"
        self.declare(other)
        ghost = f"ghost_{self.rng.randrange(1 << 20):x}"
        before = paths_snapshot(self.root)
        code, out = self.run_cmd("reference", ghost)
        self.assertNotEqual(0, code, self.why(out))
        for name in (config.DEFAULT_TARGET, PROJECT, other):
            self.assertIn(name, out, self.why("перечень проектов"))
        self.assertEqual(before, paths_snapshot(self.root), self.why("дерево изменилось"))
        self.assertEqual([], self.git_runs(), self.why("git вызван"))

    def test_ac9_broken_entry_refused_with_targets_error_text_without_absent(self):
        """Сломанная запись проекта (неверное `min_uses`, нет поля) — код ≠ 0, текст TargetsError, без `absent`.

        Сценарий: запись проекта с `min_uses` 0, 1001, `true`, строкой, а
        также запись без поля `forge`; ожидаемый текст берётся у
        `targets.target(<проект>)` той же декларации; вывод его содержит и
        не называет состояние `absent`.

        Ловит мутацию: команда читает настройку через сборку (`absent` с
        алертом и кодом сбоя) вместо `targets.target()` до любых действий,
        либо проверка записи принимает неверное `min_uses` (0, 1001, `true`,
        строка) — команда собирает справочник с кодом 0.
        """
        self.add_project()
        cases = [(f"min_uses={v!r}", dict(SETTING, min_uses=v), ())
                 for v in (0, 1001, True, "abc")]
        cases.append(("нет поля forge", SETTING, ("forge",)))
        for label, setting, omit in cases:
            with self.subTest(case=label):
                self.declare(setting=setting, omit=omit)
                with self.assertRaises(targets.TargetsError) as expected:
                    targets.target(PROJECT)
                code, out = self.run_cmd("reference", PROJECT)
                self.assertNotEqual(0, code, self.why(f"{label}: {out}"))
                self.assertIn(str(expected.exception), out, self.why(label))
                self.assertNotIn("absent", out, self.why(label))

    def test_ac10_no_clone_no_base_ref_and_no_db_refused(self):
        """Нет клона — отказ с `target-init`; нет `refs/heads/<base>` — отказ; нет БД — отказ, файл БД не создан.

        Сценарий: (1) проект объявлен, клона нет — код ≠ 0, в выводе
        `target-init`; (2) клон есть, базовая ветка переименована — код ≠ 0,
        вывод называет базовую ветку; (3) клон в порядке, файл БД пульта
        удалён — код ≠ 0, строка «журнал недоступен — сначала init», файла
        БД после вызова нет.

        Ловит мутацию: `reference` без клона не отказал (ушёл в сборку с
        `absent` или завёл клон), ссылка базы берётся через `HEAD`/`fetch`
        вместо `refs/heads/<base>`, либо БД открывается `store.db()` (файл
        создаётся) вместо проверки `store.db_usable()`.
        """
        with self.subTest(case="нет клона"):
            self.declare()
            code, out = self.run_cmd("reference", PROJECT)
            self.assertNotEqual(0, code, self.why(out))
            self.assertIn("target-init", out, self.why(out))
        with self.subTest(case="нет ссылки базы"):
            self.add_project()
            renamed = f"renamed-{self.rng.randrange(1 << 20):x}"
            self.git("-C", str(self.clones[PROJECT]), "branch", "-m",
                     config.MAIN_BRANCH, renamed)
            code, out = self.run_cmd("reference", PROJECT)
            self.assertNotEqual(0, code, self.why(out))
            self.assertIn(config.MAIN_BRANCH, out, self.why(out))
            self.git("-C", str(self.clones[PROJECT]), "branch", "-m",
                     renamed, config.MAIN_BRANCH)
        with self.subTest(case="нет БД"):
            self.drop_db()
            code, out = self.run_cmd("reference", PROJECT)
            self.assertNotEqual(0, code, self.why(out))
            self.assertIn(NO_DB, out, self.why(out))
            self.assertFalse(Path(config.DB).exists(), self.why("файл БД создан"))

    def test_ac11_sha_form_and_default_base_commit_without_fetch(self):
        """`--sha` не формы `SHA_FORM` — отказ; без `--sha` — коммит `refs/heads/<base>` клона, без `fetch`.

        Сценарий: базовая ветка клона на коммите A, рабочее дерево клона
        переключено на ветку `side` с коммитом B (HEAD = B). `--sha` с
        коротким sha, именем ветки, 39 и 41 знаком, заглавными буквами —
        код ≠ 0. Без `--sha` — код 0, кэш и вывод несут A, не B, `fetch` не
        запускался. С полным `--sha B` — код 0, кэш на B.

        Ловит мутацию: без `--sha` берётся `HEAD` клона (кэш на B) или
        перед сборкой делается `git fetch`, либо `--sha` принимает короткий
        sha / имя ветки (разрешает его через rev-parse).
        """
        base = self.add_project()
        clone = self.clones[PROJECT]
        self.git("-C", str(clone), "checkout", "-q", "-b", "side")
        side = self.commit(PROJECT, {"side/s.py": "SIDE = 1\n"})
        for value in (side[:7], "side", config.MAIN_BRANCH, side[:39], side + "0",
                      side.upper()):
            with self.subTest(sha=value):
                code, out = self.run_cmd("reference", PROJECT, "--sha", value)
                self.assertNotEqual(0, code, self.why(f"--sha {value}: {out}"))
        code, out = self.run_cmd("reference", PROJECT)
        self.assertEqual(0, code, self.why(out))
        cache = self.cache_bytes().decode("utf-8")
        self.assertIn(f"built_at_sha: {base}", cache, self.why("кэш не на базе"))
        self.assertIn(base, out)
        self.assertNotIn(side, out)
        self.assertFalse([argv for argv in self.git_runs() if "fetch" in argv],
                         self.why("fetch вызван"))
        code, out = self.run_cmd("reference", PROJECT, "--sha", side)
        self.assertEqual(0, code, self.why(out))
        self.assertIn(f"built_at_sha: {side}", self.cache_bytes().decode("utf-8"))


class CommandSummaryTest(ReferenceSandbox):

    def assert_percent(self, out: str, size: int, limit: int) -> None:
        pct = size * 100 / limit
        shown = [float(x.replace(",", ".")) for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", out)]
        self.assertTrue([x for x in shown if abs(x - pct) < 1],
                        self.why(f"доли {pct:.2f}% нет в выводе: {out}"))

    def test_ac12_summary_fields_cache_file_and_exit_codes(self):
        """Сводка: состояние, sha, байты, предел, доля, порог с источником, вывод; кэш записан; коды выхода.

        Сценарий: без подполя — `fresh`, код 0, кэш в
        `<область>/proj/knowledge/derived/core-reference.md`, вывод несёт
        sha, размер кэша в байтах, `CORE_REFERENCE_MAX_BYTES`, долю в
        процентах, порог `config` на строке с «умолчание» и «в пределе»;
        повтор — `cached`, код 0; подполе m — порог m на строке с
        «настройка проекта»; предел подменён ниже размера — код 0;
        проект без поля — `off`, код 0; несуществующий sha — `absent` с
        причиной, код ≠ 0.

        Ловит мутацию: сводка печатает размер тела вместо полного файла,
        не называет источник порога, команда возвращает ненулевой код при
        размере больше предела (это сообщение, не ошибка) или нулевой при
        `absent`, либо кэш команды не записывается.
        """
        sha = self.add_project()
        default = config.CORE_REFERENCE_MIN_USES
        limit = config.CORE_REFERENCE_MAX_BYTES
        code, out = self.run_cmd("reference", PROJECT)
        self.assertEqual(0, code, self.why(out))
        self.assertTrue(self.cache_path().is_file(), self.why("кэш не записан"))
        size = len(self.cache_bytes())
        self.assertIn("fresh", out)
        self.assertIn(sha, out)
        self.assertTrue(has_number(out, size), self.why(f"размера {size} нет: {out}"))
        self.assertTrue(has_number(out, limit), self.why(f"предела {limit} нет: {out}"))
        self.assert_percent(out, size, limit)
        self.assertTrue([line for line in out.split("\n")
                         if "умолчание" in line and has_number(line, default)],
                        self.why(f"порога {default} с «умолчание» нет: {out}"))
        self.assertEqual({WITHIN}, verdicts(out), self.why(out))

        code, out = self.run_cmd("reference", PROJECT)
        self.assertEqual(0, code, self.why(out))
        self.assertIn("cached", out)

        m = self.rng.choice([v for v in range(1, 40) if v != default])
        self.declare(setting=dict(SETTING, min_uses=m))
        code, out = self.run_cmd("reference", PROJECT)
        self.assertEqual(0, code, self.why(out))
        self.assertIn("fresh", out)
        self.assertTrue([line for line in out.split("\n")
                         if "настройка проекта" in line and has_number(line, m)],
                        self.why(f"порога {m} с «настройка проекта» нет: {out}"))

        with mock.patch.object(config, "CORE_REFERENCE_MAX_BYTES", 100):
            code, out = self.run_cmd("reference", PROJECT)
        self.assertEqual(0, code, self.why(f"больше предела — не ошибка: {out}"))

        missing = "".join(self.rng.choice("0123456789abcdef") for _ in range(40))
        code, out = self.run_cmd("reference", PROJECT, "--sha", missing)
        self.assertNotEqual(0, code, self.why(out))
        self.assertIn("absent", out)
        self.assertIn(reference_cache.SOURCE_FAILED, out, self.why("причины нет"))

        self.declare(setting=None)
        code, out = self.run_cmd("reference", PROJECT)
        self.assertEqual(0, code, self.why(out))
        self.assertIn("off", out)

    def test_ac13_size_in_utf8_bytes_and_verdict_boundaries(self):
        """Размер — байты UTF-8 файла кэша; вывод по `size > limit` и строгому `size*10 > limit*9`.

        Сценарий: справочник с кириллицей (байтов заметно больше знаков);
        модульная строка дополняется, пока размер S кэша не кратен 9. Предел
        подменяется: S−1 — «больше предела»; S и 10S/9−1 — «больше 90%»;
        ровно 10S/9 (S — ровно 90%) — «в пределе»; 2S — «в пределе». Вывод
        называет S.

        Ловит мутацию: граница 90% нестрогая (`>=` — ровно 90% даёт
        предупреждение вместо «в пределе»), размер считается знаками
        `len(text)` (при пределе S−1 сводка не называет «больше предела»),
        либо сравнение с пределом нестрогое (`>=`, при пределе S — «больше
        предела»).
        """
        size = 0
        for pad in range(30):
            sha = self.add_project(files=project_files(3, 1, "x" * pad)) if pad == 0 \
                else self.commit(PROJECT, project_files(3, 1, "x" * pad))
            code, out = self.run_cmd("reference", PROJECT, "--sha", sha)
            self.assertEqual(0, code, self.why(out))
            size = len(self.cache_bytes())
            if size % 9 == 0:
                break
        self.assertEqual(0, size % 9, self.why(f"размер {size} не подогнан"))
        chars = len(self.cache_bytes().decode("utf-8"))
        self.assertLess(chars * 10, (size - 1) * 9,
                        self.why("фикстура: байты и знаки не различаются"))
        exact = size * 10 // 9
        cases = ((size - 1, OVER), (size, WARN), (exact - 1, WARN),
                 (exact, WITHIN), (size * 2, WITHIN))
        for limit, expected in cases:
            with self.subTest(limit=limit, expected=expected):
                with mock.patch.object(config, "CORE_REFERENCE_MAX_BYTES", limit):
                    code, out = self.run_cmd("reference", PROJECT, "--sha", sha)
                self.assertEqual(0, code, self.why(out))
                self.assertTrue(has_number(out, size), self.why(f"размера {size} нет"))
                self.assertEqual({expected}, verdicts(out), self.why(f"предел {limit}: {out}"))

    def test_ac14_command_journal_rows_without_task_on_command_project(self):
        """Записи «построен» и «сбой» команды — без задачи, с `target` проекта, не `DEFAULT_TARGET`.

        Сценарий: проект `proj_<случайное>` (не artel); `reference` на нём —
        новая запись «построен» с `task_id` NULL, `target` проекта и поводом
        `reference`; `reference --sha <несуществующий>` — запись «сбой» с
        `task_id` NULL и `target` проекта; ни одной новой такой записи на
        `DEFAULT_TARGET`.

        Ловит мутацию: запись журнала команды ушла на `DEFAULT_TARGET`
        (`store.journal` без явного `target=`), либо команда пишет журнал
        от фиктивной задачи вместо `task_id=None`.
        """
        name = f"proj_{self.rng.randrange(1 << 20):x}"
        self.add_project(name)
        actions = (reference_cache.BUILT_ACTION, reference_cache.FAILED_ACTION)
        since = self.max_step()
        code, out = self.run_cmd("reference", name)
        self.assertEqual(0, code, self.why(out))
        built = self.rows_of(reference_cache.BUILT_ACTION, since)
        self.assertEqual(1, len(built), self.why(f"записи «построен»: {out}"))
        self.assertIsNone(built[0]["task_id"])
        self.assertEqual(name, built[0]["target"])
        self.assertIn("reference", built[0]["detail"])

        missing = "".join(self.rng.choice("0123456789abcdef") for _ in range(40))
        mid = self.max_step()
        code, out = self.run_cmd("reference", name, "--sha", missing)
        self.assertNotEqual(0, code, self.why(out))
        failed = self.rows_of(reference_cache.FAILED_ACTION, mid)
        self.assertEqual(1, len(failed), self.why(f"записи «сбой»: {out}"))
        self.assertIsNone(failed[0]["task_id"])
        self.assertEqual(name, failed[0]["target"])
        for action in actions:
            self.assertFalse([row for row in self.rows_of(action, since)
                              if row["target"] == config.DEFAULT_TARGET],
                             self.why(f"«{action}» ушла на DEFAULT_TARGET"))


# === AC-15: окружение роли =====================================================


class RoleRefusalTest(ReferenceSandbox):

    def test_ac15_reference_refused_in_role_environment_without_build(self):
        """Из окружения роли `reference` отказывает, как команды Оператора, без сборки.

        Сценарий: маркер роли `ARTEL_ROLE=role_<случайное>` в окружении;
        `reference proj` — код ≠ 0, текст отказа «недоступна процессу
        роли», кэша нет, git не запускался, записей «построен»/«сбой» нет.

        Ловит мутацию: `reference` выполнилась из окружения роли —
        команда внесена в `_ROLE_ALLOWED_COMMANDS` или обходит отказ
        диспетчера (справочник собран, кэш записан).
        """
        self.add_project()
        env = self.env_operator()
        env[config.ARTEL_ROLE_ENV] = f"role_{self.rng.randrange(1 << 20):x}"
        since = self.max_step()
        code, out = self.run_cmd("reference", PROJECT, env=env)
        self.assertNotEqual(0, code, self.why(out))
        self.assertIn(ROLE_REFUSAL, out, self.why(out))
        self.assertFalse(self.cache_path().exists(), self.why("кэш записан"))
        self.assertEqual([], self.git_runs(), self.why("git вызван"))
        for action in (reference_cache.BUILT_ACTION, reference_cache.FAILED_ACTION):
            self.assertFalse(self.rows_of(action, since), self.why(action))


# === AC-16: target-init =========================================================


class TargetInitTest(ReferenceSandbox):

    def project_dirs(self) -> list:
        return [config.PROJECTS / PROJECT / sub for sub in config.PROJECT_DIRS]

    def test_ac16_target_init_prints_summary_survives_failure_no_db_and_off(self):
        """`target-init`: сводка после клона; сбой сборки, нет БД и нет поля — строка, без падения.

        Сценарий (клон проекта уже есть): (1) `target-init proj` — код 0,
        сводка (`fresh`, sha базы, размер кэша, предел, «в пределе»); (2)
        предел числа файлов `CORE_REFERENCE_MAX_FILES` подменён нулём —
        код 0, вывод называет причину «сверх пределов чтения», каталоги
        проекта и клон на месте; (3) файл БД удалён — код 0, строка
        «справочник ядра: журнал недоступен — сначала init»; (4) проект без
        поля — код 0, строка «справочник ядра: выключен (нет поля
        core_reference)».

        Ловит мутацию: `target-init` упал или удалил клон при сбое сборки
        (`sys.exit`/исключение из сборки, уборка каталога клона), не
        собирает справочник после клона (сводки нет), либо без БД зовёт
        `store.db()`/падает на журнале.
        """
        sha = self.add_project()
        with self.subTest(case="сводка"):
            code, out = self.run_cmd("target-init", PROJECT)
            self.assertEqual(0, code, self.why(out))
            self.assertIn("fresh", out)
            self.assertIn(sha, out)
            self.assertTrue(has_number(out, len(self.cache_bytes())), self.why(out))
            self.assertTrue(has_number(out, config.CORE_REFERENCE_MAX_BYTES), self.why(out))
            self.assertIn(WITHIN, out)
        with self.subTest(case="сбой сборки"):
            self.cache_path().unlink()
            with mock.patch.object(config, "CORE_REFERENCE_MAX_FILES", 0):
                code, out = self.run_cmd("target-init", PROJECT)
            self.assertEqual(0, code, self.why(out))
            self.assertIn(reference_cache.OVER_LIMITS, out, self.why(out))
            for path in self.project_dirs():
                self.assertTrue(path.is_dir(), self.why(f"нет {path}"))
            self.assertTrue((self.clones[PROJECT] / ".git").is_dir(), self.why("клон удалён"))
        with self.subTest(case="нет поля"):
            self.declare(setting=None)
            code, out = self.run_cmd("target-init", PROJECT)
            self.assertEqual(0, code, self.why(out))
            self.assertIn(INIT_OFF, out, self.why(out))
            self.declare(setting=SETTING)
        with self.subTest(case="нет БД"):
            self.drop_db()
            code, out = self.run_cmd("target-init", PROJECT)
            self.assertEqual(0, code, self.why(out))
            self.assertIn(INIT_NO_DB, out, self.why(out))


# === AC-17: справка ============================================================


class HelpTest(ReferenceSandbox):

    def test_ac17_help_lists_reference_and_names_sha_form(self):
        """Общий перечень команд справки содержит `reference`, справка команды — форму `--sha <sha>`.

        Сценарий: `artel.py` без аргументов — в разделе «Команды:» есть
        строка с командой `reference`; форма `--sha <sha>` названа в
        строках перечня с `reference` либо в выводе `artel.py reference
        --help`.

        Ловит мутацию: строка команды `reference` не добавлена в перечень
        команд справки или справка команды не называет `--sha <sha>`.
        """
        code, out = self.run_cmd()
        self.assertEqual(0, code, self.why(out))
        lines = out.split("\n")
        start = next((i for i, line in enumerate(lines) if line.strip() == "Команды:"), None)
        self.assertIsNotNone(start, self.why("раздела «Команды:» нет"))
        section = []
        for line in lines[start + 1:]:
            if not line.startswith(" "):
                break
            section.append(line)
        mentions = [line for line in section
                    if re.search(r"(?<![\w-])reference(?![\w-])", line)]
        self.assertTrue(mentions, self.why("строки reference в перечне нет"))
        if not any("--sha <sha>" in line for line in mentions):
            _code, command_help = self.run_cmd("reference", "--help")
            self.assertIn("--sha <sha>", command_help, self.why(command_help))


if __name__ == "__main__":
    unittest.main()
