"""AC-7, AC-8 (tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/SPEC.md, требование 2):
`orchestrator.stack.check_stack()` — расширение S1
(01M1RDCAFENSW2VVAPECHCVGMM) — сверяет `.artel/venv` с файлом
закреплённых версий.

Красен до реализации: `orchestrator.stack` (ветка S1) ещё не смержена в
этом дереве — импорт падает `ModuleNotFoundError` для всех тестов ниже.

Подмена `subprocess.run` — через `stack.subprocess` (модульный объект),
тем же приёмом, что уже установлен S1 (`tests/test_stack.py`,
`tasks/01M1RDCAFENSW2VVAPECHCVGMM/acceptance_tests/
test_ac7_ac8_ac9_ac10_ac17_check_stack.py`) для существующих проверок
git/gh/claude — единый источник подмены на весь процесс. Различение
«это вызов сверки пакетов venv, а не проверки инструмента манифеста» —
по наличию `"freeze"` среди аргументов (`pip freeze`/`python -m pip
freeze` — обе формы содержат буквальный токен `freeze`), не по точному
пути исполняемого файла: тест не обязан знать, зовёт ли реализация
`<venv>/bin/pip` напрямую или `<venv>/bin/python -m pip`.

`config.VENV_DIR`/`config.REQUIREMENTS_LOCK` подменяются через
`mock.patch.object(..., create=True)` — атрибуты, которых сегодня в
`orchestrator/config.py` ещё нет (эта же задача их заводит), тем же
приёмом, что уже принят в этом конвейере для данных ещё не смерженной
зависимости (см. память test_author: «бутстрап данных ещё не смерженной
зависимости в песочнице теста»).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, stack  # noqa: E402

HIGH_VERSION = "999.999.999"
OK_PYTHON_VERSION_INFO = (3, 99, 0, "final", 0)

LOCK_CONTENT = "pytest==7.4.4\npytest-timeout==2.3.1\npytest-xdist==3.5.0\n"


def _make_fake_run(freeze_output: str):
    def fake_run(args, **kwargs):
        args = list(args)
        if "freeze" in args:
            return subprocess.CompletedProcess(args, 0, freeze_output, "")
        return subprocess.CompletedProcess(args, 0, f"{HIGH_VERSION}\n", "")
    return fake_run


class CheckStackVenvTest(unittest.TestCase):

    def setUp(self):
        self.version_patcher = mock.patch.object(
            sys, "version_info", OK_PYTHON_VERSION_INFO)
        self.version_patcher.start()
        self.addCleanup(self.version_patcher.stop)

    def _check_with(self, venv_dir: Path, lock_file: Path, freeze_output: str):
        with mock.patch.object(config, "VENV_DIR", venv_dir, create=True), \
             mock.patch.object(config, "REQUIREMENTS_LOCK", lock_file,
                               create=True), \
             mock.patch.object(stack.subprocess, "run",
                               side_effect=_make_fake_run(freeze_output)):
            return stack.check_stack()

    def test_ac8_missing_venv_gives_warn_naming_the_creation_command(self):
        """Требование 2/AC-8: `.artel/venv` отсутствует — статус WARN,
        текст называет команду создания (`venv-sync`, CLI из требования
        2/AC-4), а не молчит о том, что делать.

        Ловит мутацию: отсутствие venv трактуется как `ok` (проверка не
        добавлена вовсе, либо добавлена, но не смотрит на существование
        каталога) — ни один `assertTrue` ниже не найдёт WARN о venv;
        либо WARN есть, но без упоминания команды создания — второй
        `assertIn` откажет.
        """
        missing_venv = Path("/nonexistent") / "surely-not-real" / ".artel" / "venv"
        lock_file = _write_tmp_lock(self)

        checks = self._check_with(missing_venv, lock_file, "")

        venv_checks = [c for c in checks if "venv" in c.name.lower()]
        self.assertTrue(venv_checks, f"нет ни одной проверки venv: {checks}")
        warn = [c for c in venv_checks if c.status == "warn"]
        self.assertTrue(
            warn, f"отсутствие venv не даёт WARN: {venv_checks}")
        self.assertIn(
            "venv-sync", " ".join(c.detail for c in warn),
            f"WARN об отсутствующем venv не называет команду создания: "
            f"{warn}")

    def test_ac7_version_mismatch_gives_warn_naming_the_package(self):
        """Требование 2/AC-7: установленная в `.artel/venv` версия
        расходится с файлом закреплённых версий — статус WARN, имя
        РАСХОДЯЩЕГОСЯ пакета в тексте (`pytest`, тогда как
        `pytest-timeout`/`pytest-xdist` заведомо совпадают — WARN обязан
        указывать именно на расхождение, не быть общей фразой).

        Ловит мутацию: сверка версий не реализована (венв считается
        согласованным всегда, пока каталог существует) — WARN не
        появится, первый `assertTrue` откажет; либо WARN появляется, но
        не называет РАСХОДЯЩИЙСЯ пакет по имени — `assertIn("pytest",
        ...)` откажет.
        """
        venv_dir = _write_tmp_dir(self)
        lock_file = _write_tmp_lock(self)
        # pytest занижен относительно лока (7.0.0 vs 7.4.4 в LOCK_CONTENT);
        # остальные два — точно как в локе.
        freeze_output = ("pytest==7.0.0\npytest-timeout==2.3.1\n"
                         "pytest-xdist==3.5.0\n")

        checks = self._check_with(venv_dir, lock_file, freeze_output)

        warn = [c for c in checks
               if "venv" in c.name.lower() and c.status == "warn"]
        self.assertTrue(
            warn, f"расхождение версии pytest не даёт WARN: {checks}")
        detail = " ".join(c.detail.lower() for c in warn)
        self.assertIn("pytest", detail, detail)

    def test_ac7_matching_versions_produce_no_venv_warn(self):
        """Требование 2/AC-7 (контроль): все версии в `.artel/venv`
        совпадают с файлом закреплённых версий — ни одна WARN-проверка
        про venv не появляется (WARN — свойство именно РАСХОЖДЕНИЯ, не
        безусловный статус).

        Ловит мутацию: реализация всегда возвращает WARN для проверки
        venv-пакетов независимо от факта совпадения версий (например
        забыто условие сравнения) — при полностью согласованном venv
        WARN всё равно появится, `assertFalse` откажет.
        """
        venv_dir = _write_tmp_dir(self)
        lock_file = _write_tmp_lock(self)

        checks = self._check_with(venv_dir, lock_file, LOCK_CONTENT)

        warn = [c for c in checks
               if "venv" in c.name.lower() and c.status == "warn"]
        self.assertFalse(
            warn, f"venv полностью согласован с локом, но получен WARN: "
                 f"{warn}")


def _write_tmp_dir(test: unittest.TestCase) -> Path:
    import tempfile
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    return Path(tmp.name)


def _write_tmp_lock(test: unittest.TestCase) -> Path:
    tmp_dir = _write_tmp_dir(test)
    lock_file = tmp_dir / "requirements.lock"
    lock_file.write_text(LOCK_CONTENT, encoding="utf-8")
    return lock_file


if __name__ == "__main__":
    unittest.main()
