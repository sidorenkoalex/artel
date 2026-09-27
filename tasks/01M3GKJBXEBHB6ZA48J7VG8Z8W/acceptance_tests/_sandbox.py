"""Общие помощники планки 01M3GKJBXEBHB6ZA48J7VG8Z8W (проверка строки
мандата при записи `answer` и подсказка `approve` после ответа).

Три предмета, нужные больше чем одному файлу планки:

1. **Песочница команды** (`AnswerMandateSandbox`) — настоящий git-корень
   пульта (`tests.sandbox.RealGitSandbox`), заведённая задача, артефактная
   ветка пульта и НАСТОЯЩАЯ кодовая ветка задачи с известным деревом
   (`CODE_BRANCH_TREE`). Дерево положено ТОЛЬКО в кодовую ветку, а не в
   main: критерий AC-3 говорит «в дереве кодовой ветки задачи», и проверка,
   подсматривающая вместо неё main, обязана краснеть.
2. **Строки мандатов** (`zones_mandate_line`, `weakening_mandate_line`,
   `answer_text`) — собираются из ЖИВЫХ констант маркеров
   (`zones._ZONES_MANDATE_MARKER`, `test_integrity.TEST_WEAKENING_MANDATE_
   MARKER`, оба названы «Материалами» SPEC), а не литералами: маркер —
   крутилка пульта, планка не должна ломаться от его правки.
3. **Наблюдаемые разбора** (`zones_mandate_elements`,
   `weakening_mandate_elements`, `journal_mandate_paths`) — элементы, которые
   на одной и той же строке получают три потребителя разбора (AC-1).

Артефакты задачи (SPEC.md/PLAN.md/REVIEW.md) планка с диска не читает
вовсе: её предмет — команда `answer`, два гейта, документация и журнал
пульта. Единственный файл, читаемый с диска рабочей копии, —
`docs/operator-gates.md` (AC-8), и это не артефакт задачи.

Лёгкую песочницу переходов FSM этот файл не переопределяет и не копирует:
песочница настоящего git импортируется из `tests/sandbox.py`.

Имя файла с ведущим подчёркиванием — единственная форма общего кода
планки, которую checkpoint не отбрасывает (skills/test-authoring.md).
"""
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (answer, artifact_branch, catalog,  # noqa: E402
                          config, gitcmd, store)
from orchestrator.advance_gates import test_integrity, zones  # noqa: E402
from tests.sandbox import (RealGitSandbox, capture,  # noqa: E402
                           capture_new_task_id)

TASK_ID = "01M3GKJBXEBHB6ZA48J7VG8Z8W"

#: Маркеры мандатов — из кода, не литералами (см. докстринг модуля).
ZONES_MARKER = zones._ZONES_MANDATE_MARKER
WEAKENING_MARKER = test_integrity.TEST_WEAKENING_MANDATE_MARKER

# --- дерево кодовой ветки задачи ----------------------------------------

#: Файл, существующий в дереве кодовой ветки (AC-3, положительный случай).
EXISTING_FILE = "orchestrator/answer.py"

#: Каталог, существующий в том же дереве (AC-3): в дереве git каталога как
#: объекта записи нет — он существует ровно тем, что под ним лежат файлы.
EXISTING_DIR = "orchestrator"

#: Путь, которого в дереве кодовой ветки нет ни файлом, ни каталогом (AC-3,
#: отказ).
MISSING_PATH = "orchestrator/net_takogo_modulya.py"

#: Файлы `tests/` дерева — элементы мандата ослабления (AC-4) и общая пара
#: элементов для сверки трёх потребителей (AC-1): годятся обоим маркерам
#: (существуют в дереве и лежат под `tests/`).
TESTS_FILE = "tests/test_alpha.py"
OTHER_TESTS_FILE = "tests/test_beta.py"

#: Элемент мандата ослабления формы `путь::имя` (AC-4, положительный
#: случай) — класс и метод в дереве реально есть, чтобы отказ не мог
#: прийти по какой-либо иной причине, кроме формы.
TESTS_METHOD = f"{TESTS_FILE}::AlphaTest::test_x"

#: Путь ВНЕ `tests/` для мандата ослабления (AC-4, отказ): существует в
#: дереве кодовой ветки — отказ обязан прийти именно из правила «не под
#: tests/», а не из проверки существования.
OUTSIDE_TESTS_PATH = EXISTING_FILE

#: Нарушенная форма `путь::имя` (AC-4, отказ): разделитель есть, имени за
#: ним нет.
BROKEN_FORM_ELEMENT = f"{TESTS_FILE}::"

#: Элемент строки-прецедента 26.09 (AC-2): путь, пояснение и тире внутри
#: ОДНОГО элемента. `orchestrator/artel.py` в дереве кодовой ветки есть —
#: значит отказ приходит из-за пробела в элементе, а не из-за того, что
#: такого пути нет.
SPACED_ELEMENT = "orchestrator/artel.py — только разбор аргументов"

_ALPHA_TEST_TEXT = (
    "import unittest\n\n\n"
    "class AlphaTest(unittest.TestCase):\n\n"
    "    def test_x(self):\n"
    "        self.assertTrue(True)\n")

_BETA_TEST_TEXT = (
    "import unittest\n\n\n"
    "class BetaTest(unittest.TestCase):\n\n"
    "    def test_y(self):\n"
    "        self.assertTrue(True)\n")

#: Дерево, которое несёт кодовая ветка задачи (и НЕ несёт main).
CODE_BRANCH_TREE = {
    EXISTING_FILE: "# фикстура планки: модуль команды answer\n",
    "orchestrator/artel.py": "# фикстура планки: точка входа CLI\n",
    "docs/operator-gates.md": "# фикстура планки: гейты Оператора\n",
    TESTS_FILE: _ALPHA_TEST_TEXT,
    OTHER_TESTS_FILE: _BETA_TEST_TEXT,
}

# --- строки мандатов ----------------------------------------------------


def zones_mandate_line(tail: str) -> str:
    """Строка мандата расширения зон с перечнем элементов `tail`."""
    return f"{ZONES_MARKER} {tail}"


def weakening_mandate_line(tail: str) -> str:
    """Строка мандата ослабления тестов с перечнем элементов `tail`."""
    return f"{WEAKENING_MARKER} {tail}"


def answer_text(*lines: str) -> str:
    """Текст файла ответа Оператора: строки мандатов плюс отдельный абзац
    основания — та же форма, которую требование 2 SPEC называет штатной
    (пояснения отдельным абзацем, не внутри элемента)."""
    body = "\n".join(lines)
    return (f"{body}\n\n"
            f"Основание: решение Оператора, планка {TASK_ID}.\n")


PLAIN_ANSWER_TEXT = ("Ответ Оператора по существу вопроса: вариант A.\n\n"
                     "Строк мандатов в этом файле нет вовсе.\n")

#: Часть записи журнала, которой `answer` уже сегодня называет разобранные
#: элементы мандата зон (`orchestrator/answer.py:153-156`) — наблюдаемая
#: разбора со стороны самой команды (AC-1, AC-6).
MANDATE_JOURNAL_MARK = "мандат на расширение зон"


# --- песочница ----------------------------------------------------------


class AnswerMandateSandbox(RealGitSandbox):
    """Настоящий git-корень пульта: заведённая задача, её артефактная ветка
    и её кодовая ветка с деревом `CODE_BRANCH_TREE`.

    Состояние задачи ставится напрямую (`store.update_task`), минуя полный
    флоу FSM: предмет критериев — разбор и проверка строк мандата внутри
    `answer`, не сама FSM. `escalated` — состояние по умолчанию: именно в
    нём `answer` штатно принимает ЛЮБОЙ файл ответа (и именно его называет
    AC-7).

    `runner.in_role_environment()` здесь ложно по построению песочницы:
    `config.ROLE_HOME`/`config.ROLE_CONFIG_DIR` подменены на временный
    каталог, с которым `HOME` вызывающего процесса не совпадает — путь
    `in_dev`/`review` команды доступен планке без отдельного патча.
    """

    TITLE = "proverka stroki mandata answer"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, self.TITLE)
        self.conn = store.db()
        self.branch = artifact_branch.branch_name(self.TASK)
        self.code_branch = store.get_task(self.conn, self.TASK)["branch"]
        self.seed_code_branch()
        self.set_state("escalated")

    # -- фикстура кодовой ветки ------------------------------------------

    def seed_code_branch(self) -> None:
        """Кодовая ветка задачи с деревом `CODE_BRANCH_TREE`; main остаётся
        без этих путей. `git add` — только по перечисленным путям, не
        `-A`: рабочая копия песочницы несёт ещё и служебные каталоги
        пульта, которым в дереве кодовой ветки делать нечего."""
        self.git("checkout", "-q", "-b", self.code_branch)
        for rel, text in CODE_BRANCH_TREE.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "--", *CODE_BRANCH_TREE)
        self.git("commit", "-q", "-m", "дерево кодовой ветки задачи")
        self.git("checkout", "-q", config.MAIN_BRANCH)

    def code_branch_files(self) -> list:
        """Файлы дерева кодовой ветки — контроль самой фикстуры."""
        return gitcmd.ls_tree_files(self.code_branch, ".") or []

    # -- состояние и наблюдаемые -----------------------------------------

    def set_state(self, state: str) -> None:
        store.update_task(self.conn, self.TASK, state=state)

    def state(self) -> str:
        return store.get_task(self.conn, self.TASK)["state"]

    def artifact_files(self) -> list:
        return gitcmd.ls_tree_files(self.branch, f"tasks/{self.TASK}") or []

    def answer_files(self) -> list:
        """Имена `ANSWER-n.md`, лежащие в артефактной ветке задачи."""
        return sorted(p.rsplit("/", 1)[-1] for p in self.artifact_files()
                      if p.rsplit("/", 1)[-1].startswith("ANSWER-"))

    def answer_text_in_branch(self, n: int = 1) -> str | None:
        text, _reason = gitcmd.show(self.branch,
                                    f"tasks/{self.TASK}/ANSWER-{n}.md")
        return text

    def journal(self) -> list:
        """Записи журнала задачи как «действие | деталь»."""
        return [f"{row['action']} | {row['detail']}"
                for row in store.task_steps(self.conn, self.TASK)]

    def answer_journal(self) -> list:
        return [line for line in self.journal() if "ANSWER" in line]

    def journal_mandate_paths(self) -> list:
        """Списки элементов мандата зон по записям журнала — по одному
        списку на каждый успешный `answer` с мандатом (наблюдаемая разбора
        со стороны самой команды)."""
        found = []
        for row in store.task_steps(self.conn, self.TASK):
            action = row["action"] or ""
            if MANDATE_JOURNAL_MARK not in action:
                continue
            tail = action.split(MANDATE_JOURNAL_MARK, 1)[1]
            tail = tail.lstrip(": ").rstrip(")").strip()
            found.append([p.strip() for p in tail.split(",") if p.strip()])
        return found

    def zones_mandate_elements(self) -> list:
        """Элементы, которые на строках мандата файлов ANSWER получает гейт
        зон (`zones._answer_zones_mandate`, «Материалы» SPEC)."""
        return sorted(zones._answer_zones_mandate(self.branch, self.TASK))

    def weakening_mandate_elements(self) -> list:
        """То же для гейта неослабления тестов
        (`test_integrity._answer_mandate`, «Материалы» SPEC)."""
        return sorted(test_integrity._answer_mandate(self.branch, self.TASK))

    # -- вызовы команды --------------------------------------------------

    def answer_file(self, text: str) -> str:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8")
        self.addCleanup(lambda: Path(f.name).unlink(missing_ok=True))
        f.write(text)
        f.close()
        return f.name

    def succeed_answer(self, text: str) -> str:
        """`answer` с текстом `text`; возвращает напечатанное."""
        return capture(answer.cmd_answer, self.TASK, self.answer_file(text))

    def refuse_answer(self, text: str) -> str:
        """`answer` с текстом `text` обязан отказать, НЕ создав ANSWER:
        возвращает текст отказа, попутно проверяя оба следа отказа
        (требование 2 SPEC: ни коммита в артефактную ветку, ни записи в
        журнал). Вызывается только там, где ни одного ANSWER до вызова
        ещё нет."""
        before = self.answer_files()
        with self.assertRaises(SystemExit) as ctx:
            capture(answer.cmd_answer, self.TASK, self.answer_file(text))
        self.assertEqual(
            before, self.answer_files(),
            "при отказе проверки ANSWER-n.md не имеет права появляться на "
            "артефактной ветке")
        self.assertEqual(
            [], self.answer_journal(),
            "при отказе проверки записи об ANSWER в журнале быть не должно")
        return str(ctx.exception)
