"""AC-6: классификатор отказа автогейта сверен с текстами производителей.

Группа: разовый
Красен до реализации: функции `fsm_autogate.autogate_refusal_class` ещё нет — обращение к ней падает AttributeError.

Группа «разовый» — вынужденно: критерий сверяет классификатор с закрытыми
производителями текстов (`acceptance._full_suite_timeout_note`,
`_not_started_note`, `_db_in_tree_note`), а статика долгоживущего файла
`tests/` закрытые имена запрещает.
"""
import random
import unittest
from pathlib import Path

from orchestrator import acceptance, appendix_tree, fsm_autogate, models, suite_lock

TIMEOUT = "таймаут прогона"
BUSY = "машина занята"


def _holders(rng: random.Random) -> list[dict]:
    pid = rng.randint(2, 99999)
    task = f"T{rng.randint(100, 999)}"
    return [{"kind": suite_lock.KIND_GATE, "task_id": task, "pid": pid},
            {"kind": suite_lock.KIND_SUITE_RUN, "task_id": task, "pid": pid},
            {"kind": suite_lock.KIND_NOTES, "pid": pid}]


def _warning_tree() -> appendix_tree.SuiteTree:
    return appendix_tree.SuiteTree(root=Path("/tmp/run"), note="", refusal="",
                                   warning="PLAN.md не читается с ветки x")


class RefusalClassProducersTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def _cases(self):
        rng = self.rng
        limit = (rng.randint(60, 7200), "профиль тестов проекта artel")
        env = [(acceptance._full_suite_timeout_note(), TIMEOUT),
               (acceptance._full_suite_timeout_note((1500, "профиль тестов "
                                                     "проекта artel")), TIMEOUT),
               (acceptance._full_suite_timeout_note(limit), TIMEOUT)]
        for holder in _holders(rng):
            note = acceptance._not_started_note(holder)
            env.append((note, BUSY))
            env.append((_warning_tree().mark(note), BUSY))
        none = [acceptance._db_in_tree_note(Path("/tmp/run"), "T001",
                                            [".artel/state.db"]),
                acceptance.FULL_SUITE_NO_TESTS_NOTE,
                acceptance.UNKNOWN_PREFIX + "отчёт прогона не прочитан"]
        return env, none

    def test_ac6_refusal_class_matches_producers(self):
        """Тексты таймаута и занятой машины — свои виды; прочие исходы — `None`.

        Таймаут прогона (умолчание, предел 1500 с источником «профиль
        тестов проекта artel», случайный предел) — «таймаут прогона»;
        «прогон не начат: машина занята …» для держателей гейта,
        suite-run и notes, в том числе с суффиксом «[без приложений PLAN:
        …]» `appendix_tree` — «машина занята»; каждое — с префиксом
        `models.AUTOGATE_REFUSAL_PREFIX` и без. Файлы БД пульта в дереве
        прогона, отсутствие tests/ и итог неизвестен — `None`. Для причин
        «окружения» правило вины — `BLAME_PULT`.
        Ловит мутацию: сверка «прогон не начат» без «: машина занята» —
        файлы БД в дереве (тот же префикс исхода) получили бы «машина
        занята»; префикс автогейта не снят — причины с префиксом дали бы
        `None`; сверка таймаута литералом с иным числом/источником —
        отличный от умолчания предел дал бы `None`.
        """
        env, none = self._cases()
        prefix = models.AUTOGATE_REFUSAL_PREFIX
        for text, kind in env:
            for reason in (text, prefix + text):
                with self.subTest(reason=reason, seed=self.seed):
                    self.assertEqual(fsm_autogate.autogate_refusal_class(reason),
                                     kind, f"зерно: {self.seed}")
            with self.subTest(blame=text, seed=self.seed):
                self.assertEqual(models.autogate_refusal_blame(prefix + text),
                                 models.BLAME_PULT, f"зерно: {self.seed}")
        for text in none:
            for reason in (text, prefix + text):
                with self.subTest(reason=reason, seed=self.seed):
                    self.assertIsNone(
                        fsm_autogate.autogate_refusal_class(reason),
                        f"зерно: {self.seed}")


if __name__ == "__main__":
    unittest.main()
