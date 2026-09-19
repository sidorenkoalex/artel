"""AC-2, AC-3: `new --tz` отказывает по неклассифицированному пути ТЗ и
не оставляет следов.

Красен до реализации: сверки упомянутых путей с зонами в `catalog.cmd_new` ещё нет — `_tz_calibration_inputs` (orchestrator/catalog.py:126) разбирает ТЗ только ради подсказки калибровки, задача заводится при любом тексте, поэтому не будет ни отказа, ни отсутствия строки в `tasks`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from _new_sandbox import NewWithTzSandbox  # noqa: E402
from orchestrator import catalog  # noqa: E402

# Путь назван в «Требуется», в «Зоны:» его нет, разделы «Не входит:»/
# «Только чтение…:»/«Приложением:» отсутствуют вовсе.
TZ_UNCLASSIFIED = _util.tz_text(
    requires=f"Починить разбор ответа в {_util.UNCLASSIFIED_PATH}.",
    zones=_util.ZONE_PATH)


class NewRefusesUnclassifiedTzPathTest(NewWithTzSandbox):

    def test_ac2_refusal_names_the_path_and_carries_the_hint(self):
        """ТЗ называет существующий путь в разделе «Требуется», в
        «Зоны:» его нет и ни в одном из классифицирующих разделов он не
        назван — `new --tz` отказывает: задача не заведена, а в тексте
        отказа есть имя файла и подсказка «назови в Зонах, в «Не
        входит» или в «Только чтение/Приложением»».

        Ловит мутацию: классификация считает достаточным сам факт
        наличия строки «Зоны:» в ТЗ (не сверяет КАЖДЫЙ собранный путь с
        её содержимым) — задача завелась бы молча, и ни проверка числа
        строк `tasks`, ни проверка текста отказа не прошли бы.
        """
        text = self.run_new(TZ_UNCLASSIFIED)

        self.assert_no_task_created(text)
        _util.assert_unclassified_refusal(self, text, _util.UNCLASSIFIED_PATH)

    def test_ac3_refused_new_leaves_no_task_row_and_no_artifact_branch(self):
        """Тот же отказавший `new`: строки задачи в БД не появилось и
        артефактная ветка не создавалась — отказ случился ДО побочных
        эффектов заведения.

        Номер задачи — ULID (`orchestrator/idgen.py`), счётчик
        `task_counters` заморожен как legacy и `cmd_new` его не
        расходует (orchestrator/catalog.py:256): «номер не израсходован»
        наблюдаем ровно как «ни одной новой строки `tasks` и ни одного
        коммита артефактной ветки» — буквальное равенство id двух
        вызовов по построению ULID невозможно.

        Ловит мутацию: сверка путей поставлена ПОСЛЕ `_new_task_row`
        (например, рядом с печатью подсказки калибровки, которая уже
        читает текст ТЗ) — отказ был бы виден, но строка задачи и
        коммит артефактной ветки уже существовали бы.
        """
        with mock.patch.object(
                catalog.artifact_branch, "commit_files",
                wraps=catalog.artifact_branch.commit_files) as commit:
            text = self.run_new(TZ_UNCLASSIFIED)

        self.assert_no_task_created(text)
        commit.assert_not_called()

    def test_ac3_next_new_after_the_refusal_still_creates_exactly_one_task(self):
        """Отказ не ломает следующее заведение: валидный `new --tz`
        сразу после отказавшего заводит ровно одну задачу.

        Ловит мутацию: отказ реализован через частично выполненное
        заведение с откатом (удалением строки/ветки) — остаточное
        состояние (недоудалённая ветка, незакрытая транзакция) сорвало
        бы следующий `new`, и число задач выросло бы не на единицу.
        """
        self.run_new(TZ_UNCLASSIFIED)

        text = self.run_new(_util.tz_text(
            requires=f"Починить разбор в {_util.ZONE_PATH}.",
            zones=_util.ZONE_PATH), title="Вторая фикстура планки")

        _util.assert_no_unclassified_refusal(self, text)
        self.assert_task_created(text)


if __name__ == "__main__":
    unittest.main()
