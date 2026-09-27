"""AC-8 — 01M3GKJ84XM5QPC6TK5EE307Q9: слияние завершает тот же коммит
подтяжки, отдельного коммита разрешения нет, в журнал идёт запись
«аддитивный конфликт слит: <файлы>».

Источник — SPEC.md, «Критерии приёмки»:

AC-8. Слияние завершает тот же коммит подтяжки (`<id>: подтяжка
<ветка>`), отдельного коммита разрешения в ветке задачи нет; в журнал
задачи попадает запись «аддитивный конфликт слит: <файлы>» с
перечислением слитых файлов.

Сообщение коммита собирается от `config.MAIN_BRANCH` и id задачи, не
литералом: имя главной ветки — крутилка конфигурации.

Красен до реализации: аддитивное слияние ещё не написано — подтяжка
эскалирует, вершина ветки остаётся собственным коммитом ветки (не
коммитом слияния), и записи «аддитивный конфликт слит» в журнале нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

ADDITIVE_MERGE_PHRASE = "аддитивный конфликт слит"


class SinglePullCommitAndJournalTest(_sandbox.AdditivePullSandbox):

    def setUp(self):
        super().setUp()
        self.seed_additive_conflict(_sandbox.DOC_A, _sandbox.DOC_B)

    def test_ac8_merge_is_finished_by_the_pull_commit_itself(self):
        """Вершина ветки после подтяжки — коммит слияния (два родителя)
        с сообщением `<id>: подтяжка <ветка>`, и по первому родителю на
        ветку легло ровно ОДНО новое звено.

        Ловит мутацию: слитые файлы коммитятся отдельным «коммитом
        разрешения» перед завершением merge — по первому родителю
        оказалось бы два новых коммита, а вершина перестала бы быть
        коммитом слияния с ожидаемым сообщением.
        """
        self.evaluate()

        self.assertEqual(
            self.pull_commit_message(), self.head_subject(),
            "merge обязан завершаться тем же коммитом подтяжки")
        self.assertEqual(2, self.head_parent_count(),
                         "вершина ветки обязана быть коммитом слияния")
        self.assertEqual(
            1, self.commits_added_to_branch(),
            "на ветку задачи обязано лечь ровно одно новое звено — "
            "отдельного коммита разрешения быть не должно")

    def test_ac8_journal_records_the_additive_merge_with_file_names(self):
        """В журнале задачи есть запись «аддитивный конфликт слит»,
        называющая оба слитых документа.

        Ловит мутацию: запись журнала пишется без перечня файлов (или
        только по первому из них) — Оператор не увидит, какие именно
        документы пульт слил за него, и `assertIn` по имени второго
        файла покраснеет.
        """
        self.evaluate()

        texts = self.journal_texts()
        matching = [text for text in texts if ADDITIVE_MERGE_PHRASE in text]
        self.assertTrue(
            matching,
            f"нет записи «{ADDITIVE_MERGE_PHRASE}» в журнале: {texts}")
        joined = " ".join(matching)
        for rel in (_sandbox.DOC_A, _sandbox.DOC_B):
            self.assertIn(rel, joined,
                          f"запись обязана называть слитый файл {rel}: "
                          f"{matching}")


if __name__ == "__main__":
    unittest.main()
