"""Общая песочница и фикстуры для приёмочных тестов
01M1H186VEVG6NF40YKH1338MD.

Не подпадает под маркерную проверку самой задачи (SPEC требование 1
называет только `test_*.py` — этот файл в выборку не входит).

Копия лёгкой песочницы `_T064TmpRootTest`
(tasks/T064/acceptance_tests/_sandbox.py) — тот же приём (БД/артефакты
во временном каталоге, `gitcmd.git` заглушкой `fake_git`), которым уже
покрыт тот же самый вызов FSM (`orchestrator/fsm.py`,
`_tests_writing_ac_state`/`orchestrator/fsm_advance.py::tests_writing`,
SPEC «Материалы»). Не переиспользуется напрямую импортом из
tasks/T064/, потому что `acceptance_tests/` каждой задачи — отдельный
залоченный каталог (ADR-0003, инвариант 27), не общий модуль.
"""
import shutil
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, fsm, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest as _BaseTmpRootTest  # noqa: E402
from tests.sandbox import fake_git  # noqa: E402

# Фиктивный SPEC с двумя критериями, НИКАК не связанный с реальными
# AC-1..AC-5 задачи 01M1H186VEVG6NF40YKH1338MD — только чтобы
# трассируемость AC (T023) и маркер красноты (T064) внутри песочницы
# сами по себе не были причиной отказа перехода: единственная
# переменная в тестах этого каталога — наличие/отсутствие образца
# формата идентификатора задачи в содержимом acceptance_tests/.
SPEC_V2 = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
{extra}---

# SPEC: проверка формата идентификатора — песочница

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Первый критерий, проверяемый тестом.
AC-2. Второй критерий, проверяемый тестом.

## Не входит
"""

# Полное покрытие фиктивных AC-1/AC-2, валидный маркер красноты, БЕЗ
# образца формата идентификатора задачи — сценарий AC-2 (SPEC
# 01M1H186VEVG6NF40YKH1338MD): такое содержимое не имеет права
# блокировать переход по признаку формата идентификатора.
AC_TEST_CLEAN = '''"""Зелёный с рождения: фикстура-песочница без образца формата
идентификатора задачи — сама песочница, не задача
01M1H186VEVG6NF40YKH1338MD."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac2_second_criterion(self):
        self.assertEqual(1 + 1, 2)
'''

# Образец «T и три цифры» собран конкатенацией (правка Оператора по
# ADR-0012, R1-F1 ревью 02.09): буквальное написание в исходнике
# _sandbox.py само совпадало бы с образцами линта формата
# идентификатора — и активный CI-джоб, и новая проверка ложно
# срабатывали бы на этой фикстуре.
_ID_SAMPLE_RE = "T" + "\\" + "d{3}"

# Полное покрытие фиктивных AC-1/AC-2, валидный маркер красноты,
# СОДЕРЖИТ образец формата идентификатора задачи («T и три цифры»,
# подставляется из _ID_SAMPLE_RE — см. выше; тот же класс дефекта,
# что инцидент 02.09.2026 из SPEC «Контекст») — сценарий AC-1
# (SPEC 01M1H186VEVG6NF40YKH1338MD).
AC_TEST_WITH_ID_SAMPLE = '''"""Красен до реализации: фикстура-песочница содержит образец формата
идентификатора задачи — сама песочница, не задача
01M1H186VEVG6NF40YKH1338MD."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertRegex("T042", r"__ID_SAMPLE__")

    def test_ac2_second_criterion(self):
        self.assertEqual(1 + 1, 2)
'''

# Подстановка реального образца в шаблон: в исходнике фикстуры стоит
# заглушка __ID_SAMPLE__, буквальный образец существует только в
# сгенерированном при прогоне файле (см. _ID_SAMPLE_RE выше).
AC_TEST_WITH_ID_SAMPLE = AC_TEST_WITH_ID_SAMPLE.replace(
    "__ID_SAMPLE__", _ID_SAMPLE_RE)

# Строка с образцом формата идентификатора в AC_TEST_WITH_ID_SAMPLE —
# вычислено из самого текста фикстуры, а не подобрано вручную: правка
# фикстуры выше не может молча разойтись с числом, которое тест ждёт в
# сообщении отказа (SPEC AC-1 — «сообщение называет файл и строку»).
ID_SAMPLE_LINE = next(
    i for i, line in enumerate(AC_TEST_WITH_ID_SAMPLE.splitlines(), start=1)
    if _ID_SAMPLE_RE in line)


class _TmpRootTest(_BaseTmpRootTest):
    """Лёгкая песочница: БД и артефакты во временном каталоге, git — заглушка.

    `ROOT` тоже уводится (холодный старт сканирует его для посева
    счётчика) — `templates/`/`skills/` копируются рядом, `cmd_new`
    продолжает читать настоящий `templates/SPEC.md`, только уже из
    песочницы (тот же приём, что tasks/T064/acceptance_tests/_sandbox.py).
    """

    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "ROLE_HOME", "ROLE_CONFIG_DIR",
                     "WORKTREES", "ROOT")

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        # `cmd_new` возвращает фактический id (ULID, SPEC T094) — тот же
        # приём, что `capture()` теряет (только stdout), поэтому здесь
        # вызвано напрямую, без обёртки capture(). Дальнейшее содержимое
        # SPEC.md/acceptance_tests пишется прямо в `config.TASKS/<id>`
        # (`orchestrator/fsm.py::cmd_advance`, `tdir = config.TASKS /
        # task_id`, безусловно — не туда, куда фактически пишет `cmd_new`
        # для self/target, tests/sandbox.py `fake_git` держит
        # `gitcmd.on_foreign_branch` в False, так что FSM читает именно
        # отсюда).
        self.TASK = catalog.cmd_new(
            "Проверка формата идентификатора (песочница)")
        self.tdir = config.TASKS / self.TASK
        self.tdir.mkdir(parents=True, exist_ok=True)

    def state(self) -> str:
        return store.db().execute("SELECT state FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()[0]

    def row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def write_spec(self, template: str, extra: str = "") -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            template.format(task=self.TASK, extra=extra), encoding="utf-8")

    def write_acceptance_tests(self, content: str,
                               name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def enter_tests_writing(self) -> None:
        self.write_spec(SPEC_V2)
        self.set_state("tests_writing")


TmpRootTest = _TmpRootTest
