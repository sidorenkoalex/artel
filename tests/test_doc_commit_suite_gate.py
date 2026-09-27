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
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, notes, store  # noqa: E402
from tests.sandbox import capture  # noqa: E402
from tests.test_doc_commit import (DOC_REL, GREEN_SUITE_REL,  # noqa: E402
                                   GREEN_SUITE_TEXT, DocCommitSandbox)

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

    def work_status(self, rel: str) -> str:
        """`git status --porcelain` пути в ОБЩЕМ рабочем репозитории
        `note`/`doc-commit`: грязный файл после отказа — предмет проверки
        (R1-F1 ревью итерации 1)."""
        work_dir = config.ROOT / ".artel" / "notes-work"
        return subprocess.run(
            ["git", "-C", str(work_dir), "status", "--porcelain", "--", rel],
            capture_output=True, text=True).stdout.strip()

    def note_row(self, marker: str) -> str:
        return capture(notes.cmd_note,
                       ["копилка", "--text", f"4 | 09.09 | {marker} | o.py"])

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


class GateRefusalLeavesNoDirtTest(SuiteGateSandbox):
    """Отказ гейта выходит `sys.exit`'ом ПОСЛЕ записи правки в общий
    рабочий репозиторий — оба регресса R1-F1 ревью итерации 1 про то, чем
    он оставляет дерево после себя."""

    def _push_foreign_config_change(self) -> None:
        """Сторонняя правка того же пути конфигурации, уехавшая в origin
        позже базы главной копии (тот же приём, что
        `tests/test_doc_commit.py::PinBaseCheckTest`)."""
        (self.root / CONFIG_REL).write_text("developer:\n  model: haiku\n",
                                            encoding="utf-8")
        self.git("commit", "-a", "-q", "-m", "чужая правка конфигурации")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.git("reset", "-q", "--hard", "HEAD~1")

    def test_repeat_after_fixing_the_suite_commits_the_same_change(self):
        """Отказ гейта не оставляет записанную правку в дереве рабочего
        репозитория: `git status` по пути пуст, и ТА ЖЕ команда после
        починки набора доводит правку до origin.

        Ловит мутацию: отказ гейта не снимает правку с дерева, а сверка
        «содержимое уже совпадает» читает ФАЙЛ дерева вместо blob'а origin
        — повтор отказывает «содержимое уже совпадает с origin/main» даже
        при зелёном наборе, и правка конфигурации не проходит уже никогда.
        """
        self.reseed_suite(RED_SUITE_TEXT)

        message = self.refuse_config()

        self.assertIn("test_seed_always_red", message, message)
        self.assertEqual(self.work_status(CONFIG_REL), "")

        self.reseed_suite(GREEN_SUITE_TEXT)
        self.commit_config()

        self.assertEqual(self.origin_show(CONFIG_REL), NEW_CONFIG_TEXT)
        self.assertEqual(notes.pending_notes(), [])

    def test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change(self):
        """Второй сценарий R1-F1: после отказа гейта тот же путь изменён в
        origin сторонней правкой — заметка `note` всё равно доезжает до
        origin, удержанной записи не появляется.

        Ловит мутацию: дерево остаётся грязным, а `checkout -B` в
        `_fetch_and_build` идёт без `-f` и без проверки кода возврата —
        сборка молча идёт на дереве прошлого коммита, и КАЖДАЯ заметка
        отказывает «не удалось отправить заметку в origin».
        """
        self.reseed_suite(RED_SUITE_TEXT)
        self.refuse_config()
        self._push_foreign_config_change()

        self.note_row("ЗАМЕТКАПОСЛЕОТКАЗА")

        self.assertIn("ЗАМЕТКАПОСЛЕОТКАЗА",
                      self.origin_show(notes.BACKLOG_REL))
        self.assertEqual(notes.pending_notes(), [])

    def test_dirty_work_tree_is_forced_to_origin_before_the_next_record(self):
        """Дерево общего рабочего репозитория, оставшееся с посторонним
        файлом пути, который есть в origin (аварийный выход команды, снятие
        процесса), приводится к origin ПРИНУДИТЕЛЬНО — заметка доезжает.

        Ловит мутацию: `checkout -B` в `_fetch_and_build` идёт без `-f`
        (спотыкается о постороннее содержимое пути) и без проверки кода
        возврата — сборка молча идёт на пустом дереве прошлого состояния, и
        заметка отказывает вместо того, чтобы доехать.
        """
        work_config = config.ROOT / ".artel" / "notes-work" / CONFIG_REL
        work_config.parent.mkdir(parents=True, exist_ok=True)
        work_config.write_text("developer:\n  model: ГРЯЗЬ\n",
                               encoding="utf-8")

        self.note_row("ЗАМЕТКАПОВЕРХГРЯЗИ")

        self.assertIn("ЗАМЕТКАПОВЕРХГРЯЗИ",
                      self.origin_show(notes.BACKLOG_REL))
        self.assertEqual(notes.pending_notes(), [])

    def test_leftover_file_in_the_work_tree_is_not_read_as_origin_content(self):
        """Мусор в дереве общего рабочего репозитория не читается как
        содержимое origin: файл нового пути, оставшийся в
        `.artel/notes-work` и равный тому, что коммитят, ложного отказа
        «содержимое уже совпадает» не даёт — путь доезжает до origin.

        Ловит мутацию: сверка «уже совпадает» сравнивает содержимое с
        ФАЙЛОМ дерева, а дерево перед сборкой не чистится — новый путь не
        закоммитить, пока Оператор не уберёт файл в рабочем репозитории
        руками.
        """
        rel = "docs/research/new.md"
        text = "# новый документ\n"
        leftover = config.ROOT / ".artel" / "notes-work" / rel
        leftover.parent.mkdir(parents=True, exist_ok=True)
        leftover.write_text(text, encoding="utf-8")

        self.doc_commit(rel, "--from", str(self.source_file(text, "new.md")),
                        "--message", "новый документ")

        self.assertEqual(self.origin_show(rel), text)


class HeldConfigRecordFlushTest(SuiteGateSandbox):

    def test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks(self):
        """Удержанная правка конфигурации не превращает обычную `note` в
        молчаливый прогон полного набора: прогона нет, причина напечатана,
        сама заметка доезжает до origin. Явный `doc-commit --flush` прогон
        заводит и печатает причину отказа (R1-F3 ревью итерации 1).

        Ловит мутацию: попутный флаш отправляет любую удержанную запись —
        прогон позван на обычной `note`; либо `_flush_pending` снова глотает
        `SystemExit` целиком — явный флаш ничего не печатает, и запись висит
        без объяснения.
        """
        seen = self.spy_suite(green=False)
        self.open_silence_window()
        self.commit_config()
        self.close_silence_window()
        self.assertEqual(len(notes.pending_notes()), 1, notes.pending_notes())

        note_output = self.note_row("ЗАМЕТКАПРИУДЕРЖАНИИ")

        self.assertEqual(seen, [])
        self.assertIn(CONFIG_REL, note_output, note_output)
        self.assertIn("ЗАМЕТКАПРИУДЕРЖАНИИ",
                      self.origin_show(notes.BACKLOG_REL))
        self.assertEqual(len(notes.pending_notes()), 1, notes.pending_notes())

        flush_output = self.doc_commit("--flush")

        self.assertEqual(len(seen), 1, seen)
        self.assertIn("tests/", flush_output, flush_output)
        self.assertEqual(len(notes.pending_notes()), 1, notes.pending_notes())

    def test_accept_red_record_is_sent_by_the_opportunistic_flush(self):
        """Удержанная запись с `--accept-red` прогона не заведёт, поэтому
        попутным флашем отправляется как любая другая: обход Оператор уже
        объявил, ждать явного флаша нечего.

        Ловит мутацию: попутный флаш откладывает ЛЮБУЮ запись пути
        конфигурации (условие пропуска не смотрит на `accept_red`) —
        осознанный обход перестаёт доезжать сам, и тест красен на старой
        конфигурации в origin.
        """
        self.reseed_suite(RED_SUITE_TEXT)
        self.open_silence_window()
        self.commit_config("--accept-red", ACCEPT_REASON)
        self.close_silence_window()

        self.note_row("ЗАМЕТКАПРИОБХОДЕ")

        self.assertEqual(self.origin_show(CONFIG_REL), NEW_CONFIG_TEXT)
        self.assertEqual(notes.pending_notes(), [])


class AcceptRedOnDocsPathTest(SuiteGateSandbox):

    def test_docs_path_accept_red_writes_no_bypass_journal_row(self):
        """`--accept-red` на пути `docs/**`: документ коммитится, а записи
        об обходе в журнале пульта НЕТ — гейта на этом пути не существует
        (требование 16), и запись была бы ложной (R1-F4 ревью итерации 1).

        Ловит мутацию: запись журнала пишется по одному наличию флага, без
        сверки пути — журнал несёт обход, которого не было, и Оператор
        ищет по нему несуществующую правку конфигурации.
        """
        new_text = "# Роадмап\n\nбез обхода\n"

        self.doc_commit(DOC_REL, "--from", str(self.source_file(new_text)),
                        "--message", "раздел", "--accept-red", ACCEPT_REASON)

        self.assertEqual(self.origin_show(DOC_REL), new_text)
        journal = self.journal_text()
        self.assertNotIn(notes.ACCEPT_RED_JOURNAL_ACTION, journal, journal)
        self.assertNotIn(ACCEPT_REASON, journal, journal)


if __name__ == "__main__":
    unittest.main()
