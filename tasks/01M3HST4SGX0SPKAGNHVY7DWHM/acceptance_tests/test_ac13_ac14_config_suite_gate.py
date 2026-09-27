"""AC-13, AC-14 — 01M3HST4SGX0SPKAGNHVY7DWHM: `doc-commit` файла
конфигурации гоняет полный набор `tests/` перед отправкой; `--accept-red`
— осознанный обход с основанием в журнале.

Источник — SPEC.md, «Критерии приёмки»:

AC-13. `doc-commit` пути из `DOC_COMMIT_CONFIG_PATHS` при красном наборе
`tests/` на дереве с применённой правкой — отказ, называющий упавшие
тесты; коммита в `origin` нет и удержанной записи не появляется. Тот же
исход, когда набор не удалось запустить вовсе.

AC-14. Тот же вызов с `--accept-red "<основание>"` коммитит правку, а
запись журнала пульта несёт путь и основание.

Прогон — настоящий, без мока: стенд сеет в origin набор `tests/` из одного
теста, который красен РОВНО тогда, когда правка конфигурации уже
применена к дереву прогона (`_sandbox.CONDITIONAL_SUITE`). Это и проверяет
слова требования 13 «на дереве с УЖЕ применённой правкой»: реализация,
гоняющая набор до применения правки либо не на том дереве, получит зелёный
набор и закоммитит — тест покраснеет. Мок конкретной функции пульта
(`acceptance.run_full_suite`) планка сознательно не ставит: выбор функции
— дело разработчика, а критерий говорит об исходе.

Исход «набор не удалось запустить вовсе» — дерево без `tests/`: прогон не
стартует, и требование 14 велит закрывать гейт по умолчанию, без
молчаливого пропуска. Оба исхода AC-13 — отдельными тестами (каждому свой
стенд и свой рабочий репозиторий): два вызова подряд в одном процессе
проверяли бы уже не критерий, а то, чем отказ оставляет рабочее дерево
после себя.

Красен до реализации: `cmd_doc_commit` (:656) набор `tests/` не гоняет ни
для одного пути — оба вызова AC-13 сегодня успешно коммитят правку вместо
отказа, а флага `--accept-red` `_parse_doc_commit_args` (:632) не знает
вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402
from orchestrator import notes  # noqa: E402

MESSAGE = "поворот крутилки"
ACCEPT_REASON = "красный тест не про эту правку, чиню отдельной задачей"


class ConfigPathSuiteGateTest(_sandbox.NoteSandbox):

    def test_ac13_red_suite_refuses_naming_the_failed_test(self):
        """В дереве прогона посеян набор, красный РОВНО из-за применённой
        правки конфигурации: `doc-commit` отказывает, называя упавший тест
        (в тексте есть «test_seed» — именем файла набора либо именем самого
        теста), коммита в origin нет, конфигурация в origin прежняя,
        удержанной записи не появилось.

        Ловит мутацию: прогон идёт на дереве ДО применения правки (порядок
        «прогнать набор → записать файл» вместо обратного) либо не на том
        дереве вовсе — посеянный тест видит чистую конфигурацию, набор
        зелёный, правка коммитится, и тест красен на отсутствии
        `SystemExit`.
        """
        self.seed_suite(_sandbox.CONDITIONAL_SUITE)
        source = self.source_file(_sandbox.CONFIG_TEXT_POISONED,
                                  "config-draft.yaml")
        before = self.origin_head()

        message = self.refusal(notes.cmd_doc_commit, _sandbox.CONFIG_REL,
                               "--from", str(source), "--message", MESSAGE)

        self.assertIn("test_seed", message, message)
        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_show(_sandbox.CONFIG_REL),
                         _sandbox.CONFIG_TEXT)
        self.assertEqual(notes.pending_notes(), [])

    def test_ac13_unrunnable_suite_refuses_the_same_way(self):
        """Тот же вызов на дереве без `tests/` вовсе — прогон не стартует:
        исход тот же, что при красном наборе (именованный отказ, коммита в
        origin нет, удержанной записи нет), а не молчаливый пропуск гейта.

        Ловит мутацию: «набор не запустился» трактуется как «гонять нечего,
        значит можно коммитить» (`if tests_dir.is_dir()` вокруг всего
        гейта) — правка уезжает в origin, и тест красен на отсутствии
        `SystemExit`.
        """
        source = self.source_file(_sandbox.CONFIG_TEXT_POISONED,
                                  "config-draft.yaml")
        before = self.origin_head()

        message = self.refusal(notes.cmd_doc_commit, _sandbox.CONFIG_REL,
                               "--from", str(source), "--message", MESSAGE)

        self.assert_named_refusal(message, "tests", "набор", "прогон")
        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_show(_sandbox.CONFIG_REL),
                         _sandbox.CONFIG_TEXT)
        self.assertEqual(notes.pending_notes(), [])

    def test_ac14_accept_red_commits_and_journal_carries_path_and_reason(self):
        """Тот же вызов с `--accept-red "<основание>"` при том же красном
        наборе: правка приезжает в origin, а журнал пульта несёт и путь, и
        основание обхода.

        Ловит мутацию: флаг принят, но основание в журнал не попадает
        (запись пишется без него либо не пишется вовсе) — тест красен на
        отсутствии основания в журнале при верном содержимом origin.
        """
        self.seed_suite(_sandbox.CONDITIONAL_SUITE)
        source = self.source_file(_sandbox.CONFIG_TEXT_POISONED,
                                  "config-draft.yaml")

        self.doc_commit(_sandbox.CONFIG_REL, "--from", str(source),
                        "--message", MESSAGE, "--accept-red", ACCEPT_REASON)

        self.assertEqual(self.origin_show(_sandbox.CONFIG_REL),
                         _sandbox.CONFIG_TEXT_POISONED)
        journal = self.journal_text()
        self.assertIn(_sandbox.CONFIG_REL, journal, journal)
        self.assertIn(ACCEPT_REASON, journal, journal)


if __name__ == "__main__":
    unittest.main()
