"""Приёмочные тесты AC-1, AC-2, AC-5 (tasks/01M1SAA01YRRTWAVADT2F81RRQ/
SPEC.md): автокоммит артефактов шага (`orchestrator/checkpoint.py`)
переносит из `tasks/<id>/acceptance_tests/` в артефактную ветку только
разрешённый набор файлов первого уровня, посторонние — журналирует
ОДНОЙ записью и не коммитит.

Красен до реализации: `checkpoint._commit_external_step_artifacts` сейчас
безусловно коммитит ВСЁ, что нашёл `task_dir.rglob("*")` (кроме отфильтро-
ванного `.gitignore`), — фильтра «разрешённый файл первого уровня
acceptance_tests/» и журнала «в каталоге планки посторонние файлы: …» в
коде нет вовсе. Тесты AC-1/AC-2 падают на присутствии посторонних файлов
в артефактной ветке; тест AC-5 падает на том же плюс на отсутствии
журнальной записи нужного формата.

Песочница — `RealGitSandbox` + внешний target (тот же приём, что
`tests/test_checkpoint_external_step_artifacts.py`): рабочий каталог роли
— обычная директория на диске, git нужен только для артефактной ветки
пульта.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import checkpoint, config, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TARGET = "strayproj"


class _StrayFilesCheckpointBase(RealGitSandbox):

    TASK = "01STRAYFILESBASE00001"

    def setUp(self):
        super().setUp()
        # `__pycache__/` в `.gitignore` пульта — та же настройка, что несёт
        # реальный корень репозитория (SPEC 01M1KVG3KSCY47HWXWF5HM0E76):
        # без неё тест проверял бы поведение НЕсуществующей в проде
        # конфигурации, а не описанное в AC-1 «уже игнорируемый __pycache__».
        (self.root / ".gitignore").write_text("__pycache__/\n*.pyc\n",
                                              encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-q", "-m", "gitignore")
        conn = store.db()
        store.insert_task(conn, self.TASK, "Задача — посторонние файлы",
                          "tests_writing", f"task/{self.TASK.lower()}-x",
                          TARGET, config.DEFAULT_BUDGET_USD)
        self.workspace_root = config.PROJECTS / TARGET / "workspace"
        self.task_dir = self.workspace_root / "tasks" / self.TASK
        self.task_dir.mkdir(parents=True)

    def write(self, rel: str, content) -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def artifact_branch_files(self) -> list[str]:
        branch = f"artifact/{self.TASK.lower()}"
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def write_mixed_fixture(self) -> None:
        """Шесть разрешённых файлов планки, три посторонних, один
        игнорируемый `.gitignore` (`__pycache__`), плюс контрольный файл
        задачи ВНЕ `acceptance_tests/` — область правила ограничена
        только этим подкаталогом."""
        self.write("PLAN.md", "план вне acceptance_tests/")
        self.write("acceptance_tests/test_ac1_something.py", "# тест\n")
        self.write("acceptance_tests/_sandbox.py", "# песочница\n")
        self.write("acceptance_tests/markers.py", "# маркеры\n")
        self.write("acceptance_tests/__init__.py", "")
        self.write("acceptance_tests/NOTES.md", "заметки планки\n")
        self.write("acceptance_tests/README.txt", "README планки\n")
        self.write("acceptance_tests/docs/codebase-map.md",
                   "---\nbuilt_at_sha: deadbeef\n---\n# карта\n")
        self.write("acceptance_tests/fixtures.json", '{"x": 1}')
        self.write("acceptance_tests/helpers/util.py", "# хелпер\n")
        self.write("acceptance_tests/__pycache__/x.cpython-311.pyc",
                   bytes(range(8)))


class Ac1AllowedVsExtraneousTest(_StrayFilesCheckpointBase):
    """AC-1: только разрешённый набор первого уровня `acceptance_tests/`
    (`test_*.py`, `_sandbox.py`, `markers.py`, `__init__.py`,
    `*.md`/`*.txt`) доезжает до артефактной ветки; вложенные подкаталоги
    (кроме уже игнорируемого `__pycache__`) и посторонние расширения —
    нет, независимо от файлов ВНЕ `acceptance_tests/`."""

    TASK = "01STRAYFILESAC1BASE01"

    def test_ac1_allowed_top_level_files_committed_stray_ones_are_not(self):
        """Полный автокоммит шага смешанной фикстуры: шесть разрешённых
        файлов и контрольный PLAN.md вне acceptance_tests/ обязаны попасть
        в артефактную ветку, три посторонних (вложенный `.md`, посторонний
        `.json` первого уровня, вложенный `.py`) — нет; уже игнорируемый
        `.gitignore` `__pycache__` — тоже нет (регресс с существующим
        фильтром `.gitignore`, не новым правилом).

        Ловит мутацию: фильтр реализован как список РАЗРЕШЁННЫХ РАСШИРЕНИЙ
        без учёта вложенности (например, «любой `.py`/`.md`/`.txt` внутри
        acceptance_tests/, на любой глубине») — тогда `acceptance_tests/
        docs/codebase-map.md` и `acceptance_tests/helpers/util.py`
        просочились бы в артефактную ветку вопреки требованию «первого
        уровня»."""
        self.write_mixed_fixture()

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "test_author")

        files = self.artifact_branch_files()
        prefix = f"tasks/{self.TASK}/"
        for allowed in ("PLAN.md",
                       "acceptance_tests/test_ac1_something.py",
                       "acceptance_tests/_sandbox.py",
                       "acceptance_tests/markers.py",
                       "acceptance_tests/__init__.py",
                       "acceptance_tests/NOTES.md",
                       "acceptance_tests/README.txt"):
            with self.subTest(файл=allowed):
                self.assertIn(prefix + allowed, files)
        for stray in ("acceptance_tests/docs/codebase-map.md",
                     "acceptance_tests/fixtures.json",
                     "acceptance_tests/helpers/util.py",
                     "acceptance_tests/__pycache__/x.cpython-311.pyc"):
            with self.subTest(файл=stray):
                self.assertNotIn(prefix + stray, files)


class Ac2SingleJournalEntryTest(_StrayFilesCheckpointBase):
    """AC-2: несколько посторонних файлов на одном шаге дают РОВНО одну
    запись журнала «в каталоге планки посторонние файлы: <список>» — не
    по отдельной записи на файл."""

    TASK = "01STRAYFILESAC2BASE01"

    def test_ac2_multiple_stray_files_produce_exactly_one_journal_entry(self):
        """Три посторонних файла одного шага — журнал несёт ровно одну
        запись с этой формулировкой, перечисляющую все три, а не три
        отдельные записи.

        Ловит мутацию: журналирование вызывается ВНУТРИ цикла по
        посторонним файлам (естественный, но неверный способ это
        реализовать) — тогда на три посторонних файла появились бы три
        отдельные записи журнала вместо одной комбинированной."""
        self.write_mixed_fixture()

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "test_author")

        stray_entries = [d for d in self.journal_details()
                         if "посторонние файлы" in d]
        self.assertEqual(len(stray_entries), 1, stray_entries)
        entry = stray_entries[0]
        for name in ("docs/codebase-map.md", "fixtures.json",
                    "helpers/util.py"):
            with self.subTest(файл=name):
                self.assertIn(name, entry)

    def test_ac2_no_stray_files_produces_no_such_journal_entry(self):
        """Симметричный контроль: шаг без единого постороннего файла не
        порождает запись «посторонние файлы» вовсе — формулировка не
        становится безусловным шумом на каждом автокоммите.

        Ловит мутацию: журнальная запись пишется всегда, с пустым
        списком, если посторонних файлов не нашлось."""
        self.write("acceptance_tests/test_ac1_something.py", "# тест\n")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "test_author")

        stray_entries = [d for d in self.journal_details()
                         if "посторонние файлы" in d]
        self.assertEqual(stray_entries, [])


class Ac5IncidentReproductionTest(_StrayFilesCheckpointBase):
    """AC-5: воспроизведение РЕАЛЬНОГО инцидента 05.09 — `scripts/
    codebase_map.py`, запущенный с cwd внутри каталога планки, оставляет
    `acceptance_tests/docs/codebase-map.md` на диске; шаг test_author
    коммитится как обычно (легитимный тест рядом присутствует)."""

    TASK = "01STRAYFILESAC5BASE01"

    INCIDENT_MAP_MD = ("---\nbuilt_at_sha: 0123456789abcdef0123456789ab"
                       "cdef01234567\n---\n\n# Codebase-map пульта\n\n"
                       "Автосгенерировано `scripts/codebase_map.py`.\n")

    def test_ac5_incident_map_file_is_excluded_and_journaled_once(self):
        """Ловит мутацию: фильтр учитывает только расширение файла, не
        глубину пути (например, разрешает любой `*.md` независимо от
        вложенности) — тогда именно этот, буквально воспроизводящий
        инцидент, файл снова попал бы в артефактную ветку, несмотря на
        реализованный фильтр по общему правилу."""
        self.write("acceptance_tests/test_ac1_something.py", "# тест\n")
        self.write("acceptance_tests/docs/codebase-map.md",
                   self.INCIDENT_MAP_MD)

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "test_author")

        files = self.artifact_branch_files()
        prefix = f"tasks/{self.TASK}/"
        self.assertIn(prefix + "acceptance_tests/test_ac1_something.py",
                      files)
        self.assertNotIn(prefix + "acceptance_tests/docs/codebase-map.md",
                         files)
        stray_entries = [d for d in self.journal_details()
                         if "посторонние файлы" in d]
        self.assertEqual(len(stray_entries), 1, stray_entries)
        self.assertIn("acceptance_tests/docs/codebase-map.md",
                      stray_entries[0])


if __name__ == "__main__":
    unittest.main()
