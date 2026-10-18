"""Формы аргумента `<файл>` команды `artel.py guard <id> [<файл>]` (SPEC
01M56G23ZQDHV2BKEVWWC22R96, требование 1): имя артефакта и путь
`tasks/<id>/<файл>` называют один и тот же файл каталога документов.

Сравнение с эталоном и чтение-только покрывают долгоживущие файлы задачи
(`tests/test_01m56g23zqdhv2bkevwwc22r96_guard_command.py`); здесь — только
форма аргумента и отказ на пустом каталоге документов.
"""
import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from orchestrator import artel, artifact_branch, config, store
from tests.sandbox import TmpRootTest

TASK = "01M56G23ZQDHV2BKEVWWC22R97"

BROKEN_SPEC = """---
task: {task}
type: spec
author_role: analyst
status: nonsense
schema_version: 5
---

# SPEC: фикстура
"""


class GuardFileFormsTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, TASK, "Фикстура", "in_dev",
                          f"task/{TASK.lower()}-fixture", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.docs = artifact_branch.docs_dir(TASK, config.DEFAULT_TARGET)

    def guard(self, *extra: str) -> tuple:
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with mock.patch.object(sys, "argv", ["artel.py", "guard", TASK, *extra]), \
                redirect_stdout(out), redirect_stderr(err):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue() + err.getvalue() + (
            code if isinstance(code, str) else "")

    def test_task_prefixed_path_names_same_docs_file(self):
        """`guard <id> tasks/<id>/SPEC.md` проверяет SPEC.md каталога документов — тот же вывод и код, что `guard <id> SPEC.md`.

        Ловит мутацию: префикс `tasks/<id>/` не снимается — путь
        `<каталог документов>/tasks/<id>/SPEC.md` не найден, вывод — «файл
        не найден» вместо нарушения status; код выхода не зависит от
        нарушения — 0 на сломанном SPEC.
        """
        self.docs.mkdir(parents=True, exist_ok=True)
        (self.docs / "SPEC.md").write_text(BROKEN_SPEC.format(task=TASK),
                                           encoding="utf-8")
        plain = self.guard("SPEC.md")
        prefixed = self.guard(f"tasks/{TASK}/SPEC.md")
        self.assertNotEqual(plain[0], 0, plain[1])
        self.assertIn(f"{self.docs / 'SPEC.md'}: ", plain[1])
        self.assertNotIn("файл не найден", prefixed[1])
        self.assertEqual(prefixed, plain)

    def test_empty_docs_dir_refused(self):
        """`guard <id>` без файла при каталоге документов без `*.md` — ненулевой код и отказ, называющий каталог.

        Ловит мутацию: пустой перечень уходит в `scripts/guard.py` без
        аргументов — печатается справка эталона, отказ не называет каталог
        документов.
        """
        code, output = self.guard()
        self.assertNotEqual(code, 0, output)
        self.assertIn(str(self.docs), output)
        self.assertIn("нет файлов *.md", output)
