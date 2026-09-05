"""Приёмочные тесты 01M1SC40NT8T1WFKKKJ67CK96Z — AC-3, AC-6: вывод цикла
`auto` (журнал и stdout) на трёх сценариях байт-в-байт совпадает с
фикстурой, записанной с ДОРЕФАКТОРИНГОВОЙ реализации `orchestrator/
auto.py::_cmd_auto`.

Зелёный с рождения: три фикстуры ниже (`_FIXTURE_1`..`_FIXTURE_3`)
записаны буквальным прогоном песочницы `tests.test_auto_cycle.
AutoCycleTest` НА ТЕКУЩЕМ, ДОРЕФАКТОРИНГОВОМ коде `orchestrator/auto.py`
(commit ветки задачи на момент написания этого файла) — тем же
временным скриптом, каким SPEC требует зафиксировать «записанный вывод
текущей реализации» (AC-6). Сам сценарий воспроизведения (классы ниже)
— общий код с фикстурой: пока `orchestrator/auto.py` не тронут
рефакторингом, тест сравнивает вывод текущего кода САМ С СОБОЙ и обязан
быть зелёным уже сегодня; после рефакторинга (без правки поведения,
SPEC «Не входит») он останется зелёным ТОЛЬКО если тексты журнала,
подсказок и print не разошлись ни на символ — это и есть буквальная
проверка AC-3 их «буквального совпадения».

Нормализация: id задачи (ULID, разный на каждый прогон —
`catalog.cmd_new`) и pid родительского процесса в `session.session_id`
(`ppid-<pid>`, дефолт `lease` без явного `session_id`) заменены на
`<TASK>`/`<PPID>` И в захваченной фикстуре, И в свежем выводе теста —
это единственные два источника недетерминизма вывода этой песочницы
(лог агента детерминирован: `agent_log.last_agent_log` возвращает "—",
пока `FakeRun` не пишет настоящих файлов лога, что она и не делает).
Всё остальное в выводе — литеральный текст, который эта проверка и
защищает.

Три сценария выбраны так, чтобы вместе задеть все пять шагов цикла
из AC-1: (1) рубеж «замечания ревью не отработаны» (шаг а) с
последующим запуском роли (шаг в) и переходом по готовому артефакту
без роли (шаг б); (2) стоп-кран повторного одинакового отказа `advance`
(шаг г) с остановкой (шаг д); (3) исчерпание лимита шагов (шаг г) с
остановкой (шаг д) при реально бегущей роли на каждом шаге (шаг в).
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, fsm, store  # noqa: E402
from tests.test_auto_cycle import AutoCycleTest, FakeAdvance  # noqa: E402

_PPID_RE = re.compile(r"ppid-\d+")


def _normalize(text, task_id):
    text = (text or "").replace(task_id, "<TASK>").replace(task_id.lower(), "<TASK>")
    return _PPID_RE.sub("<PPID>", text)


def _normalized_journal(rows, task_id):
    return [(_normalize(actor, task_id), _normalize(action, task_id),
             _normalize(detail, task_id)) for actor, action, detail in rows]


_FIXTURE_1_STDOUT = (
    '[<TASK>] auto: старт из in_dev, лимит 30 шагов за вызов\n'
    '[<TASK>] переход отклонён: замечания ревью не отработаны: нет шага '
    'developer после итерации 2\n'
    '[<TASK>] auto шаг 1/30: developer in_dev -> in_dev, лог: —\n'
    '[<TASK>] -> review  (MR готов — прогон ревьювера)\n'
    '[<TASK>] шаг developer не нужен: переход выполнен по готовым '
    'артефактам (in_dev -> review)\n'
    '[<TASK>] переход отклонён: дерево не на ветке задачи '
    'artifact/<TASK> — REVIEW.md ветки не прочитан (файла нет на диске)\n'
    '[<TASK>] auto шаг 2/30: reviewer review -> review, лог: —\n'
    '[<TASK>] переход отклонён: дерево не на ветке задачи '
    'artifact/<TASK> — REVIEW.md ветки не прочитан (файла нет на диске)\n'
    '[<TASK>] auto шаг 3/30: reviewer review -> review, лог: —\n'
    '[<TASK>] переход отклонён: дерево не на ветке задачи '
    'artifact/<TASK> — REVIEW.md ветки не прочитан (файла нет на диске)\n'
    '[<TASK>] auto шаг 4/30: reviewer review -> review, лог: —\n'
    '[<TASK>] переход отклонён: дерево не на ветке задачи '
    'artifact/<TASK> — REVIEW.md ветки не прочитан (файла нет на диске)\n'
    '[<TASK>] auto шаг 5/30: reviewer review -> review, лог: —\n'
    '[<TASK>] переход отклонён: дерево не на ветке задачи '
    'artifact/<TASK> — REVIEW.md ветки не прочитан (файла нет на диске)\n'
    '[<TASK>] auto остановлен: цикл не сходится: 5 шагов без перехода\n'
    '  состояние: review\n'
    '  дальше: artel.py log <TASK> — глянь, что происходит на последних '
    'шагах, затем artel.py advance <TASK>\n'
)

_FIXTURE_1_JOURNAL = [
    ('operator', 'created', 'Цикл auto'),
    ('fsm', 'state -> in_dev', 'замечания ревью, итерация 2'),
    ('lease', 'lease взят', 'взят сессией <PPID>'),
    ('operator', 'auto старт', 'состояние in_dev, лимит 30 шагов'),
    ('fsm', 'переход отклонён: замечания ревью не отработаны',
     'замечания ревью не отработаны: нет шага developer после итерации 2'),
    ('developer', 'agent run finished', 'rc=0, тестовая заглушка цикла auto'),
    ('fsm', 'state -> review', 'MR готов — прогон ревьювера'),
    ('fsm', 'sha зафиксирован', 'target=artel, sha=—, чисто=False, код=—'),
    ('operator', 'шаг developer не нужен: переход выполнен по готовым артефактам',
     'in_dev -> review'),
    ('fsm', 'переход отклонён: дерево не на ветке задачи',
     'дерево не на ветке задачи artifact/<TASK> — REVIEW.md ветки не '
     'прочитан (файла нет на диске)'),
    ('reviewer', 'agent run finished', 'rc=0, тестовая заглушка цикла auto'),
    ('fsm', 'переход отклонён: дерево не на ветке задачи',
     'дерево не на ветке задачи artifact/<TASK> — REVIEW.md ветки не '
     'прочитан (файла нет на диске)'),
    ('reviewer', 'agent run finished', 'rc=0, тестовая заглушка цикла auto'),
    ('fsm', 'переход отклонён: дерево не на ветке задачи',
     'дерево не на ветке задачи artifact/<TASK> — REVIEW.md ветки не '
     'прочитан (файла нет на диске)'),
    ('reviewer', 'agent run finished', 'rc=0, тестовая заглушка цикла auto'),
    ('fsm', 'переход отклонён: дерево не на ветке задачи',
     'дерево не на ветке задачи artifact/<TASK> — REVIEW.md ветки не '
     'прочитан (файла нет на диске)'),
    ('reviewer', 'agent run finished', 'rc=0, тестовая заглушка цикла auto'),
    ('fsm', 'переход отклонён: дерево не на ветке задачи',
     'дерево не на ветке задачи artifact/<TASK> — REVIEW.md ветки не '
     'прочитан (файла нет на диске)'),
    ('operator', 'auto остановлен', 'review: цикл не сходится: 5 шагов без перехода'),
]

_FIXTURE_2_STDOUT = (
    '[<TASK>] auto: старт из in_dev, лимит 30 шагов за вызов\n'
    '[<TASK>] auto остановлен: переход отклонён: рабочая копия артефактов '
    'грязная — почини причину и повтори artel.py advance <TASK>\n'
    '  состояние: in_dev\n'
    '  дальше: почини причину и повтори artel.py advance <TASK>\n'
)

_FIXTURE_2_JOURNAL = [
    ('operator', 'created', 'Цикл auto'),
    ('lease', 'lease взят', 'взят сессией <PPID>'),
    ('operator', 'auto старт', 'состояние in_dev, лимит 30 шагов'),
    ('fsm', 'переход отклонён: рабочая копия артефактов грязная',
     'деталь тестового отказа'),
    ('fsm', 'переход отклонён: рабочая копия артефактов грязная',
     'деталь тестового отказа'),
    ('operator', 'auto остановлен',
     'in_dev: переход отклонён: рабочая копия артефактов грязная — '
     'почини причину и повтори artel.py advance <TASK>'),
]

_FIXTURE_3_STDOUT = (
    '[<TASK>] auto: старт из in_dev, лимит 2 шагов за вызов\n'
    '[<TASK>] PLAN.md не ready — разработчик ещё работает\n'
    '[<TASK>] auto шаг 1/2: developer in_dev -> in_dev, лог: —\n'
    '[<TASK>] PLAN.md не ready — разработчик ещё работает\n'
    '[<TASK>] auto шаг 2/2: developer in_dev -> in_dev, лог: —\n'
    '[<TASK>] auto остановлен: лимит 2 шагов за вызов исчерпан\n'
    '  состояние: in_dev\n'
    '  дальше: artel.py log <TASK> (что происходит), затем artel.py auto '
    '<TASK> — продолжит отсюда\n'
)

_FIXTURE_3_JOURNAL = [
    ('operator', 'created', 'Цикл auto'),
    ('lease', 'lease взят', 'взят сессией <PPID>'),
    ('operator', 'auto старт', 'состояние in_dev, лимит 2 шагов'),
    ('developer', 'agent run finished', 'rc=0, тестовая заглушка цикла auto'),
    ('developer', 'agent run finished', 'rc=0, тестовая заглушка цикла auto'),
    ('operator', 'auto остановлен', 'in_dev: лимит 2 шагов за вызов исчерпан'),
]


class RecordedScenariosMatchPreRefactorFixtureTest(AutoCycleTest):
    """AC-3/AC-6: три сценария цикла `auto`, сравненные буквально с
    выводом дорефакторинговой реализации."""

    def test_ac3_ac6_rework_gate_refusal_then_role_run_then_transition(self):
        """Сценарий 1: `in_dev` со свежей записью «замечания ревью,
        итерация 2» без завершённого шага developer после неё — рубеж
        держит пред-advance (шаг а), роль всё равно получает шанс
        отработать (шаг в), затем пред-advance следующей итерации
        проходит по готовому PLAN.md мимо роли (шаг б), и цикл
        останавливается стоп-краном буксования в `review` (шаг г/д).

        Ловит мутацию: любая правка текста рубежа `_rework_not_addressed_
        reason`/`REWORK_REFUSAL_ACTION`, сообщения «шаг X не нужен...»,
        нумерации `auto шаг N/M` или причины стоп-крана буксования —
        байт-в-байт сравнение с зафиксированной фикстурой покраснеет на
        первой же разошедшейся строке.
        """
        self.write_plan("ready")
        self.set_state("in_dev")
        store.journal(store.db(), self.TASK, "fsm", "state -> in_dev",
                      "замечания ревью, итерация 2")
        self.agent.script = [lambda: None]

        out = self.auto()
        rows = self.journal_rows()

        self.assertEqual(_FIXTURE_1_STDOUT, _normalize(out, self.TASK))
        self.assertEqual(_FIXTURE_1_JOURNAL, _normalized_journal(rows, self.TASK))

    def test_ac3_ac6_identical_advance_refusal_twice_in_a_row_stops(self):
        """Сценарий 2: `fsm.cmd_advance` дважды подряд журналирует ОДИН и
        тот же текст отказа — стоп-кран требования 1 (SPEC T038, шаг г)
        останавливает цикл (шаг д) до единого запуска роли.

        Ловит мутацию: правка текста подсказки «почини причину и повтори
        artel.py advance...», порядка причины/подсказки в `auto_stop`,
        либо снятие самого стоп-крана (цикл дошёл бы до `runner.cmd_run` —
        `self.agent.calls` в журнале появилась бы запись `agent run
        finished`, которой в фикстуре нет) — сравнение покраснеет.
        """
        self.patch_object(config, "AUTO_STALL_STEPS_LIMIT",
                          config.AUTO_MAX_STEPS + 1)
        self.write_plan("ready")
        self.set_state("in_dev")
        advance = FakeAdvance()
        self.patch_object(fsm, "cmd_advance", advance)
        text = "переход отклонён: рабочая копия артефактов грязная"
        advance.script = [text, text]

        out = self.auto()
        rows = self.journal_rows()

        self.assertEqual(_FIXTURE_2_STDOUT, _normalize(out, self.TASK))
        self.assertEqual(_FIXTURE_2_JOURNAL, _normalized_journal(rows, self.TASK))

    def test_ac3_ac6_step_limit_exhausted_with_the_role_running_each_step(self):
        """Сценарий 3: `AUTO_MAX_STEPS = 2`, PLAN.md ещё `draft` — роль
        реально запускается на каждом шаге (шаг в), и цикл останавливается
        ровно на исчерпании лимита (шаг г/д), не раньше и не позже.

        Ловит мутацию: сдвиг нумерации `auto шаг N/M` (например, N с 0 или
        M без учёта текущего `AUTO_MAX_STEPS`), лишний или пропущенный шаг
        до остановки, либо правка формулировки «лимит N шагов за вызов
        исчерпан» — байт-в-байт сравнение с фикстурой покраснеет.
        """
        self.patch_object(config, "AUTO_MAX_STEPS", 2)
        self.write_plan("draft")
        self.set_state("in_dev")
        self.agent.script = [lambda: None, lambda: None]

        out = self.auto()
        rows = self.journal_rows()

        self.assertEqual(_FIXTURE_3_STDOUT, _normalize(out, self.TASK))
        self.assertEqual(_FIXTURE_3_JOURNAL, _normalized_journal(rows, self.TASK))


if __name__ == "__main__":
    unittest.main()
