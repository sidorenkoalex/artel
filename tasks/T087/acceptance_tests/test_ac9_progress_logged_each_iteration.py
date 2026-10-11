"""AC-9 (tasks/T087/SPEC.md): каждая итерация цикла ожидания записывает
в журнал задачи (`store.journal`) и печатает в консоль текущий статус CI
и прошедшее время ожидания.

Источник — tasks/T087/SPEC.md, «Критерии приёмки», AC-9.

Точный формат записи SPEC не называет (только «текущий статус CI и
прошедшее время ожидания») — тест ищет узнаваемые фрагменты статуса
(дословный текст `note`, который вернул замоканный `ci.branch_status`
— единственный источник текста статуса, который в принципе может
попасть в журнал/консоль) и наличие числового индикатора прошедшего
времени (последовательность цифр — секунды, минуты, что угодно
числовое) в записи КАЖДОЙ непоследней итерации, не только факт хоть
одной записи вообще.

Красен до реализации: сегодня после "pulled" `approve` останавливается
СРАЗУ единственным сообщением ("дождись зелёного CI... и повтори"),
`ci.branch_status` не вызывается в этом вызове вовсе — журнал не
получает ни одной записи со статусом "ещё идёт"/"неизвестен", а
`assertGreaterEqual(calls, 2)` ниже ловит это явно.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import GREEN, MergeGateCiWaitTest, RUNNING, UNKNOWN  # noqa: E402

# Не просто "есть цифра где-то" (заметки статуса и так несут цифры —
# "abc12345") — узнаваемая форма прошедшего времени: "число + единица
# времени" (тот же формат, каким остальной код пульта уже описывает
# длительность — `orchestrator/merge_lock.py`: "heartbeat {age} сек
# назад") либо часы:минуты[:секунды]. SPEC не называет точный формат —
# полоса допуска пошире буквальной "сек", чтобы не навязать разработчику
# конкретное слово, которого критерий не требует.
ELAPSED_TIME = re.compile(
    r"\d+\s*(сек|мин|час|min|sec|hour)|\d{1,3}:\d{2}(:\d{2})?", re.IGNORECASE)


class Ac9ProgressLoggedEachIterationTest(MergeGateCiWaitTest):

    def setUp(self):
        super().setUp()
        self.enter_merge_gate()

    def test_ac9_journal_and_console_carry_status_and_elapsed_time(self):
        self.add_main_commit()
        sequence = [RUNNING, UNKNOWN, GREEN]
        calls = {"n": 0}

        def sequenced(branch):
            resp = sequence[min(calls["n"], len(sequence) - 1)]
            calls["n"] += 1
            return resp

        self.patch_branch_status(sequenced)

        console_out = self.approve()

        self.assertGreaterEqual(
            calls["n"], 2,
            f"предпосылка теста: обязаны быть прочитаны хотя бы две "
            f"непоследние итерации (идёт/неизвестен), фактически "
            f"{calls['n']}")

        journal = self.journal_blob()
        for note in (RUNNING[1], UNKNOWN[1]):
            self.assertIn(
                note.lower(), journal,
                f"AC-9: журнал задачи обязан нести текущий статус CI "
                f"каждой итерации ожидания ({note!r} не найден в "
                f"журнале); журнал: {journal!r}")
        self.assertTrue(
            ELAPSED_TIME.search(journal),
            f"AC-9: журнал обязан нести прошедшее время ожидания в виде "
            f"«число + единица времени» (сек/мин); журнал: {journal!r}")

        console_lower = console_out.lower()
        for note in (RUNNING[1], UNKNOWN[1]):
            self.assertIn(
                note.lower(), console_lower,
                f"AC-9: консоль обязана печатать текущий статус CI "
                f"каждой итерации ожидания ({note!r} не найден в выводе); "
                f"вывод: {console_out!r}")
        self.assertTrue(
            ELAPSED_TIME.search(console_out),
            f"AC-9: консоль обязана печатать прошедшее время ожидания в "
            f"виде «число + единица времени» (сек/мин); вывод: "
            f"{console_out!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
