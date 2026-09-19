"""Общая обвязка приёмочной планки задачи 01M2XJKV84SQ9VEVR0VNVKDNGJ
(«Роль запускается по абсолютному пути из манифеста, модель роли
сверяется с версией CLI до старта агента»).

Не копия `tests/sandbox.py`, а тонкая надстройка над ней (скил
test-authoring, «Лёгкая песочница»): базовый класс
(`DeveloperBriefTmpRootTest`), `fake_git`, `disk_backed_show`/
`disk_backed_ls_tree_files`, `FakeProc`, `capture_new_task_id`,
`sync_spec_from_worktree` импортируются оттуда и здесь НЕ определяются
заново. Своё здесь только сценарное: управляемая модель роли в
`roles.yaml`, управляемый ответ `claude --version`, прогон одного шага
`runner.cmd_run` с перехватом отказа до старта агента и чтение журнала
шага.

Каркас шага (порядок патчей `fake_git`/`disk_backed_*`, маркер
обязательного артефакта роли в worktree, `keychain.token`,
`doctor.preflight_checks`) повторяет рабочие песочницы
`tests/test_agent_failure.py::CmdRunFailureTest` и
`tests/test_runner_role_model.py::ModelFlagJournalTest` — обе доводят
`cmd_run` до реального вызова `spawn_agent`.

ГРАНИЦА УПРАВЛЕНИЯ ВЕРСИЕЙ CLI. «Установленная версия CLI» задаётся
планкой на уровне подпроцесса `claude --version` (`set_cli_version`
подменяет `subprocess.run`, пропуская мимо себя всё, что не `claude`, —
`git` продолжает идти в мок песочницы, а не в настоящий репозиторий).
Это тот же источник, который SPEC называет требованием 3 («`claude
--version`, уже разбирается `stack._tool_check`»). Реализация,
берущая версию из `stack.check_stack()`, планкой не покрывается
намеренно: `check_stack` в песочнице `tests/sandbox.py` подменён
заглушкой (иначе `role_env` каждого шага отказывал бы отсутствием
`.artel/venv` во временном каталоге), а предполётная проверка ОДНОЙ
модели через полный `check_stack` завела бы лишние подпроцессы
`git`/`gh`/`claude` на каждый шаг роли — ровно то, от чего
предостерегают «Материалы» SPEC.
"""
import io
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import (auto, catalog, config, gitcmd, runner,  # noqa: E402
                          stack, store)
from tests.sandbox import (DeveloperBriefTmpRootTest, FakeProc,  # noqa: E402
                           capture_new_task_id, disk_backed_ls_tree_files,
                           disk_backed_show, fake_git,
                           sync_spec_from_worktree)

# Настоящий `subprocess.run`, снятый ДО любых патчей песочниц: git-справки
# этой планки (merge-base, содержимое файла на базе ветки) обязаны идти в
# настоящий git, а не в `SpyRun`/фейк, который в этот момент стоит на
# `subprocess.run` (урок T051: мок, задушивший git, красит планку по
# причине, не относящейся к предмету проверки).
_REAL_RUN = subprocess.run

REAL_ROLES_TEXT = (REPO_ROOT / "roles.yaml").read_text(encoding="utf-8")

# Модель инцидента 19.09 — единственная запись, которую SPEC (AC-5)
# требует от таблицы совместимости; число минимальной версии планка
# берёт из самой таблицы, не литералом по месту.
INCIDENT_MODEL = "claude-fable-5-1"
# Модель, которой в таблице заведомо нет: имя выдумано планкой, Оператор
# такую в `roles.yaml` не заводит.
UNKNOWN_MODEL = "claude-test-model-vne-tablitsy"

# Поверхности отказа, названные SPEC дословно (требования 3-4, AC-6..AC-9).
REFUSAL_PREFIX = "модель роли не поддерживается CLI"
UPGRADE_HINT = "обнови CLI либо смени model роли в roles.yaml"
NOT_IN_TABLE_WARNING = "модель не в таблице совместимости"
# Сигнатура вывода попытки из инцидента 19.09 (требование 4, AC-9).
UNSUPPORTED_MODEL_OUTPUT = (
    "API Error: 400 {\"type\":\"error\",\"error\":{\"type\":"
    "\"invalid_request_error\",\"message\":\"This Claude Code version "
    "does not support this model; version 2.1.251 or newer is required\"}}\n")


def version_text(version) -> str:
    """`(2, 1, 251)` -> `2.1.251` — та же форма, которой версии печатает
    `orchestrator/stack.py`."""
    return ".".join(str(part) for part in version)


def expected_flags() -> list:
    """Состав и порядок флагов `role_cmd()` ПОСЛЕ argv[0], как они стоят
    до этой задачи (AC-2). Значение `--setting-sources` читается из
    `config`, а не зашито числом/строкой: это крутилка Оператора."""
    return ["-p", "--permission-mode", "acceptEdits",
            "--output-format", "stream-json", "--verbose",
            "--allowedTools", "Bash(git:*),Bash(python3:*)",
            "--setting-sources", config.AGENT_SETTING_SOURCES,
            "--strict-mcp-config"]


def expected_role_path_dirs() -> list:
    """Каталоги PATH роли, пересчитанные планкой независимо от
    `runner._role_path_dirs`: `.artel/venv/bin` первым, затем каталоги
    объявленных манифестом инструментов в порядке манифеста, для
    `python3` — каталог интерпретатора пульта (AC-2)."""
    dirs = [str(config.VENV_DIR / "bin")]
    for name in stack.DECLARED_TOOLS:
        if name == "python3":
            directory = str(Path(sys.executable).parent)
        else:
            directory = str(Path(shutil.which(name)).parent)
        if directory not in dirs[1:]:
            dirs.append(directory)
    return dirs


def roles_yaml_text(role: str, model) -> str:
    """Настоящий `roles.yaml` репозитория с подменённым `model:` у одной
    роли (приём `tests/test_runner_role_model.py::_roles_yaml_text`):
    `skills:`/`token_slot:`/состав остальных ролей не трогаются."""
    lines = REAL_ROLES_TEXT.splitlines(keepends=True)
    anchor = f"  {role}:\n"
    for i, line in enumerate(lines):
        if line == anchor:
            j = i + 1
            while j < len(lines) and lines[j].startswith("    "):
                if lines[j].lstrip().startswith("model:"):
                    del lines[j]
                    break
                j += 1
            if model is not None:
                lines[i] = line + f"    model: {model}\n"
            break
    else:
        raise AssertionError(f"роль {role!r} не найдена в roles.yaml")
    return "".join(lines)


def claude_version_run(text: str, inner):
    """`subprocess.run`, отвечающий на `claude --version` строкой `text`;
    любая другая команда уходит в `inner` — тот `subprocess.run`, что
    стоял до подмены (в песочнице это `SpyRun` git-примитивов).

    Сверка по БАЗОВОМУ имени argv[0]: после этой задачи шаг роли зовёт
    CLI абсолютным путём, а `stack._tool_check` — по-прежнему литералом
    `claude` (SPEC, «Не входит»), и обе формы обязаны попадать сюда."""
    def run(args, *rest, **kwargs):
        argv = [args] if isinstance(args, (str, bytes)) else list(args)
        if argv and Path(str(argv[0])).name == "claude":
            return subprocess.CompletedProcess(argv, 0,
                                               f"{text} (Claude Code)\n", "")
        return inner(args, *rest, **kwargs)
    return run


def write_executable(path: Path) -> Path:
    """Исполняемый файл-пустышка: нужен, чтобы `shutil.which` его нашёл.
    Ни один из них не запускается — `spawn_agent` в планке подменён."""
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


# ------------------------------------------------------- git-справки планки

def git_text(*args: str) -> str:
    return _REAL_RUN(["git", *args], cwd=REPO_ROOT, capture_output=True,
                     text=True, check=True).stdout


def merge_base_or_skip(test) -> str:
    """Sha базы ветки задачи относительно `main`; на самом `main` — скип:
    диффить не с чем (приём `tasks/01M1SAA01YRRTWAVADT2F81RRQ/
    acceptance_tests/test_existing_zone_tests_not_weakened.py`). Нет
    локальной ветки `main` — тоже скип, а не отказ по причине, не
    относящейся к предмету критерия."""
    branch = git_text("rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch == config.MAIN_BRANCH:
        test.skipTest("рабочее дерево на main — диффить не с чем")
    try:
        return git_text("merge-base", config.MAIN_BRANCH, branch).strip()
    except subprocess.CalledProcessError as exc:
        test.skipTest(f"база ветки не вычислена ({exc}) — сверять не с чем")


def files_at(ref: str, prefix: str) -> list:
    out = git_text("ls-tree", "-r", "--name-only", ref, "--", prefix)
    return [line for line in out.splitlines() if line]


def text_at(ref: str, path: str):
    """Содержимое файла на ревизии `ref`; `None` — файла там нет."""
    try:
        return git_text("show", f"{ref}:{path}")
    except subprocess.CalledProcessError:
        return None


def text_on_disk(path: str):
    full = REPO_ROOT / path
    if not full.is_file():
        return None
    return full.read_text(encoding="utf-8")


# ------------------------------------------------------------ шаг роли

class StepRunSandbox(DeveloperBriefTmpRootTest):
    """Один шаг роли `developer` командой `runner.cmd_run` во временном
    каталоге: настоящий путь запуска шага (резолв инструментов манифеста,
    предполётные отказы, цикл попыток), подменён только сам процесс
    агента."""

    ROLE = "developer"

    def setUp(self):
        super().setUp()
        self.patch(gitcmd, "git", fake_git)
        self.patch(gitcmd, "show", disk_backed_show)
        self.patch(gitcmd, "ls_tree_files", disk_backed_ls_tree_files)

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new,
                                           "Абсолютный путь и модель роли")
        sync_spec_from_worktree(self.TASK)
        conn = store.db()
        conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (self.TASK,))
        conn.commit()
        # Обязательный артефакт роли этого состояния: без PLAN.md на диске
        # рабочего каталога успешная попытка честно ретраится, а планке
        # нужен один тихий успех.
        tdir = config.WORKTREES / self.TASK / "tasks" / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "PLAN.md").write_text("маркер\n", encoding="utf-8")

        self.pauses = []
        self.patch(runner.time, "sleep", self.pauses.append)
        self.patch(auto.time, "sleep", self.pauses.append)
        self.patch(runner.keychain, "token", lambda slot: "tok-test")
        preflight = mock.patch("orchestrator.doctor.preflight_checks",
                               lambda role, target: [])
        preflight.start()
        self.addCleanup(preflight.stop)
        self.exit_message = None
        self.spawn = None

    # ----------------------------------------------------------- патчи

    def patch(self, target, attr: str, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def set_model(self, model) -> None:
        path = self.root / "roles-under-test.yaml"
        path.write_text(roles_yaml_text(self.ROLE, model), encoding="utf-8")
        self.patch(config, "ROLES", path)

    def set_cli_version(self, text: str) -> None:
        self.patch(subprocess, "run", claude_version_run(text, subprocess.run))

    def set_min_versions(self, table: dict) -> None:
        """Подмена таблицы совместимости: тест задаёт числа сам, поэтому
        проверяет, что код ЧИТАЕТ таблицу, а не повторяет её значения по
        месту (AC-5)."""
        self.patch(stack, "MODEL_MIN_CLI_VERSION", dict(table))

    # ---------------------------------------------------------- прогоны

    def _fake_procs(self, attempts):
        return [FakeProc(lines, rc) for rc, lines in attempts]

    def run_step(self, *attempts) -> str:
        """`cmd_run` одним шагом. `attempts` — пары `(rc, строки вывода)`,
        по одной на попытку агента; без аргументов — одна успешная.
        Отказ шага до старта агента (`sys.exit`) перехватывается: его
        текст остаётся в `self.exit_message`, как его увидел бы `auto`."""
        if not attempts:
            attempts = ((0, ["готово\n"]),)
        buf = io.StringIO()
        with mock.patch.object(runner, "spawn_agent",
                               side_effect=self._fake_procs(attempts)) as spawn:
            with redirect_stdout(buf):
                try:
                    runner.cmd_run(self.TASK)
                except SystemExit as exc:
                    self.exit_message = str(exc)
        self.spawn = spawn
        return buf.getvalue()

    def run_auto(self) -> str:
        """Цикл `auto` на той же задаче: агент отвечает успехом на ЛЮБОЕ
        число запусков (свежий `FakeProc` на каждый вызов) — цикл,
        проскочивший отказ, обязан быть виден счётчиком запусков, а не
        замаскирован исчерпанным списком заготовок."""
        def fresh_proc(*args, **kwargs):
            return FakeProc(["готово\n"], 0)

        buf = io.StringIO()
        with mock.patch.object(runner, "spawn_agent",
                               side_effect=fresh_proc) as spawn:
            with redirect_stdout(buf):
                try:
                    auto.cmd_auto(self.TASK)
                except SystemExit as exc:
                    self.exit_message = str(exc)
        self.spawn = spawn
        return buf.getvalue()

    def argv(self) -> list:
        return list(self.spawn.call_args.args[0])

    # ---------------------------------------------------------- журнал

    def journal_rows(self) -> list:
        return store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()

    def journal_details(self, action: str) -> list:
        return [r["detail"] for r in self.journal_rows()
                if r["action"] == action]

    def entries_containing(self, needle: str) -> list:
        """Записи журнала шага, несущие `needle` в действии ИЛИ детали:
        планка не предписывает, какой половиной записи реализация назовёт
        отказ, — предмет проверки в том, что он назван."""
        return [f"{r['action']}: {r['detail']}" for r in self.journal_rows()
                if needle in f"{r['action']}: {r['detail']}"]

    def state(self) -> str:
        return store.db().execute(
            "SELECT state FROM tasks WHERE id=?", (self.TASK,)).fetchone()["state"]
