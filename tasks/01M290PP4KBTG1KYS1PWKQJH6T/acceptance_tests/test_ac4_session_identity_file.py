"""Приёмочный тест AC-4 задачи 01M290PP4KBTG1KYS1PWKQJH6T —
`session.resolve_session_id` без явного аргумента и без
`ARTEL_SESSION_ID` читает identity из файла сессии в `.artel/`, создавая
файл при первом обращении; порядок приоритета (явный аргумент >
`ARTEL_SESSION_ID` > файл > `ppid-<n>`-fallback) не меняется — меняется
только последний fallback.

Красен до реализации: `orchestrator/session.py::resolve_session_id`
сегодня не читает и не пишет никакой файл — `os.environ.get(
"ARTEL_SESSION_ID") or f"ppid-{os.getppid()}"` вычисляется заново на
КАЖДЫЙ вызов, поэтому второй вызов под другим (замоканным) `ppid`
возвращает ДРУГУЮ identity, а не ту же самую, прочитанную из файла —
тест «persists_identity_despite_ppid_change» ниже красен именно по этой
причине; первый тест («creates_a_file») красен тоже — `.artel/` в
пустой временной песочнице после вызова остаётся либо не существующим,
либо не содержит ни одного нового файла.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, session  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


def _dot_artel_files(root: Path) -> set:
    dot_artel = root / ".artel"
    if not dot_artel.exists():
        return set()
    return {str(p.relative_to(dot_artel)) for p in dot_artel.rglob("*")
            if p.is_file()}


def _env_without_session_var() -> dict:
    env = dict(os.environ)
    env.pop("ARTEL_SESSION_ID", None)
    return env


class SessionIdentityFileTest(TmpRootTest):

    def test_ac4_first_access_creates_a_file_under_dot_artel(self):
        """Первое обращение без аргумента и без переменной окружения —
        `.artel/` временной песочницы (`config.ROOT`, патчен `TmpRootTest`)
        приобретает НОВЫЙ файл, которого не было до вызова; вернувшаяся
        identity — прежний `ppid-<pid родителя>`-fallback (файла ещё не
        было В МОМЕНТ вызова).

        Ловит мутацию: `resolve_session_id` продолжает читать только
        `ARTEL_SESSION_ID`/`os.getppid()`, не касаясь диска — множество
        файлов `.artel/` до и после вызова совпадает, `assertTrue` по
        разнице множеств покраснеет.
        """
        before = _dot_artel_files(config.ROOT)

        with mock.patch.dict(os.environ, _env_without_session_var(),
                             clear=True):
            result = session.resolve_session_id(None)

        self.assertEqual(result, f"ppid-{os.getppid()}")

        after = _dot_artel_files(config.ROOT)
        self.assertTrue(
            after - before,
            "обращение без аргумента/переменной не завело ни одного "
            "нового файла в .artel/")

    def test_ac4_second_call_reads_persisted_identity_despite_ppid_change(self):
        """Второй вызов (без аргумента, без переменной) под ДРУГИМ
        (замоканным) `ppid`, чем первый, возвращает ТУ ЖЕ identity, что и
        первый вызов — она прочитана из файла, заведённого первым
        обращением, не пересчитана заново из живого `os.getppid()`. Это
        и есть механизм, которым отвязанный цикл `auto` (другой `ppid`
        после отвязки) и `watch --mine` той же сессии видят одну и ту же
        identity (AC-5).

        Ловит мутацию: `resolve_session_id` не персистирует identity
        (каждый вызов заново вычисляет `ppid-{os.getppid()}` без файла) —
        второй вызов вернёт `ppid-222`, отличный от первого `ppid-111`,
        `assertEqual(second, first)` покраснеет.
        """
        with mock.patch.dict(os.environ, _env_without_session_var(),
                             clear=True):
            with mock.patch("os.getppid", return_value=111):
                first = session.resolve_session_id(None)
            with mock.patch("os.getppid", return_value=222):
                second = session.resolve_session_id(None)

        self.assertEqual(first, "ppid-111")
        self.assertEqual(second, first,
                         "вторая identity не совпала с первой — файл "
                         "сессии не перечитан, использован живой ppid")

    def test_ac4_explicit_argument_and_env_var_still_beat_the_file(self):
        """Файл сессии уже существует (заведён предыдущим обращением) —
        явный аргумент и `ARTEL_SESSION_ID` по-прежнему СИЛЬНЕЕ файла:
        порядок приоритета не поменялся, поменялся только последний
        fallback.

        Ловит мутацию: приоритет источников переставлен так, что файл
        читается РАНЬШЕ явного аргумента/переменной окружения — обе
        проверки ниже вернули бы identity из файла вместо явного
        значения, оба `assertEqual` покраснеют.
        """
        with mock.patch.dict(os.environ, _env_without_session_var(),
                             clear=True):
            file_identity = session.resolve_session_id(None)

            self.assertEqual(
                session.resolve_session_id("явный-аргумент"),
                "явный-аргумент")
            self.assertNotEqual("явный-аргумент", file_identity)

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "env-value"}):
            self.assertEqual(session.resolve_session_id(None), "env-value")
            self.assertNotEqual("env-value", file_identity)


if __name__ == "__main__":
    unittest.main()
