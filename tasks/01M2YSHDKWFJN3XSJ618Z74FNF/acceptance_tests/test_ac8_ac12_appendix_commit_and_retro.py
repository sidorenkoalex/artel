"""AC-8/AC-12 (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF): применение приложения на
мерже — отдельный коммит «<id>: приложения Оператора — <пути>» ДО коммита
снимка артефактов, запись журнала «приложения применены: <пути> (sha)» и
строка с перечнем путей в RETRO задачи.

Красен до реализации: тело гейта мержа (`orchestrator/fsm_merge_gate.py::_cmd_approve_merge_gate`) приложения PLAN не читает вовсе — main origin после мержа несёт только коммиты merge/снимка/RETRO, коммита приложений среди них нет ни одного, а журнал и RETRO о приложениях не знают.

Приложение — применимая правка защищённого пути ВНЕ `tests/` и
`.github/` (порождена настоящим `git diff` по файлу базы сравнения),
поэтому полный прогон по требованию 5 здесь не нужен: предмет этих двух
критериев — коммит, его место и следы в журнале/RETRO.

Провалидировано стабом (решение Оператора 03.09): временное применение
приложений в `_publish_merge_artifacts` (до наложения снимка) с
коммитом, записью журнала и строкой путей в тексте RETRO зеленит оба
теста файла; стаб удалён, репозиторий не тронут.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _parse  # noqa: E402
import _sandbox  # noqa: E402

from orchestrator import retro  # noqa: E402

MARKER = "вторая строка правки Оператора"
SHA_IN_TEXT = re.compile(r"[0-9a-f]{7,40}")


class AppendixAppliedOnMergeTest(_sandbox.MergeAppendixSandbox):

    def setUp(self):
        super().setUp()
        self.commit_plan([_parse.appendix_section(
            [self.applicable_diff_block(_parse.PROTECTED_FILE, MARKER)],
            suffix=f": правка {_parse.PROTECTED_FILE}")])

    def test_ac8_appendix_commit_precedes_the_artifact_snapshot_commit(self):
        """После мержа main origin несёт отдельный коммит с сообщением
        «<id>: приложения Оператора — …», этот коммит изменяет
        защищённый путь приложения (и правка видна в содержимом файла
        main), и стоит он РАНЬШЕ коммита снимка артефактной ветки.

        Ловит мутацию: приложения применяются ПОСЛЕ наложения снимка
        артефактов (вызов переставлен ниже `_publish_merge_artifacts`) —
        тогда sha «коммита мержа», на который адресуется RETRO, указывает
        на содержимое БЕЗ приложений, а порядок коммитов в main
        разойдётся с AC-8; проверка индексов ниже это поймает. Та же
        проверка ловит и приложение, применённое `git apply` без
        коммита: коммита с этим сообщением в main не окажется вовсе.
        """
        outcome = self.approve()

        self.assertEqual(outcome, ("done",))
        subjects = self.origin_main_subjects()
        applied = [i for i, s in enumerate(subjects)
                   if _sandbox.APPLIED_COMMIT_MARK in s]
        self.assertEqual(
            len(applied), 1,
            f"ожидался ровно один коммит приложений в main origin: "
            f"{subjects}")
        subject = subjects[applied[0]]
        self.assertTrue(
            subject.startswith(self.TASK),
            f"сообщение коммита приложений не начинается с id задачи: "
            f"{subject!r}")
        self.assertIn(_parse.PROTECTED_FILE, subject,
                      f"сообщение коммита не перечисляет пути: {subject!r}")
        self.assertIn(
            _parse.PROTECTED_FILE,
            self.origin_files_changed_by(_sandbox.APPLIED_COMMIT_MARK),
            "коммит приложений не изменил защищённый путь приложения")
        self.assertIn(MARKER, self.origin_file_text(_parse.PROTECTED_FILE),
                      "правка приложения не доехала до main origin")

        snapshot = [i for i, s in enumerate(subjects)
                    if _sandbox.SNAPSHOT_COMMIT_MARK in s]
        self.assertTrue(
            snapshot,
            f"в main origin нет коммита снимка артефактной ветки — порядок "
            f"AC-8 не на чем проверить: {subjects}")
        self.assertLess(
            applied[0], snapshot[0],
            f"коммит приложений обязан стоять ДО коммита снимка "
            f"артефактов: {subjects}")

    def test_ac12_journal_and_retro_carry_the_applied_paths(self):
        """После успешного мержа журнал задачи несёт запись «приложения
        применены: …» с путём и sha, а RETRO задачи в main origin —
        строку с перечнем применённых путей.

        Ловит мутацию: запись журнала пишется ДО `git apply`/коммита (или
        вместо sha подставлен пустой результат `head_sha` scratch-дерева,
        уже убранного к этому моменту) — в detail не окажется sha; и
        мутацию «строка RETRO собирается из ветки задачи, а не из
        применённых приложений» — в RETRO не окажется пути.
        """
        self.approve()

        applied = [f"{a} | {d}" for a, d in self.journal()
                   if _sandbox.APPLIED_JOURNAL_MARK in f"{a} {d}"]
        self.assertTrue(
            applied,
            f"нет записи журнала «{_sandbox.APPLIED_JOURNAL_MARK}»:\n"
            f"{self.journal_blob()}")
        record = applied[-1]
        self.assertIn(_parse.PROTECTED_FILE, record)
        self.assertTrue(
            SHA_IN_TEXT.search(record.replace(self.TASK, "")),
            f"в записи нет sha коммита приложений: {record!r}")

        retro_text = self.origin_file_text(retro.retro_rel_path(self.TASK))
        self.assertTrue(
            retro_text,
            f"RETRO задачи не доехало до main origin: "
            f"{self.origin_main_subjects()}")
        lines = [line for line in retro_text.splitlines()
                 if _parse.PROTECTED_FILE in line]
        self.assertTrue(
            lines,
            f"в RETRO задачи нет строки с перечнем применённых путей:\n"
            f"{retro_text}")


if __name__ == "__main__":
    unittest.main()
