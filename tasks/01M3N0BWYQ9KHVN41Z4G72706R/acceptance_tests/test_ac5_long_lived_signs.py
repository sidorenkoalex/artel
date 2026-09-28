"""AC-5 — долгоживущий файл с любым из девяти признаков требования 3
отклоняет выход из `tests_writing`; ошибка называет файл, строку и признак.

Каждый сценарий — чистая фикстура `_sandbox.plank_source` (она сама
переход проходит — см. AC-3) плюс ОДНА строка с признаком; ожидаемый номер
строки считается по тексту фикстуры. Формы признака, перечисленные в
требовании 3 (три формы импорта, `os.system`, `append`/`extend`/срез,
относительный импорт и т.п.), разыгрываются подтестами того же метода.

Группа: разовый
Красен до реализации: статической проверки долгоживущего файла на выходе из `tests_writing` нет — любая фикстура с признаком уходит в `in_dev`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402


class LongLivedSignsTest(_sandbox.GroupPlankSandbox):

    def check_head(self, line: str, sign: str) -> None:
        """Признак строкой уровня модуля (после импортов фикстуры)."""
        source = _sandbox.plank_source(head=[line])
        self.assert_sign_refused(source, line, sign)

    def check_body(self, line: str, sign: str) -> None:
        """Признак строкой тела тестового метода фикстуры."""
        source = _sandbox.plank_source(body=[line])
        self.assert_sign_refused(source, line, sign)

    def test_ac5_sign_tasks_literal(self):
        """Строковый литерал, содержащий `tasks/`, в долгоживущем файле —
        отказ с признаком `tasks/`, файлом и строкой литерала.

        Ловит мутацию: признак ищет только литералы, НАЧИНАЮЩИЕСЯ с
        `tasks/` (как якорь чтения артефактов в `scan_artifact_disk_reads`),
        — литерал «каталог tasks/ пульта» проходит, задача уходит в
        `in_dev`.
        """
        self.check_head('NOTE = "каталог tasks/ пульта"', _sandbox.SIGN_TASKS)

    def test_ac5_sign_git_module_import(self):
        """Импорт `orchestrator.gitcmd`/`orchestrator.artifact_branch` в
        любой из трёх форм требования 3 — отказ с признаком `git-модуль`.

        Ловит мутацию: признак смотрит только на `ast.Import`
        (`import orchestrator.gitcmd`), а `ast.ImportFrom` (`from
        orchestrator import gitcmd`) пропускает — подтест этой формы
        уходит в `in_dev`.
        """
        for line in ("from orchestrator import gitcmd  # noqa: F401",
                     "import orchestrator.gitcmd  # noqa: F401",
                     "from orchestrator.gitcmd import show  # noqa: F401",
                     "from orchestrator import artifact_branch  # noqa: F401",
                     "import orchestrator.artifact_branch  # noqa: F401"):
            with self.subTest(line=line):
                self.check_head(line, _sandbox.SIGN_GIT_MODULE)

    def test_ac5_sign_git_call_through_subprocess(self):
        """Вызов git через `subprocess` (список с `"git"` первым элементом,
        строка `"git …"`) или `os.system("git …")` — отказ с признаком
        `git-вызов`.

        Ловит мутацию: признак распознаёт только список аргументов
        `["git", …]` и не смотрит на строку команды, начинающуюся с
        `git ` (`shell=True`, `os.system`) — эти подтесты уходят в
        `in_dev`.
        """
        for line in ('subprocess.run(["git", "status"], check=False)',
                     'subprocess.check_output("git log -1", shell=True)',
                     'os.system("git status")'):
            with self.subTest(line=line):
                self.check_body(line, _sandbox.SIGN_GIT_CALL)

    def test_ac5_sign_task_id(self):
        """Литерал или имя, содержащие идентификатор ЭТОЙ (вложенной)
        задачи в любом регистре, — отказ с признаком «номер задачи».

        Ловит мутацию: сравнение с идентификатором задачи без приведения
        регистра — литерал в нижнем регистре и имя `ref_<id>` проходят в
        `in_dev`.
        """
        task_id = self.TASK
        for line in (f'REF = "{task_id}"',
                     f'REF = "{task_id.lower()}"',
                     f"ref_{task_id.lower()} = 1"):
            with self.subTest(line=line):
                self.check_head(line, _sandbox.SIGN_TASK_ID)

    def test_ac5_sign_sys_path_change(self):
        """`sys.path.insert`/`append`/`extend` и присваивание в `sys.path`
        целиком, по индексу и по срезу — отказ с признаком `sys.path`.

        Ловит мутацию: признак ловит только вызов `sys.path.insert`
        (как во всех старых планках) — `append`, `extend` и присваивания
        уходят в `in_dev`.
        """
        for line in ('sys.path.insert(0, "/nonexistent")',
                     'sys.path.append("/nonexistent")',
                     'sys.path.extend(["/nonexistent"])',
                     'sys.path = ["/nonexistent"]',
                     'sys.path[0] = "/nonexistent"',
                     'sys.path[0:0] = ["/nonexistent"]'):
            with self.subTest(line=line):
                self.check_head(line, _sandbox.SIGN_SYS_PATH)

    def test_ac5_sign_import_outside_allowed_list(self):
        """Импорт собственного помощника по голому имени (`import
        _sandbox`, `from _util import …`), стороннего пакета и любой
        относительный импорт — отказ с признаком «импорт вне перечня».

        Ловит мутацию: относительный импорт (`level > 0`, `module` пуст)
        проверяется по имени модуля и, не найдя его, пропускается —
        `from . import neighbour` уходит в `in_dev`.
        """
        for line in ("import _sandbox  # noqa: F401",
                     "from _util import helper  # noqa: F401",
                     "import requests  # noqa: F401",
                     "from . import neighbour  # noqa: F401",
                     "from .neighbour import thing  # noqa: F401"):
            with self.subTest(line=line):
                self.check_head(line, _sandbox.SIGN_FOREIGN_IMPORT)

    def test_ac5_sign_private_name_import(self):
        """Импорт из `orchestrator`/`scripts` имени или сегмента пути,
        начинающегося с подчёркивания, — отказ с признаком «закрытое
        имя».

        Ловит мутацию: признак проверяет импортируемые имена, но не
        сегменты пути модуля — `import orchestrator.advance_gates._base`
        уходит в `in_dev`.
        """
        for line in (
                "from orchestrator.fsm import _tests_writing_ac_state  # noqa: F401",
                "import orchestrator.advance_gates._base  # noqa: F401",
                "from orchestrator.advance_gates._base import GateRefusal  # noqa: F401",
                "from scripts.guard import _private_helper  # noqa: F401"):
            with self.subTest(line=line):
                self.check_head(line, _sandbox.SIGN_PRIVATE_NAME)

    def test_ac5_sign_patch_of_private_name(self):
        """`patch`/`mock.patch`/`unittest.mock.patch` со строковым путём,
        сегмент которого начинается с подчёркивания, и `patch.object` с
        закрытым именем атрибута — отказ с признаком «patch закрытого».

        Ловит мутацию: признак смотрит только на `mock.patch("…")` и не
        разбирает второй аргумент `mock.patch.object(obj, "_x")` — этот
        подтест уходит в `in_dev`.
        """
        for line in ('mock.patch("orchestrator.fsm._origin_main_sha")',
                     'mock.patch.object(fsm, "_origin_main_sha")',
                     'unittest.mock.patch("orchestrator.fsm._origin_main_sha")'):
            with self.subTest(line=line):
                self.check_body(line, _sandbox.SIGN_PATCH_PRIVATE)
        bare = 'patch("orchestrator.fsm._origin_main_sha")'
        source = _sandbox.plank_source(
            head=["from unittest.mock import patch  # noqa: F401"], body=[bare])
        self.assert_sign_refused(source, bare, _sandbox.SIGN_PATCH_PRIVATE)

    def test_ac5_sign_private_attribute_access(self):
        """Обращение `obj._x` к имени, привязанному импортом из
        `orchestrator`, — отказ с признаком «закрытый атрибут».

        Ловит мутацию: исключение «корень — `self`/`cls`» написано как
        «корень — любое имя, кроме импортированного модулем `import`»
        (`from orchestrator import store` не считается импортом) —
        `store._private_value` уходит в `in_dev`.
        """
        for line in ("value = store._private_value",
                     "value = fsm._origin_main_sha"):
            with self.subTest(line=line):
                self.check_body(line, _sandbox.SIGN_PRIVATE_ATTR)


if __name__ == "__main__":
    unittest.main()
