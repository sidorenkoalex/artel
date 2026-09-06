"""Общая песочница приёмочных тестов 01M1NWCHVTYQ0M8PCJ1YJ2N78P (не
test_*.py — не подхватывается `unittest discover` напрямую, только
импортом из `test_ac*.py`, тот же приём, что `tasks/T074/acceptance_tests/
_sandbox.py`).

## Допущения интерфейса, которые вводит этот файл

SPEC (SPEC.md) фиксирует только ВНЕШНЮЮ форму: `artel.py run/auto <id>
[--attach]`, новую команду `artel.py stop <id>`, поведение `kill`/`status`/
`doctor` — не имя модуля/функции, которая всё это внутри реализует
(«Материалы» называют зоны файлов, не сигнатуры). Поэтому весь стенд
проверяет только ЧЁРНЫЙ ЯЩИК CLI — реальный `python3 orchestrator/
artel.py <cmd> ...` НАСТОЯЩИМ отдельным процессом ОС, а не замоканный
вызов внутренней функции: сам предмет этой задачи — поведение процесса
относительно других процессов (сессия, pid, сигналы), которое подменой
`subprocess.Popen` внутри одного интерпретатора не воспроизвести (мок
живёт в памяти вызывающего процесса, а не как отдельный адресуемый pid
ОС) и НИ ОДНО имя внутренней функции внутри `run`/`auto`/`stop`/`kill`
разработчика не обязано совпасть с фантазией теста.

Ключевая техническая проблема: `orchestrator/config.py` вычисляет
`ROOT = Path(__file__).resolve().parent.parent` — то есть каталог,
где ФИЗИЧЕСКИ лежит сам файл `config.py`, а не что-то патчимое из теста
через `unittest.mock`. Мок в процессе теста не пересекает границу
`subprocess.Popen` (новый интерпретатор Python читает файлы с диска
заново). Значит, чтобы «отвязанный процесс» использовал ПЕСОЧНИЦУ
(temp-БД, temp-worktrees), а не настоящее `.artel/` пульта — пакет
`orchestrator/` физически КОПИРУЕТСЯ во временный каталог, и CLI
запускается оттуда (`self.artel_path`). Что бы разработчик ни выбрал
внутри (`sys.argv[0]`, `__file__`, `-m orchestrator.artel`) для
повторного запуска себя же отвязанным процессом — все эти способы
одинаково резолвятся ВНУТРИ физической копии, поэтому и «вызывающая»
команда, и «отвязанный» цикл видят один и тот же временный `.artel/`.

Для операций ЭТОГО теста (посев задачи, чтение lease/журнала) тот же
временный каталог виден через ОБЫЧНЫЙ импортированный `orchestrator`
(не копию) с патчем путей `config` — `tests.test_git_fixation.
RealPultGitTest` уже делает это (настоящий git, self/артель, ULID id
через `catalog.cmd_new`) и переиспользуется, а не копируется
(skills/conventions-core). Оба набора путей указывают на ОДИН И ТОТ ЖЕ
`self.root` — файлы (sqlite БД, worktree) общие для теста и для
запускаемого им CLI-процесса.

Роль шага заменяется НАСТОЯЩИМ, но управляемым исполняемым файлом
`claude` (шелл-скрипт на PATH подставного окружения): без него шаг не
стартует вовсе (`doctor.preflight_checks` требует `claude` в PATH и
токен), а с реальным `claude` тест либо стоил бы денег, либо не был бы
детерминирован. Скрипт спит `FAKE_CLAUDE_SLEEP` секунд (управляемое,
воспроизводимое «идёт шаг») и печатает валидное финальное событие
потока (`spend.parse_cost_event` его разбирает) — это даёт РЕАЛЬНЫЙ,
адресуемый по pid дочерний процесс на управляемое время, не требуя
подписки/сети (тот же принцип, что `tests/test_pause_now.py::
spawn_sleep_process` — реальный процесс вместо мока ради проверки
факта уровня ОС, только здесь ещё и сквозь весь `cmd_run`).

Прогон ДО реализации падает `FileNotFoundError`/ненулевым кодом возврата
при попытке `--attach`-эквивалентного старого поведения ИЛИ печатью,
не совпадающей с ожидаемым форматом («pid <N>» / путь `.log`) — команды
`run`/`auto` сегодня не отвязываются и не возвращают управление, пока
цикл не остановится сам; `stop` сегодня не существует как команда
(`Неизвестная команда stop`). Ожидаемо (skills/test-authoring: «падать
на отсутствующей пока реализации — нормально»), не брак теста.
"""
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, liveness, store  # noqa: E402
from tests.sandbox import capture_new_task_id  # noqa: E402
from tests.test_git_fixation import SPEC_READY, RealPultGitTest  # noqa: E402

__all__ = ["config", "liveness", "store", "DetachedCycleSandbox",
          "PID_RE", "LOG_PATH_RE"]

# Толерантный разбор печати команды: SPEC называет ФАКТ («напечатав pid
# отвязанного процесса»), не точный текст строки — формат решает
# разработчик. Ищем число рядом со словом pid, без привязки к языку/
# пунктуации вокруг него.
PID_RE = re.compile(r"pid\D{0,3}(\d+)", re.IGNORECASE)
# Путь лога — что-то похожее на `.../.artel/logs/<...>.log`, тоже без
# точной привязки к обрамляющему тексту.
LOG_PATH_RE = re.compile(r"(\S*\.artel/logs/\S+\.log)")

# Имитация `claude` CLI (SPEC не тестирует прогон настоящего агента —
# только то, что процесс, несущий шаг, реально существует ОС-уровнем
# управляемое время). `--version` отвечает мгновенно: его синхронно
# зовёт `doctor.check_cli_version`/`preflight_checks` на КАЖДОМ шаге и
# КАЖДОМ прогоне `doctor` — если бы он тоже спал, тесты, использующие
# `doctor`, платили бы лишним `FAKE_CLAUDE_SLEEP` без всякой пользы.
FAKE_CLAUDE_SH = """#!/bin/sh
for a in "$@"; do
  if [ "$a" = "--version" ]; then
    echo "1.0.0 (Claude Code, sandbox stub)"
    exit 0
  fi
done
sleep "${FAKE_CLAUDE_SLEEP:-4}"
cat <<'JSON'
{"type":"result","subtype":"success","is_error":false,"total_cost_usd":0.001,"duration_ms":100,"num_turns":1,"result":"готово (sandbox stub)"}
JSON
"""


class DetachedCycleSandbox(RealPultGitTest):
    """`RealPultGitTest` (T001, git настоящий, self/артель, ULID-задача в
    `spec_writing`) + реальный, физически скопированный CLI и подставной
    `claude` — стенд для проверки поведения отвязанного процесса ОС.
    """

    FAKE_CLAUDE_SLEEP = 4

    def setUp(self):
        super().setUp()
        # Базовый стенд (`_GitFixationTmpRootTest.PATCHED_ATTRS`) не несёт
        # WORKTREES/BACKUP_MARKER — этой песочнице они нужны отдельно,
        # чтобы `workspace.ensure` не потянулась к настоящему `.artel/`
        # репозитория пульта, где реально исполняется тест.
        for attr, rel in (("WORKTREES", ".artel/worktrees"),
                         ("BACKUP_MARKER", ".artel/backup-marker")):
            patcher = mock.patch.object(config, attr, self.root / rel)
            patcher.start()
            self.addCleanup(patcher.stop)

        # `config.ROLES` (в отличие от TEMPLATES она НЕ патчится ни одной
        # существующей песочницей — вычисляется один раз при импорте
        # реального config.py) остаётся у РЕАЛЬНОГО roles.yaml для этого,
        # обычного, импорта. Физическая копия ниже резолвит СВОЙ ROLES
        # заново от СВОЕГО __file__ — файл обязан лежать в копии тоже.
        shutil.copy(REPO_ROOT / "roles.yaml", self.root / "roles.yaml")

        # Физическая копия пакета — единственный способ, которым
        # отвязанный процесс (новый интерпретатор) увидит ЭТУ песочницу,
        # а не настоящий `.artel/` пульта (см. докстринг модуля).
        copy_dst = self.root / "orchestrator"
        shutil.copytree(REPO_ROOT / "orchestrator", copy_dst,
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.artel_path = copy_dst / "artel.py"
        # `orchestrator/fsm.py` и соседи зовут `from scripts import guard`
        # (валидатор структуры артефактов) — тоже физическая копия рядом,
        # тем же доводом, что и у orchestrator/ выше.
        shutil.copytree(REPO_ROOT / "scripts", self.root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        # Untracked-копия не должна красить `git status` внутри ROOT
        # (некоторые пути кода проверяют чистоту дерева) — дописывается
        # ПОСЛЕ начального коммита `RealPultGitTest.setUp`, коммитить
        # заново не нужно: git читает `.gitignore` рабочего дерева
        # живьём, не только из индекса.
        with open(self.root / ".gitignore", "a", encoding="utf-8") as fh:
            fh.write("\norchestrator/\nroles.yaml\nscripts/\n")

        # Подставной `claude` — вне self.root (никак не участвует в git
        # этой песочницы).
        self._bin_dir = Path(tempfile.mkdtemp(prefix="artel-fake-bin-"))
        self.addCleanup(shutil.rmtree, self._bin_dir, True)
        claude_path = self._bin_dir / "claude"
        claude_path.write_text(FAKE_CLAUDE_SH, encoding="utf-8")
        claude_path.chmod(claude_path.stat().st_mode | stat.S_IEXEC
                          | stat.S_IXGRP | stat.S_IXOTH)
        # Правка планки Оператором 06.09.2026 (amend-tests, ADR-0012): после
        # стека ч.3 (01M1RDCEF0JZ4AVQRE43JFH8TN) PATH роли собирается из
        # КАТАЛОГОВ объявленных инструментов в порядке манифеста (python3,
        # git, gh, claude), а не наследуется от процесса; каталог `gh`
        # (например /opt/homebrew/bin) может содержать настоящий `claude`,
        # который затеняет подставной. Символические ссылки на настоящие
        # `git` и `gh` в подставном каталоге делают его каталогом ВСЕХ
        # инструментов манифеста, кроме python3 (тот берётся из
        # sys.executable), — и подставной `claude` снова первый.
        for tool in ("git", "gh"):
            real = shutil.which(tool)
            if real:
                (self._bin_dir / tool).symlink_to(real)

        caller_home = Path(tempfile.mkdtemp(prefix="artel-fake-home-"))
        self.addCleanup(shutil.rmtree, caller_home, True)
        self.subprocess_env = dict(os.environ)
        self.subprocess_env.update({
            "PATH": f"{self._bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "HOME": str(caller_home),
            "CLAUDE_CODE_OAUTH_TOKEN": "sandbox-token-not-real",
            "GIT_AUTHOR_NAME": "Роль Артели",
            "GIT_AUTHOR_EMAIL": "role@artel.invalid",
            "GIT_COMMITTER_NAME": "Роль Артели",
            "GIT_COMMITTER_EMAIL": "role@artel.invalid",
            "FAKE_CLAUDE_SLEEP": str(self.FAKE_CLAUDE_SLEEP),
        })

        self._live_pids: list[int] = []
        self.addCleanup(self._reap_live_pids)

    # ---- управление подставным claude ------------------------------

    def set_claude_sleep(self, seconds) -> None:
        self.subprocess_env["FAKE_CLAUDE_SLEEP"] = str(seconds)

    # ---- запуск НАСТОЯЩЕГО CLI как отдельного процесса ОС -----------

    def artel_argv(self, *args: str) -> list:
        return [sys.executable, str(self.artel_path), *args]

    def spawn(self, *args: str) -> subprocess.Popen:
        """Popen реального `artel.py <args>` — вызывающий тест сам решает,
        ждать его (`communicate`) или нет (переживает ли его смерть
        порождённый процесс, AC-5)."""
        proc = subprocess.Popen(
            self.artel_argv(*args), cwd=self.root, env=self.subprocess_env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self._live_pids.append(proc.pid)
        return proc

    def run_cli(self, *args: str, timeout: float = 20.0):
        """(stdout, returncode, elapsed_seconds, pid, timed_out) вызывающей
        команды — по завершении ЕЁ СОБСТВЕННОГО процесса (не отвязанного
        потомка, который она могла породить и с которым не ждёт).

        До реализации AC-1/AC-2 (и до `--attach`) `run`/`auto` не
        возвращают управление, пока цикл не остановится сам — на задаче
        `in_dev` без готового PLAN.md это далеко за пределами разумного
        таймаута теста (`AUTO_STALL_STEPS_LIMIT` повторов). `timed_out=
        True` (а не необработанное исключение) — тот же самый честный
        красный исход («не вернулась вовремя»), только с понятным текстом
        причины вместо трейсбека `subprocess.TimeoutExpired`."""
        proc = self.spawn(*args)
        start = time.monotonic()
        try:
            out, _ = proc.communicate(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
            timed_out = True
        elapsed = time.monotonic() - start
        return out, proc.returncode, elapsed, proc.pid, timed_out

    def spawn_via_shell(self, *args: str) -> subprocess.Popen:
        """Запуск через ПРОМЕЖУТОЧНУЮ оболочку (AC-5: «завершение
        процесса-родителя (промежуточной оболочки)») — `sh -c "<argv>"`,
        а не прямой Popen самой команды: у прямого Popen «родитель» и
        «вызывающая команда» — один и тот же процесс, и завершение
        родителя было бы неотличимо от завершения самой команды."""
        quoted = " ".join(_sh_quote(a) for a in self.artel_argv(*args))
        proc = subprocess.Popen(
            ["sh", "-c", quoted], cwd=self.root, env=self.subprocess_env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self._live_pids.append(proc.pid)
        return proc

    # ---- разбор вывода -----------------------------------------------

    @staticmethod
    def extract_pid(text: str):
        match = PID_RE.search(text)
        return int(match.group(1)) if match else None

    @staticmethod
    def extract_log_path(text: str):
        match = LOG_PATH_RE.search(text)
        return match.group(1) if match else None

    # ---- живость / сигналы --------------------------------------------

    @staticmethod
    def is_alive(pid: int) -> bool:
        return liveness._pid_alive(pid)

    def kill_pid(self, pid: int, sig=signal.SIGKILL) -> None:
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass

    def wait_until(self, predicate, timeout: float = 15.0,
                  interval: float = 0.15):
        """Опрос `predicate()` до True или таймаута — возвращает последнее
        значение (True при успехе, False/None при таймауте)."""
        deadline = time.monotonic() + timeout
        result = predicate()
        while not result and time.monotonic() < deadline:
            time.sleep(interval)
            result = predicate()
        return result

    def track_pid(self, pid: int) -> None:
        """Регистрирует ЧУЖОЙ (не порождённый напрямую `self.spawn`) pid —
        например, отвязанный процесс, который CLI породил сам и о котором
        мы знаем только по числу, напечатанному в stdout — на уборку по
        завершении теста."""
        if pid is not None:
            self._live_pids.append(pid)

    def _reap_live_pids(self) -> None:
        for pid in self._live_pids:
            self.kill_pid(pid)

    # ---- данные задачи --------------------------------------------------

    def lease_row(self):
        return store.lease_row(store.db(), self.TASK)

    def journal(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def journal_text(self) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}"
                         for r in self.journal())

    def task_state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def new_task_in_dev(self, title: str = "Git-фиксация, доп. задача") -> str:
        """Заводит ЕЩЁ ОДНУ (не `self.TASK`) задачу self/артели и доводит
        её до `in_dev` — тот же путь, что `RealPultGitTest.enter_in_dev`,
        но параметризованный id (нужен AC-12: doctor обязан различить
        состояния ТРЁХ разных циклов одновременно)."""
        from orchestrator import artifact_branch, catalog, fsm
        _, task_id = capture_new_task_id(catalog.cmd_new, title)
        tdir = self.repo() / "tasks" / task_id
        tdir.mkdir(parents=True, exist_ok=True)
        spec_text = SPEC_READY.format(task=task_id)
        (tdir / "SPEC.md").write_text(spec_text, encoding="utf-8")
        artifact_branch.commit_files(
            task_id, {f"tasks/{task_id}/SPEC.md": spec_text},
            f"{task_id}: SPEC готов")
        self.capture(fsm.cmd_advance, task_id)
        sha = self.head()
        self.capture(fsm.cmd_approve, task_id, sha)
        self.assertEqual(
            store.get_task(store.db(), task_id)["state"], "in_dev")
        return task_id


def _sh_quote(token: str) -> str:
    if token and all(c.isalnum() or c in "-_./:" for c in token):
        return token
    return "'" + token.replace("'", "'\\''") + "'"
