"""Класс отказа автогейта «окружение» (SPEC 01M5KBGF184B07SVXMD4R1NXXC).

Сторож после мержа задачи: планка задачи разовая, а классификатор
`fsm_autogate.autogate_refusal_class` держит начала текстов производителей
`acceptance.py` — смена текста таймаута или занятой машины там молча
выключила бы класс. Тесты сверяют классификатор с самими производителями
(не с литералами) и ветку отказа `_maybe_autogate_acceptance`: вторая
запись журнала и строка подсказки — только для класса «окружение».
"""
import contextlib
import io
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, fsm_autogate, gates, models, store, suite_lock
from tests.sandbox import SchemaConnTmpRootTest

TASK = "T001"
REFUSAL_ACTION = "автогейт acceptance не пройден"
HOLDER = {"kind": suite_lock.KIND_GATE, "task_id": "T777", "pid": 4242}


def _env_hint(kind: str) -> str:
    return (f"окружение ({kind}) — качество задачи не оценено; "
            f"повторить проверку: artel.py approve {TASK}")


class RefusalClassProducersTest(unittest.TestCase):

    def test_environment_producers_get_their_kind(self):
        """Таймаут прогона (умолчание и предел из профиля) и «машина занята»
        — свои виды, с префиксом автогейта и без, и вина за ними — пульта.
        Ловит мутацию: смена начала текста `_full_suite_timeout_note` или
        `_not_started_note` в `acceptance.py` без правки классификатора —
        таймаут или занятая машина дали бы `None`; префикс автогейта не
        снят — причина с префиксом дала бы `None`.
        """
        cases = [(acceptance._full_suite_timeout_note(), "таймаут прогона"),
                 (acceptance._full_suite_timeout_note(
                     (1500, "профиль тестов проекта artel")), "таймаут прогона"),
                 (acceptance._not_started_note(HOLDER), "машина занята")]
        for text, kind in cases:
            for reason in (text, models.AUTOGATE_REFUSAL_PREFIX + text):
                with self.subTest(reason=reason):
                    self.assertEqual(
                        fsm_autogate.autogate_refusal_class(reason), kind)
            self.assertEqual(
                models.autogate_refusal_blame(
                    models.AUTOGATE_REFUSAL_PREFIX + text), models.BLAME_PULT)

    def test_other_producers_are_not_environment(self):
        """Файлы БД пульта в дереве прогона, пустой tests/ и итог неизвестен
        — не «окружение».
        Ловит мутацию: сверка по одному `FULL_SUITE_NOT_STARTED` без
        «: машина занята» — отказ «файлы БД в дереве» получил бы вид
        «машина занята».
        """
        for text in (acceptance._db_in_tree_note(Path("/tmp/run"), TASK,
                                                 [".artel/state.db"]),
                     acceptance.FULL_SUITE_NO_TESTS_NOTE,
                     acceptance.UNKNOWN_PREFIX + "отчёт прогона не прочитан"):
            for reason in (text, models.AUTOGATE_REFUSAL_PREFIX + text):
                with self.subTest(reason=reason):
                    self.assertIsNone(fsm_autogate.autogate_refusal_class(reason))


class EnvRefusalRecordTest(SchemaConnTmpRootTest):

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, TASK, "Задача", "acceptance",
                          "task/t001-zadacha", "artel", 25.0)

    def refuse(self, reason: str):
        out = io.StringIO()
        t = store.get_task(self.conn, TASK)
        with mock.patch.object(gates, "policy", return_value=gates.AUTO), \
                mock.patch.object(fsm_autogate, "_log_acceptance_checklist"), \
                mock.patch.object(fsm_autogate, "_autogate_conditions",
                                  return_value=(["ok"], reason)), \
                mock.patch.object(fsm_autogate.models,
                                  "suspend_on_autogate_refusal") as suspend, \
                contextlib.redirect_stdout(out):
            fsm_autogate._maybe_autogate_acceptance(
                self.conn, TASK, t, Path(self.root), 1)
        steps = [(r["actor"], r["action"], r["detail"])
                 for r in store.task_steps(self.conn, TASK)]
        return out.getvalue().splitlines(), steps, suspend

    def test_environment_refusal_adds_record_and_hint(self):
        """Отказ по таймауту прогона: прежние запись и строка, следом запись
        `AUTOGATE_ENV_REFUSAL_ACTION` и строка подсказки, затем прежний
        вызов приостановки пары; задача остаётся в `acceptance`.
        Ловит мутацию: ветка отказа не зовёт классификатор (или пишет
        подсказку не тем текстом/действием) — второй записи и строки нет;
        вторая запись подменяет первую — прежней записи с причиной нет.
        """
        reason = models.AUTOGATE_REFUSAL_PREFIX + acceptance._full_suite_timeout_note()
        lines, steps, suspend = self.refuse(reason)
        hint = _env_hint("таймаут прогона")
        self.assertEqual(
            [s for s in steps if s[1] in (REFUSAL_ACTION,
                                          fsm_autogate.AUTOGATE_ENV_REFUSAL_ACTION)],
            [("fsm", REFUSAL_ACTION, reason),
             ("fsm", fsm_autogate.AUTOGATE_ENV_REFUSAL_ACTION, f"класс: {hint}")])
        start = lines.index(f"[{TASK}] {reason} — жду Оператора")
        self.assertEqual(lines[start + 1], f"[{TASK}] класс отказа: {hint}")
        suspend.assert_called_once()
        self.assertEqual(suspend.call_args.args[2], reason)
        self.assertEqual(store.task_state(self.conn, TASK), "acceptance")

    def test_other_refusal_has_no_environment_record(self):
        """Отказ вне класса (красный набор) — одна прежняя запись и одна
        строка, без записи и подсказки «окружения».
        Ловит мутацию: вторая запись пишется на любой отказ — запись
        `AUTOGATE_ENV_REFUSAL_ACTION` появилась бы и здесь.
        """
        reason = models.AUTOGATE_REFUSAL_PREFIX + "полный набор tests/ красный: 1 failed"
        lines, steps, _ = self.refuse(reason)
        self.assertEqual([s for s in steps if s[1] == REFUSAL_ACTION],
                         [("fsm", REFUSAL_ACTION, reason)])
        self.assertNotIn(fsm_autogate.AUTOGATE_ENV_REFUSAL_ACTION,
                         [s[1] for s in steps])
        self.assertEqual([ln for ln in lines if ln.startswith(f"[{TASK}] ")],
                         [f"[{TASK}] {reason} — жду Оператора"])
        self.assertEqual(store.task_state(self.conn, TASK), "acceptance")


if __name__ == "__main__":
    unittest.main()
