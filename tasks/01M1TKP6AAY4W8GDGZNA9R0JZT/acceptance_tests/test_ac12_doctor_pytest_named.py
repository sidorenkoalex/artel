"""AC-12 (SPEC.md, требование 8): `orchestrator.doctor` (через
`orchestrator.stack.check_stack()`) в статусе проверки `venv-packages`
явно называет `pytest`, если он отсутствует в `.artel/venv` или
расходится по версии с `requirements.lock` — не только общей сверкой
списка несовпавших имён пакетов.

`orchestrator.doctor.cmd_doctor`/`_stack_checks_section` собирают карточки
из `stack.check_stack()` напрямую (докстринг `orchestrator/doctor.py`) —
испытание самого `check_stack()` тем же приёмом, что задача-предшественник
01M1REVEZ1HESMJ7AFD5A9MEJ8 уже применила для AC-7/AC-8 (`tasks/
01M1REVEZ1HESMJ7AFD5A9MEJ8/acceptance_tests/test_ac7_ac8_check_stack_venv.py`)
— проверять то же самое через `doctor.cmd_doctor` целиком означало бы
заново собирать её же обвязку (печать, `--fix`, восстановление), не
имеющую отношения к требованию 8.

Красен до реализации: сегодня `_venv_packages_check` (`orchestrator/
stack.py`) уже перечисляет РАСХОДЯЩИЕСЯ пакеты через запятую — pytest
попадает в этот список, если расходится, тем же способом, что и любой
другой пакет; но при ПОЛНОМ отсутствии pytest среди пакетов, о которых
вообще что-то известно `pip freeze`, и особенно при нескольких
расходящихся пакетах ОДНОВРЕМЕННО, ничего не выделяет pytest явно среди
прочих имён — до правки требования 8 сообщение остаётся ОБЩИМ списком,
`assertRegex` на отдельное упоминание pytest вне общего перечисления
ниже падает, пока разработчик не добавит выделенную фразу.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, stack  # noqa: E402

OK_PYTHON_VERSION_INFO = (3, 99, 0, "final", 0)
HIGH_VERSION = "999.999.999"

LOCK_CONTENT = (
    "pytest==7.4.4\npytest-timeout==2.3.1\npytest-xdist==3.5.0\n"
    "requests==2.31.0\n")


def _make_fake_run(freeze_output: str):
    def fake_run(args, **kwargs):
        args = list(args)
        if "freeze" in args:
            return subprocess.CompletedProcess(args, 0, freeze_output, "")
        return subprocess.CompletedProcess(args, 0, f"{HIGH_VERSION}\n", "")
    return fake_run


class DoctorPytestNamedExplicitlyTest(unittest.TestCase):

    def setUp(self):
        self.version_patcher = mock.patch.object(
            sys, "version_info", OK_PYTHON_VERSION_INFO)
        self.version_patcher.start()
        self.addCleanup(self.version_patcher.stop)

        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.venv_dir = Path(tmp.name) / "venv"
        self.venv_dir.mkdir()
        self.lock_file = Path(tmp.name) / "requirements.lock"
        self.lock_file.write_text(LOCK_CONTENT, encoding="utf-8")

    def _venv_packages_check(self, freeze_output: str):
        with mock.patch.object(config, "VENV_DIR", self.venv_dir, create=True), \
             mock.patch.object(config, "REQUIREMENTS_LOCK", self.lock_file,
                               create=True), \
             mock.patch.object(stack.subprocess, "run",
                               side_effect=_make_fake_run(freeze_output)):
            checks = stack.check_stack()
        matching = [c for c in checks if c.name == "venv-packages"]
        self.assertTrue(matching, f"нет проверки venv-packages: {checks}")
        return matching[0]

    def test_ac12_pytest_absent_from_venv_is_named_explicitly(self):
        """`pytest` вовсе отсутствует среди пакетов `.artel/venv`
        (`pip freeze` его не перечисляет), остальные три закреплённых
        пакета совпадают точно — статус WARN, текст явно называет
        `pytest` доступность которого нарушена (не только «не найден
        среди установленных», растворённое в общем перечислении).

        Ловит мутацию: разработчик считает требование 8 выполненным,
        потому что имя `pytest` и так попадает в список расходящихся
        через запятую (текущее поведение) — не добавляет отдельное
        упоминание, `assertRegex` на выделенную фразу про pytest
        (не являющуюся частью списка через запятую) откажет.
        """
        freeze_output = (
            "pytest-timeout==2.3.1\npytest-xdist==3.5.0\nrequests==2.31.0\n")
        check = self._venv_packages_check(freeze_output)

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn("pytest", check.detail.lower())
        self.assertRegex(
            check.detail, r"pytest[^,\n]{0,60}(недоступ|нет в venv|отсутств)",
            f"детали не несут выделенной фразы про недоступность pytest, "
            f"а не просто имя в общем списке: {check.detail!r}")

    def test_ac12_pytest_version_mismatch_is_named_explicitly(self):
        """`pytest` установлен, но с версией ниже закреплённой, остальные
        три пакета совпадают точно — статус WARN, текст явно называет
        именно `pytest` (не просто попадание в список расходящихся имён).

        Ловит мутацию: то же, что выше, но для случая несовпадения
        версии (а не полного отсутствия) — обе ветки требования 8
        («отсутствует… или расходится по версии») обязаны получить
        явное упоминание, не только одна из двух.
        """
        freeze_output = ("pytest==7.0.0\npytest-timeout==2.3.1\n"
                         "pytest-xdist==3.5.0\nrequests==2.31.0\n")
        check = self._venv_packages_check(freeze_output)

        self.assertEqual(check.status, "warn", check.detail)
        self.assertRegex(
            check.detail, r"pytest[^,\n]{0,60}(недоступ|версия|расхо)",
            f"детали не несут выделенной фразы про pytest: {check.detail!r}")


if __name__ == "__main__":
    unittest.main()
