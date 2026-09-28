"""Приёмочные тесты AC-5 и AC-10 (ретроспектива снимка читает артефактную
ветку) — tasks/01M3KE80RNBCY9G48E75Z14TA7/SPEC.md, «Критерии приёмки».

Сценарий обоих: каталога задачи в главной копии НЕТ (он там и не
заводится — `tasks/<id>/` живёт в артефактной ветке пульта), а сама
артефактная ветка несёт и каталог приёмочных тестов с известными числами,
и `SPEC.md` с известным первым предложением «Контекста».

Красен до реализации: счётчики приёмочных тестов и текст `SPEC.md` для
строки «Суть» читаются из каталога главной копии (`orchestrator/
retro.py:439` и `:253`), которого в момент записи ретроспективы нет, —
снимок несёт «0 тест(ов), 0 manual, 0 skip» и одно название задачи вместо
сути.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import (FIXTURE_GIST_SENTENCE, FIXTURE_MANUAL_COUNT,  # noqa: E402
                      FIXTURE_SKIP_COUNT, FIXTURE_TEST_COUNT,
                      ClosingSnapshotSandbox, fixture_artifact_files)

TASK = "01PLANKBRANCHSOURCED000001"


class SnapshotReadsArtifactBranchTest(ClosingSnapshotSandbox):

    def setUp(self):
        super().setUp()
        self.seed_merge_gate_task(TASK, fixture_artifact_files(TASK))
        # Предпосылка обоих критериев, названная ими дословно: каталога
        # задачи в главной копии нет. Проверяется, а не предполагается —
        # иначе тест мог бы незаметно съехать на чтение с диска.
        self.assertFalse(
            (config.TASKS / TASK).exists(),
            "предпосылка AC-5/AC-10 нарушена: каталог задачи есть в "
            "главной копии")
        self.approve_merge(TASK)

    def test_ac5_snapshot_counts_acceptance_tests_of_the_artifact_branch(self):
        """Счётчики приёмочных тестов в ретроспективе снимка равны числам
        каталога приёмочных тестов АРТЕФАКТНОЙ ВЕТКИ, а не нулям
        отсутствующего каталога главной копии.

        Ловит мутацию: подсчёт остаётся на `config.TASKS / <id>` (или
        новое чтение из ветки добавлено, но старое не убрано и выигрывает)
        — строка снимка останется «0 тест(ов), 0 manual, 0 skip», а
        ожидаемые числа фикстуры больше нуля.
        """
        self.assertGreater(
            FIXTURE_TEST_COUNT, 0,
            "фикстура обязана нести непустой каталог приёмочных тестов "
            "(AC-5: N > 0)")

        expected = (f"Приёмочные тесты: {FIXTURE_TEST_COUNT} тест(ов), "
                    f"{FIXTURE_MANUAL_COUNT} manual, {FIXTURE_SKIP_COUNT} skip")
        retro_text = self.snapshot_retro_text(TASK)
        self.assertIn(
            expected, retro_text,
            f"ретроспектива снимка обязана нести счётчики каталога "
            f"приёмочных тестов артефактной ветки (AC-5): «{expected}»; "
            f"получено:\n{retro_text}")

    def test_ac10_snapshot_gist_takes_the_spec_of_the_artifact_branch(self):
        """Строка «Суть» ретроспективы снимка смерженной задачи несёт
        название задачи и первое предложение «Контекста» `SPEC.md`
        артефактной ветки, а не одно название.

        Ловит мутацию: текст `SPEC.md` для «Сути» по-прежнему берётся с
        диска главной копии (или читается из ветки, но по пути без
        префикса `tasks/<id>/`) — `_read_spec_text` вернёт `None`,
        `_gist` выродится в одно название задачи, и строки с предложением
        фикстуры в снимке не будет.
        """
        expected = f"Суть: {self.TITLE} — {FIXTURE_GIST_SENTENCE}"
        retro_text = self.snapshot_retro_text(TASK)
        self.assertIn(
            expected, retro_text,
            f"ретроспектива снимка смерженной задачи обязана нести суть из "
            f"SPEC.md артефактной ветки (AC-10): «{expected}»; получено:\n"
            f"{retro_text}")


if __name__ == "__main__":
    unittest.main()
