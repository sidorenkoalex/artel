"""Приёмочные тесты 01M1SHK3MD4ZF9NYXSCT67J8AP: самовыбор интерпретатора
точкой входа `orchestrator/artel.py` (AC-1..AC-9 SPEC.md).

Красен до реализации: `orchestrator/artel.py` сегодня безусловно
исполняет `from orchestrator import (amend, answer, ..., doctor, ...)`
(модули с синтаксисом 3.10+ внутри) без всякой защиты версии — под
старым интерпретатором это падает необработанным `TypeError` из глубины
импорта, а не именованным отказом или перезапуском под `.artel/venv`.
Каждый сценарий ниже (AC-1, AC-3..AC-6, AC-8, AC-9) обязан начать
проходить только после того, как точка входа обзаведётся проверкой
`sys.version_info` до этого импорта; до тех пор `_ensure_supported_python`-
подобной логики не существует вовсе, поэтому `os.execv` не вызывается,
именованный отказ не печатается, а поведение отличается от ожидаемого.

Реальный интерпретатор Python 3.9/3.10 в этой песочнице недоступен
(`sys.version_info` == 3.13 — единственный установленный) — тесты не
воспроизводят буквальный TypeError разбора аннотаций, а тем же приёмом,
что уже применяет `tests/test_stack.py` к `stack._python_check()`
(`mock.patch.object(sys, "version_info", ...)`), подменяют версию и
наблюдают ДЕКЛАРАТИВНОЕ решение точки входа (execv/именованный отказ/
проход). Проверка версии обязана жить на уровне МОДУЛЯ (не внутри
`main()`, которую `if __name__ == "__main__":` не вызывает при простом
импорте) — сегодняшний крэш происходит уже при самом импорте
`orchestrator.artel` (безусловный top-level `from orchestrator import
(...)`), а не при вызове `main()`; это верно для всех трёх способов
столкнуться с этим кодом — `python3 orchestrator/artel.py`, `python3 -m
orchestrator.artel` и `from orchestrator import artel` — их top-level
код идентичен, поэтому `importlib.reload(orchestrator.artel)` в
работающем процессе — точный аналог перезапуска точки входа с нужной
подменой `sys.version_info`/`os.execv`, без реального замещения образа
процесса.
"""
import ast
import contextlib
import importlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator import agent_log, artel, config, stack  # noqa: E402

ARTEL_PY = ROOT / "orchestrator" / "artel.py"
OLD_VERSION_INFO = (3, 9, 0, "final", 0)
OK_VERSION_INFO = tuple(sys.version_info)


class _FakeExecvInvoked(Exception):
    """Сигнал теста: `os.execv` вызван — настоящий `execv` заменил бы
    образ процесса и не вернул бы управление, поэтому тест обязан
    остановиться здесь же, не продолжая исполнение module-level кода."""


def _make_fake_venv(tmp_path: Path) -> Path:
    """`<tmp>/venv/bin/python` — символическая ссылка на РЕАЛЬНЫЙ
    `sys.executable` (не текстовый стаб-скрипт): годится для любого
    способа проверки версии венва, каким бы его ни выбрала реализация
    (`--version`, `-c "import sys; ..."`, что угодно ещё) — это
    по-настоящему рабочий современный интерпретатор."""
    venv_dir = tmp_path / "venv"
    bin_dir = venv_dir / "bin"
    bin_dir.mkdir(parents=True)
    os.symlink(sys.executable, bin_dir / "python")
    return venv_dir


def _reload_artel_recording_execv(execv_calls: list) -> None:
    def fake_execv(path, args):
        execv_calls.append((path, list(args)))
        raise _FakeExecvInvoked()
    with mock.patch.object(os, "execv", side_effect=fake_execv):
        importlib.reload(artel)


def _run_old_interpreter_with_ok_venv(extra_env=None):
    """Сценарий «старый интерпретатор + пригодный `.artel/venv`» — общий
    стенд для AC-3/AC-5/AC-8: возвращает `(execv_calls, venv_dir,
    env_before, env_after, exit_exc)`. `extra_env`, если задан,
    устанавливается в `os.environ` ДО прогона (сценарий AC-5 — маркер уже
    стоит) и снимается после, независимо от исхода."""
    tmp = Path(tempfile.mkdtemp())
    venv_dir = _make_fake_venv(tmp)
    execv_calls = []
    original_environ = dict(os.environ)
    for k, v in (extra_env or {}).items():
        os.environ[k] = v
    env_before = dict(os.environ)
    exit_exc = None
    try:
        with mock.patch.object(sys, "version_info", OLD_VERSION_INFO), \
             mock.patch.object(config, "VENV_DIR", venv_dir, create=True), \
             mock.patch.object(sys, "argv", ["orchestrator/artel.py", "status", "T1"]):
            try:
                _reload_artel_recording_execv(execv_calls)
            except _FakeExecvInvoked:
                pass
    except SystemExit as exc:
        exit_exc = exc
    env_after = dict(os.environ)
    # Восстановление ДО исходного снимка (а не просто удаление добавленных
    # `extra_env` ключей): код под тестом мог сам добавить в os.environ
    # маркер против рекурсии — не откатив его, следующий вызов этой же
    # функции в другом тесте процесса застал бы маркер уже стоящим.
    os.environ.clear()
    os.environ.update(original_environ)
    return execv_calls, venv_dir, env_before, env_after, exit_exc


def _required_python_text() -> str:
    return ".".join(str(part) for part in stack.REQUIRED_PYTHON)


class _ArtelReloadTestCase(unittest.TestCase):
    """Общая песочница: каждый тест перегружает `orchestrator.artel` под
    своими подменами. Сбой посреди `importlib.reload` (например,
    `SystemExit`, поднятый на середине top-level кода) оставляет модуль
    в частично обновлённом состоянии — `tearDown` возвращает его в
    рабочее состояние честной перезагрузкой под настоящими условиями
    (реальный `sys.version_info` — заведомо адекватен в этой песочнице),
    чтобы не испортить остальные тесты процесса/файла."""

    def tearDown(self):
        importlib.reload(artel)
        super().tearDown()


class Ac1VersionCheckPrecedesRiskyImportTest(_ArtelReloadTestCase):

    def test_ac1_version_check_runs_before_the_doctor_import(self):
        """Старый интерпретатор без пригодного venv, при этом
        `sys.modules['orchestrator.doctor']` «отравлен» (`None` — любая
        попытка реально импортировать этот модуль подняла бы
        `ImportError`, см. `orchestrator.doctor`, явно упомянутый в
        тексте AC-1 как пример модуля с синтаксисом 3.10+). Если точка
        входа проверяет версию РАНЬШЕ бульк-импорта `doctor`,
        перезагрузка обязана завершиться именованным `SystemExit(2)` (нет
        пригодного venv в этом сценарии), не дойдя до отравленного
        импорта.

        Ловит мутацию: проверка версии перенесена ПОСЛЕ бульк-импорта
        (или живёт только внутри `main()`, не исполняемой при простом
        импорте модуля) — перезагрузка попытается импортировать
        `orchestrator.doctor`, поймает `ImportError` вместо ожидаемого
        `SystemExit(2)`.
        """
        orchestrator_pkg = sys.modules["orchestrator"]
        real_doctor = sys.modules.get("orchestrator.doctor")
        had_attr = hasattr(orchestrator_pkg, "doctor")
        if had_attr:
            delattr(orchestrator_pkg, "doctor")
        sys.modules["orchestrator.doctor"] = None
        try:
            with mock.patch.object(sys, "version_info", OLD_VERSION_INFO), \
                 mock.patch.object(config, "VENV_DIR",
                                   Path(tempfile.mkdtemp()) / "no-venv-here",
                                   create=True):
                with self.assertRaises(SystemExit) as ctx:
                    importlib.reload(artel)
            self.assertNotIsInstance(ctx.exception.__cause__, ImportError)
        finally:
            if real_doctor is not None:
                sys.modules["orchestrator.doctor"] = real_doctor
            else:
                sys.modules.pop("orchestrator.doctor", None)
            if had_attr:
                setattr(orchestrator_pkg, "doctor", real_doctor)

    def test_ac1_no_forbidden_39_syntax_before_the_doctor_import_in_artel_py(self):
        """AC-1: «сам код проверки не использует `X | None`/`match`».
        Разбор AST `orchestrator/artel.py`: код точки входа, обязанный
        работать под 3.9, — это всё, что лежит СТРОГО РАНЬШЕ строки
        `from orchestrator import (..., doctor, ...)` (буквально та
        строка, что цитирует сам текст AC-1).

        Ловит мутацию: проверка версии реализована как `def`/выражение с
        аннотацией `X | None` или оператором `match` РАНЬШЕ этого
        импорта — обход найдёт узел с `lineno` меньше найденной строки
        импорта, `assertEqual([], ...)` откажет.
        """
        source = ARTEL_PY.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(ARTEL_PY))
        import_line = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "orchestrator" and \
                    any(alias.name == "doctor" for alias in node.names):
                import_line = node.lineno
                break
        self.assertIsNotNone(
            import_line,
            "не найден `from orchestrator import (..., doctor, ...)` — "
            "AC-1 ссылается именно на эту строку буквально")
        offenders = []
        for node in ast.walk(tree):
            lineno = getattr(node, "lineno", None)
            if lineno is None or lineno >= import_line:
                continue
            if isinstance(node, ast.Match):
                offenders.append(f"match на строке {lineno}")
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                offenders.append(f"`|` на строке {lineno}")
        self.assertEqual([], offenders)


class Ac2RequiredPythonMatchesStackTest(_ArtelReloadTestCase):

    def test_ac2_stack_module_has_no_39_incompatible_syntax(self):
        """Предпосылка AC-2: `orchestrator/stack.py` и зависимый от него
        `config.py` не используют синтаксис 3.10+ — значит точка входа
        обязана читать `REQUIRED_PYTHON` ПРЯМЫМ импортом `stack.py`, а не
        заводить дублирующую константу (SPEC допускает дублирование
        только «если он окажется несовместим с 3.9»).

        Ловит мутацию: в `stack.py`/`config.py` появляется `X | None`
        или `match` — обход AST найдёт нарушение.
        """
        offenders = []
        for path in (ROOT / "orchestrator" / "stack.py",
                     ROOT / "orchestrator" / "config.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Match):
                    offenders.append(f"{path.name}:{node.lineno} match")
                if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                    offenders.append(f"{path.name}:{node.lineno} `|`")
        self.assertEqual([], offenders)

    def test_ac2_entry_point_threshold_tracks_stack_required_python(self):
        """Раз предпосылка выше верна, точка входа обязана реально
        читать `REQUIRED_PYTHON` ИЗ `stack.py` (не собственную зашитую
        копию): подмена `stack.REQUIRED_PYTHON` на нарочито высокое
        значение делает ДАЖЕ современный интерпретатор песочницы (3.13)
        «слишком старым» — именованный отказ обязан назвать именно этот
        подменённый порог.

        Ловит мутацию: точка входа держит собственную константу
        `REQUIRED_PYTHON`, не связанную со `stack.py` — подмена
        `stack.REQUIRED_PYTHON` ни на что не повлияет, реальный (3.13)
        интерпретатор пройдёт без отказа, `assertRaises` откажет.
        """
        high_threshold = (999, 0)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf), \
             mock.patch.object(stack, "REQUIRED_PYTHON", high_threshold), \
             mock.patch.object(config, "VENV_DIR",
                               Path(tempfile.mkdtemp()) / "no-venv-here",
                               create=True):
            with self.assertRaises(SystemExit) as ctx:
                importlib.reload(artel)
        self.assertEqual(2, ctx.exception.code)
        self.assertIn("999", buf.getvalue())


class Ac3ExecvRestartTest(_ArtelReloadTestCase):

    def test_ac3_old_interpreter_with_ok_venv_reexecs_via_os_execv(self):
        """Старый интерпретатор, `.artel/venv/bin/python` пригоден,
        маркер против рекурсии не стоит: точка входа обязана исполнить
        `os.execv` ИМЕННО этим путём, с `sys.argv[1:]` в хвосте
        аргументов (требование 3/AC-3 — «те же аргументы»), и добавить
        хотя бы одну новую переменную окружения (маркер).

        Ловит мутацию: перезапуск зовёт другой путь (например, системный
        `python3` вместо venv), теряет хвост исходных аргументов, либо
        вовсе не отличает окружение до/после — соответствующий `assert`
        откажет.
        """
        execv_calls, venv_dir, before, after, exit_exc = \
            _run_old_interpreter_with_ok_venv()
        self.assertIsNone(exit_exc, "venv пригоден — отказа быть не должно")
        self.assertEqual(1, len(execv_calls))
        path, args = execv_calls[0]
        expected_python = str(venv_dir / "bin" / "python")
        self.assertEqual(expected_python, str(path))
        self.assertIn("status", args)
        self.assertIn("T1", args)
        diff_keys = {k for k in after if before.get(k) != after.get(k)}
        self.assertTrue(diff_keys,
                        "execv обязан нести маркер против рекурсии — "
                        "новых/изменённых переменных окружения не появилось")


class Ac4NamedFailureWithoutUsableVenvTest(_ArtelReloadTestCase):

    def test_ac4_old_interpreter_without_usable_venv_names_the_failure_and_exits_2(self):
        """Старый интерпретатор, `.artel/venv/bin/python` отсутствует:
        точка входа не исполняет команду пользователя, печатает ровно
        именованный отказ (версия+путь фактического интерпретатора,
        подсказка `venv-sync`) и завершается кодом 2 — не 1, не голым
        traceback.

        Ловит мутацию: реализация зовёт `sys.exit("текст")` без
        отдельного числового кода (реальный код выхода процесса стал бы
        1, не 2) — `assertEqual(2, ...)` откажет; либо сообщение теряет
        фактическую версию/путь/подсказку `venv-sync` — `assertIn`
        откажет.
        """
        missing_venv = Path(tempfile.mkdtemp()) / "venv"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf), \
             mock.patch.object(sys, "version_info", OLD_VERSION_INFO), \
             mock.patch.object(config, "VENV_DIR", missing_venv, create=True):
            with self.assertRaises(SystemExit) as ctx:
                importlib.reload(artel)
        self.assertEqual(2, ctx.exception.code)
        printed = buf.getvalue()
        self.assertIn(_required_python_text(), printed)
        self.assertIn("3.9", printed)
        self.assertIn(sys.executable, printed)
        self.assertIn("venv-sync", printed)


class Ac5MarkerPreventsReRecursionTest(_ArtelReloadTestCase):

    def test_ac5_marker_already_set_refuses_without_second_execv(self):
        """Маркер против рекурсии уже стоит в окружении процесса (взят
        из реального результата сценария AC-3, а не из угаданного
        имени — имя маркера не зафиксировано SPEC текстом), интерпретатор
        всё ещё старый, venv всё ещё пригоден: точка входа НЕ повторяет
        `os.execv`, а завершается тем же именованным отказом (AC-4) и
        кодом 2.

        Ловит мутацию: точка входа не проверяет маркер вовсе — второй
        прогон снова вызовет `os.execv` (уйдёт в бесконечную рекурсию в
        реальности) — `assertEqual([], ...)` откажет.
        """
        first_calls, _, before1, after1, first_exit = \
            _run_old_interpreter_with_ok_venv()
        self.assertIsNone(first_exit, "предпосылка: первый прогон обязан execv'ить")
        marker_env = {k: after1[k] for k in after1 if before1.get(k) != after1.get(k)}
        self.assertTrue(marker_env, "предпосылка: AC-3 обязан выставлять маркер")

        second_calls, _, _, _, second_exit = \
            _run_old_interpreter_with_ok_venv(extra_env=marker_env)
        self.assertEqual([], second_calls,
                         "маркер уже стоит — повторного os.execv быть не должно")
        self.assertIsInstance(second_exit, SystemExit)
        self.assertEqual(2, second_exit.code)


class Ac6ModernInterpreterPassthroughTest(_ArtelReloadTestCase):

    def test_ac6_modern_interpreter_runs_without_reexec(self):
        """Текущий интерпретатор не ниже `REQUIRED_PYTHON` (реальный
        интерпретатор песочницы, 3.13, версию не подменяем): точка входа
        не должна звать `os.execv` вовсе — работает как сегодня.

        Ловит мутацию: точка входа execv'ит безусловно (перепутанное
        условие сравнения версий) — подмена `os.execv` на исключение
        поймает лишний вызов.
        """
        with mock.patch.object(os, "execv", side_effect=AssertionError(
                "os.execv не должен вызываться для современного интерпретатора")):
            importlib.reload(artel)
        self.assertTrue(hasattr(artel, "main"))

    def test_ac6_interpreter_already_inside_dot_artel_venv_still_no_reexec(self):
        """То же самое (AC-6: «независимо от того, из `.artel/venv`
        запущен интерпретатор или нет») — даже если `sys.executable`
        указывает на путь ВНУТРИ `.artel/venv`, современная версия сама
        по себе не должна провоцировать перезапуск.

        Ловит мутацию: точка входа принимает решение по ПУТИ
        интерпретатора вместо его версии — лишний `os.execv` поймает
        подмена ниже.
        """
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = _make_fake_venv(Path(tmp))
            fake_running_path = str(venv_dir / "bin" / "python")
            with mock.patch.object(sys, "executable", fake_running_path), \
                 mock.patch.object(config, "VENV_DIR", venv_dir, create=True), \
                 mock.patch.object(os, "execv", side_effect=AssertionError(
                     "os.execv не должен вызываться — интерпретатор уже адекватен")):
                importlib.reload(artel)

    def test_ac6_role_step_python_field_format_is_unchanged(self):
        """AC-6, последняя оговорка: строка «окружение: python=…»
        журнала шага роли (`agent_log.environment_fingerprint`) не
        получает новых полей — ни маркера, ни venv-заметки.

        Ловит мутацию: `environment_fingerprint()` дописывает venv/
        маркер в python-часть строки — формат `python=<версия>
        (<путь>)` перестанет совпадать с шаблоном ровно из двух частей.
        """
        original_cache = agent_log._environment_fingerprint_cache
        agent_log._environment_fingerprint_cache = None
        try:
            text = agent_log.environment_fingerprint()
        finally:
            agent_log._environment_fingerprint_cache = original_cache
        python_part = text.split(", ")[0]
        self.assertRegex(python_part, r"^python=[^\s(]+ \([^)]+\)$")


class Ac7DoctorPythonCheckCarriesInterpreterAndVenvInfoTest(unittest.TestCase):

    def test_ac7_python_check_status_depends_only_on_version_not_on_venv(self):
        """Статус существующей проверки `python` (ok/warn) обязан
        остаться функцией ТОЛЬКО версии — не меняется от того, есть
        `.artel/venv` или нет (AC-7: «статус... при этом не меняется»).

        Ловит мутацию: добавление сведений о venv в проверку `python`
        заодно меняет её статус (например, отсутствие venv превращает
        `ok` в `warn`) — `assertEqual` статусов между двумя прогонами
        откажет.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys, "version_info", OLD_VERSION_INFO):
                existing_venv = Path(tmp) / "venv"
                existing_venv.mkdir()
                with mock.patch.object(config, "VENV_DIR", existing_venv, create=True):
                    checks_with_venv = stack.check_stack()
                missing_venv = Path(tmp) / "missing"
                with mock.patch.object(config, "VENV_DIR", missing_venv, create=True):
                    checks_without_venv = stack.check_stack()
        python_with = next(c for c in checks_with_venv if c.name == "python")
        python_without = next(c for c in checks_without_venv if c.name == "python")
        self.assertEqual("warn", python_with.status)
        self.assertEqual(python_with.status, python_without.status)

    def test_ac7_doctor_visible_checks_name_actual_interpreter_path_and_venv_presence(self):
        """Проверка стека `python`, видимая в выводе `doctor`
        (`stack.check_stack()` — её результат `doctor.all_checks`
        дословно расширяет своим списком, см. `checks.extend(stack.
        check_stack())`), обязана нести фактический путь интерпретатора
        (`sys.executable`) и факт существования `.artel/venv` где-то
        среди своих проверок.

        Ловит мутацию: сведения не добавлены вовсе — ни `sys.executable`,
        ни путь `.artel/venv` не встретятся ни в одном `detail`.
        """
        with tempfile.TemporaryDirectory() as tmp:
            existing_venv = Path(tmp) / "venv"
            existing_venv.mkdir()
            with mock.patch.object(config, "VENV_DIR", existing_venv, create=True), \
                 mock.patch.object(sys, "version_info", OK_VERSION_INFO):
                checks = stack.check_stack()
        combined = "\n".join(f"{c.name}:{c.detail}" for c in checks)
        self.assertIn(sys.executable, combined)
        self.assertIn(str(existing_venv), combined)


class Ac8ExecvCarriesMarkerAndOriginalEnvTest(_ArtelReloadTestCase):

    def test_ac8_reexec_env_keeps_original_variables_and_adds_marker(self):
        """Юнит-тест воспроизводит исход «старый интерпретатор + пригодный
        venv» и подтверждает, что `os.execv` уходит с ДОПОЛНЕННЫМ (не
        построенным с нуля) окружением: контрольная переменная,
        выставленная ДО прогона, обязана пережить его — маркер
        ДОБАВЛЯЕТСЯ, а не заменяет всё окружение.

        Ловит мутацию: реализация строит окружение для `execv` заново
        (например, только маркер плюс несколько ожидаемых переменных)
        вместо дополнения текущего `os.environ` — контрольная переменная
        пропадёт, `assertEqual` откажет.
        """
        sentinel_key, sentinel_value = "ARTEL_TEST_SENTINEL_AC8", "held"
        os.environ[sentinel_key] = sentinel_value
        try:
            execv_calls, _, before, after, exit_exc = \
                _run_old_interpreter_with_ok_venv()
        finally:
            os.environ.pop(sentinel_key, None)
        self.assertIsNone(exit_exc)
        self.assertEqual(1, len(execv_calls))
        self.assertEqual(sentinel_value, after.get(sentinel_key),
                         "execv обязан унаследовать текущее окружение процесса, "
                         "не только новый маркер")
        marker_keys = {k for k in after if before.get(k) != after.get(k)}
        self.assertTrue(marker_keys)


class Ac9RegressionOfExistingStackAndDoctorSuitesTest(unittest.TestCase):
    """Три исхода AC-9 («venv нет/непригоден» → именованный отказ+код 2,
    «маркер уже стоит» → отказ без повторного execv, «интерпретатор ≥
    минимума» → без перезапуска) — те же сценарии, что уже покрывают
    `Ac4NamedFailureWithoutUsableVenvTest`, `Ac5MarkerPreventsReRecursionTest`
    и `Ac6ModernInterpreterPassthroughTest` этого файла: не дублирую тот
    же мутационный охват под новым именем. Здесь — единственная НОВАЯ
    часть AC-9: существующие `tests/test_stack.py`/`tests/test_doctor.py`
    остаются зелёными без изменения ожидаемых ими статусов."""

    def test_ac9_existing_stack_and_doctor_suites_still_pass(self):
        """Прогон `tests/test_stack.py` и `tests/test_doctor.py` целиком
        под изменениями этой задачи обязан завершиться кодом 0.

        Ловит мутацию: правка `_python_check()`/`check_stack()`/
        структуры `all_checks()` меняет число проверок или чей-то
        существующий статус (ok/warn/fail) — соответствующий тест
        файлов упадёт, код возврата прогона станет ненулевым.
        """
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_stack", "tests.test_doctor"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=300)
        self.assertEqual(
            0, result.returncode,
            (result.stdout[-4000:] + "\n" + result.stderr[-4000:]))


if __name__ == "__main__":
    unittest.main()
