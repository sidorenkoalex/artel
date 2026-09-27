"""AC-4 — 01M3HST1381E1FZCYAN2TSB1F3: указателя в доме роли пульта нет —
именованный отказ ДО эфемерного клона.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. Указателя в доме роли пульта нет — команда прогона на наборе с ролью
на Codex отказывает ДО эфемерного клона: отказ называет отсутствующий путь
указателя и несёт текст `CODEX_AUTH_RECIPE`; эфемерный каталог клона не
создаётся, строка задачи не заводится, ни один шаг роли не исполняется.

«ДО эфемерного клона» наблюдается тремя независимыми фактами, а не одним:
ни одного `git clone` среди перехваченных процессов, ни одного временного
каталога с префиксом клона и ни одной строки в `tasks`. Один факт мог бы
держаться случайно — например, если клон упал бы по другой причине.

Текст рецепта сверяется с константой `doctor.CODEX_AUTH_RECIPE`, а не с
литералом: рецепт — чужой путь (`orchestrator/doctor/preflight.py`), и его
переформулировка не должна красить планку. Сверка идёт по тексту, сведённому
к одному пробелу (`_util.normalized`): перенос строки в отчёте не меняет
того, что рецепт назван.

Красен до реализации: указателя прогон не спрашивает вовсе — команда без
указателя в доме роли пульта доходит до клона и заводит задачу, поэтому
`SystemExit` не наступает и `assertIsNotNone` падает первым.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from orchestrator import doctor, store  # noqa: E402


class MissingPointerRefusedBeforeCloneTest(_util.CodexClonePlankSandbox):

    def setUp(self):
        super().setUp()
        # Сценарий требования 3: дом роли пульта развёрнут и обитаем, но
        # указателя в нём нет — ровно состояние пульта после `init` без
        # однократного шага Оператора.
        self.seed_pult_role_home(with_pointer=False)
        self.assertFalse(self.pointer.exists(),
                         "предпосылка: указателя в доме роли пульта нет")

    def test_ac4_refusal_names_the_missing_pointer_path_and_the_recipe(self):
        """Команда отказывает `SystemExit`, называя отсутствующий путь
        указателя и несущий рецепт двух однократных шагов Оператора.

        Ловит мутацию: отказ собран своим текстом без рецепта (или без
        пути) — Оператор получил бы «вход не найден» без указания, какой
        файл поставить и какой командой, то есть ровно ту непочинябельную
        строку, ради устранения которой отказ и заводится.
        """
        outcome = self.run_canary(set_name=_util.SET_NAME)

        self.assertIsNotNone(outcome.exited,
                             f"команда не отказала: {outcome.text}")
        text = _util.normalized(outcome.text)
        self.assertIn(str(self.pointer), text)
        self.assertIn(_util.normalized(doctor.CODEX_AUTH_RECIPE), text)

    def test_ac4_no_clone_and_no_task_row_and_no_role_step(self):
        """Ни `git clone`, ни временного каталога клона, ни строки в
        `tasks`, ни вождения задачи.

        Ловит мутацию: проверка указателя поставлена ВНУТРИ блока клона
        (там, где живёт перенос) — за отсутствие однократного шага Оператора
        пульт платил бы клонированием репозитория и заведённой задачей, а
        причина умирала бы вместе с уничтоженным клоном.
        """
        outcome = self.run_canary(set_name=_util.SET_NAME)

        self.assertNotIn("clone", outcome.spy.git_subcommands(),
                         outcome.spy.git_subcommands())
        self.assertEqual([], outcome.clone_dirs,
                         "эфемерный каталог клона создан до отказа")
        self.assertEqual([], store.all_tasks(self.conn),
                         "строка задачи заведена до отказа")
        self.assertEqual([], outcome.drive_calls,
                         "задача поехала по FSM до отказа")

    def test_ac4_a_set_without_a_codex_role_is_not_refused_without_the_pointer(self):
        """Тот же пульт без указателя на наборе БЕЗ роли Codex прогон не
        отказывает: отказ привязан к наличию роли Codex, а не к отсутствию
        файла само́му по себе.

        Ловит мутацию: проверка указателя поставлена безусловно, до разбора
        набора — пульт, Codex не использующий, потерял бы команду `canary`
        целиком, потому что указателя связки ключей у него нет и не нужно.
        """
        outcome = self.run_canary(set_name=_util.CLAUDE_SET_NAME)

        self.assertIsNone(outcome.exited,
                          f"прогон без роли Codex отказал: {outcome.text}")
        self.assertEqual(1, len(outcome.drive_calls),
                         f"задача не проведена: {outcome.text}")


if __name__ == "__main__":
    unittest.main()
