"""AC-1, AC-2: отказ автогейта класса «окружение» — вторая запись журнала
и вторая строка вывода вслед за прежними.

Группа: разовый
Красен до реализации: ветка отказа `_maybe_autogate_acceptance` пишет одну запись и одну строку — записи «автогейт acceptance: отказ окружения» и строки «класс отказа: окружение» нет.

Группа «разовый» — вынужденно: сценарий критериев сам называет закрытые
имена (`_autogate_conditions` подменяется, причина строится от
`acceptance._full_suite_timeout_note`/`_not_started_note`), а статика
долгоживущего файла `tests/` закрытые имена запрещает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import acceptance, fsm_autogate, suite_lock  # noqa: E402

from _scenario import (DIGEST, ENV_ACTION_TEXT, REFUSAL_ACTION,  # noqa: E402
                       RefusalSandbox, env_detail, env_line, refusal_line)


class EnvRefusalRecordTest(RefusalSandbox):

    def _check_env_refusal(self, reason: str, kind: str):
        out, _suspend = self.refuse(reason)

        actions = self.actions()
        refusals = [i for i, a in enumerate(actions) if a[1] == REFUSAL_ACTION]
        self.assertEqual(len(refusals), 1, actions)
        i = refusals[0]
        self.assertEqual(actions[i], ("fsm", REFUSAL_ACTION, reason))
        self.assertGreater(len(actions), i + 1, actions)
        self.assertEqual(actions[i + 1],
                         ("fsm", ENV_ACTION_TEXT, env_detail(kind)), actions)

        self.assertEqual(out.splitlines(),
                         [refusal_line(reason), env_line(kind)], out)
        self.assert_stays_in_acceptance()

    def test_ac1_timeout_refusal_adds_env_record_and_line(self):
        """Таймаут прогона с выжимкой — две записи журнала и две строки.

        Причина «автогейт: <текст таймаута прогона>: <выжимка> (лог …)»:
        прежняя запись «автогейт acceptance не пройден» с причиной в
        детали, следом запись `AUTOGATE_ENV_REFUSAL_ACTION` (actor `fsm`)
        с деталью «класс: окружение (таймаут прогона) — …approve T001»;
        вывод — прежняя строка «— жду Оператора» и за ней строка «класс
        отказа: окружение (таймаут прогона) — …»; задача в `acceptance`.
        Ловит мутацию: вид классификатора, сверенный не с началом текста
        таймаута (например, только с «прогон не начат») — второй записи
        и второй строки не было бы; деталь, перепутавшая вид («машина
        занята») или без имени задачи в подсказке approve — иное
        значение детали и строки.
        """
        self.assertEqual(
            getattr(fsm_autogate, "AUTOGATE_ENV_REFUSAL_ACTION", None),
            ENV_ACTION_TEXT)
        reason = "автогейт: " + acceptance._full_suite_timeout_note() + DIGEST
        self._check_env_refusal(reason, "таймаут прогона")

    def test_ac2_machine_busy_refusal_adds_env_record_and_line(self):
        """Машина занята — две записи журнала и две строки с видом «машина занята».

        Причина «автогейт: прогон не начат: машина занята прогоном гейта
        задачи T002 (pid 4242) — …» (держатель замка — гейт другой
        задачи): вторая запись `AUTOGATE_ENV_REFUSAL_ACTION` с деталью
        «класс: окружение (машина занята) — …», вторая строка вывода тем
        же текстом, задача остаётся в `acceptance`.
        Ловит мутацию: классификатор, знающий только таймаут прогона, —
        на занятой машине второй записи и строки нет; запись, вставленная
        ДО прежней (порядок «окружение, затем отказ») — следом за
        «автогейт acceptance не пройден» оказалась бы не она.
        """
        holder = {"kind": suite_lock.KIND_GATE, "task_id": "T002",
                  "pid": 4242}
        reason = "автогейт: " + acceptance._not_started_note(holder)
        self._check_env_refusal(reason, "машина занята")


if __name__ == "__main__":
    unittest.main()
