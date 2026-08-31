"""Приёмочные тесты T074 — AC-9.

Источник — tasks/T074/SPEC.md, «Критерии приёмки».

AC-9. Аварийное завершение агентного шага (rc != 0 или обрыв потока
агента) с грязным деревом worktree порождает WIP-чекпоинт с пометкой
причины — расширение правила T041 не только на таймаут; пометка стоит и
в коммите, и в журнале.

До T074 `tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py::
test_ac3_return_code_failure_does_not_checkpoint` фиксировал ПРОТИВОПОЛОЖНОЕ
поведение (rc != 0 НЕ коммитит чекпоинт) — это не противоречие, а именно
то расширение правила, которое явно называет SPEC T074, требование 3
(«правило чекпоинта WIP (T041) расширяется... не только при таймауте, но
и при аварийном завершении шага»): старый тест кодировал правило ДО этой
задачи, этот — правило ПОСЛЕ неё. Оба сценария (rc != 0 и обрыв потока)
тем же приёмом, что `tasks/T040/acceptance_tests/
test_step_cost_on_missing_final_event.py` (`FailedProc`/`BrokenPipeStream`),
и той же песочницей настоящего git worktree, что `tasks/T041/
acceptance_tests` (заглушкой `gitcmd.git` чекпоинт не проверить).

Пометка причины проверяется ТОЛЬКО в сообщении коммита-чекпоинта и в
записях журнала actor=orchestrator (`orchestrator_journal`) — не по
всему тексту журнала целиком: у обрыва потока СЕГОДНЯ уже существует
не связанная с чекпоинтом запись «agent log INCOMPLETE» (actor=роль,
не orchestrator, `close_pump`, SPEC T040) с текстом «обрыв stdout-пайпа»
— совпадение по ключевому слову с ней дало бы зелёный тест ДО реализации
этой задачи (ложноположительный, поймано прогоном на немодифицированном
коде при подготовке этого файла). Чекпоинт — действие оркестратора
(тот же довод, что `commit_timeout_checkpoint`), поэтому его пометка
причины ищется именно там.

Красен до реализации: сегодняшний код (`orchestrator/runner.py`) не
чекпоинтит WIP при rc != 0/обрыве потока — рабочее дерево останется
грязным после прогона (для варианта rc != 0), и тест провалится по
`assertTrue(is_clean)`; для варианта обрыва потока дерево сегодня
случайно чистое (существующий автокоммит успеха, T059, безусловно
срабатывающий на rc=0), но новой пометки причины «аварийного
завершения» в actor=orchestrator записи нет вовсе — тест провалится по
отсутствию новой пометки чекпоинта в этой записи.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import InterruptSandbox, runner  # noqa: E402

from orchestrator import config  # noqa: E402


class FakeStream:
    def __init__(self, lines):
        self.lines = iter(lines)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        self.closed = True


class BrokenPipeStream(FakeStream):
    """Обрыв stdout-пайпа посреди чтения (T040) — `OSError` вместо
    чистого EOF."""

    def __next__(self) -> str:
        try:
            return next(self.lines)
        except StopIteration:
            raise OSError("обрыв stdout-пайпа шага") from None


class FailedProc:
    """Провал по коду возврата (не таймаут): `wait()` сразу отдаёт
    ненулевой `returncode`, оставив WIP до этого."""

    def __init__(self, lines, returncode, leaves_wip=None):
        self.stdout = FakeStream(lines)
        self.returncode = returncode
        self._leaves_wip = leaves_wip

    def wait(self, timeout=None) -> int:
        if self._leaves_wip:
            self._leaves_wip()
        return self.returncode

    def kill(self) -> None:
        pass


class BrokenPipeProc:
    """Обрыв потока: процесс сам завершается rc=0, но пайп рвётся
    посреди чтения — `pump.error` фиксирует обрыв (T040)."""

    def __init__(self, lines, leaves_wip=None):
        self.stdout = BrokenPipeStream(lines)
        self.returncode = 0
        self._leaves_wip = leaves_wip

    def wait(self, timeout=None) -> int:
        if self._leaves_wip:
            self._leaves_wip()
        return self.returncode

    def kill(self) -> None:
        pass


class CheckpointOnAbnormalStepEndTest(InterruptSandbox):

    def run_agent(self, proc):
        with mock.patch.object(runner, "spawn_agent", return_value=proc), \
                mock.patch.object(runner.time, "sleep", lambda _: None):
            return self.capture(runner.cmd_run, self.TASK)

    def orchestrator_journal_text(self) -> str:
        return "\n".join(f"{r['action']} | {r['detail']}"
                         for r in self.orchestrator_journal())

    def checkpoint_marker_text(self) -> str:
        """Сообщение коммита-чекпоинта + записи журнала actor=orchestrator
        одной строкой — область поиска пометки причины (AC-9), НЕ весь
        журнал целиком (см. докстринг модуля)."""
        subject = self.git_in_worktree("log", "-1", "--format=%s").strip()
        return f"{subject}\n{self.orchestrator_journal_text()}".lower()

    def test_ac9_return_code_failure_with_dirty_tree_creates_checkpoint(self):
        self.enter_in_dev()
        before = self.head()

        with mock.patch.object(config, "AGENT_ATTEMPTS", 1):
            out = self.run_agent(FailedProc(
                ["падаю с кодом возврата\n"], returncode=1,
                leaves_wip=self.write_dirty_wip))

        self.assertNotEqual(
            self.head(), before,
            f"AC-9: аварийное завершение (rc != 0) с грязным деревом "
            f"обязано породить новый коммит-чекпоинт — вывод run: {out!r}")
        self.assertEqual(
            self.git_in_worktree("status", "--porcelain").strip(), "",
            f"AC-9: рабочее дерево worktree задачи обязано стать чистым "
            f"после аварийного завершения (rc != 0) — вывод run: {out!r}")
        marker = self.checkpoint_marker_text()
        self.assertIn(
            "чекпоинт", marker,
            f"AC-9: коммит-чекпоинт обязан быть узнаваем как чекпоинт "
            f"(та же природа, что и чекпоинт таймаута T041), не как "
            f"обычный автокоммит артефактов успеха — фактически: "
            f"{marker!r}")
        self.assertTrue(
            "аварийн" in marker or "rc=" in marker or "провал" in marker
            or "упал" in marker or "код возврата" in marker,
            f"AC-9: коммит-чекпоинт и/или запись журнала orchestrator "
            f"обязаны нести пометку причины аварийного завершения — "
            f"фактически: {marker!r}")

    def test_ac9_stream_break_with_dirty_tree_creates_checkpoint(self):
        self.enter_in_dev()
        before = self.head()

        with mock.patch.object(config, "AGENT_ATTEMPTS", 1):
            out = self.run_agent(BrokenPipeProc(
                ["агент начал работу\n"], leaves_wip=self.write_dirty_wip))

        self.assertEqual(
            self.git_in_worktree("status", "--porcelain").strip(), "",
            f"AC-9: рабочее дерево worktree задачи обязано стать чистым "
            f"после обрыва потока агента — вывод run: {out!r}")
        marker = self.checkpoint_marker_text()
        self.assertIn(
            "чекпоинт", marker,
            f"AC-9: коммит-чекпоинт обязан быть узнаваем как чекпоинт "
            f"причины «обрыв потока», не как обычный успешный "
            f"автокоммит артефактов (T059, который безусловно коммитит "
            f"WIP на rc=0 и без новой пометки был бы неотличим от этого "
            f"критерия) — до этой задачи новый коммит {self.head()!r} "
            f"отличался от {before!r}, но не нёс слова «чекпоинт»; "
            f"фактически: {marker!r}")
        self.assertTrue(
            "обрыв" in marker or "поток" in marker,
            f"AC-9: коммит-чекпоинт и/или запись журнала orchestrator "
            f"обязаны нести пометку причины обрыва потока — фактически: "
            f"{marker!r}")


if __name__ == "__main__":
    unittest.main()
