"""Юнит-тесты чистых функций `orchestrator/notes.py` (tasks/
01M1VBEHTDYPK3E4RRFHWYYYW3): разбор таблицы раздела, вставка/`--append`,
хранилище удержанных заметок, разбор аргументов `cmd_note`.

Полный сценарий (fetch/commit/push от `origin/main`, повтор
non-fast-forward, удержание при сетевом отказе, журнал) — приёмочные
тесты `tasks/01M1VBEHTDYPK3E4RRFHWYYYW3/acceptance_tests/` через
настоящий git (`NoteSandbox`); здесь — функции, для которых реальный
git не нужен, быстрым `TmpRootTest`.

Окно тишины (01M2B6JS2BZNBW9WSHT1RPFXTE, AC-9): `NoteSilenceSandbox`
ниже — стенд с настоящим bare origin (по образцу приёмочных тестов
задачи), покрывающий AC-1..AC-8 отдельно от локальных, залоченных
`tasks/01M2B6JS2BZNBW9WSHT1RPFXTE/acceptance_tests/` (те материализуются
только на время задачи и не остаются постоянным регрессом).
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, doctor, notes, store  # noqa: E402
from tests.sandbox import RealGitSandbox, SchemaTmpRootTest, TmpRootTest  # noqa: E402

BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое УНИКАЛЬНЫЙКЛЮЧ | orchestrator/x.py |
| 2 | 01.01 | повтор ПОВТОРКЛЮЧ один | orchestrator/y.py |
| 2 | 01.01 | повтор ПОВТОРКЛЮЧ два | orchestrator/z.py |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта | Заметка |
|---|---|---|---|---|---|---|
| 1 | Кандидат A | Суть A | $10 | orchestrator/a.py | сразу | — |
"""


class RowCellsTest(unittest.TestCase):

    def test_strips_outer_pipes_and_whitespace(self):
        self.assertEqual(notes._row_cells("| 1 | два | 3 |"), ["1", "два", "3"])


class ApplyInsertTest(unittest.TestCase):

    def test_inserts_right_after_separator(self):
        new_text, section_key = notes._apply_insert(
            BACKLOG_TEXT, "копилка",
            "9 | 09.09 | новое | orchestrator/new.py")
        self.assertEqual(section_key, "копилка")
        lines = new_text.splitlines()
        sep_idx = lines.index("|---|---|---|---|")
        self.assertEqual(lines[sep_idx + 1],
                         "| 9 | 09.09 | новое | orchestrator/new.py |")
        # Прежняя первая строка данных сдвинута, не потеряна.
        self.assertIn("старое УНИКАЛЬНЫЙКЛЮЧ", lines[sep_idx + 2])

    def test_column_count_mismatch_refuses_naming_expected_count(self):
        with self.assertRaises(SystemExit) as cm:
            notes._apply_insert(BACKLOG_TEXT, "копилка", "1 | 2 | 3")
        self.assertIn("4", str(cm.exception))

    def test_unknown_section_heading_refuses(self):
        with self.assertRaises(SystemExit):
            notes._apply_insert("без разделов вовсе", "копилка", "1|2|3|4")


class ApplyAppendTest(unittest.TestCase):

    def test_unique_key_appends_to_last_column_only(self):
        new_text, section_key = notes._apply_append(
            BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "доп. текст")
        self.assertEqual(section_key, "копилка")
        matched = [ln for ln in new_text.splitlines()
                  if "УНИКАЛЬНЫЙКЛЮЧ" in ln][0]
        self.assertIn("orchestrator/x.py", matched)
        self.assertIn("доп. текст", matched)
        # Остальные строки раздела не задеты байт-в-байт.
        untouched = [ln for ln in BACKLOG_TEXT.splitlines()
                    if "ПОВТОРКЛЮЧ один" in ln][0]
        self.assertIn(untouched, new_text)

    def test_zero_matches_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_append(BACKLOG_TEXT, "НЕТТАКОГОКЛЮЧА", "текст")

    def test_multiple_matches_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_append(BACKLOG_TEXT, "ПОВТОРКЛЮЧ", "текст")


class ApplyDropTest(unittest.TestCase):

    def test_removes_matched_row_only_neighbours_untouched(self):
        new_text, section_key, observation = notes._apply_drop(
            BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ")
        self.assertEqual(section_key, "копилка")
        self.assertNotIn("УНИКАЛЬНЫЙКЛЮЧ", new_text)
        self.assertIn("orchestrator/x.py", observation)
        # Соседние строки раздела остаются байт-в-байт прежними.
        for marker in ("ПОВТОРКЛЮЧ один", "ПОВТОРКЛЮЧ два"):
            untouched = [ln for ln in BACKLOG_TEXT.splitlines()
                        if marker in ln][0]
            self.assertIn(untouched, new_text)
        # Другой раздел не задет.
        self.assertIn("Кандидат A", new_text)

    def test_zero_matches_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_drop(BACKLOG_TEXT, "НЕТТАКОГОКЛЮЧА")

    def test_multiple_matches_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_drop(BACKLOG_TEXT, "ПОВТОРКЛЮЧ")


class ApplySetStateTest(unittest.TestCase):

    def test_replaces_last_column_entirely_not_appends(self):
        new_text, section_key = notes._apply_set_state(
            BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "новое состояние")
        self.assertEqual(section_key, "копилка")
        matched = [ln for ln in new_text.splitlines()
                  if "УНИКАЛЬНЫЙКЛЮЧ" in ln][0]
        cells = notes._row_cells(matched)
        self.assertEqual(cells[-1], "новое состояние")
        self.assertNotIn("orchestrator/x.py", cells[-1])

    def test_multiple_matches_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_set_state(BACKLOG_TEXT, "ПОВТОРКЛЮЧ", "текст")


class ApplySetPriorityTest(unittest.TestCase):

    def test_replaces_first_column_with_valid_value(self):
        new_text, section_key = notes._apply_set_priority(
            BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "3")
        self.assertEqual(section_key, "копилка")
        matched = [ln for ln in new_text.splitlines()
                  if "УНИКАЛЬНЫЙКЛЮЧ" in ln][0]
        cells = notes._row_cells(matched)
        self.assertEqual(cells[0], "3")

    def test_value_above_range_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_set_priority(BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "5")

    def test_value_below_range_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_set_priority(BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "0")

    def test_non_numeric_value_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_set_priority(BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "х")


class PendingNotesStorageTest(TmpRootTest):

    def test_empty_by_default(self):
        self.assertEqual(notes.pending_notes(), [])

    def test_hold_then_read_back_round_trips(self):
        request = {"kind": "insert", "section": "копилка", "text": "x"}
        notes._hold_pending(request)
        pending = notes.pending_notes()
        self.assertEqual(pending, [request])

    def test_two_holds_are_both_visible(self):
        notes._hold_pending({"kind": "insert", "section": "копилка", "text": "a"})
        notes._hold_pending({"kind": "append", "key": "k", "text": "b"})
        self.assertEqual(len(notes.pending_notes()), 2)


class CmdNoteArgumentValidationTest(SchemaTmpRootTest):
    """Отказы разбора аргументов, не доходящие до git вовсе (пустая
    `pending_notes()` — оппортунистический flush внутри `cmd_note` не
    находит, что отправлять, и не трогает сеть).

    Схема БД заведена явно (`store.create_schema`, не полновесный
    `catalog.cmd_init`): с этой задачи `cmd_note` читает `merge_locks`/
    `tasks` на КАЖДЫЙ вызов (проверка окна тишины, требование 1) —
    без схемы `store.merge_lock_row`/`store.all_tasks` падали бы
    `sqlite3.OperationalError` раньше ожидаемого `SystemExit` разбора
    аргументов."""

    def test_no_arguments_at_all_refuses(self):
        with self.assertRaises(SystemExit):
            notes.cmd_note([])

    def test_section_without_text_refuses(self):
        with self.assertRaises(SystemExit):
            notes.cmd_note(["копилка"])

    def test_append_without_text_refuses(self):
        with self.assertRaises(SystemExit):
            notes.cmd_note(["--append", "ключ"])

    def test_set_state_without_text_refuses(self):
        with self.assertRaises(SystemExit):
            notes.cmd_note(["--set-state", "ключ"])

    def test_set_priority_without_text_refuses(self):
        with self.assertRaises(SystemExit):
            notes.cmd_note(["--set-priority", "ключ"])

    def test_flush_with_nothing_pending_is_a_noop(self):
        notes.cmd_note(["--flush"])  # не должно поднять исключение


class CheckPendingNotesTest(TmpRootTest):

    def test_ok_when_nothing_pending(self):
        self.assertEqual(doctor.check_pending_notes().status, "ok")

    def test_warn_when_something_pending(self):
        notes._hold_pending({"kind": "insert", "section": "копилка", "text": "x"})
        check = doctor.check_pending_notes()
        self.assertEqual(check.status, "warn")
        self.assertIn("note --flush", check.detail)


class NoteSilenceSandbox(RealGitSandbox):
    """Стенд окна тишины `note` (01M2B6JS2BZNBW9WSHT1RPFXTE, AC-9): bare
    `origin` синхронный с `BACKLOG_TEXT`, схема БД уже создана
    (`RealGitSandbox.setUp`) — пустая, без задач и без держателя
    `merge_locks`: окно тишины закрыто по умолчанию, пока тест сам не
    заведёт задачу нужного состояния/держателя мьютекса merge-окна."""

    def setUp(self):
        super().setUp()
        self.origin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        self.git("init", "-q", "--bare", self.origin)
        self.git("remote", "add", "origin", self.origin)
        docs = self.root / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "backlog.md").write_text(BACKLOG_TEXT, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "backlog")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def origin_run(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", self.origin, *args],
                              capture_output=True, text=True)

    def origin_head(self) -> str:
        res = self.origin_run("rev-parse", config.MAIN_BRANCH)
        return res.stdout.strip() if res.returncode == 0 else ""

    def origin_backlog(self) -> str:
        res = self.origin_run("show", f"{config.MAIN_BRANCH}:docs/backlog.md")
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def insert_task_in_state(self, state: str, task_id: str = "T-WIN") -> None:
        store.insert_task(store.db(), task_id, "окно тишины", state,
                          f"task/{task_id}", config.DEFAULT_TARGET, 10.0)

    def set_live_merge_lock(self, task_id: str = "T-LOCK",
                            session_id: str = "s-live") -> None:
        store.set_merge_lock(store.db(), task_id, session_id, os.getpid(),
                             socket.gethostname(), store.now())


class SilenceWindowReasonTest(NoteSilenceSandbox):

    def test_ac1_live_merge_lock_alone_without_any_task_state_opens_window(self):
        """Живой держатель `merge_locks` — единственный триггер (`store.
        all_tasks` пуст) — окно тишины уже открыто (условие ИЛИ, AC-1).

        Ловит мутацию: реализация проверяет только `store.all_tasks` и
        игнорирует держателя `merge_locks` — при пустом наборе задач
        такая версия ошибочно вернула бы `None` (окна нет)."""
        self.set_live_merge_lock()
        self.assertIsNotNone(notes._silence_window_reason())

    def test_no_holder_and_no_task_in_set_closes_window(self):
        """База: пустая БД — окна нет (AC-5).

        Ловит мутацию: удержание навсегда (условие открытия окна
        перевёрнуто) — здесь уже красно на непустом результате."""
        self.assertIsNone(notes._silence_window_reason())

    def test_escalated_state_does_not_open_window(self):
        """`escalated` НЕ входит в `config.NOTE_SILENCE_WINDOW_STATES`
        (ровно пять состояний AC-1, не шесть состояний `zone_lock.
        BLOCKING_STATES`) — задача в `escalated` не открывает окно.

        Ловит мутацию: набор состояний случайно берёт чужую константу
        (`zone_lock.BLOCKING_STATES`, несущую `escalated`) — тест красен
        на непустом результате."""
        self.insert_task_in_state("escalated")
        self.assertIsNone(notes._silence_window_reason())

    def test_dead_merge_lock_holder_does_not_open_window(self):
        """Протухший heartbeat держателя `merge_locks` — тот же признак
        мёртвости, что `merge_lock._holder_is_dead` — не открывает окно
        сам по себе (без задачи в состоянии набора).

        Ловит мутацию: реализация не проверяет живость держателя (любая
        строка `merge_locks` трактуется как открытое окно) — тест красен
        на непустом результате."""
        old_heartbeat = "2000-01-01 00:00:00Z"
        store.set_merge_lock(store.db(), "T-DEAD", "s-dead", 999999,
                             "иной-хост", old_heartbeat)
        self.assertIsNone(notes._silence_window_reason())


class WindowHoldsValidNoteTest(NoteSilenceSandbox):

    def test_ac2_all_five_kinds_held_not_pushed_when_task_in_dev(self):
        """Задача в `in_dev` держит окно тишины открытым — все пять видов
        записи по очереди удерживаются, `origin` не сдвигается ни разу.

        Ловит мутацию: окно проверяется только для вида `insert` (ветка
        удержания добавлена лишь в путь раздела с `--text`, а `--append`/
        `--drop`/`--set-state`/`--set-priority` продолжают пушить
        немедленно) — тест красен на изменившемся `origin_head()` уже на
        втором вызове."""
        self.insert_task_in_state("in_dev")
        before = self.origin_head()

        self.capture(notes.cmd_note,
                    ["копилка", "--text",
                     "9 | 09.09 | вставка при окне | orchestrator/i.py"])
        self.capture(notes.cmd_note,
                    ["--append", "УНИКАЛЬНЫЙКЛЮЧ", "--text", "доп-текст"])
        self.capture(notes.cmd_note, ["--drop", "УНИКАЛЬНЫЙКЛЮЧ"])
        self.capture(notes.cmd_note,
                    ["--set-state", "ПОВТОРКЛЮЧ один", "--text", "новое"])
        self.capture(notes.cmd_note,
                    ["--set-priority", "ПОВТОРКЛЮЧ один", "--text", "3"])

        self.assertEqual(before, self.origin_head())
        pending = notes.pending_notes()
        self.assertEqual([p["kind"] for p in pending],
                         ["insert", "append", "drop", "set-state",
                          "set-priority"])

    def test_ac3_hold_message_prefix_and_suffix(self):
        """Сообщение удержания несёт фиксированные пролог/эпилог и
        непустую причину между ними (AC-3).

        Ловит мутацию: реализация молчит при удержании (не печатает
        ничего) — тест красен на пустом `captured`."""
        self.insert_task_in_state("acceptance")

        captured = self.capture(
            notes.cmd_note,
            ["копилка", "--text", "9 | 09.09 | сообщение | orchestrator/m.py"])

        self.assertIn("заметка удержана:", captured, captured)
        self.assertIn("отправка — note --flush либо автоматически "
                      "следующим note вне окна", captured, captured)
        reason = captured.split("заметка удержана:", 1)[1].split(";", 1)[0]
        self.assertTrue(reason.strip())

    def test_ac4_unmatched_key_refuses_before_hold_even_with_window_open(self):
        """Окно открыто (`merge_gate`), `--append` нацелен на
        несуществующий ключ: отказ валидации происходит раньше решения
        об удержании — `origin` не меняется, `notes-pending/` пуст
        (AC-4).

        Ловит мутацию: проверка окна тишины перенесена ПЕРЕД валидацией
        — тест красен на непустом `pending_notes()` вместо `SystemExit`."""
        self.insert_task_in_state("merge_gate")
        before = self.origin_head()

        with self.assertRaises(SystemExit):
            notes.cmd_note(["--append", "НЕТТАКОГОКЛЮЧА", "--text", "текст"])

        self.assertEqual(before, self.origin_head())
        self.assertEqual(notes.pending_notes(), [])

    def test_ac9_held_note_uses_existing_pending_json_shape(self):
        """Запись, удержанная окном тишины, лежит в `.artel/notes-pending/`
        и несёт те же поля, что и удержание по сетевому отказу — общий
        формат `_hold_pending`, не параллельный (AC-9).

        Ловит мутацию: окно тишины удерживает запись собственным,
        параллельным путём/форматом — тест красен на пустом
        `pending_notes()`."""
        self.insert_task_in_state("review")

        self.capture(
            notes.cmd_note,
            ["копилка", "--text", "9 | 09.09 | формат | orchestrator/fmt.py"])

        pending = notes.pending_notes()
        self.assertEqual(len(pending), 1, pending)
        self.assertEqual(pending[0]["kind"], "insert")
        self.assertEqual(pending[0]["section"], "копилка")


class WindowBypassAndNoWindowTest(NoteSilenceSandbox):

    def test_ac5_no_window_pushes_immediately_unchanged(self):
        """Без держателя `merge_locks` и без задач в состояниях набора —
        push немедленный, как до этой задачи (AC-5).

        Ловит мутацию: условие удержания перевёрнуто (держит всегда) —
        тест красен на пустом `origin_backlog()`."""
        self.capture(notes.cmd_note,
                    ["копилка", "--text",
                     "9 | 09.09 | без окна | orchestrator/nw.py"])

        self.assertIn("без окна", self.origin_backlog())
        self.assertEqual(notes.pending_notes(), [])

    def test_ac6_flush_pushes_held_note_while_window_stays_open(self):
        """`note --flush` допушивает удержанную запись, даже когда окно
        ОСТАЁТСЯ открытым той же задачей (AC-6, явный обход).

        Ловит мутацию: `--flush` делегирует оппортунистическому флашу,
        уважающему окно (требование 7), вместо безусловного пути — тест
        красен на непустом `pending_notes()` после вызова."""
        self.insert_task_in_state("review")
        self.capture(notes.cmd_note,
                    ["копилка", "--text",
                     "9 | 09.09 | до флаша | orchestrator/f.py"])
        self.assertEqual(len(notes.pending_notes()), 1)

        self.capture(notes.cmd_note, ["--flush"])

        self.assertIn("до флаша", self.origin_backlog())
        self.assertEqual(notes.pending_notes(), [])

    def test_ac7_now_pushes_immediately_and_does_not_hold(self):
        """`note --now <раздел> --text …` пушит немедленно в обход
        открытого окна, не удерживая запись вовсе (AC-7).

        Ловит мутацию: `--now` принят флагом, но обход не реализован
        (запись удерживается как обычная) — тест красен на пустом
        `origin_backlog()` и непустом `pending_notes()`."""
        self.insert_task_in_state("acceptance")

        self.capture(
            notes.cmd_note,
            ["--now", "копилка", "--text",
             "9 | 09.09 | срочно | orchestrator/now.py"])

        self.assertIn("срочно", self.origin_backlog())
        self.assertEqual(notes.pending_notes(), [])

    def test_ac8_open_window_leaves_previously_held_note_untouched(self):
        """Заметка уже удержана ДО вызова; окно открыто (`verifying`) —
        обычный вызов `note` не допушивает старую удержанную заметку,
        новая тоже уходит в удержание (AC-8, оппортунистический флаш
        уважает окно).

        Ловит мутацию: оппортунистический флаш безусловен — тест красен
        на изменившемся `origin_head()` либо на потере старой заметки."""
        notes._hold_pending({"kind": "insert", "section": "копилка",
                             "text": "9 | 09.09 | старая | orchestrator/o.py"})
        self.insert_task_in_state("verifying")
        before = self.origin_head()

        self.capture(notes.cmd_note,
                    ["копилка", "--text",
                     "9 | 09.09 | новая при открытом окне | orchestrator/p.py"])

        self.assertEqual(before, self.origin_head())
        pending = notes.pending_notes()
        self.assertEqual(len(pending), 2, pending)

    def test_ac8_closed_window_still_flushes_previously_held_note(self):
        """Та же предпосылка, но БЕЗ открытого окна — обычный вызов
        `note` допушивает старую удержанную заметку оппортунистически
        (AC-8, поведение вне окна не меняется).

        Ловит мутацию: условие инвертировано (флаш только при открытом
        окне) — тест красен на непустом `pending_notes()`."""
        notes._hold_pending({"kind": "insert", "section": "копилка",
                             "text": "9 | 09.09 | старая без окна | orchestrator/q.py"})

        self.capture(notes.cmd_note,
                    ["копилка", "--text",
                     "9 | 09.09 | новая без окна | orchestrator/r.py"])

        text = self.origin_backlog()
        self.assertIn("старая без окна", text)
        self.assertIn("новая без окна", text)
        self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
