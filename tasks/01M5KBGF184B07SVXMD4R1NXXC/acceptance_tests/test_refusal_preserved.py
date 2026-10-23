"""AC-3, AC-4, AC-5: прежнее поведение отказа автогейта сохраняется.

Группа: разовый
Зелёный с рождения: критерии держат прежнее поведение — одна запись и одна строка на отказ вне класса «окружение», прежний вызов приостановки пары и прежний читатель канарейки; задача обязана их не сломать.

Группа «разовый» — вынужденно: сценарий критериев называет закрытые имена
(`_autogate_conditions`, `acceptance._db_in_tree_note`,
`canary._acceptance_from_steps`), а статика долгоживущего файла `tests/`
закрытые имена запрещает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import acceptance, canary, models, suite_lock  # noqa: E402

from _scenario import (DIGEST, ENV_ACTION_TEXT, REFUSAL_ACTION,  # noqa: E402
                       RefusalSandbox, refusal_line)


def _non_env_reasons() -> list[str]:
    return [
        "автогейт: " + acceptance._db_in_tree_note(
            Path("/tmp/run-tree"), "T001", [".artel/state.db"]),
        "автогейт: " + acceptance.FULL_SUITE_NO_TESTS_NOTE,
        "автогейт: полный набор tests/ красный: 3 failed, 117 passed",
        "автогейт: критерии manual — AC-1 (визуальная проверка)",
        "автогейт: бюджет задачи исчерпан",
        "автогейт: " + acceptance.UNKNOWN_PREFIX + "отчёт прогона не прочитан",
    ]


class NonEnvRefusalUnchangedTest(RefusalSandbox):

    def test_ac3_non_env_refusal_keeps_single_record_and_line(self):
        """Шесть причин вне класса «окружение» — журнал и вывод прежние.

        Для файлов БД в дереве прогона, отсутствия tests/, красного
        набора, критериев manual, исчерпанного бюджета и итога
        неизвестного: записи «автогейт acceptance: отказ окружения» нет,
        запись «автогейт acceptance не пройден» с причиной — ровно одна,
        вывод — ровно строка «[T001] <причина> — жду Оператора», задача
        в `acceptance`.
        Ловит мутацию: классификатор по подстроке «прогон не начат» без
        «: машина занята» (файлы БД в дереве начинаются тем же
        «прогон не начат: ») или по вхождению «tests/» — для этих причин
        появилась бы вторая запись и вторая строка.
        """
        for reason in _non_env_reasons():
            with self.subTest(reason=reason):
                out, _suspend = self.refuse(reason)
                actions = self.actions()
                self.assertNotIn(ENV_ACTION_TEXT, [a[1] for a in actions])
                self.assertEqual(
                    [a for a in actions
                     if a[1] == REFUSAL_ACTION and a[2] == reason],
                    [("fsm", REFUSAL_ACTION, reason)])
                self.assertEqual(out.splitlines(), [refusal_line(reason)])
                self.assert_stays_in_acceptance()


class EnvRefusalSuspendCallTest(RefusalSandbox):

    def test_ac4_env_refusal_calls_suspend_once_with_reason(self):
        """Отказ класса «окружение» зовёт приостановку пары один раз прежней причиной.

        Причины таймаута прогона и занятой машины: подменённый
        `models.suspend_on_autogate_refusal` вызван ровно один раз, его
        причина — та же строка, что в детали записи «автогейт acceptance
        не пройден»; правило вины относит её к `BLAME_PULT`.
        Ловит мутацию: в ветке «окружение» `return` до вызова приостановки
        (вызовов 0) или вызов с деталью новой записи вместо причины
        (аргумент — «класс: окружение …»).
        """
        holder = {"kind": suite_lock.KIND_SUITE_RUN, "task_id": "T002",
                  "pid": 77}
        for reason in ("автогейт: " + acceptance._full_suite_timeout_note()
                       + DIGEST,
                       "автогейт: " + acceptance._not_started_note(holder)):
            with self.subTest(reason=reason):
                _out, suspend = self.refuse(reason)
                self.assertEqual(suspend.call_count, 1, suspend.call_args_list)
                args = suspend.call_args.args
                self.assertEqual(args[-1], reason)
                details = [a[2] for a in self.actions()
                           if a[1] == REFUSAL_ACTION]
                self.assertEqual(details[-1], args[-1])
                self.assertEqual(models.autogate_refusal_blame(reason),
                                 models.BLAME_PULT)


class CanaryReaderTest(RefusalSandbox):

    def test_ac5_canary_reads_original_refusal_detail(self):
        """Читатель канарейки по журналу отказа «окружение» видит прежнюю причину.

        После отказа таймаутом прогона `canary._acceptance_from_steps`
        журнала задачи возвращает причиной деталь записи «автогейт
        acceptance не пройден», а не деталь второй записи.
        Ловит мутацию: вторая запись под тем же действием «автогейт
        acceptance не пройден» (вместо своего) — читатель взял бы
        последнюю, «класс: окружение (таймаут прогона) — …».
        """
        reason = "автогейт: " + acceptance._full_suite_timeout_note() + DIGEST
        self.refuse(reason)
        _route, refusal, _reached = canary._acceptance_from_steps(self.steps())
        self.assertEqual(refusal, reason)


if __name__ == "__main__":
    unittest.main()
