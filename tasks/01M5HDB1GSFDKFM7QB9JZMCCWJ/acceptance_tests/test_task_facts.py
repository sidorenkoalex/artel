"""Факты задачи: миграция стенда `readonly_db` строго в рамке мандата, матрица неослабления в PLAN, новый файл тестов задачи в `tests/`.

Группа: разовый
Красен до реализации: AC-8 — в `ROLES` стенда `readonly_db` ещё есть `developer`, а PLAN.md с матрицей неослабления не написан; AC-7 (файл прежних тестов `suite-run` не тронут) и AC-9 (новый файл `tests/` задачи написан автором тестов) зелены с рождения.

Дифф задачи и её пути — помощник пульта `_pult.py` (`changed_paths`,
`DIFF_BASE`, `CODE_ROOT`); PLAN.md — из ссылки документов
(`artifact_text`). Прежний текст файла `readonly_db` — `git show` базы
диффа задачи, текущий — рабочая копия кода.

Провалидировано временным стабом (удалён, не закоммичен): `ROLES` стенда
без `developer` — `test_ac8_readonly_db_…` зелёный. Матрицу PLAN стабом не
проверить: PLAN.md читается из ссылки документов, которую пишет только
автокоммит пульта по итогам шага разработчика.
"""
import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, artifact_text, changed_paths  # noqa: E402

READONLY = "tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py"
SUITE_RUN_TESTS = "tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py"
NEW_FILE = re.compile(r"^tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_[a-z0-9_]+\.py$")
METHODS = (
    ("ReadonlyDbOutcomeTest",
     "test_ac4_readonly_db_run_reaches_same_outcome_and_report"),
    ("JournalRedeliveryTest", "test_ac5_pult_process_delivers_journal_record"),
    ("SharedLockTest", "test_ac6_role_suite_run_and_gate_share_one_lock_file"),
    ("LimitUnchangedTest",
     "test_ac8_readonly_db_run_keeps_profile_limit_and_timeout_outcome"),
    ("LogPlacementTest", "test_ac9_suite_run_logs_live_under_suite_run_dir"),
)
ROLES_STMT = re.compile(r"^ROLES = \(.*?\)\n", re.MULTILINE | re.DOTALL)


def base_text(rel: str) -> str:
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "show",
                          f"{DIFF_BASE}:{rel}"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"git show {DIFF_BASE}:{rel}: {res.stderr}")
    return res.stdout


def assertion_kinds(tree: ast.Module, cls: str, method: str) -> list | None:
    """Имена утверждений `self.assert*` метода по порядку; `None` — метода
    в классе нет."""
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method:
                    return [call.func.attr for call in ast.walk(item)
                            if isinstance(call, ast.Call)
                            and isinstance(call.func, ast.Attribute)
                            and call.func.attr.startswith(("assert", "fail"))]
    return None


def roles_value(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "ROLES"
                for t in node.targets):
            return ast.literal_eval(node.value)
    return None


class MigrationTest(unittest.TestCase):

    def test_ac8_readonly_db_roles_without_developer_rest_unchanged(self):
        """В стенде `readonly_db` из `ROLES` убран developer, остальной файл и пять методов — прежние.

        Сценарий: текущий текст файла стенда сравнивается с текстом базы
        диффа задачи. `ROLES` — непустой перечень без `developer`; пять
        адресных методов есть в прежних классах с теми же по виду и числу
        утверждениями; после замены оператора `ROLES` заглушкой в обоих
        текстах они совпадают дословно — прочих изменений нет.

        Ловит мутацию: developer оставлен в `ROLES` или стенд выбирает роль
        иначе; вместе с `ROLES` ослаблен или переименован один из пяти
        методов (снято утверждение, метод перенесён в другой класс); в файл
        стенда внесена любая другая правка."""
        current = (Path(CODE_ROOT) / READONLY).read_text(encoding="utf-8")
        before = base_text(READONLY)
        tree, base_tree = ast.parse(current), ast.parse(before)
        roles = roles_value(tree)
        self.assertTrue(roles, f"ROLES нет или пуст: {roles!r}")
        self.assertNotIn("developer", roles, f"ROLES: {roles!r}")
        for cls, method in METHODS:
            with self.subTest(method=method):
                kinds = assertion_kinds(tree, cls, method)
                self.assertIsNotNone(kinds, f"{cls}::{method} нет")
                self.assertEqual(kinds, assertion_kinds(base_tree, cls, method),
                                 f"{cls}::{method}: утверждения изменены")
        stub = "ROLES = <перечень ролей стенда>\n"
        self.assertIsNotNone(ROLES_STMT.search(current), "оператор ROLES не найден")
        self.assertEqual(ROLES_STMT.sub(stub, current, count=1),
                         ROLES_STMT.sub(stub, before, count=1),
                         "в файле стенда изменено что-то кроме ROLES")

    def test_ac8_plan_carries_non_weakening_matrix_row_per_method(self):
        """PLAN.md несёт матрицу неослабления: строка таблицы на каждый из пяти методов.

        Сценарий: PLAN.md из ссылки документов задачи; в нём слово
        «неослабления» и для каждого из пяти методов `readonly_db` —
        строка таблицы Markdown (начинается с `|`), называющая метод и
        несущая не меньше трёх непустых ячеек (метод, свойство, чем оно
        держится после).

        Ловит мутацию: матрица пропустила один из пяти методов; матрица
        записана прозой без строк таблицы; строка метода без свойства и
        покрытия (одна ячейка)."""
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md в ссылке документов нет")
        self.assertRegex(plan, r"(?i)неослаблени", "матрицы неослабления нет")
        rows = [line for line in plan.splitlines()
                if line.lstrip().startswith("|")]
        for _cls, method in METHODS:
            with self.subTest(method=method):
                mine = [row for row in rows if method in row]
                self.assertTrue(mine, f"строки матрицы для {method} нет")
                self.assertTrue(any(
                    len([c for c in row.strip().strip("|").split("|")
                         if c.strip()]) >= 3 for row in mine),
                    f"строка {method} без свойства и покрытия: {mine}")


class MissionFileTest(unittest.TestCase):

    def test_ac7_suite_run_mission_test_file_untouched(self):
        """Файл с `MissionTest::test_ac25` задача не правит.

        Сценарий: пути задачи (`changed_paths` помощника пульта) не
        содержат файла прежних тестов `suite-run`, в котором живёт
        `MissionTest::test_ac25_developer_mission_names_suite_run_with_pult_path`
        — тест держится зелёным без правки.

        Ловит мутацию: новая миссия developer не прошла `test_ac25`, и его
        подогнали правкой файла — путь файла в диффе задачи."""
        self.assertNotIn(SUITE_RUN_TESTS, changed_paths())


class NewTestsFileTest(unittest.TestCase):

    def test_ac9_new_tests_file_covers_ac1_to_ac7_without_waits(self):
        """Новые тесты задачи — отдельный файл `tests/`: AC-1…AC-7, без сна и ожиданий, зёрна, заявки мутаций.

        Сценарий: среди путей задачи — файл
        `tests/test_<id задачи>_<имя>.py`. Его тестовые методы покрывают
        `test_ac1_`…`test_ac7_`; у каждого метода `test_*` в докстринге —
        «Ловит мутацию:»; вызовов `sleep`, `.wait(`/`.communicate(` в нём
        нет; зерно печатается (`print(f"зерно`); запуск фонового процесса
        (`Popen`) и прогон набора (`run_full_suite`) подменены; заявки
        мутаций называют отказ после `deliver_journal` и после замка, отказ
        любой роли, `--failed`/`--wait`, уже идущий прогон и непроверенный
        маркер.

        Ловит мутацию: тесты задачи дописаны в чужой файл `tests/`; один
        из AC-1…AC-7 не покрыт; метод без заявки мутации; тест ждёт
        фоновый процесс или спит; зерно не печатается."""
        files = [p for p in changed_paths() if NEW_FILE.match(p)]
        self.assertTrue(files, f"нового файла tests/ задачи нет: "
                               f"{sorted(changed_paths())}")
        methods, claims, text = {}, [], ""
        for rel in files:
            source = (Path(CODE_ROOT) / rel).read_text(encoding="utf-8")
            text += source
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and \
                        node.name.startswith("test_"):
                    doc = ast.get_docstring(node) or ""
                    methods[f"{rel}::{node.name}"] = doc
                    claims.append(doc.partition("Ловит мутацию:")[2])
                if isinstance(node, ast.Call):
                    func = node.func
                    name = (func.attr if isinstance(func, ast.Attribute)
                            else func.id if isinstance(func, ast.Name) else "")
                    with self.subTest(call=name, line=node.lineno):
                        self.assertNotIn(name, ("sleep", "wait", "communicate"),
                                         f"{rel}:{node.lineno}")
        names = [key.split("::")[1] for key in methods]
        for n in range(1, 8):
            with self.subTest(ac=n):
                self.assertTrue(any(name.startswith(f"test_ac{n}_")
                                    for name in names), names)
        for key, doc in methods.items():
            with self.subTest(method=key):
                self.assertIn("Ловит мутацию:", doc)
        self.assertIn('print(f"зерно', text)
        for part in ("Popen", "run_full_suite"):
            self.assertIn(part, text)
        joined = " ".join(claims)
        for part in ("deliver_journal", "замк", "любой роли", "--failed",
                     "--wait", "уже идёт", "маркер"):
            with self.subTest(claim=part):
                self.assertIn(part, joined)


if __name__ == "__main__":
    unittest.main()
