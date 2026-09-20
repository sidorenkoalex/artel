"""Юнит-тесты `scripts/guard.py::artifact_disk_read_errors_from_files`/
`scan_artifact_disk_reads` (SPEC 01M2XJKKPHM5XDAE42838AMBQH, требования
1-4, AC-1..AC-5, AC-8) — постоянный набор `tests/`, отдельный от
залоченной планки задачи (`tasks/01M2XJKKPHM5XDAE42838AMBQH/
acceptance_tests/`), которая наблюдает те же свойства только через
`fsm.cmd_advance` вложенной песочницы; здесь — сама функция по
отдельности, тем же приёмом, что `tests/test_guard_mutation_claim.py`.

Правило действует по ANSWER-1 задачи (вариант B, уточнение требования 1
и AC-1/AC-5): ошибка — только путь, якоренный на рабочую копию
(`Path(__file__)`, `config.ROOT`/`config.TASKS`, литерал `tasks/…`, имена,
присвоенные от них); пути от временных каталогов песочницы под правило
не подпадают — класс `AnchoringTest`.
"""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import guard  # noqa: E402

RECIPE = ('читай из артефактной ветки: '
          'gitcmd.show(artifact_branch.branch_name(TASK_ID), '
          '"tasks/<id>/PLAN.md")')

# Пролог фикстурной планки: `TASK_DIR` — якорное имя (от `Path(__file__)`),
# `FIXTURE_DIR` — неякорное (от `tempfile`), оба на уровне модуля.
PRELUDE = (
    "import os\n"
    "import subprocess\n"
    "import tempfile\n"
    "from pathlib import Path\n"
    "from orchestrator import artifact_branch, config, gitcmd\n"
    "TASK = '01FIXTURETASK'\n"
    "TASK_DIR = Path(__file__).resolve().parents[1]\n"
    "FIXTURE_DIR = Path(tempfile.mkdtemp())\n"
)


def source_with(*lines: str) -> str:
    """Текст файла планки: общий пролог плюс строки сценария — каждая
    строка сценария получает номер `len(PRELUDE.splitlines()) + i`."""
    return PRELUDE + "\n".join(lines) + "\n"


FIRST_SCENARIO_LINE = len(PRELUDE.splitlines()) + 1


def errors_for(*lines: str) -> list[str]:
    return guard.artifact_disk_read_errors_from_files(
        [("acceptance_tests/test_x.py", source_with(*lines))])


class DiskReadFormsTest(unittest.TestCase):
    """Требование 1/AC-1 (в редакции ANSWER-1): каждый названный образец
    доступа к файловой системе со строковым литералом имени артефакта по
    якорному пути — ошибка."""

    FORMS = {
        "Path(__file__)... / literal":
            'plan = Path(__file__).resolve().parents[1] / "PLAN.md"',
        "якорное имя / literal (TASK_DIR от Path(__file__))":
            'plan = TASK_DIR / "PLAN.md"',
        "Path(literal tasks/...)":
            'plan = Path("tasks/01FIXTURETASK/PLAN.md")',
        "pathlib.Path(literal tasks/...)":
            'plan = pathlib.Path("tasks/01FIXTURETASK/PLAN.md")',
        "open(literal tasks/...)":
            'handle = open("tasks/01FIXTURETASK/PLAN.md", encoding="utf-8")',
        ".read_text( на цепочке с joinpath(literal) от якорного имени":
            'text = TASK_DIR.joinpath("PLAN.md").read_text(encoding="utf-8")',
        "os.path.join('tasks', ...)":
            'path = os.path.join("tasks", "01FIXTURETASK", "PLAN.md")',
        "os.path.exists(literal tasks/...)":
            'exists = os.path.exists("tasks/01FIXTURETASK/PLAN.md")',
        "f-строка tasks/... в open(":
            'handle = open(f"tasks/{TASK}/PLAN.md")',
        "f-строка операндом / от якорного имени":
            'plan = TASK_DIR / f"{TASK}-PLAN.md"',
        "config.TASKS / ... / literal":
            'plan = config.TASKS / TASK / "PLAN.md"',
        "config.ROOT / 'tasks' / ... / literal":
            'spec = config.ROOT / "tasks" / TASK / "SPEC.md"',
        "os.path.join(str(config.TASKS), ...)":
            'path = os.path.join(str(config.TASKS), TASK, "PLAN.md")',
        "open(str(якорное имя) + literal)":
            'handle = open(str(TASK_DIR) + "/PLAN.md", encoding="utf-8")',
        "Path(f-строка от якорного имени)":
            'plan = Path(f"{TASK_DIR}/PLAN.md")',
    }

    def test_each_named_form_is_reported_once_with_file_and_line(self):
        """Ловит мутацию: список выражений доступа собран не полностью
        (только `/` с `Path(...)`, забыты `open(`/`os.path.*`/`.read_text(`
        либо f-строка не разбирается как литерал) или список якорей сведён
        к `__file__` (забыты `config.ROOT`/`config.TASKS`, литерал
        `tasks/`, конкатенация `+`, f-строка от якоря) — подтест с этим
        образцом получит пустой список ошибок; вторая половина ассерта
        ловит подмену номера строки узла-выражения на номер строки
        начала файла или инструкции."""
        for form, line in self.FORMS.items():
            with self.subTest(form=form):
                errors = errors_for(line)
                self.assertEqual(len(errors), 1, errors)
                self.assertTrue(
                    errors[0].startswith(
                        f"acceptance_tests/test_x.py:{FIRST_SCENARIO_LINE}: "),
                    errors[0])

    def test_error_text_carries_the_artifact_branch_recipe(self):
        """Требование 3: текст ошибки — файл, строка и рецепт с
        `gitcmd.show(artifact_branch.branch_name(TASK_ID), "tasks/<id>/
        PLAN.md")`, имя артефакта в рецепте — найденное, не всегда PLAN.md.

        Ловит мутацию: рецепт сокращён до констатации «читает с диска» или
        подставляет одно и то же имя `PLAN.md` в рецепт для любого
        артефакта — вторая проверка (SPEC.md) покраснеет."""
        errors = errors_for('plan = TASK_DIR / "PLAN.md"')
        self.assertIn(RECIPE, errors[0])
        errors = errors_for('spec = TASK_DIR / "SPEC.md"')
        self.assertIn('"tasks/<id>/SPEC.md")', errors[0])

    def test_every_artifact_name_is_covered(self):
        """AC-5: семь имён из `guard.ARTIFACT_FILE_NAMES` в одном и том же
        выражении — каждое даёт ошибку; для префикса `ANSWER-` рецепт
        называет настоящее имя файла из литерала.

        Ловит мутацию: список имён сведён к образцам инцидентов (PLAN.md,
        SPEC.md) — подтест с `TZ.md`/`QUESTIONS.md`/`TEST_REPORT.md`/
        `ANSWER-` даст пустой список."""
        self.assertEqual(
            guard.ARTIFACT_FILE_NAMES,
            ("PLAN.md", "SPEC.md", "REVIEW.md", "TZ.md", "QUESTIONS.md",
             "TEST_REPORT.md", "ANSWER-"))
        for name in guard.ARTIFACT_FILE_NAMES:
            literal = "ANSWER-2.md" if name == "ANSWER-" else name
            with self.subTest(artifact=name):
                errors = errors_for(f'path = TASK_DIR / "{literal}"')
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(f'"tasks/<id>/{literal}")', errors[0])

    def test_nested_expressions_over_one_literal_report_one_error(self):
        """`open(os.path.join(..., "PLAN.md"))` — два выражения доступа
        над одним литералом дают одну ошибку, не две.

        Ловит мутацию: дедупликация по (строка, имя) снята — роль получит
        две одинаковые строки отказа на одно место."""
        errors = errors_for(
            'handle = open(os.path.join("tasks", TASK, "PLAN.md"))')
        self.assertEqual(len(errors), 1, errors)

    def test_errors_are_ordered_by_line_within_a_file(self):
        """Две ошибки в одном файле идут по возрастанию номера строки —
        `ast.walk` обходит дерево в ширину, порядок восстанавливается.

        Ловит мутацию: сортировка по строке снята — порядок ошибок
        зависит от формы выражений, не от места в файле."""
        errors = errors_for(
            'handle = open(os.path.join("tasks", TASK, "SPEC.md"))',
            'plan = TASK_DIR / "PLAN.md"')
        self.assertEqual(len(errors), 2, errors)
        self.assertIn(f":{FIRST_SCENARIO_LINE}: ", errors[0])
        self.assertIn(f":{FIRST_SCENARIO_LINE + 1}: ", errors[1])


class AnchoringTest(unittest.TestCase):
    """ANSWER-1 (вариант B, уточнение требования 1 и AC-1/AC-5): ошибка —
    только путь, якоренный на рабочую копию; пути от временных каталогов
    песочницы (`tempfile`, `self.tdir` вложенной песочницы) правило не
    касается, а имена, присвоенные от якорей, якорны транзитивно."""

    TEMP_FORMS = {
        "запись фикстуры от имени модуля из tempfile":
            '(FIXTURE_DIR / "tasks" / TASK / "SPEC.md").write_text("x")',
        "чтение фикстуры от tempfile":
            'spec = (FIXTURE_DIR / "SPEC.md").read_text(encoding="utf-8")',
        "open(os.path.join(tmp, ...))":
            'handle = open(os.path.join(FIXTURE_DIR, "tasks", TASK, "PLAN.md"))',
        "Path(tmp, literal)":
            'plan = Path(FIXTURE_DIR, "PLAN.md")',
        "os.path.exists от tempfile":
            'exists = os.path.exists(os.path.join(str(FIXTURE_DIR), "REVIEW.md"))',
        "локальное имя от tempfile.mkdtemp()":
            'tmp = tempfile.mkdtemp()\n'
            'plan = Path(tmp) / "tasks" / TASK / "PLAN.md"',
        "Path(tempfile.gettempdir())":
            'plan = Path(tempfile.gettempdir()) / "PLAN.md"',
        "self.tdir вложенной песочницы":
            'class Sandbox:\n'
            '    def enter(self):\n'
            '        (self.tdir / "SPEC.md").write_text("x", encoding="utf-8")',
    }

    def test_paths_from_temporary_directories_are_not_reported(self):
        """Восемь форм доступа с именем артефакта по пути от временного
        каталога — записи и чтения фикстур вложенной песочницы — ошибок не
        дают.

        Ловит мутацию: якорный предикат снят (правило вернулось к «любое
        выражение доступа с именем артефакта») либо голый литерал `tasks`
        правым операндом `/` посчитан корнем пути — `Path(tmp) / "tasks" /
        TASK / "PLAN.md"` и `(self.tdir / "SPEC.md").write_text(...)`
        получили бы ошибку, как 68 из 186 исторических планок до
        уточнения."""
        for form, line in self.TEMP_FORMS.items():
            with self.subTest(form=form):
                self.assertEqual(errors_for(line), [])

    def test_names_assigned_from_anchors_are_anchored_transitively(self):
        """`PLAN_DIR = TASK_DIR.parent` и `TASKS_ROOT = config.TASKS` —
        имена второго порядка якорны; порядок присваивания и
        использования в файле не важен (использование внутри функции,
        объявленной раньше присваивания, — та же ошибка).

        Ловит мутацию: имена собираются одним проходом только от прямых
        якорных выражений (`Path(__file__)`, `config.TASKS`) без замыкания
        по цепочке присваиваний либо только по порядку строк — `PLAN_DIR`
        от `TASK_DIR` или имя, использованное раньше объявления, дадут
        пустой список."""
        errors = errors_for('PLAN_DIR = TASK_DIR.parent',
                            'plan = PLAN_DIR / "PLAN.md"')
        self.assertEqual(len(errors), 1, errors)
        self.assertIn(f":{FIRST_SCENARIO_LINE + 1}: ", errors[0])
        errors = errors_for('TASKS_ROOT = config.TASKS',
                            'spec = TASKS_ROOT / TASK / "SPEC.md"')
        self.assertEqual(len(errors), 1, errors)
        errors = errors_for('def read():',
                            '    return (PLAN_DIR / "PLAN.md").read_text()',
                            'PLAN_DIR = TASK_DIR.parent')
        self.assertEqual(len(errors), 1, errors)
        self.assertIn(f":{FIRST_SCENARIO_LINE + 1}: ", errors[0])

    def test_incident_sample_01m2b6k3em_stays_reported(self):
        """Эталон инцидента 12.09 (`tasks/01M2B6K3EM7F2J72RC2F520Y2K/
        acceptance_tests/test_ac8_…:26`, ANSWER-1 п. 3): модульное
        `PLAN_DISK = Path(__file__).resolve().parents[1] / "PLAN.md"` рядом
        с законным `gitcmd.show(...)` — ровно одна ошибка, на строке
        `PLAN_DISK`, с именем `PLAN.md`.

        Ловит мутацию: `__file__` выпал из якорей (якоря сведены к
        `config.*`/литералу `tasks/`) — инцидентный образец, ради которого
        задача затевалась, прошёл бы гейт."""
        source = (
            '"""AC-8 — образец инцидента 12.09."""\n'
            'import unittest\n'
            'from pathlib import Path\n'
            '\n'
            'from orchestrator import artifact_branch, gitcmd\n'
            '\n'
            'TASK_ID = "01M2B6K3EM7F2J72RC2F520Y2K"\n'
            'PLAN_DISK = Path(__file__).resolve().parents[1] / "PLAN.md"\n'
            'text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),\n'
            '                            f"tasks/{TASK_ID}/PLAN.md")\n')
        errors = guard.artifact_disk_read_errors_from_files(
            [("acceptance_tests/test_ac8_plan.py", source)])
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].startswith(
            "acceptance_tests/test_ac8_plan.py:8: чтение артефакта задачи "
            "PLAN.md с диска"), errors[0])

    def test_bare_tasks_literal_anchors_only_at_the_path_root(self):
        """Голый литерал `tasks` — якорь в корне пути (`os.path.join("tasks",
        …)`, `Path("tasks") / …`), но не правым операндом `/` посреди цепочки
        от временного каталога (`FIXTURE_DIR / "tasks" / TASK / "PLAN.md"`).

        Ловит мутацию: `_literal_is_anchored` перестал различать корневую
        позицию — либо `os.path.join("tasks", …)` пропущен, либо путь от
        временного каталога с сегментом `tasks` отклонён."""
        self.assertEqual(len(errors_for(
            'path = os.path.join("tasks", TASK, "PLAN.md")')), 1)
        self.assertEqual(len(errors_for(
            'plan = Path("tasks") / TASK / "PLAN.md"')), 1)
        self.assertEqual(errors_for(
            'plan = FIXTURE_DIR / "tasks" / TASK / "PLAN.md"'), [])

    def test_recipe_names_the_artifact_not_the_literal_fragment(self):
        """R1-F2 REVIEW.md итерации 1: для части f-строки `f"{TASK}-PLAN.md"`
        рецепт называет `tasks/<id>/PLAN.md`, а не несуществующий
        `tasks/<id>/-PLAN.md`; имя файла из литерала подставляется только
        когда basename начинается с имени артефакта (`ANSWER-1.md`).

        Ловит мутацию: условие подстановки basename вернулось к `name in
        basename` — фрагмент `-PLAN.md` ушёл бы в рецепт как есть."""
        errors = errors_for('plan = TASK_DIR / f"{TASK}-PLAN.md"')
        self.assertIn('"tasks/<id>/PLAN.md")', errors[0])
        self.assertNotIn("-PLAN.md", errors[0])
        errors = errors_for('answer = TASK_DIR / "ANSWER-1.md"')
        self.assertIn('"tasks/<id>/ANSWER-1.md")', errors[0])
        errors = errors_for('answer = Path("tasks/01FIXTURETASK/ANSWER-3.md")')
        self.assertIn('"tasks/<id>/ANSWER-3.md")', errors[0])


class AllowedSourcesTest(unittest.TestCase):
    """Требование 2/AC-2/AC-3/AC-4: артефактная ветка, subprocess с git,
    докстринги и комментарии — не ошибка."""

    def test_gitcmd_show_and_artifact_branch_are_not_reported(self):
        """Ловит мутацию: проверка ищет имя артефакта в любом строковом
        литерале файла (или в аргументах любого вызова), не только в
        выражениях доступа к файловой системе — законное
        `gitcmd.show(..., "tasks/<id>/PLAN.md")` получит ошибку."""
        self.assertEqual(errors_for(
            'text, _reason = gitcmd.show(',
            '    artifact_branch.branch_name(TASK),',
            '    "tasks/01FIXTURETASK/PLAN.md")',
            'rev = artifact_branch.branch_name(TASK) + (',
            '    ":tasks/01FIXTURETASK/REVIEW.md")'), [])

    def test_subprocess_git_show_and_cat_file_are_not_reported(self):
        """Ловит мутацию: `subprocess.run` внесён в набор вызовов доступа
        к файловой системе (как «внешняя команда — тоже доступ») — чтение
        артефакта через `git show`/`git cat-file` отклонялось бы."""
        self.assertEqual(errors_for(
            'res = subprocess.run(',
            '    ["git", "show",',
            '     "artifacts/01FIXTURETASK:tasks/01FIXTURETASK/PLAN.md"],',
            '    capture_output=True, text=True)',
            'res = subprocess.run(',
            '    ["git", "cat-file", "-p",',
            '     "artifacts/01FIXTURETASK:tasks/01FIXTURETASK/SPEC.md"],',
            '    capture_output=True, text=True)'), [])

    def test_docstrings_and_comments_are_not_reported(self):
        """Имя артефакта в докстринге модуля, в комментарии-строке и в
        КОНЦЕВОМ комментарии строки с настоящим чтением постороннего
        файла — не ошибка.

        Ловит мутацию: проверка по сырому тексту строки (regex «литерал
        + признак доступа») вместо AST — строка `open("fixture.txt")  #
        не PLAN.md` даст ложную ошибку."""
        source = (
            '"""PLAN.md, SPEC.md, REVIEW.md, TZ.md, QUESTIONS.md, '
            'TEST_REPORT.md, ANSWER-1.md — из артефактной ветки."""\n'
            + PRELUDE
            + '# REVIEW.md и TEST_REPORT.md читать с диска незачем\n'
            + 'sample = TASK_DIR / "fixture.txt"  # рядом с SPEC.md\n'
            + 'data = open("fixture.txt", encoding="utf-8")  # не PLAN.md\n')
        self.assertEqual(guard.artifact_disk_read_errors_from_files(
            [("acceptance_tests/test_x.py", source)]), [])

    def test_unparseable_file_yields_no_errors_here(self):
        """Файл с `SyntaxError` ошибок этой проверки не даёт — синтаксис
        планки ловит сухой сбор того же гейта своим текстом.

        Ловит мутацию: `SyntaxError` не перехвачен — гейт падал бы
        трейсбеком вместо именованного отказа сухого сбора."""
        self.assertEqual(guard.artifact_disk_read_errors_from_files(
            [("acceptance_tests/test_x.py", 'plan = TASK_DIR / "PLAN.md"\n'
                                            'def broken(:\n')]), [])


class ScanDirectoryTest(unittest.TestCase):
    """`scan_artifact_disk_reads`: область — все `*.py` каталога
    `acceptance_tests/`, метка — путь относительно каталога задачи."""

    def write(self, tdir: Path, rel: str, text: str) -> None:
        path = tdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_non_test_modules_are_in_scope_with_relative_labels(self):
        """AC-5: нарушение в `_helper.py` (не `test_*.py`) найдено, метка —
        `acceptance_tests/_helper.py`, чистый `test_ac.py` ошибок не даёт.

        Ловит мутацию: область сужена до `rglob("test_*.py")` копипастой
        из `scan_redness_markers` — `_helper.py` остался бы невидим."""
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            self.write(tdir, "acceptance_tests/test_ac.py",
                       source_with('data = TASK_DIR.name'))
            self.write(tdir, "acceptance_tests/_helper.py",
                       source_with('PLAN = TASK_DIR / "PLAN.md"'))
            errors = guard.scan_artifact_disk_reads(tdir)
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].startswith(
            f"acceptance_tests/_helper.py:{FIRST_SCENARIO_LINE}: "), errors[0])

    def test_missing_directory_yields_no_errors(self):
        """Каталога `acceptance_tests/` нет — пустой список, не исключение.

        Ловит мутацию: `is_dir()`-предохранитель снят — `rglob` по
        несуществующему каталогу поднимал бы ошибку на задаче без планки."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(guard.scan_artifact_disk_reads(Path(tmp)), [])


class NotWiredIntoCheckOrMainTest(unittest.TestCase):
    """Требование 4/AC-8: проверка не вызывается ни из `check()`, ни из
    `main()` — `--all` по дереву с исторической планкой, читающей
    артефакт с диска, остаётся зелёным."""

    TASK = "01FAKEDISKREADHISTORY1"

    def run_guard_all_in(self, tmp_root: Path) -> tuple:
        buf = io.StringIO()
        orig_cwd = Path.cwd()
        os.chdir(tmp_root)
        try:
            with mock.patch.object(sys, "argv", ["scripts/guard.py", "--all"]):
                with redirect_stdout(buf):
                    rc = guard.main()
        finally:
            os.chdir(orig_cwd)
        return rc, buf.getvalue()

    def test_all_mode_stays_green_and_never_calls_the_scan(self):
        """Ловит мутацию: `scan_artifact_disk_reads` добавлена в обход
        `--all` рядом с `scan_indented_ac_markers` — `rc` стал бы 1 на
        исторической планке, а спай зафиксировал бы вызов."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            task_dir = tmp_root / "tasks" / self.TASK
            (task_dir / "acceptance_tests").mkdir(parents=True)
            # TZ.md — единственный артефакт без обязательных секций:
            # валиден одним frontmatter, так что `--all`/`check()` идут
            # по своему обычному пути и зелены не «за отсутствием файлов».
            (task_dir / "TZ.md").write_text(
                "---\ntask: x\ntype: tz\nauthor_role: operator\n"
                "status: ready\n---\n# x\n", encoding="utf-8")
            (task_dir / "acceptance_tests" / "test_ac1_plan.py").write_text(
                source_with('plan = TASK_DIR / "PLAN.md"'), encoding="utf-8")
            with mock.patch.object(
                    guard, "scan_artifact_disk_reads",
                    wraps=guard.scan_artifact_disk_reads) as scan:
                rc, out = self.run_guard_all_in(tmp_root)
                check_errors = guard.check(task_dir / "TZ.md")
        self.assertEqual(rc, 0, out)
        self.assertEqual(check_errors, [])
        scan.assert_not_called()


if __name__ == "__main__":
    unittest.main()
