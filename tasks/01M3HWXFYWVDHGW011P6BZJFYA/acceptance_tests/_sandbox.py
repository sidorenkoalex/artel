"""Тонкая надстройка сценария поверх `tests.sandbox.RealGitSandbox` —
общая для всех файлов планки 01M3HWXFYWVDHGW011P6BZJFYA.

Настоящий git, не `fake_git`: предмет узла — сравнение `tests/` ВЕТКИ с
БАЗОЙ (`gitcmd.diff_base`, `git diff -M --name-status`), и вся разница
между «новым» и «существующим» именем метода берётся из ответа git о
двух деревьях. Тот же довод, что у планки 01M3FQ2V77QNK95Z599DM124QN,
заводившей этот узел.

Здесь только сценарная надстройка (базовое дерево `tests/`, фикстуры
файлов, правка ветки, вызов обёрток обоих рубежей, чтение журнала) — ни
`disk_backed_*`, ни `advance_from_in_dev`, ни собственный поддельный git
не переопределяются: их источник — `tests/sandbox.py`
(`skills/test-authoring.md`, «Лёгкая песочница переходов — не копия,
импорт»).
"""
import sys
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

from orchestrator import (config, fsm_advance, fsm_merge_gate,  # noqa: E402
                          repo_context, store)
from tests.sandbox import RealGitSandbox, capture  # noqa: E402

# Задача песочницы — не эта задача пульта: строка в БД временного каталога
# заводится напрямую `store.insert_task`, id нужен только уникальный
# ULID-образный.
TASK = "01M3HWCONDITIONALSKIP00001"

# Именованное действие отказа гейта — прежнее (SPEC, AC-3: «отказывает
# ПРЕЖНИМ именованным действием»), берётся из самого узла, а не копией
# строкой: задача его не меняет, и планка обязана краснеть, если поменяли.
REFUSAL_ACTION = "переход отклонён: гейт неослабления тестов"

# Именованное действие журнальной записи требования 7 / AC-2.
CONDITIONAL_SKIP_ACTION = "новый тест с условным пропуском"

# Разделитель между путём файла и квалифицированным именем метода в
# записи журнала (AC-2: «<файл>::<квалифицированное имя метода> —
# <причина>»). Внутри самого квалифицированного имени разделитель берётся
# из `guard.TEST_NAME_SEP` — единственного адреса этого правила в пульте.
FILE_NAME_SEP = "::"


def qualified(cls: str, method: str) -> str:
    return f"{cls}{guard.TEST_NAME_SEP}{method}"


def journal_item(path: str, cls: str, method: str, reason: str) -> str:
    """Ожидаемый элемент detail журнальной записи AC-2."""
    return f"{path}{FILE_NAME_SEP}{qualified(cls, method)} — {reason}"


# ------------------------------------------------------ базовое дерево

EXISTING_PATH = "tests/test_existing.py"
EXISTING_CLASS = "ExistingTest"

EXISTING = '''"""Фикстура базового дерева: обычный файл тестов, оба метода которого
существуют в базе сравнения."""
import unittest


class ExistingTest(unittest.TestCase):

    def test_existing_one(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(True)

    def test_existing_two(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(1, 1)
'''

# Тот же файл: на СУЩЕСТВУЮЩЕМ методе `test_existing_one` появился
# условный пропуск с названной причиной (AC-5, первая половина).
EXISTING_WITH_CONDITIONAL_SKIP_ON_METHOD = '''"""Фикстура базового дерева: обычный файл тестов, оба метода которого
существуют в базе сравнения."""
import os
import unittest

HAS_ZSH = os.path.exists("/bin/zsh")


class ExistingTest(unittest.TestCase):

    @unittest.skipUnless(HAS_ZSH, "оболочка /bin/zsh не установлена")
    def test_existing_one(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(True)

    def test_existing_two(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(1, 1)
'''

# Тот же файл: условный пропуск с названной причиной появился над КЛАССОМ,
# который есть в базе сравнения (AC-5, вторая половина).
EXISTING_WITH_CONDITIONAL_SKIP_ON_CLASS = '''"""Фикстура базового дерева: обычный файл тестов, оба метода которого
существуют в базе сравнения."""
import os
import unittest

import pytest

HAS_ZSH = os.path.exists("/bin/zsh")


@pytest.mark.skipif(not HAS_ZSH, reason="без /bin/zsh класс проверять нечем")
class ExistingTest(unittest.TestCase):

    def test_existing_one(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(True)

    def test_existing_two(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(1, 1)
'''

EARLY_RETURN_BASE_PATH = "tests/test_early_return_base.py"
EARLY_RETURN_BASE_CLASS = "EarlyReturnFromBaseTest"

EARLY_RETURN_IN_BASE = '''"""Фикстура базового дерева: ранний return под условием, УЖЕ стоявший в
базе сравнения (AC-6, вторая фраза)."""
import os
import unittest

HAS_ZSH = os.path.exists("/bin/zsh")


class EarlyReturnFromBaseTest(unittest.TestCase):

    def test_early_return_from_base(self):
        """Ловит мутацию: фикстура песочницы."""
        if not HAS_ZSH:
            return
        self.assertTrue(HAS_ZSH)
'''

# Тот же файл с ДОБАВЛЕННЫМ обычным методом: файл попадает в дифф, но
# ранний return на прежнем имени — тот же, что в базе.
EARLY_RETURN_IN_BASE_PLUS_NEW_METHOD = EARLY_RETURN_IN_BASE + '''
    def test_added_on_branch(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertEqual(7, 7)
'''

BASE_FILES = {
    EXISTING_PATH: EXISTING,
    EARLY_RETURN_BASE_PATH: EARLY_RETURN_IN_BASE,
}

# ------------------------------------------- новые файлы ветки задачи

NEW_CONDITIONAL_PATH = "tests/test_new_conditional.py"
NEW_CONDITIONAL_CLASS = "ConditionalSkipTest"

# Три формы, названные AC-1 поимённо: вызов пропуска внутри `if`,
# `@skipUnless(<условие>, "<причина>")`, `@pytest.mark.skipif(<условие>,
# reason="<причина>")`.
CONDITIONAL_SKIPS = (
    ("test_skiptest_call_inside_if", "на машине нет /bin/zsh"),
    ("test_skip_unless_decorator", "оболочка /bin/zsh не установлена"),
    ("test_pytest_skipif_reason_kwarg", "без /bin/zsh проверять нечего"),
)

NEW_CONDITIONAL = '''"""Фикстура: НОВЫЙ файл тестов, три формы условного пропуска с
непустой строковой причиной (AC-1)."""
import os
import unittest

import pytest

HAS_ZSH = os.path.exists("/bin/zsh")


class ConditionalSkipTest(unittest.TestCase):

    def test_skiptest_call_inside_if(self):
        """Ловит мутацию: фикстура песочницы."""
        if not HAS_ZSH:
            self.skipTest("на машине нет /bin/zsh")
        self.assertTrue(HAS_ZSH)

    @unittest.skipUnless(HAS_ZSH, "оболочка /bin/zsh не установлена")
    def test_skip_unless_decorator(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(HAS_ZSH)

    @pytest.mark.skipif(not HAS_ZSH, reason="без /bin/zsh проверять нечего")
    def test_pytest_skipif_reason_kwarg(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(HAS_ZSH)
'''

NO_REASON_PATH = "tests/test_new_without_reason.py"
NO_REASON_CLASS = "SkipWithoutReasonTest"
NO_REASON_METHOD = "test_pytest_skip_without_reason"

NO_REASON = '''"""Фикстура: НОВЫЙ файл — условный пропуск БЕЗ аргумента причины (AC-3)."""
import os
import unittest

import pytest

HAS_ZSH = os.path.exists("/bin/zsh")


class SkipWithoutReasonTest(unittest.TestCase):

    def test_pytest_skip_without_reason(self):
        """Ловит мутацию: фикстура песочницы."""
        if not HAS_ZSH:
            pytest.skip()
        self.assertTrue(HAS_ZSH)
'''

BLANK_REASON_PATH = "tests/test_new_blank_reason.py"
BLANK_REASON_CLASS = "BlankReasonTest"
BLANK_REASON_METHODS = ("test_skiptest_with_empty_reason",
                        "test_skiptest_with_spaces_reason")

BLANK_REASON = '''"""Фикстура: НОВЫЙ файл — условный пропуск с ПУСТОЙ и с пробельной
причиной (AC-3)."""
import os
import unittest

HAS_ZSH = os.path.exists("/bin/zsh")


class BlankReasonTest(unittest.TestCase):

    def test_skiptest_with_empty_reason(self):
        """Ловит мутацию: фикстура песочницы."""
        if not HAS_ZSH:
            self.skipTest("")
        self.assertTrue(HAS_ZSH)

    def test_skiptest_with_spaces_reason(self):
        """Ловит мутацию: фикстура песочницы."""
        if not HAS_ZSH:
            self.skipTest("   ")
        self.assertTrue(HAS_ZSH)
'''

COMPUTED_REASON_PATH = "tests/test_new_computed_reason.py"
COMPUTED_REASON_CLASS = "ComputedReasonTest"
COMPUTED_REASON_METHODS = ("test_skip_unless_reason_is_a_variable",
                           "test_skiptest_reason_is_an_fstring")

COMPUTED_REASON = '''"""Фикстура: НОВЫЙ файл — причина пропуска ВЫЧИСЛЯЕМАЯ: переменная и
f-строка (AC-3)."""
import os
import unittest

SHELL = "/bin/zsh"
HAS_ZSH = os.path.exists(SHELL)
WHY = "оболочка не установлена"


class ComputedReasonTest(unittest.TestCase):

    @unittest.skipUnless(HAS_ZSH, WHY)
    def test_skip_unless_reason_is_a_variable(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(HAS_ZSH)

    def test_skiptest_reason_is_an_fstring(self):
        """Ловит мутацию: фикстура песочницы."""
        if not HAS_ZSH:
            self.skipTest(f"на машине нет {SHELL}")
        self.assertTrue(HAS_ZSH)
'''

UNCONDITIONAL_PATH = "tests/test_new_unconditional.py"
UNCONDITIONAL_CLASS = "UnconditionalMarkerTest"
# Четыре формы, названные AC-4 поимённо.
UNCONDITIONAL_METHODS = ("test_plain_skip_decorator",
                         "test_expected_failure_decorator",
                         "test_pytest_xfail_decorator",
                         "test_skiptest_call_outside_any_if")

UNCONDITIONAL = '''"""Фикстура: НОВЫЙ файл — БЕЗУСЛОВНЫЕ маркеры, причина у каждого из них
названа (AC-4)."""
import unittest

import pytest


class UnconditionalMarkerTest(unittest.TestCase):

    @unittest.skip("окружение не готово, чиню отдельной задачей")
    def test_plain_skip_decorator(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(True)

    @unittest.expectedFailure
    def test_expected_failure_decorator(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(False)

    @pytest.mark.xfail(reason="известный дефект, чиню отдельной задачей")
    def test_pytest_xfail_decorator(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(False)

    def test_skiptest_call_outside_any_if(self):
        """Ловит мутацию: фикстура песочницы."""
        self.skipTest("окружение не готово, чиню отдельной задачей")
        self.assertTrue(True)
'''

NEW_CLASS_SKIP_PATH = "tests/test_new_class_skip.py"
NEW_CLASS_SKIP_CLASS = "NewConditionallySkippedTest"

NEW_CLASS_SKIP = '''"""Фикстура: НОВЫЙ файл — условный пропуск с названной причиной над
КЛАССОМ (AC-5, вторая половина)."""
import os
import unittest

import pytest

HAS_ZSH = os.path.exists("/bin/zsh")


@pytest.mark.skipif(not HAS_ZSH, reason="без /bin/zsh класс проверять нечем")
class NewConditionallySkippedTest(unittest.TestCase):

    def test_new_method_under_skipped_class(self):
        """Ловит мутацию: фикстура песочницы."""
        self.assertTrue(HAS_ZSH)
'''

EARLY_RETURN_PATH = "tests/test_new_early_return.py"
EARLY_RETURN_CLASS = "EarlyReturnTest"
EARLY_RETURN_METHOD = "test_early_return_under_condition"

EARLY_RETURN = '''"""Фикстура: НОВЫЙ файл — ранний return под условием первым
исполняемым оператором тела (AC-6)."""
import os
import unittest

HAS_ZSH = os.path.exists("/bin/zsh")


class EarlyReturnTest(unittest.TestCase):

    def test_early_return_under_condition(self):
        """Ловит мутацию: фикстура песочницы."""
        if not HAS_ZSH:
            return
        self.assertTrue(HAS_ZSH)
'''


# ----------------------------------------------------- сама песочница

class GateOutcome(NamedTuple):
    """Наблюдаемый исход одного прогона рубежа `in_dev -> verifying`:
    `refused` — ответ обёртки, `printed` — stdout `_run_gates` (там живёт
    `hint`), `steps` — пары (действие, деталь) журнала задачи."""

    refused: bool
    printed: str
    steps: list

    @property
    def actions(self) -> list:
        return [action for action, _ in self.steps]

    def detail_of(self, action: str) -> str:
        """Деталь записи с названным действием; пустая строка — такой
        записи в журнале нет (утверждения о содержимом тогда честно
        краснеют, а не падают `TypeError` на `None`)."""
        for name, detail in self.steps:
            if name == action:
                return detail or ""
        return ""

    @property
    def detail(self) -> str:
        return self.detail_of(REFUSAL_ACTION)

    @property
    def journal(self) -> str:
        return "\n".join(f"{action}: {detail}" for action, detail in self.steps)


class MergeOutcome(NamedTuple):
    """Наблюдаемый исход одного захода в гейт мержа на том же узле."""

    escalated: bool
    printed: str
    state: str
    steps: list

    @property
    def actions(self) -> list:
        return [action for action, _ in self.steps]

    @property
    def journal(self) -> str:
        return "\n".join(f"{action}: {detail}" for action, detail in self.steps)


class GateSandbox(RealGitSandbox):
    """Репозиторий с базовым деревом `tests/` на main и веткой задачи
    поверх него; сценарий каждого теста — правка ветки + `commit`.

    Артефактная и кодовая ветка здесь одна и та же (`self.branch`): так
    сценарий не зависит от того, какой из двух аргументов гейта
    реализация возьмёт для диффа. Мандата Оператора ни в одном сценарии
    планки нет — предмет задачи в том, что мандат перестаёт требоваться
    (AC-1) либо требуется по-прежнему (AC-3..AC-6).
    """

    TASK = TASK

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        for rel, text in BASE_FILES.items():
            self.write(rel, text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "базовое дерево тестов")

        self.branch = f"task/{TASK.lower()}-x"
        self.git("checkout", "-q", "-b", self.branch)
        store.insert_task(self.conn, TASK, "Условный пропуск в новом тесте",
                          "in_dev", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    # ---- правка рабочего дерева ветки ----

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message: str = None) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message or f"{TASK}: правка ветки")

    def apply(self, rel: str, text: str) -> None:
        """Единственная правка ветки сценария: записать файл и закоммитить."""
        self.write(rel, text)
        self.commit()

    def set_task_fields(self, **fields) -> None:
        assignments = ", ".join(f"{name}=?" for name in fields)
        self.conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                          (*fields.values(), TASK))
        self.conn.commit()

    def steps(self) -> list:
        return [(row["action"], row["detail"]) for row in self.conn.execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (TASK,))]

    # ---- рубеж 1: переход in_dev -> verifying ----

    def run_gate(self) -> GateOutcome:
        """Обёртка гейта `fsm_advance._test_integrity_gate_refuses` — та
        же форма вызова, что у соседей по `in_dev`."""
        t = store.get_task(self.conn, TASK)
        box: list = []
        printed = capture(
            lambda: box.append(fsm_advance._test_integrity_gate_refuses(
                self.conn, TASK, t, self.branch)))
        return GateOutcome(box[0], printed, self.steps())

    # ---- рубеж 2: гейт мержа ----

    def run_merge_gate(self) -> MergeOutcome:
        """Тело рубежа неослабления тестов ВНУТРИ гейта мержа
        (`fsm_merge_gate._test_integrity_diff_gate`) — ровно тот же вызов,
        который делает `_cmd_approve_merge_gate` между гейтом защищённых
        путей и публикацией головы.

        Зовётся именно он, а не весь `_cmd_approve_merge_gate`: за этим
        рубежом в теле гейта идут публикация головы, свежесть main, CI и
        плотницкий merge — шаги, ничего не добавляющие к предмету AC-7 и
        уводящие сценарий в сеть и в чужие отказы.
        """
        self.set_task_fields(state="merge_gate")
        ctx = repo_context.resolve(store.task_target(self.conn, TASK))
        box: list = []
        printed = capture(
            lambda: box.append(fsm_merge_gate._test_integrity_diff_gate(
                self.conn, TASK, "merge_gate", self.branch, ctx)))
        state = self.conn.execute("SELECT state FROM tasks WHERE id=?",
                                  (TASK,)).fetchone()["state"]
        return MergeOutcome(box[0], printed, state, self.steps())
