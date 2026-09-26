"""Тонкая надстройка `LightTransitionSandbox` (tests/sandbox.py) для планки
задачи 01M3F7C2DVYCEANQ8CF1FCSD87: сценарий один на все файлы — синтетическая
задача пульта ставится в `verifying`, `gh` подменяется целиком (сети нет ни в
одном тесте, требование 12 SPEC), после чего зовётся команда пульта `ci-rerun`
и наблюдается её исход: состояние задачи, записи журнала, факт и аргументы
вызова `ci.trigger_rerun`, сырые argv подменённого `gh`.

`disk_backed_show`/`disk_backed_ls_tree_files`/`fake_git`/`set_state`/
`advance_from_in_dev` здесь НЕ переопределяются — импортируются готовыми
вместе с `LightTransitionSandbox` (skills/test-authoring.md, «Лёгкая
песочница переходов — не копия, импорт»). Собственного здесь только то,
чего эталонная песочница не знает:

- двухадресный `gh`-стенд (`_gh`): check-run'ы головы ветки задачи и
  check-run'ы вершины главной ветки различаются ПО SHA в URL, потому что
  сверка требования 5 SPEC читает оба коммита одним и тем же вызовом
  `gh api .../commits/<sha>/check-runs`;
- голова ветки задачи и вершина главной ветки как ИЗМЕНЯЕМЫЕ величины
  (`self.head`, `self.main_sha`) — сценарии AC-4 (голова уехала) и AC-6
  (вершина главной ветки не определена) отличаются от штатного только ими;
- шпион `ci.trigger_rerun`, ДЕЛЕГИРУЮЩИЙ настоящей функции (требование 7:
  повтор исполняет существующий узел, дублирующего кода не заводится) —
  считает вызовы, не подменяя поведение: `gh run rerun`/`gh run watch`
  внутри неё всё равно уходят в тот же подменённый `gh`;
- вход в `verifying` С НАСТОЯЩЕЙ записью журнала о красном CI
  (`enter_verifying_red`): требование 4 SPEC читает sha именно из
  последней такой записи, поэтому запись обязана появиться тем же кодом
  (`fsm_advance.verifying` -> `fsm.VERIFYING_STATUS_ACTION`), которым её
  пишет живой цикл, а не подделкой руками.

## Почему адрес команды разыскивается, а не зашит

SPEC называет регистрацию команды в `orchestrator/artel.py` (требование 1)
и зоны `orchestrator/ci.py`/`orchestrator/artel.py`/`orchestrator/fsm.py`,
но НЕ называет ни модуль тела команды, ни имя его функции. Планка —
неизменяемый лок: зафиксируй она выбранное автором тестов имя, разработчик
был бы обязан угадать именно его, хотя ни один критерий такого не требует.
`resolve_command` идёт от того, что SPEC действительно называет: разбирает
таблицу команд `orchestrator/artel.py` (запись `"ci-rerun": lambda: X.Y(...)`)
и берёт оттуда адрес обработчика; таблица не разобрана — перебирает
очевидные адреса (`fsm.cmd_ci_rerun`, `ci.cmd_ci_rerun`).

## Почему отказ перехватывается, а не ожидается `assertRaises`

«Именованный отказ» в этой кодовой базе — и `sys.exit("текст")`
(`amend.cmd_amend_tests`, `_cmd_stop`), и `print` + `return`
(`fsm._cmd_advance`); ни один критерий AC-1..AC-6/AC-9/AC-11 механизма не
называет. `run_ci_rerun` приводит оба к одному тексту, чтобы планка
проверяла наблюдаемое по критериям (текст отказа, отсутствие повтора,
неизменность состояния), а не произвольно выбранный ею механизм. Любое
ДРУГОЕ исключение (трейсбек — прямой запрет требования 8/AC-9) наружу
проходит и валит тест.
"""
import importlib
import inspect
import io
import json
import re
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import ci, config, fsm, gitcmd, runner, store  # noqa: E402
from tests.sandbox import LightTransitionSandbox, fake_git  # noqa: E402

# Три sha сценариев. Разные первые 8 символов — отказы называют sha
# короткой формой (`ci.verifying_status`: `short = sha[:8]`), и сверка по
# префиксу обязана различать их однозначно.
BRANCH_HEAD = "1a2b3c4d" + "0" * 32
MOVED_HEAD = "5c5c5c5c" + "1" * 32
MAIN_SHA = "9f8e7d6c" + "2" * 32

# Id workflow-прогона головы ветки задачи: его находит `ci.find_run_id`
# внутри `ci.trigger_rerun`, и он обязан попасть в запись журнала
# (требование 8, AC-7).
RUN_ID = "4242"

# Задание, упавшее на ветке задачи. AC-5 разыгрывается тем, что ЭТО ЖЕ имя
# красно и на вершине главной ветки (сверка требования 5 — по именам).
FAILED_JOB = "python"

# Основания Оператора. Второе (AC-11) отличается от первого дословно —
# именно дословное совпадение с последним основанием отказывает.
#
# Ни одно из них НЕ содержит слов, по которым `names_*_outcome` ниже узнают
# исход ожидания («красн», «зелён», «успеш», «failure», «не ответил»):
# запись журнала несёт основание дословно, и слово об исходе внутри самого
# основания делало бы сверку исхода тавтологией.
REASON = ("флейк test_command_writes_nothing: прогон push упал, "
          "pull_request того же sha прошёл")
REASON_NEW = "второй флейк того же прогона: job guard упал по таймауту сети"


def completed(name: str, conclusion: str) -> dict:
    return {"name": name, "status": "completed", "conclusion": conclusion}


def check_runs_json(runs: list) -> str:
    return json.dumps({"total_count": len(runs), "check_runs": runs})


# Четыре исхода `ci.verifying_status` для головы ветки задачи (SPEC T079,
# этой задачей не меняются — требование 2 ссылается на них как на данность).
BRANCH_RED = check_runs_json([completed("guard", "success"),
                              completed(FAILED_JOB, "failure")])
BRANCH_GREEN = check_runs_json([completed("guard", "success"),
                                completed(FAILED_JOB, "success")])
BRANCH_RUNNING = check_runs_json(
    [{"name": FAILED_JOB, "status": "in_progress", "conclusion": None}])
BRANCH_NO_RUNS = check_runs_json([])

# Вершина главной ветки: зелёная (штатный путь — краснота ветки задачи
# флейк) либо красная тем же заданием (AC-5 — дефект main, не флейк).
MAIN_GREEN = check_runs_json([completed("guard", "success"),
                              completed(FAILED_JOB, "success")])
MAIN_RED_SAME_JOB = check_runs_json([completed("guard", "success"),
                                     completed(FAILED_JOB, "failure")])

RUN_LIST_EMPTY = "[]"

WORKFLOW_RUNS = json.dumps({"workflow_runs": [
    {"databaseId": int(RUN_ID), "status": "completed", "conclusion": "failure"},
]})

# Адреса обработчика команды на случай, если таблица команд
# `orchestrator/artel.py` не разобрана (см. докстринг модуля).
ENTRY_FALLBACKS = (("fsm", "cmd_ci_rerun"), ("ci", "cmd_ci_rerun"),
                   ("fsm", "cmd_rerun_ci"), ("ci", "cmd_rerun_ci"))

_TABLE_ENTRY_RE = re.compile(r'"ci-rerun"\s*:\s*lambda[^:]*:\s*([\w.]+)\s*\(')


def resolve_command():
    """Обработчик команды `ci-rerun` пульта либо `None` — команды нет.

    Сначала — адрес из таблицы команд `orchestrator/artel.py` (требование
    1 SPEC), затем очевидные адреса `ENTRY_FALLBACKS`. Чтение исходника
    пульта, а не артефакта задачи: `orchestrator/artel.py` есть и в
    рабочей копии автора, и в среде прогона гейта (планка там импортирует
    те же модули `orchestrator/`).
    """
    source = (REPO_ROOT / "orchestrator" / "artel.py").read_text(
        encoding="utf-8")
    match = _TABLE_ENTRY_RE.search(source)
    candidates = list(ENTRY_FALLBACKS)
    if match:
        module_path, _, attr = match.group(1).rpartition(".")
        if module_path:
            candidates.insert(0, (module_path, attr))
    for module_name, attr in candidates:
        try:
            module = importlib.import_module(f"orchestrator.{module_name}")
        except ImportError:
            continue
        handler = getattr(module, attr, None)
        if callable(handler):
            return handler
    return None


_NEGATED_GREEN_RE = re.compile(r"не\s+(?:стал\s+|сделал\w*\s+)?зел[её]н\w*")


def names_green_outcome(text: str) -> bool:
    """Текст называет исход ожидания «зелёный» (требование 8, AC-7).

    Отрицания зелёного (`не зелёный`, `не стал зелёным` — форма, которой
    описывают ровно ОБРАТНЫЙ исход) вырезаются до сверки: иначе запись «CI
    не зелёный» читалась бы как объявленный зелёный исход, и AC-8 падал бы
    на корректной реализации."""
    low = _NEGATED_GREEN_RE.sub("", text.lower())
    return "зел" in low or "green" in low or "успеш" in low


def names_red_outcome(text: str) -> bool:
    """Текст называет исход ожидания «снова красный» (требование 8, AC-8)."""
    low = text.lower()
    return "красн" in low or "не зелён" in low or "failure" in low


def names_gh_silence(text: str) -> bool:
    """Текст называет исход «`gh` не ответил» (требование 8, AC-9)."""
    low = text.lower()
    return ("не ответил" in low or "не запущен" in low or "молчал" in low
            or "неизвест" in low or "нет ответа" in low)


class CiRerunSandbox(LightTransitionSandbox):
    """Задача песочницы в `verifying` + подменённый `gh` + вызов `ci-rerun`."""

    TASK_TITLE = "Повтор упавшего CI ветки на verifying"

    def setUp(self):
        super().setUp()

        # Фикстура CI: каждое поле — крутилка одного сценария планки.
        self.head = BRANCH_HEAD
        self.main_sha = MAIN_SHA
        self.branch_check_runs = BRANCH_RED
        self.main_check_runs = MAIN_GREEN
        self.main_check_runs_fail = False
        self.run_list_json = RUN_LIST_EMPTY
        self.rerun_rc = 0
        self.rerun_stderr = "gh run rerun не ответил"
        self.watch_rc = 0
        self.watch_stderr = "gh run watch не ответил"
        self.gh_down = False
        self.gh_down_after_rerun = False
        # Чем становятся check-run'ы головы ветки ПОСЛЕ повтора: `None` —
        # ничем (остаются теми же, сценарий «снова красный»), иначе —
        # заданным ответом (сценарий зелёного повтора).
        self.branch_check_runs_after_rerun = None

        self.gh_calls: list[tuple] = []
        self.rerun_calls: list[tuple] = []
        self.watch_calls: list[tuple] = []
        self.trigger_calls: list[str] = []
        self._gh_calls_before_command = 0

        real_trigger_rerun = ci.trigger_rerun

        def trigger_spy(branch, *args, **kwargs):
            self.trigger_calls.append(branch)
            return real_trigger_rerun(branch, *args, **kwargs)

        for target, value in (("gh", self._gh),
                              ("head_sha", self._head_sha),
                              ("trigger_rerun", trigger_spy)):
            patcher = mock.patch.object(ci, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        # Вершина главной ветки: тот же адрес, каким её читает пульт сегодня
        # (`fsm._origin_main_sha`), плюс `rev-parse` через подменённый
        # `gitcmd.git` — команда вправе взять любой из двух, оба отдают
        # `self.main_sha`.
        origin_patcher = mock.patch.object(
            fsm, "_origin_main_sha", lambda *a, **k: self.main_sha or None)
        origin_patcher.start()
        self.addCleanup(origin_patcher.stop)

        git_patcher = mock.patch.object(gitcmd, "git", self._git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)

        # Ни один сценарий планки не имеет права запустить агента: команда
        # `ci-rerun` роли не запускает (требование 9, AC-8). Настоящий
        # `cmd_run`/`spawn_agent` здесь породил бы внешний CLI без сети и
        # токена вместо читаемого сообщения.
        for attr in ("cmd_run", "spawn_agent"):
            patcher = mock.patch.object(runner, attr, self._no_agent_here)
            patcher.start()
            self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ стенды

    @staticmethod
    def _no_agent_here(*args, **kwargs):
        raise AssertionError(
            "агент запущен: команда ci-rerun роли не запускает (требование "
            "9 SPEC), а verifying агентской роли не несёт вовсе")

    def _gh(self, *args: str, **kwargs) -> subprocess.CompletedProcess:
        """Подменённый `ci.gh`: сеть не задействована ни в одном вызове.

        Порядок разбора важен: `run rerun`/`run watch` обрабатываются ДО
        флага `self.gh_down`, потому что сценарий AC-9 «`gh` перестал
        отвечать» включает молчание ИМЕННО с повтора и дальше.
        """
        self.gh_calls.append(args)
        joined = " ".join(args)

        if args[:2] == ("run", "rerun"):
            self.rerun_calls.append(args)
            if self.branch_check_runs_after_rerun is not None:
                self.branch_check_runs = self.branch_check_runs_after_rerun
            if self.gh_down_after_rerun:
                self.gh_down = True
            return self._answer(self.rerun_rc, "", self.rerun_stderr)
        if args[:2] == ("run", "watch"):
            self.watch_calls.append(args)
            if self.gh_down_after_rerun:
                self.gh_down = True
            return self._answer(self.watch_rc, "прогон завершён",
                                self.watch_stderr)
        if self.gh_down:
            return self._answer(1, "", "gh не ответил: сеть недоступна")
        if "check-runs" in joined:
            return self._check_runs_answer(joined)
        if "actions/runs" in joined:
            return self._answer(0, WORKFLOW_RUNS, "")
        if args[:2] == ("run", "list"):
            return self._answer(0, self.run_list_json, "")
        return self._answer(0, "", "")

    def _check_runs_answer(self, url: str) -> subprocess.CompletedProcess:
        """Check-run'ы КОНКРЕТНОГО коммита: голова ветки задачи и вершина
        главной ветки различаются по sha в URL (см. докстринг модуля).
        Посторонний sha (в т.ч. пустой — вершина главной ветки не
        определена) — отказ `gh`, а не чужие проверки: иначе сценарий AC-6
        читался бы как «main зелёная»."""
        match = re.search(r"commits/([0-9a-zA-Z]*)/check-runs", url)
        sha = match.group(1) if match else ""
        if sha == self.head:
            return self._answer(0, self.branch_check_runs, "")
        if sha and sha == self.main_sha:
            if self.main_check_runs_fail:
                return self._answer(
                    1, "", "gh не ответил: HTTP 503 на проверках main")
            return self._answer(0, self.main_check_runs, "")
        return self._answer(1, "", f"gh не ответил: коммит {sha or '?'} "
                                   f"неизвестен")

    @staticmethod
    def _answer(returncode: int, stdout: str,
                stderr: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            ["gh"], returncode, stdout if returncode == 0 else "",
            "" if returncode == 0 else stderr)

    def _head_sha(self, branch: str, repo=None) -> tuple:
        """Голова ветки задачи (`self.head`) либо вершина главной ветки —
        по имени ветки, тем же контрактом `(sha, причина)`, что у
        настоящей `ci.head_sha`."""
        if branch == self.branch:
            return (self.head, "") if self.head else (
                "", f"головной коммит ветки {branch} не определён")
        if config.MAIN_BRANCH in branch:
            return (self.main_sha, "") if self.main_sha else (
                "", f"головной коммит ветки {branch} не определён")
        return "", f"головной коммит ветки {branch} не определён"

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        """`fake_git` эталонной песочницы + `rev-parse` вершины главной
        ветки: `fake_git` отвечает на `rev-parse` пустой строкой, и
        команда, читающая вершину main через git, не отличила бы штатный
        сценарий от AC-6."""
        if args[:1] == ("rev-parse",) and any(
                config.MAIN_BRANCH in a for a in args):
            if not self.main_sha:
                return subprocess.CompletedProcess(
                    list(args), 1, "", "fatal: ambiguous argument")
            return subprocess.CompletedProcess(
                list(args), 0, f"{self.main_sha}\n", "")
        return fake_git(*args)

    # ------------------------------------------------------------ сценарий

    def enter_verifying_red(self) -> str:
        """Вводит задачу в `verifying` и оставляет в журнале НАСТОЯЩУЮ
        запись о завершённом красном CI головы ветки — ту, из которой
        требование 4 берёт sha остановки цикла.

        Запись пишет настоящий `fsm_advance.verifying` (через
        `fsm.cmd_advance`), а не подделка руками: форма detail
        (`ci.verifying_status`) — вход сверки требования 4, и подделка
        расходилась бы с живым циклом молча.
        """
        self.set_state("verifying")
        self.branch_check_runs = BRANCH_RED
        out = self.capture(lambda: fsm.cmd_advance(self.TASK))
        self.assertEqual(
            self.state(), "verifying",
            "красный CI сам по себе не двигает задачу из verifying — "
            "фикстура планки сломана, а не реализация")
        return out

    def run_ci_rerun(self, reason=REASON) -> str:
        """Зовёт команду пульта `ci-rerun` и отдаёт всё, что она сказала.

        `SystemExit` именованного отказа перехватывается, его сообщение
        дописывается к тексту (см. докстринг модуля). Команды нет вовсе —
        тест падает здесь с адресом, который планка искала.
        """
        handler = resolve_command()
        if handler is None:
            self.fail(
                "команда пульта `ci-rerun` не найдена: ни в таблице команд "
                "orchestrator/artel.py (запись \"ci-rerun\": lambda: "
                "<модуль>.<функция>(...)), ни по адресам "
                f"{['.'.join(c) for c in ENTRY_FALLBACKS]}")
        self._gh_calls_before_command = len(self.gh_calls)
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            try:
                self._invoke(handler, reason)
            except SystemExit as exc:
                buf.write(f"\n{exc}\n")
        return buf.getvalue()

    def _invoke(self, handler, reason) -> None:
        """Вызов обработчика: основание — позиционно, а если сигнатура
        объявила его keyword-only, то по имени. Форму сигнатуры SPEC не
        называет, и планка не имеет права её диктовать."""
        try:
            params = inspect.signature(handler).parameters
        except (TypeError, ValueError):  # pragma: no cover — С-функция
            params = {}
        keyword_only = any(
            name in ("reason", "основание")
            and p.kind is inspect.Parameter.KEYWORD_ONLY
            for name, p in params.items())
        if keyword_only:
            handler(self.TASK, reason=reason)
            return
        handler(self.TASK, reason)

    # ------------------------------------------------------------ наблюдение

    def gh_calls_since_command(self) -> list[tuple]:
        """Сырые argv `gh`, сделанные ПОСЛЕ старта последней команды
        (вход `verifying` со своим опросом CI — не её обращения)."""
        return self.gh_calls[self._gh_calls_before_command:]

    def last_step_id(self) -> int:
        rows = store.task_steps(store.db(), self.TASK)
        return rows[-1]["id"] if rows else 0

    def journal_since(self, since_id: int) -> list[str]:
        """Строки журнала (`action` + `detail`) после `since_id`:
        содержательный текст `store.journal` кладёт то в одно поле, то в
        другое."""
        rows = store.task_steps(store.db(), self.TASK)
        return [f"{r['action']} {r['detail'] or ''}"
                for r in rows if r["id"] > since_id]

    def state_transitions_since(self, since_id: int) -> list[str]:
        """Записи перехода состояния (`state -> X`) после `since_id` —
        AC-8/AC-10 требуют их ОТСУТСТВИЯ от самой команды."""
        return [line for line in self.journal_since(since_id)
                if line.startswith("state ->")]

    def names_ci_status(self, text: str) -> bool:
        """Текст называет статус CI ветки (AC-1/AC-2): либо пояснением
        `ci.verifying_status` (его команда и читает — требование 2), либо
        кодом исхода (`red`/`green`/`running`/`none`). Своего третьего
        словаря для статуса планка не вводит: назвать статус, не взяв ни
        то, ни другое, значит переписать текст уже существующего узла."""
        outcome, note = self.status_note()
        return note in text or outcome in text

    def status_note(self) -> tuple:
        """`(исход, пояснение)` настоящей `ci.verifying_status` на текущей
        фикстуре — то, что команда обязана назвать статусом CI в отказах
        AC-1/AC-2. Считается тем же кодом, что читает статус в проде, а не
        переписанным текстом."""
        return ci.verifying_status(self.branch)
