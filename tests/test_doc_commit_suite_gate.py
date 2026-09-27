"""Юнит-тесты гейта полного набора `tests/` перед коммитом конфигурации
Оператора (`orchestrator/notes.py::_suite_gate_refusal`, tasks/
01M3HST4SGX0SPKAGNHVY7DWHM, требования 13-16): красный и не запустившийся
набор отказывают, `--accept-red` — осознанный обход с основанием в
журнале, путь `docs/**` прогона не заводит.

Стенд — `tests/test_doc_commit.py::DocCommitSandbox` (настоящий bare
`origin`, синхронный с главной копией, и посеянный ЗЕЛЁНЫЙ набор
`tests/`), сюда добавлен только пересев набора в дереве прогона. Прогон
набора где нужно настоящий (исход «набор не запустился вовсе» субпроцесса
вообще не требует), а где предмет проверки — КАКОЕ дерево видит прогон,
там `acceptance.run_full_suite` подменяется шпионом, читающим это дерево:
иначе «прогон идёт до применения правки» и «прогон идёт после» не
различить.

Причина гейта — прецедент 27.09: правка `roles.yaml` (a6da0abe) сделала
главную ветку красной, потребовался откат (d910c523) и встали ветки
волны.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, notes, store  # noqa: E402
from tests.test_doc_commit import (DOC_REL, GREEN_SUITE_REL,  # noqa: E402
                                   DocCommitSandbox)

CONFIG_REL = notes.DOC_COMMIT_CONFIG_PATHS[0]
NEW_CONFIG_TEXT = "developer:\n  model: sonnet\n"
MESSAGE = "поворот крутилки"
ACCEPT_REASON = "красный тест не про эту правку, чиню отдельной задачей"

RED_SUITE_TEXT = '''"""Набор стенда: красен всегда."""


def test_seed_always_red():
    assert False, "набор красный намеренно"
'''


class SuiteGateSandbox(DocCommitSandbox):
    """`DocCommitSandbox` + пересев набора `tests/` в дереве прогона:
    дерево рабочего репозитория `doc-commit` чекаутится из origin, поэтому
    набор меняется в главной копии и пушится."""

    def reseed_suite(self, text: str | None) -> None:
        path = self.root / GREEN_SUITE_REL
        if text is None:
            path.unlink()
        else:
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "набор tests/")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def config_source(self) -> str:
        return str(self.source_file(NEW_CONFIG_TEXT, "config-draft.yaml"))

    def commit_config(self, *extra: str) -> str:
        return self.doc_commit(CONFIG_REL, "--from", self.config_source(),
                               "--message", MESSAGE, *extra)

    def refuse_config(self, *extra: str) -> str:
        with self.assertRaises(SystemExit) as ctx:
            notes.cmd_doc_commit([CONFIG_REL, "--from", self.config_source(),
                                  "--message", MESSAGE, *extra])
        return str(ctx.exception)

    def journal_text(self) -> str:
        rows = store.db().execute(
            "SELECT actor, action, detail FROM steps ORDER BY id").fetchall()
        return "\n".join(" ".join(str(col) for col in row) for row in rows)

    def spy_suite(self, green: bool = True):
        """Шпион `acceptance.run_full_suite`: запоминает корень прогона и
        содержимое конфигурации в нём на момент вызова."""
        seen = []

        def run(root):
            seen.append((Path(root),
                         (Path(root) / CONFIG_REL).read_text(encoding="utf-8")))
            return green, "1 passed in 0.1s" if green else "FAILED шпион"

        patcher = mock.patch.object(notes.acceptance, "run_full_suite", run)
        patcher.start()
        self.addCleanup(patcher.stop)
        return seen


class RedSuiteTest(SuiteGateSandbox):

    def test_red_suite_refuses_naming_the_failed_test(self):
        """Настоящий прогон красного набора: `doc-commit` конфигурации
        отказывает, называя упавший тест, коммита в origin нет,
        конфигурация в origin прежняя, удержанной записи не появилось
        (требование 13).

        Ловит мутацию: гейт не заведён вовсе либо стоит ПОСЛЕ `git
        commit`/push — правка уезжает в origin, и тест красен на
        отсутствии `SystemExit`.
        """
        self.reseed_suite(RED_SUITE_TEXT)
        before = self.origin_head()

        message = self.refuse_config()

        self.assertIn("test_seed_always_red", message, message)
        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_show(CONFIG_REL),
                         "developer:\n  model: opus\n")
        self.assertEqual(notes.pending_notes(), [])

    def test_unrunnable_suite_refuses_the_same_way(self):
        """Дерево без `tests/` вовсе — прогон не стартует: исход тот же,
        что при красном наборе (отказ, коммита нет, удержанной записи
        нет), а не молчаливый пропуск гейта (требование 14).

        Ловит мутацию: «набор не запустился» трактуется как «гонять
        нечего, значит можно коммитить» (`if tests_dir.is_dir()` вокруг
        всего гейта) — правка уезжает в origin.
        """
        self.reseed_suite(None)
        before = self.origin_head()

        message = self.refuse_config()

        self.assertIn("tests/", message, message)
        self.assertEqual(before, self.origin_head())
        self.assertEqual(notes.pending_notes(), [])

    def test_green_suite_lets_the_commit_through(self):
        """Зелёный набор (посеян стендом) — коммит проходит, содержимое
        приезжает в origin: гейт закрыт по умолчанию, но не наглухо.

        Ловит мутацию: гейт отказывает независимо от исхода прогона
        (условие перевёрнуто) — правка конфигурации перестаёт коммититься
        вовсе.
        """
        self.commit_config()

        self.assertEqual(self.origin_show(CONFIG_REL), NEW_CONFIG_TEXT)
        self.assertEqual(notes.pending_notes(), [])


class SuiteTreeTest(SuiteGateSandbox):

    def test_suite_runs_on_the_tree_with_the_change_already_applied(self):
        """Прогон видит дерево, в котором правка УЖЕ записана: шпион
        читает конфигурацию в корне прогона и находит там НОВОЕ содержимое
        (требование 13).

        Ловит мутацию: порядок «прогнать набор → записать файл» вместо
        обратного либо прогон не на том дереве (`config.ROOT` вместо
        рабочего репозитория) — шпион видит старую конфигурацию или падает
        на её отсутствии.
        """
        seen = self.spy_suite(green=True)

        self.commit_config()

        self.assertEqual(len(seen), 1, seen)
        root, content = seen[0]
        self.assertEqual(content, NEW_CONFIG_TEXT)
        self.assertEqual(root, config.ROOT / ".artel" / "notes-work")
        self.assertEqual(self.origin_show(CONFIG_REL), NEW_CONFIG_TEXT)

    def test_docs_path_does_not_run_the_suite_at_all(self):
        """Путь `docs/**` прогона не заводит: шпион не позван ни разу, а
        документ доезжает до origin поверх красного набора (требование 16).

        Ловит мутацию: прогон поставлен на ВСЕ пути `doc-commit` (проверка
        `path in DOC_COMMIT_CONFIG_PATHS` забыта либо инвертирована) —
        документный путь отказывает по красному набору.
        """
        self.reseed_suite(RED_SUITE_TEXT)
        seen = self.spy_suite(green=False)
        new_text = "# Роадмап\n\nНовый раздел.\n"

        self.doc_commit(DOC_REL, "--from", str(self.source_file(new_text)),
                        "--message", "перенос раздела")

        self.assertEqual(seen, [])
        self.assertEqual(self.origin_show(DOC_REL), new_text)

    def test_open_window_holds_the_record_and_the_gate_fires_on_flush(self):
        """Окно тишины открыто: запись удерживается, прогона нет вовсе —
        отправки ещё не было. Прогон случается на `doc-commit --flush`,
        когда отправка действительно идёт; красный набор оставляет запись
        удержанной (тот же исход, что у любой записи, не прошедшей
        собственную валидацию при флаше, — `doctor.check_pending_notes`
        её и покажет), и origin не сдвигается.

        Ловит мутацию: гейт вынесен из `_commit_and_push` выше, к
        построению правки — набор гоняется на каждом удержании, то есть
        минуты прогона тратятся на запись, которая никуда не поедет; либо
        наоборот, флаш обходит гейт, и красная правка уезжает в origin
        мимо требования 13.
        """
        self.reseed_suite(RED_SUITE_TEXT)
        seen = self.spy_suite(green=False)
        self.open_silence_window()
        before = self.origin_head()

        self.commit_config()

        self.assertEqual(seen, [])
        self.assertEqual(len(notes.pending_notes()), 1, notes.pending_notes())

        self.doc_commit("--flush")

        self.assertEqual(len(seen), 1, seen)
        self.assertEqual(before, self.origin_head())
        self.assertEqual(len(notes.pending_notes()), 1, notes.pending_notes())


class AcceptRedTest(SuiteGateSandbox):

    def test_accept_red_commits_and_journal_carries_path_and_reason(self):
        """`--accept-red "<основание>"` при красном наборе: правка
        приезжает в origin, а журнал пульта несёт и путь, и основание
        обхода (требование 15).

        Ловит мутацию: флаг принят, но основание в журнал не попадает
        (запись пишется без него либо не пишется вовсе) — обход становится
        невидимым.
        """
        self.reseed_suite(RED_SUITE_TEXT)

        self.commit_config("--accept-red", ACCEPT_REASON)

        self.assertEqual(self.origin_show(CONFIG_REL), NEW_CONFIG_TEXT)
        journal = self.journal_text()
        self.assertIn(CONFIG_REL, journal, journal)
        self.assertIn(ACCEPT_REASON, journal, journal)

    def test_accept_red_skips_the_run_entirely(self):
        """С флагом набор не гоняется вовсе: шпион не позван ни разу.

        Ловит мутацию: флаг учитывается только ПОСЛЕ прогона (исход
        игнорируется, но минуты тратятся) — шпион позван, и тест красен.
        """
        seen = self.spy_suite(green=False)

        self.commit_config("--accept-red", ACCEPT_REASON)

        self.assertEqual(seen, [])
        self.assertEqual(self.origin_show(CONFIG_REL), NEW_CONFIG_TEXT)

    def test_accept_red_without_reason_refuses_by_substance_not_argparse(self):
        """Флаг без основания — ИМЕНОВАННЫЙ отказ, называющий флаг, а не
        код выхода 2 самого argparse (требование 15, «без основания флаг
        отказывает»); origin не сдвигается, удержанной записи нет.

        Ловит мутацию: флаг объявлен обычным `add_argument("--accept-red")`
        — голый флаг тогда даёт `SystemExit(2)` без внятного текста, и
        Оператор не знает, чего от него хотят.
        """
        before = self.origin_head()

        message = self.refuse_config("--accept-red")

        self.assertNotEqual(message.strip(), "2", message)
        self.assertIn("--accept-red", message, message)
        self.assertEqual(before, self.origin_head())
        self.assertEqual(notes.pending_notes(), [])

    def test_green_suite_with_accept_red_still_journals_the_bypass(self):
        """Флаг при ЗЕЛЁНОМ наборе: коммит проходит, и обход всё равно
        записан журналом — Оператор объявил осознанное решение, и оно
        остаётся в истории независимо от того, что показал бы прогон.

        Ловит мутацию: запись журнала привязана к исходу прогона, которого
        при флаге нет вовсе (`if not green and reason`) — обход уходит
        бесследно, а отличить его от обычного коммита потом нечем.
        """
        self.commit_config("--accept-red", ACCEPT_REASON)

        journal = self.journal_text()
        self.assertIn(notes.ACCEPT_RED_JOURNAL_ACTION, journal, journal)
        self.assertIn(ACCEPT_REASON, journal, journal)


if __name__ == "__main__":
    unittest.main()
