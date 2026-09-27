"""Тонкая надстройка сценария поверх `tests.sandbox.RealGitSandbox` —
общая для всех файлов планки 01M3FQ2V77QNK95Z599DM124QN.

Настоящий git, не `fake_git`: предмет гейта — РАСПОЗНАВАНИЕ удаления,
переименования и ослабления тестов в диффе ветки против базы
(`gitcmd.diff_base`, `git diff -M --name-status`). Переименование по
требованию 3 SPEC определяет сам git, а не эвристика пульта — заглушкой
такое не изобразить, и планка, замокавшая `diff_names`/новый примитив
чтения, проверяла бы собственную выдумку вместо ответа git.

Здесь только сценарная надстройка (базовое дерево `tests/`, правка ветки,
вызов обёртки гейта, чтение журнала) — ни `disk_backed_*`, ни
`advance_from_in_dev`, ни собственный поддельный git не переопределяются:
их источник — `tests/sandbox.py` (`skills/test-authoring.md`, «Лёгкая
песочница переходов — не копия, импорт»).
"""
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (catalog, config, fsm_advance,  # noqa: E402
                          fsm_merge_gate, store)
from tests.sandbox import RealGitSandbox, capture  # noqa: E402

# Задача песочницы — не эта задача пульта: строка в БД временного каталога
# заводится напрямую `store.insert_task`, id нужен только уникальный
# ULID-образный.
TASK = "01M3FQTESTINTEGRITYGATE001"

# Посторонняя задача, чья планка приёмки лежит в базовом дереве — предмет
# второй половины AC-5 («tasks/*/acceptance_tests/** этим гейтом не
# рассматривается»).
OTHER_TASK = "01M0OTHERTASK0000000000001"

# Именованное действие отказа нового гейта (SPEC, требование 6, AC-1).
REFUSAL_ACTION = "переход отклонён: гейт неослабления тестов"

# Маркер мандата Оператора (SPEC, требование 4, AC-7).
MANDATE_MARKER = "Ослабление тестов разрешено:"

# Префикс сообщения автокоммита артефактов шага роли
# (`advance_gates/zones.py::_STEP_ARTIFACTS_COMMIT_PREFIX`) — им
# подписывается ANSWER-n.md сценария AC-9.
ROLE_STEP_AUTOCOMMIT_SUBJECT = "{task}: артефакты шага {role} (автокоммит оркестратора)"

# Сообщение коммита команды `answer` (`orchestrator/answer.py`) — подпись
# настоящего мандата Оператора (AC-7).
ANSWER_COMMIT_SUBJECT = "{task}: ANSWER-{n} — ответ Оператора"


ALPHA = '''"""Фикстура базового дерева: обычный файл тестов верхнего уровня."""
import unittest


class AlphaTest(unittest.TestCase):

    def test_alpha_one(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(True)

    def test_alpha_two(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(1, 1)
'''

# Тот же файл без `test_alpha_two` — метод, бывший в base, исчез из head
# (класс находки «в» требования 1, AC-3).
ALPHA_WITHOUT_SECOND_METHOD = '''"""Фикстура базового дерева: обычный файл тестов верхнего уровня."""
import unittest


class AlphaTest(unittest.TestCase):

    def test_alpha_one(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(True)
'''

# Тот же файл, но на `test_alpha_one` появился `@unittest.skip` (класс
# находки «г» требования 1, AC-4).
ALPHA_WITH_SKIP_DECORATOR = '''"""Фикстура базового дерева: обычный файл тестов верхнего уровня."""
import unittest


class AlphaTest(unittest.TestCase):

    @unittest.skip("временно, пока чиню окружение")
    def test_alpha_one(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(True)

    def test_alpha_two(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(1, 1)
'''

DOOMED = '''"""Фикстура базового дерева: файл, который сценарии удаляют целиком."""
import unittest


class DoomedTest(unittest.TestCase):

    def test_doomed_one(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(True)

    def test_doomed_two(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(2, 2)
'''

MOVABLE = '''"""Фикстура базового дерева: файл, который сценарии переименовывают."""
import unittest


class MovableTest(unittest.TestCase):

    def test_movable_one(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(1, 1)

    def test_movable_two(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(2, 2)

    def test_movable_three(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(3, 3)

    def test_movable_four(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(4, 4)

    def test_movable_five(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(5, 5)
'''

# Тот же файл без `test_movable_three` — содержимое остаётся похожим на
# base больше чем наполовину, поэтому `git diff -M` по-прежнему признаёт
# переименование, а эвристика «совпадающий набор имён тестовых методов»
# — уже нет (обоснование выбора примитива, требование 3).
MOVABLE_WITHOUT_THIRD_METHOD = MOVABLE.replace(
    '''    def test_movable_three(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(3, 3)

''', "")

NESTED = '''"""Фикстура базового дерева: тесты в ПОДКАТАЛОГЕ tests/ (AC-5)."""
import unittest


class NestedTest(unittest.TestCase):

    def test_nested_one(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(True)

    def test_nested_two(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertFalse(False)
'''

# Тот же файл, но в теле `test_nested_one` появился вызов `self.skipTest(`
# (вторая половина класса находки «г», AC-4).
NESTED_WITH_SKIPTEST_CALL = '''"""Фикстура базового дерева: тесты в ПОДКАТАЛОГЕ tests/ (AC-5)."""
import unittest


class NestedTest(unittest.TestCase):

    def test_nested_one(self):
        """Ловит мутацию: фикстура песочницы."""
        self.skipTest("окружение не готово")
        self.assertTrue(True)

    def test_nested_two(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertFalse(False)
'''

HELPERS_WITHOUT_TESTS = '''"""Фикстура базового дерева: файл под tests/ БЕЗ тестовых методов —
помощник сценариев, предмет AC-6."""


def build_payload(size: int) -> list:
    return list(range(size))


def merge_payloads(left: list, right: list) -> list:
    return sorted(left + right)
'''

ALREADY_SKIPPED = '''"""Фикстура базового дерева: пропуск, УЖЕ стоявший в base (AC-4,
вторая фраза: тот же декоратор в base отказа не даёт)."""
import unittest


class AlreadySkippedTest(unittest.TestCase):

    @unittest.skip("давняя причина, зафиксированная Оператором")
    def test_skipped_from_base(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(True)

    def test_live_from_base(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(True)
'''

# Тот же файл с ДОБАВЛЕННЫМ методом (файл попадает в дифф), но пропуск
# `test_skipped_from_base` — прежний, из base.
ALREADY_SKIPPED_PLUS_NEW_METHOD = ALREADY_SKIPPED + '''
    def test_added_on_branch(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(7, 7)
'''

MOVABLE_WITH_XFAIL_ON_CLASS = '''"""Фикстура базового дерева: файл, который сценарии переименовывают."""
import unittest

import pytest


@pytest.mark.xfail(reason="пока не чиним")
class MovableTest(unittest.TestCase):
''' + MOVABLE.split("class MovableTest(unittest.TestCase):\n", 1)[1]

FOREIGN_PLANK = '''"""Фикстура: планка приёмки ПОСТОРОННЕЙ задачи (AC-5, вторая половина)."""
import unittest


class ForeignPlankTest(unittest.TestCase):

    def test_ac1_foreign_plank_method(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(True)
'''

BASE_FILES = {
    "tests/test_alpha.py": ALPHA,
    "tests/test_doomed.py": DOOMED,
    "tests/test_movable.py": MOVABLE,
    "tests/test_already_skipped.py": ALREADY_SKIPPED,
    "tests/deep/test_nested.py": NESTED,
    "tests/helpers_without_tests.py": HELPERS_WITHOUT_TESTS,
    f"tasks/{OTHER_TASK}/acceptance_tests/test_plank.py": FOREIGN_PLANK,
}


class GateOutcome(NamedTuple):
    """Наблюдаемый исход одного прогона гейта: `refused` — ответ обёртки,
    `printed` — stdout `_run_gates` (там живёт `hint`), `steps` — пары
    (действие, деталь) журнала задачи."""

    refused: bool
    printed: str
    steps: list

    @property
    def actions(self) -> list:
        return [action for action, _ in self.steps]

    @property
    def detail(self) -> str:
        """Деталь ИМЕННО отказа нового гейта; пустая строка — записи с
        таким действием в журнале нет (утверждения о содержимом detail
        тогда честно краснеют, а не падают `TypeError` на `None`)."""
        for action, detail in self.steps:
            if action == REFUSAL_ACTION:
                return detail
        return ""

    @property
    def journal(self) -> str:
        """Весь журнал задачи одной строкой — для утверждений «запись где-то
        в журнале есть» (AC-8)."""
        return "\n".join(f"{action}: {detail}" for action, detail in self.steps)


class TestIntegritySandbox(RealGitSandbox):
    """Репозиторий с базовым деревом `tests/` на `main` и пустой веткой
    задачи поверх него; сценарий каждого теста — правка ветки + `commit`.

    Артефактная и кодовая ветка здесь ОДНА И ТА ЖЕ (`self.branch`): так
    сценарий не зависит от того, какой из двух аргументов соседних гейтов
    (`branch` артефактов или `t["branch"]` кода) реализация возьмёт для
    диффа и для чтения ANSWER-n.md.
    """

    TASK = TASK

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        for rel, text in BASE_FILES.items():
            self.write(rel, text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "базовое дерево тестов")
        self.base_sha = self.git("rev-parse", "HEAD").strip()

        self.branch = f"task/{TASK.lower()}-x"
        self.git("checkout", "-q", "-b", self.branch)
        store.insert_task(self.conn, TASK, "Гейт неослабления тестов",
                          "in_dev", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    # ---- правка рабочего дерева ветки ----

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def remove(self, rel: str) -> None:
        self.git("rm", "-q", rel)

    def move(self, src: str, dst: str) -> None:
        (self.root / dst).parent.mkdir(parents=True, exist_ok=True)
        self.git("mv", src, dst)

    def commit(self, message: str = None) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message or f"{TASK}: правка ветки")

    # ---- мандат Оператора ----

    def write_answer(self, n: int, allowed: str, *, autocommit_role: str = None,
                     basis: str = "ADR-0002, решение Оператора") -> None:
        """`tasks/<TASK>/ANSWER-n.md` со строкой мандата и ссылкой на
        основание ОТДЕЛЬНОЙ строкой (перечень разбирается по запятой —
        свободный текст на той же строке стал бы её элементом).

        `autocommit_role` — подписать коммит как автокоммит артефактов шага
        этой роли (AC-9); по умолчанию подпись команды `answer` (AC-7).
        """
        body = (f"# Ответ Оператора {n}\n\n"
                f"{MANDATE_MARKER} {allowed}\n"
                f"Основание: {basis}.\n")
        self.write(f"tasks/{TASK}/ANSWER-{n}.md", body)
        if autocommit_role:
            subject = ROLE_STEP_AUTOCOMMIT_SUBJECT.format(task=TASK,
                                                          role=autocommit_role)
        else:
            subject = ANSWER_COMMIT_SUBJECT.format(task=TASK, n=n)
        self.commit(subject)

    # ---- прогон гейта ----

    def run_gate(self) -> GateOutcome:
        """Обёртка гейта `fsm_advance._test_integrity_gate_refuses`
        (требование 6) — та же форма вызова, что у соседей по `in_dev`
        (`_review_rework_gate_refuses(conn, task_id, t, branch)`)."""
        t = store.get_task(self.conn, TASK)
        box: list = []
        printed = capture(
            lambda: box.append(fsm_advance._test_integrity_gate_refuses(
                self.conn, TASK, t, self.branch)))
        return GateOutcome(box[0], printed, self.steps())

    def steps(self) -> list:
        return [(row["action"], row["detail"]) for row in self.conn.execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (TASK,))]

    def set_task_fields(self, **fields) -> None:
        assignments = ", ".join(f"{name}=?" for name in fields)
        self.conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                          (*fields.values(), TASK))
        self.conn.commit()


class MergeOutcome(NamedTuple):
    """Наблюдаемый исход одного захода в тело гейта мержа."""

    result: tuple
    printed: str
    state: str
    steps: list

    @property
    def actions(self) -> list:
        return [action for action, _ in self.steps]

    @property
    def journal(self) -> str:
        return "\n".join(f"{action}: {detail}" for action, detail in self.steps)


class MergeGateSandbox(TestIntegritySandbox):
    """`TestIntegritySandbox` + инициализированный пульт и bare `origin`,
    синхронный с main, — минимум, без которого `_cmd_approve_merge_gate`
    отказывает раньше своего предмета (тот же приём, что у
    `tasks/01M27JPEGCGMDDRX5A98QWJW0Z/acceptance_tests/
    test_ac5_merge_gate_protected_path_diff.py`)."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        self.pult_origin = self.add_synced_origin()

    def approve(self, *, confirmed_ci_note: str = "зелёный (тест)") -> MergeOutcome:
        """Один заход в тело гейта мержа из состояния `merge_gate` —
        HEAD переводится на main, как в реальном маршруте `approve`."""
        self.git("checkout", "-q", config.MAIN_BRANCH)
        self.set_task_fields(state="merge_gate")
        t = store.get_task(self.conn, TASK)
        box: list = []
        printed = capture(
            lambda: box.append(fsm_merge_gate._cmd_approve_merge_gate(
                self.conn, TASK, "merge_gate", t,
                confirmed_ci_note=confirmed_ci_note)))
        state = self.conn.execute("SELECT state FROM tasks WHERE id=?",
                                  (TASK,)).fetchone()["state"]
        return MergeOutcome(box[0], printed, state, self.steps())


def pytest_run(*rel_paths: str) -> subprocess.CompletedProcess:
    """Прогон именованных файлов `tests/` рабочей копии кода отдельным
    процессом — тем же интерпретатором, что исполняет саму планку."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         *rel_paths],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=300)
