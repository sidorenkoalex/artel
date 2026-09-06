"""Общая песочница приёмочных тестов 01M1TNMBY8G3AH3MYCB07RW14N (не
test_*.py — не подхватывается `unittest discover` напрямую, только
импортом из `test_ac*.py`, приём `tasks/T074/acceptance_tests/_sandbox.py`).

## Почему реальный отдельный процесс ОС, а не мок

Предмет этой задачи — поведение ПРОЦЕССА относительно других процессов
(сессия, pid, сигналы, переживание смерти родителя): подменой
`subprocess.Popen` внутри одного интерпретатора это не воспроизвести (мок
живёт в памяти вызывающего процесса, не как отдельный адресуемый pid ОС).
Стенд запускает НАСТОЯЩИЙ `python3 orchestrator/artel.py <cmd> ...`
отдельным процессом, с физически СКОПИРОВАННЫМ пакетом `orchestrator/`
(и `scripts/`) во временный каталог песочницы — `orchestrator/config.py`
вычисляет `ROOT = Path(__file__).resolve().parent.parent`, то есть
каталог, где ФИЗИЧЕСКИ лежит сам файл; мок текущего интерпретатора не
пересекает границу `subprocess.Popen` (новый интерпретатор читает файлы
с диска заново). Копия ставится ИМЕННО в `self.root` — тот же временный
каталог, на который уже указывают патченные пути `config` ЭТОГО
(родительского, обычный импорт) процесса, поэтому оба видят один и тот
же файл БД, worktree'ы и журнал.

## Сценарий: analyst/spec_writing, не developer/in_dev

Первый заход (закрытая задача 01M1NWCHVTYQ0M8PCJ1YJ2N78P, `keep/
01m1nwchvt-artifacts`) гонял сценарий through `in_dev`/`review`
(разработчик, ревьювер) и уткнулся в три структурных конфликта с
механикой main (ТЗ этой задачи, раздел 2; PLAN.md закрытой задачи,
«Риски» пп.1-3): PATH роли собирается из каталогов инструментов манифеста
(коллизия `gh`/`claude`, если они физически соседствуют), гейт ёмкости
diff сверяет `main...<ветка задачи>` уже на входе `in_dev -> review`
(ветки кода без единого шага developer не существует), заглушка
ревьювера со статусом `draft` гоняется `AUTO_STALL_STEPS_LIMIT` (5) кругов
без единого перехода.

Этот стенд идёт ЛЁГКИМ путём: задача создаётся сразу в `spec_writing` с
`TZ.md` (`catalog.cmd_new(title, tz_path)` — единственный способ, которым
`runner.step_role` резолвит роль `analyst`, `orchestrator/runner.py`
строки 66-118) и НИКОГДА не продвигается до `in_dev`/`review` — гейт
ёмкости diff (только `in_dev -> review`) и заглушка ревьювера вообще не
участвуют. PATH-коллизию `gh`/`claude` стенд снимает тем же приёмом, что
и закрытая задача (символические ссылки на настоящие `git`/`gh` В ТОМ ЖЕ
каталоге, что и подставной `claude`, — `_role_path_dirs` дедуплицирует
каталоги, поэтому все три инструмента резолвятся в ОДИН каталог, и
никакой другой каталог манифеста не может «протолкнуть» настоящий
`claude` раньше подставного).

## Почему подставной `claude` НИКОГДА не пишет SPEC.md

`_missing_required_artifact` (`orchestrator/runner.py`) для роли analyst
считает шаг обеспеченным артефактом, если `tasks/<id>/SPEC.md` (или
`QUESTIONS.md`) СУЩЕСТВУЕТ на диске рабочего каталога роли — а он там
УЖЕ есть: `role_cwd` материализует `tasks/<id>/` из артефактной ветки
ПЕРЕД каждым шагом, а `catalog.cmd_new` коммитит черновик SPEC.md (статус
`draft`) в артефактную ветку сразу при заведении задачи. Поэтому
подставной `claude`, который вообще ничего не пишет (только спит
`FAKE_CLAUDE_SLEEP` секунд и завершается rc=0), уже проходит проверку
обязательного артефакта — «шаг агента» всегда журналирует «agent run
finished», НИКОГДА не проваливается по коду возврата и не тратит бюджет
на ретраи. Однако `SPEC.md` остаётся черновиком (`status: draft`) —
`fsm_advance.spec_writing` не переводит задачу дальше («SPEC.md ещё не
ready — нечего продвигать», без записи в журнал), и `auto._pre_advance_
step` считает это шагом «без перехода» (`cycle.idle_steps += 1`)
НЕЗАВИСИМО от состояния (стоп-кран «два подряд одинаковых отказов» из
`other_class_refusal` держит только `in_dev` — здесь `other_class_
refusal` всегда `None`, действует только общий стоп-кран N шагов подряд
без перехода). Итог: цикл `auto` без вмешательства детерминированно
останавливается сам ровно через `config.AUTO_STALL_STEPS_LIMIT - 1`
успешных шагов роли (стоп-кран срабатывает на N-й проверке ДО N-го шага
роли) — быстро (секунды, не минуты), без бэкоффов и без AUTO_MAX_STEPS,
и БЕЗ единого экземпляра `escalated`/`review`/кода. `run <id>` (без
цикла `auto`) видит тот же единственный успешный шаг и просто завершается
после него.

Это же свойство даёт управляемое окно для сигналов (`stop`/`kill`/обрыв):
подставной `claude` спит `FAKE_CLAUDE_SLEEP` секунд на КАЖДОМ шаге —
достаточно, чтобы тест успел поймать «agent run started» в журнале и
среагировать, прежде чем шаг сам завершится.

## Прочие фиксы против рисков закрытой задачи

- `.artel/venv`, согласованный с `requirements.lock` (`_provision_stub_
  venv`, тем же приёмом, что и `keep/01m1nwchvt-code:tests/test_git_
  fixation.py`): `runner.role_env` зовёт `stack.check_stack()` на КАЖДОМ
  шаге роли (для ЛЮБОЙ роли, не только developer) и отказывает `OSError`
  без согласованного venv — не зависит от состояния/роли сценария этого
  стенда, нужен всегда.
- `spawn_via_shell` (AC-5) резолвит `sh` АБСОЛЮТНЫМ путём из окружения
  ЭТОГО (тестового) процесса, а не из курируемого PATH роли — курируемый
  PATH роли (только каталоги python3/git/gh/claude манифеста) не обязан
  нести `/bin`, где реально лежит `sh` (закрытая задача, PLAN.md
  «Риски» п.2, `FileNotFoundError` ИМЕННО на рабочем месте с таким PATH).
"""
import os
import re
import shutil
import socket
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
from orchestrator import catalog, doctor, projects  # noqa: E402
from tests.sandbox import capture, capture_new_task_id  # noqa: E402
from tests.test_git_fixation import (  # noqa: E402
    ARTEL_TARGETS_YAML, TmpRootTest as GitFixationTmpRootTest)

__all__ = ["config", "doctor", "liveness", "store", "DetachedCycleSandbox",
          "PID_RE", "LOG_PATH_RE", "CLAUDE_SLEEP_SEC", "natural_stall_timeout"]

# Толерантный разбор печати команды: SPEC называет ФАКТ («напечатав pid
# отвязанного процесса»), не точный текст строки вокруг него — формат
# самого числа/пути AC-1..AC-3 называют явно (см. test_ac1_ac2_ac3_*.py).
PID_RE = re.compile(r"pid\D{0,3}(\d+)", re.IGNORECASE)
LOG_PATH_RE = re.compile(r"(\S*\.artel/logs/\S+\.log)")

# Подставной агент спит столько секунд на КАЖДОМ шаге — управляемое окно
# для сигналов (AC-9/AC-10/AC-11) и наблюдаемого прогресса (AC-1..AC-3),
# не впритык (skills/test-authoring): пары секунд достаточно, чтобы тест
# гарантированно успел увидеть «agent run started» до конца сна.
CLAUDE_SLEEP_SEC = 1.0

# Оверхед одной итерации цикла (git worktree/checkpoint/журнал) поверх
# сна подставного агента — эмпирический запас, не измеренная константа
# системы: используется только для верхней границы таймаутов ожидания,
# не для утверждений о правильности.
_ITERATION_OVERHEAD_SEC = 3.0
_SAFETY_MARGIN_SEC = 15.0


def natural_stall_timeout(claude_sleep: float = CLAUDE_SLEEP_SEC) -> float:
    """Верхняя граница времени, за которое `auto` обязан остановиться САМ
    стоп-краном «N шагов без перехода» (`config.AUTO_STALL_STEPS_LIMIT`),
    ни разу не продвинув черновой SPEC.md дальше `spec_writing` (см.
    докстринг модуля) — динамически от `config`, не литералом (skills/
    test-authoring: потолок — крутилка Оператора, тест обязан пережить её
    поворот)."""
    return (config.AUTO_STALL_STEPS_LIMIT
           * (claude_sleep + _ITERATION_OVERHEAD_SEC) + _SAFETY_MARGIN_SEC)


_CLAUDE_STUB_SRC = '''#!__PYTHON__
import os
import sys
import time

if "--version" in sys.argv[1:]:
    print("1.0.0 (Claude Code, acceptance sandbox stub)")
    sys.exit(0)

time.sleep(float(os.environ.get("FAKE_CLAUDE_SLEEP", "4")))
print('{"type": "result", "total_cost_usd": 0.001}')
'''


def _write_claude_stub(bin_dir: Path) -> Path:
    script = bin_dir / "claude"
    script.write_text(_CLAUDE_STUB_SRC.replace("__PYTHON__", sys.executable),
                      encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP
                | stat.S_IXOTH)
    return script


_STUB_VENV_PYTHON_SRC = """#!{real_python}
import sys, subprocess
if sys.argv[1:4] == ["-m", "pip", "freeze"]:
    sys.stdout.write(open({lock!r}, encoding="utf-8").read())
    sys.exit(0)
sys.exit(subprocess.run([{real_python!r}] + sys.argv[1:]).returncode)
"""


def _provision_stub_venv(root: Path) -> None:
    """`.artel/venv` + `requirements.lock` согласованные друг с другом —
    `runner.role_env` (через `_venv_interpreter_bin`/`stack.check_stack`)
    отказывает ЛЮБОМУ шагу роли без этого, независимо от того, какая роль
    (см. докстринг модуля, «Прочие фиксы»)."""
    lock = root / "requirements.lock"
    shutil.copy(REPO_ROOT / "requirements.lock", lock)
    venv_bin = root / ".artel" / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    script = _STUB_VENV_PYTHON_SRC.format(lock=str(lock),
                                          real_python=sys.executable)
    for name in ("python", "python3"):
        path = venv_bin / name
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP
                  | stat.S_IXOTH)


class DetachedCycleSandbox(GitFixationTmpRootTest):
    """Реальный git-пульт (self/артель) + физически скопированный CLI +
    подставной `claude` — стенд для поведения отвязанного цикла на уровне
    процесса ОС. Каждый тест заводит свои задачи через `self.new_task`.
    """

    def setUp(self):
        super().setUp()
        # Базовый `_GitFixationTmpRootTest.PATCHED_ATTRS` не несёт
        # WORKTREES/BACKUP_MARKER — они нужны отдельно, чтобы
        # `workspace.ensure`, вызванный ВНУТРИ отвязанного дочернего
        # процесса (роль всегда получает worktree, `runner.role_cwd`),
        # не путался с этим (родительским) процессом, случайно смотрящим
        # на тот же путь другим способом.
        for attr, rel in (("WORKTREES", ".artel/worktrees"),
                         ("BACKUP_MARKER", ".artel/backup-marker")):
            patcher = mock.patch.object(config, attr, self.root / rel)
            patcher.start()
            self.addCleanup(patcher.stop)

        config.TARGETS.write_text(ARTEL_TARGETS_YAML, encoding="utf-8")
        self.capture(projects.cmd_target_init, config.DEFAULT_TARGET)
        self.capture(catalog.cmd_init)

        subprocess.run(["git", "init", "-q", "-b", config.MAIN_BRANCH],
                       cwd=config.ROOT, check=True)
        subprocess.run(["git", "config", "user.email", "artel@example.invalid"],
                       cwd=config.ROOT, check=True)
        subprocess.run(["git", "config", "user.name", "artel tests"],
                       cwd=config.ROOT, check=True)
        shutil.copytree(REPO_ROOT / "templates", config.ROOT / "templates")
        shutil.copytree(REPO_ROOT / "skills", config.ROOT / "skills")
        shutil.copy(REPO_ROOT / ".gitignore", config.ROOT / ".gitignore")
        shutil.copy(REPO_ROOT / "roles.yaml", config.ROOT / "roles.yaml")
        (config.ROOT / "docs").mkdir()
        (config.ROOT / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
        (config.ROOT / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        # Согласованный venv — до коммита ниже: `requirements.lock`
        # (верхнеуровневый файл, не под `.artel/`) обязан попасть в
        # коммит, иначе рабочее дерево `config.ROOT` навсегда «грязное»
        # для любой проверки чистоты self-репозитория.
        _provision_stub_venv(config.ROOT)
        subprocess.run(["git", "add", "-A"], cwd=config.ROOT, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"],
                       cwd=config.ROOT, check=True)

        # Физическая копия — единственный способ, которым отвязанный
        # процесс (новый интерпретатор) увидит ЭТУ песочницу, а не
        # настоящий `.artel/` пульта (см. докстринг модуля).
        shutil.copytree(REPO_ROOT / "orchestrator", self.root / "orchestrator",
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.artel_path = self.root / "orchestrator" / "artel.py"
        shutil.copytree(REPO_ROOT / "scripts", self.root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        with open(self.root / ".gitignore", "a", encoding="utf-8") as fh:
            fh.write("\norchestrator/\nroles.yaml\nscripts/\n")

        # Подставной `claude` + символические ссылки на настоящие
        # `git`/`gh` В ТОМ ЖЕ каталоге (см. докстринг модуля, «Сценарий»):
        # `_role_path_dirs` дедуплицирует каталоги в порядке манифеста —
        # если git/gh резолвятся В ЭТОТ ЖЕ каталог, PATH роли содержит
        # его ОДИН раз, и никакой другой каталог манифеста не может
        # протолкнуть настоящий `claude`, случайно соседствующий с
        # настоящим `gh` где-то на диске, раньше подставного.
        self._bin_dir = Path(tempfile.mkdtemp(prefix="artel-fake-bin-"))
        self.addCleanup(shutil.rmtree, self._bin_dir, True)
        _write_claude_stub(self._bin_dir)
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
            "FAKE_CLAUDE_SLEEP": str(CLAUDE_SLEEP_SEC),
        })

        self._live_pids: list[int] = []
        self.addCleanup(self._reap_live_pids)
        self._tz_dir = Path(tempfile.mkdtemp(prefix="artel-fake-tz-"))
        self.addCleanup(shutil.rmtree, self._tz_dir, True)

    # ---- заведение задачи --------------------------------------------

    def new_task(self, title: str = "Задача отвязки цикла") -> str:
        """Заводит задачу СРАЗУ в `spec_writing` с `TZ.md` — единственный
        путь, которым `runner.step_role` резолвит роль `analyst` (см.
        докстринг модуля, «Сценарий»); никогда не продвигается до
        `in_dev`/`review`."""
        tz_path = self._tz_dir / f"tz-{len(list(self._tz_dir.iterdir()))}.md"
        tz_path.write_text(
            f"# ТЗ: {title}\n\nОписание для песочницы приёмочных тестов.\n",
            encoding="utf-8")
        _, task_id = capture_new_task_id(catalog.cmd_new, title, str(tz_path))
        self.assertEqual(store.get_task(store.db(), task_id)["state"],
                         "spec_writing")
        return task_id

    def set_claude_sleep(self, seconds) -> None:
        self.subprocess_env["FAKE_CLAUDE_SLEEP"] = str(seconds)

    # ---- запуск НАСТОЯЩЕГО CLI как отдельного процесса ОС -------------

    def artel_argv(self, *args: str) -> list:
        return [sys.executable, str(self.artel_path), *args]

    def spawn(self, *args: str) -> subprocess.Popen:
        proc = subprocess.Popen(
            self.artel_argv(*args), cwd=self.root, env=self.subprocess_env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self._live_pids.append(proc.pid)
        return proc

    def run_cli(self, *args: str, timeout: float = 20.0):
        """(stdout, returncode, elapsed_seconds, pid, timed_out) вызывающей
        команды — по завершении ЕЁ СОБСТВЕННОГО процесса (не отвязанного
        потомка, который она могла породить и с которым не ждёт)."""
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
        """Запуск через ПРОМЕЖУТОЧНУЮ оболочку (AC-5) — `sh -c "<argv>"`,
        не прямой Popen самой команды: у прямого Popen «родитель» и
        «вызывающая команда» — один и тот же процесс, завершение
        родителя было бы неотличимо от завершения самой команды.

        `sh` — АБСОЛЮТНЫМ путём из фиксированного списка стандартных
        расположений (`os.path.exists`), НЕ `shutil.which("sh")`: PATH
        роли (курируемый только каталогами python3/git/gh/claude
        манифеста) не обязан нести `/bin`, где реально лежит `sh` —
        закрытая задача поймала именно это как `FileNotFoundError` на
        рабочем месте с таким PATH (PLAN.md «Риски» п.2), и то же самое
        рабочее место, на котором писалась ЭТА планка, подтверждает
        находку буквально: `shutil.which("sh")` в PATH ЭТОГО процесса
        (курируемый PATH роли test_author) тоже возвращает `None`, хотя
        `/bin/sh` физически существует на диске."""
        sh_path = next((p for p in ("/bin/sh", "/usr/bin/sh")
                       if os.path.exists(p)), None)
        self.assertIsNotNone(sh_path, "sh не найден ни по одному "
                             "стандартному пути на этом рабочем месте")
        quoted = " ".join(_sh_quote(a) for a in self.artel_argv(*args))
        proc = subprocess.Popen(
            [sh_path, "-c", quoted], cwd=self.root, env=self.subprocess_env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self._live_pids.append(proc.pid)
        return proc

    # ---- разбор вывода --------------------------------------------------

    @staticmethod
    def extract_pid(text: str):
        match = PID_RE.search(text)
        return int(match.group(1)) if match else None

    @staticmethod
    def extract_log_path(text: str):
        match = LOG_PATH_RE.search(text)
        return match.group(1) if match else None

    # ---- живость / сигналы ----------------------------------------------

    @staticmethod
    def is_alive(pid: int) -> bool:
        return liveness._pid_alive(pid)

    def kill_pid(self, pid: int, sig=None) -> None:
        import signal as _signal
        sig = _signal.SIGKILL if sig is None else sig
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, TypeError):
            pass

    def wait_until(self, predicate, timeout: float = 15.0,
                  interval: float = 0.1):
        deadline = time.monotonic() + timeout
        result = predicate()
        while not result and time.monotonic() < deadline:
            time.sleep(interval)
            result = predicate()
        return result

    def track_pid(self, pid) -> None:
        if pid is not None:
            self._live_pids.append(pid)

    def _reap_live_pids(self) -> None:
        for pid in self._live_pids:
            self.kill_pid(pid)

    # ---- данные задачи ----------------------------------------------------

    def lease_row(self, task_id: str):
        return store.lease_row(store.db(), task_id)

    def journal(self, task_id: str) -> list:
        return store.task_steps(store.db(), task_id)

    def journal_text(self, task_id: str) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}"
                         for r in self.journal(task_id))

    def task_state(self, task_id: str) -> str:
        return store.get_task(store.db(), task_id)["state"]


def _sh_quote(token: str) -> str:
    if token and all(c.isalnum() or c in "-_./:" for c in token):
        return token
    return "'" + token.replace("'", "'\\''") + "'"
