"""Приёмочный тест AC-7 (деградация без артефактной ветки) —
tasks/01M3KE80RNBCY9G48E75Z14TA7/SPEC.md, «Критерии приёмки».

Сценарий: артефактной ветки задачи нет вовсе (её единственный реальный
случай — долговая генерация `docs/retro/<id>.md` ликвидированной задачи
на следующем мерже, SPEC «Обоснование источника чтения»), каталога задачи
в главной копии тоже нет. Оба генератора ретроспективы обязаны отработать
без исключения, с нулевыми счётчиками и «Сутью» из одного названия.

Зелёный с рождения: прежняя деградация, которую требование 7 велит
сохранить, — сегодня оба чтения (`config.TASKS / <id>`) просто не находят
каталога и честно отдают нули и пустое первое предложение. Тест стережёт,
чтобы перевод чтений на git не превратил отсутствующую ветку в исключение.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, config, gitcmd, retro, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ClosingSnapshotSandbox  # noqa: E402

TASK = "01PLANKNOARTIFACTBRANCH001"

MERGE_SHA = "0123456789abcdef0123456789abcdef01234567"

ZERO_COUNTS = "Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip"


class MissingArtifactBranchTest(ClosingSnapshotSandbox):

    def setUp(self):
        super().setUp()
        # Строка задачи есть, артефактной ветки НЕТ: `seed_task` её завёл
        # бы, поэтому задача заводится голым `insert_task`.
        store.insert_task(store.db(), TASK, self.TITLE, "merge_gate",
                          self.code_branch(TASK), self.TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.assertFalse(
            gitcmd.branch_exists(artifact_branch.branch_name(TASK)),
            "предпосылка AC-7 нарушена: артефактная ветка задачи есть")
        self.assertFalse(
            (config.TASKS / TASK).exists(),
            "предпосылка AC-7 нарушена: каталог задачи есть в главной копии")

    def assert_degraded(self, text: str) -> None:
        self.assertIn(
            ZERO_COUNTS, text,
            f"без артефактной ветки счётчики обязаны быть нулевыми "
            f"(AC-7): «{ZERO_COUNTS}»; получено:\n{text}")
        self.assertRegex(
            text, re.compile(rf"^Суть: {re.escape(self.TITLE)}$", re.M),
            f"без артефактной ветки «Суть» — одно название задачи без "
            f"второй части (AC-7); получено:\n{text}")

    def test_ac7_done_retro_degrades_without_the_artifact_branch(self):
        """Генератор ретроспективы смерженной задачи без артефактной ветки
        не падает и деградирует: нули в счётчиках, «Суть» из одного
        названия.

        Ловит мутацию: перевод чтений на git сделан без деградации —
        например, `gitcmd.show` вернул `None`, а результат сразу уходит в
        разбор текста, либо отсутствие ветки поднимается исключением —
        вызов ниже упадёт вместо того, чтобы вернуть текст.
        """
        self.assert_degraded(retro.build_done(store.db(), TASK, MERGE_SHA))

    def test_ac7_killed_retro_degrades_without_the_artifact_branch(self):
        """То же для генератора ретроспективы ликвидированной задачи — это
        и есть единственный реальный случай отсутствия ветки (долговая
        генерация на следующем мерже).

        Ловит мутацию: деградация предусмотрена только на ветке `done`
        (например, `try/except` обёрнут вокруг одного из двух вызовов) —
        долговая генерация killed-ретроспективы упадёт, и вызов ниже
        это покажет.
        """
        self.assert_degraded(retro.build_killed(store.db(), TASK))


if __name__ == "__main__":
    unittest.main()
