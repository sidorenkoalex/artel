"""Приёмочные тесты AC-6 и AC-11 (`docs/retro/<id>.md` смерженной задачи)
— tasks/01M3KE80RNBCY9G48E75Z14TA7/SPEC.md, «Критерии приёмки».

Те же предпосылки, что у AC-5/AC-10: каталога задачи в главной копии нет,
артефактная ветка несёт каталог приёмочных тестов и `SPEC.md`. Предмет
здесь — ВТОРАЯ ретроспектива, `docs/retro/<id>.md`, то есть
`orchestrator/retro.py::build_done`: модуль объявлен «детерминированной
генерацией СОДЕРЖИМОГО docs/retro/<id>.md», а запись файла — дело
`orchestrator/fsm_merge_gate.py`, которое текст не меняет.

Момент записи взят как у настоящего закрытия мержем: `docs/retro/<id>.md`
пишется на шаге публикации артефактов мержа, когда артефактная ветка ещё
жива (SPEC, «Обоснование источника чтения», требование 8).

Красен до реализации: `build_done` считает тесты по `config.TASKS / <id>`
(`orchestrator/retro.py:439`) и читает оттуда же `SPEC.md`
(`orchestrator/retro.py:253`) — каталога закрываемой задачи в главной
копии нет, поэтому строка счётчиков сегодня нулевая, а «Суть» вырождается
в одно название задачи.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, retro, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import (FIXTURE_GIST_SENTENCE, FIXTURE_MANUAL_COUNT,  # noqa: E402
                      FIXTURE_SKIP_COUNT, FIXTURE_TEST_COUNT,
                      ClosingSnapshotSandbox, fixture_artifact_files)

TASK = "01PLANKDOCSRETROSOURCE0001"

#: sha мержа — произвольный, в предмете обоих критериев не участвует.
MERGE_SHA = "0123456789abcdef0123456789abcdef01234567"


class DocsRetroReadsArtifactBranchTest(ClosingSnapshotSandbox):

    def setUp(self):
        super().setUp()
        self.seed_task(TASK, "merge_gate", fixture_artifact_files(TASK))
        self.assertFalse(
            (config.TASKS / TASK).exists(),
            "предпосылка AC-6/AC-11 нарушена: каталог задачи есть в "
            "главной копии")
        self.retro_text = retro.build_done(store.db(), TASK, MERGE_SHA)

    def test_ac6_docs_retro_counts_acceptance_tests_of_the_artifact_branch(self):
        """`docs/retro/<id>.md` смерженной задачи несёт числа каталога
        приёмочных тестов артефактной ветки, а не «0 тест(ов), 0 manual,
        0 skip».

        Ловит мутацию: чтение из ветки заведено только для ретроспективы
        снимка, а `docs/retro/<id>.md` оставлен на каталоге главной копии
        (требование 5 велит поменять источник у ОБЕИХ) — строка счётчиков
        здесь останется нулевой при непустой фикстуре ветки.
        """
        expected = (f"Приёмочные тесты: {FIXTURE_TEST_COUNT} тест(ов), "
                    f"{FIXTURE_MANUAL_COUNT} manual, {FIXTURE_SKIP_COUNT} skip")
        self.assertIn(
            expected, self.retro_text,
            f"docs/retro/<id>.md смерженной задачи обязан нести счётчики "
            f"артефактной ветки (AC-6): «{expected}»; получено:\n"
            f"{self.retro_text}")

    def test_ac11_docs_retro_gist_takes_the_spec_of_the_artifact_branch(self):
        """`docs/retro/<id>.md` смерженной задачи несёт ту же строку
        «Суть: <название> — S», что и ретроспектива снимка.

        Ловит мутацию: источник `SPEC.md` поменян только в ветке
        ретроспективы снимка, а `build_done` для `docs/retro/<id>.md`
        по-прежнему читает каталог главной копии — «Суть» здесь останется
        одним названием задачи без второй части.
        """
        expected = f"Суть: {self.TITLE} — {FIXTURE_GIST_SENTENCE}"
        self.assertIn(
            expected, self.retro_text,
            f"docs/retro/<id>.md смерженной задачи обязан нести суть из "
            f"SPEC.md артефактной ветки (AC-11): «{expected}»; получено:\n"
            f"{self.retro_text}")


if __name__ == "__main__":
    unittest.main()
