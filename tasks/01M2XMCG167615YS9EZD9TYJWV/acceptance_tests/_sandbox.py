"""Общая песочница приёмочных тестов задачи 01M2XMCG167615YS9EZD9TYJWV
(`doc-commit`: документы и конфигурация Оператора коммитятся от
`origin/main` механикой `note`).

`DocCommitSandbox` — тонкая надстройка над `tests.sandbox.RealGitSandbox`
(`self.root` — главная копия пульта, настоящий git-репозиторий с веткой
`config.MAIN_BRANCH` и пустой схемой БД): добавляет локальный bare
`self.origin` в роли `origin/<MAIN_BRANCH>`, синхронный с главной копией
набор фикстурных файлов (`docs/backlog.md`, `docs/roadmap.md`, а также
`roles.yaml`/`gates.yaml`/`targets.yaml` — конфигурация Оператора из
требования 3 SPEC) и помощники чтения origin. Собственных копий
`disk_backed_*`/`advance_from_in_dev` здесь нет — сценарию нужен
настоящий git, не лёгкая песочница переходов FSM.

Команда зовётся через диспетчер `orchestrator/artel.py` (`artel.main` с
подменённым `sys.argv`) — ровно так, как её называет требование 1 SPEC
(`artel.py doc-commit <путь> --from <файл> [--message …]`), и тем же
приёмом, каким диспетчер уже проверяют `tests/test_artel_role_restricted_
commands.py:25` и `tests/test_kill_live_cycle_refusal.py:137`.

`assert_refused` отдельно сверяет, что отказ пришёл ОТ КОМАНДЫ, а не от
отсутствия команды в таблице диспетчера: без этой сверки любой тест
отказа зеленел бы уже сегодня на `sys.exit("Неизвестная команда …")`
(`orchestrator/artel.py:836`) — имитация теста вместо теста критерия.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import artel, config, store  # noqa: E402
from tests.sandbox import RealGitSandbox, capture  # noqa: E402

# Захвачено ДО того, как любой тест подменит `subprocess.run`.
_REAL_RUN = subprocess.run

# Текст отказа диспетчера на незаведённую команду — `orchestrator/
# artel.py:836`. Служит маркером «команды doc-commit вовсе нет», не
# предметом проверки.
UNKNOWN_COMMAND_MARKER = "Неизвестная команда"

DOC_REL = "docs/roadmap.md"
CONFIG_REL = "roles.yaml"

BACKLOG_TEXT = """# Копилка и бэклог

## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое наблюдение УНИКАЛЬНЫЙКЛЮЧ | orchestrator/x.py |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта | Заметка |
|---|---|---|---|---|---|---|
| 1 | Кандидат A | Суть A | $10 | orchestrator/a.py | сразу | — |

## Очередь Оператора

| П | Действие |
|---|---|
| 1 | Действие A |
"""

ROADMAP_TEXT = "# Роадмап\n\nСтарый раздел роадмапа.\n"

ROLES_TEXT = "developer:\n  model: opus\n"
GATES_TEXT = "in_dev:\n  next: review\n"
TARGETS_TEXT = "artel:\n  kind: self\n"

FIXTURE_FILES = {
    "docs/backlog.md": BACKLOG_TEXT,
    DOC_REL: ROADMAP_TEXT,
    "roles.yaml": ROLES_TEXT,
    "gates.yaml": GATES_TEXT,
    "targets.yaml": TARGETS_TEXT,
}


class DocCommitSandbox(RealGitSandbox):
    """Главная копия пульта с фикстурными документами и конфигурацией,
    синхронная с bare `self.origin`: содержимое каждого фикстурного пути
    в `origin/<MAIN_BRANCH>` и в HEAD главной копии совпадает — сверка
    базы (требование 5 SPEC) по умолчанию проходит, пока тест сам не
    разведёт origin и пин."""

    def setUp(self):
        super().setUp()
        self.origin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        self.git("init", "-q", "--bare", self.origin)
        self.git("remote", "add", "origin", self.origin)
        for rel, text in FIXTURE_FILES.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "документы и конфигурация")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.git("fetch", "-q", "origin", config.MAIN_BRANCH)

        self.source_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.source_dir, ignore_errors=True)

    # --- источник правки (`--from <файл>`) ---

    def source_file(self, text: str, name: str = "draft.md") -> Path:
        """Файл-источник ВНЕ главной копии — «любой путь на диске,
        например из каталога сессии» (требование 1 SPEC)."""
        path = Path(self.source_dir) / name
        path.write_text(text, encoding="utf-8")
        return path

    # --- вызов команды через диспетчер ---

    def run_artel(self, *argv: str) -> str:
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            return capture(artel.main)

    def run_allowing_exit(self, *argv: str) -> str:
        """Вызов, исход которого сценарию безразличен (удержание может
        завершаться и молча, и `sys.exit`). Незаведённую команду не
        глотает — иначе сценарий удержания зеленел бы без реализации."""
        try:
            return self.run_artel(*argv)
        except SystemExit as exc:
            self.assertNotIn(UNKNOWN_COMMAND_MARKER, str(exc),
                             "команда doc-commit не заведена в диспетчере")
            return str(exc)

    def assert_refused(self, argv: list, phrase: str | None = None) -> str:
        with self.assertRaises(SystemExit) as ctx:
            self.run_artel(*argv)
        message = str(ctx.exception)
        self.assertNotIn(UNKNOWN_COMMAND_MARKER, message,
                         "команда doc-commit не заведена в диспетчере")
        if phrase is not None:
            self.assertIn(phrase, message, message)
        return message

    # --- чтение origin ---

    def origin_run(self, *args) -> subprocess.CompletedProcess:
        return _REAL_RUN(["git", "-C", self.origin, *args],
                         capture_output=True, text=True)

    def origin_head(self) -> str:
        res = self.origin_run("rev-parse", config.MAIN_BRANCH)
        return res.stdout.strip() if res.returncode == 0 else ""

    def origin_show(self, rel: str) -> str:
        res = self.origin_run("show", f"{config.MAIN_BRANCH}:{rel}")
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def origin_subject(self) -> str:
        res = self.origin_run("log", "-1", "--format=%s", config.MAIN_BRANCH)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout.strip()

    # --- снимок главной копии ---

    def main_copy_snapshot(self) -> tuple:
        """HEAD, текущая ветка и рабочее дерево главной копии одним
        значением — то, что требование 2/AC-1 запрещает сдвигать."""
        return (self.git("rev-parse", "HEAD").strip(),
                self.git("rev-parse", "--abbrev-ref", "HEAD").strip(),
                self.git("status", "--porcelain"))

    def pending_dir(self) -> Path:
        return config.ROOT / ".artel" / "notes-pending"

    def pending_files(self) -> list:
        """Удержанные записи как файлы каталога — читаются с диска, а не
        через `notes.pending_notes()`: критерии говорят о появлении
        записи в `.artel/notes-pending/`, и сверка не должна зависеть от
        того, разбирает ли новый формат существующий читатель."""
        d = self.pending_dir()
        return sorted(d.glob("*.json")) if d.exists() else []

    def pending_records(self) -> list:
        """Содержимое удержанных записей (JSON) в порядке имён файлов."""
        return [json.loads(p.read_text(encoding="utf-8"))
                for p in self.pending_files()]

    def work_repo_dir(self) -> Path:
        return config.ROOT / ".artel" / "notes-work"

    # --- окно тишины ---

    def open_silence_window(self, task_id: str = "T-WIN") -> None:
        """Задача в первом состоянии `config.NOTE_SILENCE_WINDOW_STATES`
        — окно тишины открыто (`notes._silence_window_reason` даёт
        причину). Состояние берётся от config, не литералом: набор —
        крутилка Оператора."""
        state = config.NOTE_SILENCE_WINDOW_STATES[0]
        store.insert_task(store.db(), task_id, "окно тишины", state,
                          f"task/{task_id}", config.DEFAULT_TARGET, 10.0)

    def close_silence_window(self, task_id: str = "T-WIN") -> None:
        """Снимает строку задачи — держателя `merge_locks` песочница не
        заводит, так что окно закрывается детерминированно, независимо
        от словаря состояний."""
        conn = store.db()
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()
