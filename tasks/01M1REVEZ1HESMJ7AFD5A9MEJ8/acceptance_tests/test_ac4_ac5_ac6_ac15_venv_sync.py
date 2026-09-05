"""AC-4, AC-5, AC-6, AC-15 (tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/SPEC.md,
требования 2, 6): `orchestrator.venv.sync()` создаёт `.artel/venv`
средствами стандартной библиотеки, идемпотентно, тем же интерпретатором,
что и сам пульт.

Красен до реализации: `orchestrator.venv` ещё не существует — импорт
падает `ModuleNotFoundError` для всех тестов ниже.

Контракт, который этой планкой фиксируется за разработчика (SPEC не
называет модуль/функцию буквально, кроме CLI `artel.py venv-sync`):
`orchestrator.venv.sync(target: Path, lock_file: Path) -> None` —
создаёт venv В `target` командой `subprocess.run([sys.executable, "-m",
"venv", str(target)], ...)`, если он ещё не похож на venv (нет
`pyvenv.cfg`), затем ставит зависимости командой `subprocess.run([...,
"install", "-r", str(lock_file)], ...)`.

Сеть в тестах запрещена (docs/invariants.md, инвариант 35; SPEC,
требование 6): подмена `orchestrator.venv.subprocess.run` — ТОЛЬКО ветку
`pip install` (полностью фейковая, без сети); ветка `python -m venv`
пропускается к НАСТОЯЩЕМУ `subprocess.run` — сама по себе offline
(стандартная библиотека, `ensurepip` использует локально вшитые wheel'ы,
сети не касается), и только так тест может честно проверить AC-4/AC-5/
AC-6 наблюдением РЕАЛЬНОГО артефакта venv на диске, а не веры в
зафиксированный вызов.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import venv as artel_venv  # noqa: E402

REAL_RUN = subprocess.run


def _is_venv_creation_call(args: list) -> bool:
    return len(args) >= 3 and args[1:3] == ["-m", "venv"]


def _make_fake_run(creation_calls: list, pip_calls: list):
    def fake_run(args, **kwargs):
        args = list(args)
        if _is_venv_creation_call(args):
            creation_calls.append(args)
            return REAL_RUN(args, **kwargs)
        pip_calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")
    return fake_run


class VenvSyncTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.target = root / ".artel" / "venv"
        self.lock_file = root / "requirements.lock"
        self.lock_file.write_text("pytest==7.4.4\n", encoding="utf-8")

    def _sync(self):
        creation_calls, pip_calls = [], []
        with mock.patch.object(artel_venv.subprocess, "run",
                               side_effect=_make_fake_run(creation_calls,
                                                          pip_calls)):
            artel_venv.sync(target=self.target, lock_file=self.lock_file)
        return creation_calls, pip_calls

    def test_ac4_sync_creates_a_real_venv_via_stdlib_and_installs_from_the_lock_file(self):
        """Требование 2/AC-4: команда пульта создаёт `.artel/venv`
        средствами стандартной библиотеки (`python3 -m venv` — здесь
        РЕАЛЬНЫЙ вызов, не мок) и ставит зависимости из файла закреплённых
        версий (мок, без сети).

        Ловит мутацию: `sync()` не вызывает создание venv вовсе (только
        имитирует установку) — на диске не появится `pyvenv.cfg`,
        `assertTrue(exists)` откажет; либо установка не ссылается на
        файл закреплённых версий (например захардкожен список пакетов
        вместо `-r <файл>`) — `assertIn(str(self.lock_file), ...)`
        откажет.
        """
        creation_calls, pip_calls = self._sync()

        self.assertTrue(
            (self.target / "pyvenv.cfg").exists(),
            f"после sync() в {self.target} нет pyvenv.cfg — venv не "
            f"создан по-настоящему")
        self.assertTrue(creation_calls, "sync() не вызвал `python -m venv`")
        self.assertTrue(pip_calls, "sync() не вызвал установку пакетов")
        install_call = pip_calls[0]
        self.assertIn("install", install_call)
        self.assertIn(str(self.lock_file), install_call,
                     f"установка не ссылается на файл закреплённых "
                     f"версий: {install_call}")

    def test_ac5_second_call_on_an_existing_venv_is_idempotent(self):
        """Требование 2/AC-5: повторный вызов `sync()` на уже созданном
        `.artel/venv` НЕ пересоздаёт его и не завершается ошибкой.

        Ловит мутацию: `sync()` безусловно зовёт `python -m venv` заново
        при каждом вызове (не проверяет `pyvenv.cfg`) — второй вызов
        добавит ещё одну запись в `creation_calls`, `assertEqual(1, ...)`
        откажет; либо повторный вызов на существующем venv поднимает
        исключение — `sync()` во втором `with` его не проглотит.
        """
        first_creation, _first_pip = self._sync()
        self.assertEqual(1, len(first_creation))

        second_creation, _second_pip = self._sync()

        self.assertEqual(
            0, len(second_creation),
            f"второй вызов sync() на уже созданном venv снова вызвал "
            f"`python -m venv`: {second_creation}")

    def test_ac6_the_venv_is_created_with_the_pult_own_interpreter(self):
        """Требование 2/AC-6: интерпретатор `.artel/venv` — ТОТ ЖЕ
        `sys.executable`, которым запущен сам пульт (не «python3» из
        PATH, который на многоверсийной машине может указывать на другой
        интерпретатор).

        Ловит мутацию: команда создания собрана как `["python3", "-m",
        "venv", ...]` (имя из PATH) вместо `[sys.executable, "-m",
        "venv", ...]` — `assertEqual` по первому элементу откажет.
        """
        creation_calls, _pip_calls = self._sync()

        self.assertEqual(
            sys.executable, creation_calls[0][0],
            f"venv создан не тем же интерпретатором, что сам пульт: "
            f"{creation_calls[0]}")

    def test_ac15_the_install_command_is_exactly_pip_install_dash_r_lock_file(self):
        """Требование 6/AC-15: тест проверяет СОСТАВ вызванной команды
        установки — `pip install -r <файл>`, без сети (мок).

        Ловит мутацию: установка собрана без флага `-r` (например
        разработчик передал путь файла позиционным аргументом без флага,
        и pip читает его как имя пакета) — `assertIn("-r", ...)` откажет;
        либо `install` и `-r <файл>` не идут рядом одной командой (два
        раздельных вызова, из которых ни один не несёт обоих) —
        `assertIn` на полном списке аргументов откажет.
        """
        _creation_calls, pip_calls = self._sync()

        self.assertEqual(1, len(pip_calls),
                         f"ожидался ровно один вызов установки: {pip_calls}")
        install_call = pip_calls[0]
        self.assertIn("install", install_call)
        self.assertIn("-r", install_call)
        self.assertIn(str(self.lock_file), install_call)
        # `-r` обязан идти НЕПОСРЕДСТВЕННО перед путём файла (иначе это
        # не флаг для НЕГО) — та же проверка, что уже читаемое требование
        # «pip install -r <файл>» дословно, не «где-то в аргументах».
        r_index = install_call.index("-r")
        self.assertEqual(
            str(self.lock_file), install_call[r_index + 1],
            f"`-r` не сопровождается путём файла закреплённых версий "
            f"сразу следующим аргументом: {install_call}")


if __name__ == "__main__":
    unittest.main()
