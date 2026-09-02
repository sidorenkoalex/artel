"""AC-4 (tasks/01M1GV6H5DDDCWW4G3GW1D3A1X/SPEC.md): идентификатор границ
не записывается ни в один файл репозитория (артефакты задачи, коммиты
веток) и не появляется в брифе или ревью-пакете предыдущего запуска —
до начала текущего запуска роль не может знать закрывающий маркер этого
запуска.

Область теста: код `orchestrator/brief.py`/`orchestrator/review.py`
сам по себе не коммитит и не пишет файлы задачи (эти функции только
читают источники и возвращают строку промпта) — единственные каналы,
которыми ЭТОТ код мог бы случайно «утечь» идентификатор в репозиторий,
это (а) журнал шага (`store.journal`, который брифовые функции пишут
сами) и (б) файлы каталога задачи на диске, если бы будущая реализация
вдруг стала что-то дописывать рядом. Коммиты веток тестом не покрыты —
эти функции физически не делают git-коммитов ни до, ни после этой
задачи (это работа роли/оркестратора в другом месте), поэтому для кода
из зоны этой задачи утверждение «не появляется в коммите» уже
гарантировано отсутствием самого коммита, а не чем-то, что можно
сломать правкой brief.py/review.py.

Красен до реализации: без маркеров `marker_id_for` бросает
`AssertionError` — нечего искать/сравнивать.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import BriefSandbox, MAP_FRESH, marker_id_for  # noqa: E402


class Ac4IdNotInJournalOrTaskFilesTest(BriefSandbox):

    def test_ac4_run_id_is_not_journaled(self):
        """Идентификатор границы не попадает в детали журнала шага —
        журнал уже сегодня пишет sha256 компонента (`_journal_component`/
        `_manifest_component`), и было бы легко по ошибке протащить туда
        же и id границы.

        Ловит мутацию: код журналирует полностью собранный (уже обёрнутый
        маркерами) текст компонента вместо исходного — id границы
        просачивается в `steps.detail`.
        """
        text = self.build_developer_brief()
        run_id = marker_id_for(text, MAP_FRESH.strip())

        details = self.journal_details("developer")
        self.assertTrue(details, "журнал компонентов брифа обязан быть непустым")
        for detail in details:
            self.assertNotIn(
                run_id, detail,
                f"идентификатор границы не должен попадать в журнал: {detail!r}")

    def test_ac4_run_id_is_not_written_to_any_file_under_the_task_directory(self):
        """Идентификатор границы не оседает ни в одном файле каталога
        задачи — единственные файлы, которые могла бы затронуть будущая
        реализация (SPEC.md, ANSWER/QUESTIONS), остаются такими же
        входными артефактами, как и раньше, без побочной записи.

        Ловит мутацию: реализация кэширует использованный id в файле
        рядом с задачей (например для «дебага») — тест находит эту
        утечку на диске.
        """
        text = self.build_developer_brief()
        run_id = marker_id_for(text, MAP_FRESH.strip())

        from orchestrator import config
        task_dir = config.TASKS / "T001"
        for path in task_dir.rglob("*"):
            if path.is_file():
                content = path.read_text(encoding="utf-8", errors="replace")
                self.assertNotIn(
                    run_id, content,
                    f"идентификатор границы просочился в файл задачи: {path}")

    def test_ac4_previous_run_id_is_unknown_to_and_absent_from_the_next_run(self):
        """До начала запуска роль не может знать закрывающий маркер этого
        запуска: id прошлого запуска не появляется в тексте следующего
        запуска (и наоборот) — если бы появлялся, содержимое репозитория,
        полученное РАНЬШЕ (в рамках прошлого запуска), уже несло бы
        закрывающую границу будущего.

        Ловит мутацию: id границы вычисляется от чего-то, что переживает
        между запусками (например счётчик или время с грубой
        дискретностью), и случайно повторяется/просачивается в соседний
        запуск.
        """
        text_run1 = self.build_developer_brief()
        id_run1 = marker_id_for(text_run1, MAP_FRESH.strip())

        text_run2 = self.build_developer_brief()
        id_run2 = marker_id_for(text_run2, MAP_FRESH.strip())

        self.assertNotIn(id_run1, text_run2,
                         "id прошлого запуска не должен появляться в "
                         "тексте следующего запуска")
        self.assertNotIn(id_run2, text_run1,
                         "id текущего запуска не мог быть в тексте "
                         "предыдущего — он ещё не существовал")


if __name__ == "__main__":
    unittest.main()
