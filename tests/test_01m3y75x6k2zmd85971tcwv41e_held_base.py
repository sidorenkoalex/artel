"""Удержанный `doc-commit` сверяется с базой сборки; `note --pending` и
`note --drop-pending <id>` — просмотр и снятие одной удержанной записи.

Сценарии — стендом с настоящим bare `origin` и главной копией-пином
(`tests.sandbox.RealGitSandbox`): запись удерживается окном тишины
(задача в состоянии из `config.NOTE_SILENCE_WINDOW_STATES`), затем origin
и пин двигаются, затем идёт отправка удержанных записей.

Группа: долгоживущий
Красен до реализации: удержанная запись не несёт базы, флаш сверяет origin только с пином (после сдвига пина чужая правка затирается без отказа), предупреждения «база не сохранена» нет, а `note --pending`/`--drop-pending` argparse отвергает — тесты AC-1, AC-2, AC-4, AC-6, AC-7, AC-8 падают.
"""
import io
import json
import os
import random
import re
import shutil
import tempfile
import time
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import config, notes, store
from tests.sandbox import RealGitSandbox, clone_artel_from_origin

DOC_REL = "docs/roadmap.md"
GUIDE_REL = "docs/guide.md"
BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое | orchestrator/x.py |
"""
LEGACY_KEYS = {"kind", "path", "content", "message", "accept_red"}
STALE_PHRASE = "файл изменился в origin после сборки записи"
REBUILD_PHRASE = "собери заново от origin"
NO_BASE_PHRASE = "база не сохранена"
ALPHABET = "абвгдежзиклмнопрстуфхцчшщэюяabcdefghijklmnopqrstuvwxyz0123456789"


def run_command(fn, argv) -> str:
    """Вывод команды (stdout и stderr) вместе с текстом отказа, если он был."""
    buf = io.StringIO()
    exit_text = ""
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            fn(list(argv))
        except SystemExit as exc:
            exit_text = "" if exc.code is None else str(exc.code)
    return buf.getvalue() + "\n" + exit_text


class HeldBaseSandbox(RealGitSandbox):
    """Главная копия с `docs/backlog.md`, двумя документами и bare origin,
    синхронным с пином; окно тишины закрыто."""

    def setUp(self):
        super().setUp()
        role_patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role_patcher.start()
        self.addCleanup(role_patcher.stop)
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.origin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        self.git("init", "-q", "--bare", self.origin)
        self.git("remote", "add", "origin", self.origin)
        self.doc_text = f"# Роадмап\n\n{self.words(6)}\n"
        self.guide_text = f"# Руководство\n\n{self.words(6)}\n"
        for rel, text in ((notes.BACKLOG_REL, BACKLOG_TEXT),
                          (DOC_REL, self.doc_text),
                          (GUIDE_REL, self.guide_text)):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "документы")
        self.push_main()
        # Клон артели из origin, как его заводит `init` (ADR-0021 п.1,
        # этап 2): команды Оператора коммитят и пушат через него.
        clone_artel_from_origin(self.origin)
        self.source_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.source_dir, ignore_errors=True)

    # --- случайные входы ---

    def word(self, n: int = 8) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(n))

    def words(self, k: int) -> str:
        return " ".join(self.word(self.rng.randrange(3, 10)) for _ in range(k))

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # --- git ---

    def push_main(self) -> None:
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def origin_git(self, *args) -> str:
        return self.git("-C", self.origin, *args)

    def origin_head(self) -> str:
        return self.origin_git("rev-parse", config.MAIN_BRANCH).strip()

    def origin_show(self, rel: str) -> str | None:
        listed = self.origin_git("ls-tree", "--name-only", config.MAIN_BRANCH,
                                 "--", rel)
        if not listed.strip():
            return None
        return self.origin_git("show", f"{config.MAIN_BRANCH}:{rel}")

    def origin_blob(self, rel: str) -> str:
        return self.origin_git("rev-parse",
                               f"{config.MAIN_BRANCH}:{rel}").strip()

    def origin_commits_touching(self, since: str, rel: str) -> list:
        out = self.origin_git("log", "--format=%H",
                              f"{since}..{config.MAIN_BRANCH}", "--", rel)
        return [line for line in out.split("\n") if line.strip()]

    def advance_pin_and_origin(self, rel: str, text: str) -> None:
        """Чужая правка пути в главной копии, отправленная в origin: пин и
        голова origin совпадают — сверка с пином прошла бы."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("add", rel)
        self.git("commit", "-q", "-m", "чужая правка")
        self.push_main()

    def push_foreign_past_the_pin(self, rel: str, text: str) -> None:
        """Чужая правка пути в origin, пин остаётся прежним."""
        self.advance_pin_and_origin(rel, text)
        self.git("reset", "-q", "--hard", "HEAD~1")

    # --- окно тишины и записи ---

    def open_window(self) -> None:
        store.insert_task(store.db(), "T-WIN", "окно тишины",
                          config.NOTE_SILENCE_WINDOW_STATES[0], "task/t-win",
                          config.DEFAULT_TARGET, 10.0)

    def close_window(self) -> None:
        conn = store.db()
        conn.execute("DELETE FROM tasks WHERE id=?", ("T-WIN",))
        conn.commit()

    def source(self, text: str) -> Path:
        path = Path(self.source_dir) / f"{self.word()}.md"
        path.write_bytes(text.encode("utf-8"))
        return path

    def doc_commit(self, rel: str, text: str) -> str:
        return run_command(notes.cmd_doc_commit,
                           [rel, "--from", str(self.source(text)),
                            "--message", self.words(2)])

    def hold_doc_commit(self, rel: str, text: str) -> None:
        before = len(notes.pending_notes())
        out = self.doc_commit(rel, text)
        self.assertEqual(len(notes.pending_notes()), before + 1,
                         self.msg(f"запись не удержана: {out}"))

    def hold_note(self, text: str) -> None:
        before = len(notes.pending_notes())
        out = run_command(notes.cmd_note, ["копилка", "--text", text])
        self.assertEqual(len(notes.pending_notes()), before + 1,
                         self.msg(f"заметка не удержана: {out}"))

    def pending_dir(self) -> Path:
        return config.ROOT / ".artel" / "notes-pending"

    def pending_ids(self) -> list:
        return sorted(p.stem for p in self.pending_dir().glob("*.json"))

    def pending_paths(self) -> list:
        return [r.get("path") for r in notes.pending_notes()]


def string_values(obj) -> list:
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in string_values(v)]
    if isinstance(obj, (list, tuple)):
        return [s for v in obj for s in string_values(v)]
    return [obj] if isinstance(obj, str) else []


class HeldRecordBaseTest(HeldBaseSandbox):

    def test_ac1_held_record_stores_pin_blob_or_absent_mark(self):
        """Удержанная запись несёт blob-sha пути из HEAD главной копии.

        Сценарий: окно тишины открыто, `doc-commit` существующего пути
        удерживается — среди значений записи есть blob-sha `HEAD:<путь>`
        (не sha коммита и не blob содержимого записи); `doc-commit` нового
        пути (в HEAD его нет) удерживается — запись несёт поле сверх
        прежнего формата (`kind`/`path`/`content`/`message`) — отметку
        «файла не было».

        Ловит мутацию: `_hold_pending` пишет прежний словарь без базы либо
        база берётся как sha коммита HEAD/blob нового содержимого — среди
        значений записи нет blob-sha пути в HEAD, у записи нового файла нет
        поля сверх прежних.
        """
        base = self.git("rev-parse", f"HEAD:{DOC_REL}").strip()
        new_rel = f"docs/research/{self.word().lower()}.md"
        self.open_window()

        self.hold_doc_commit(DOC_REL, f"# Роадмап\n\n{self.words(5)}\n")
        self.hold_doc_commit(new_rel, f"# Новое\n\n{self.words(5)}\n")

        records = {r["path"]: r for r in notes.pending_notes()}
        self.assertIn(base, string_values(records[DOC_REL]),
                      self.msg(f"база {base} не сохранена: {records[DOC_REL]}"))
        extra = set(records[new_rel]) - LEGACY_KEYS
        self.assertTrue(extra, self.msg(
            f"у записи нового файла нет отметки «файла не было»: "
            f"{records[new_rel]}"))


class StaleBaseRefusalTest(HeldBaseSandbox):

    def _stale_scenario(self, send) -> None:
        """Сценарий 02.10: запись удержана на базе B, затем путь изменён в
        origin и пин сдвинут на голову origin, затем отправка `send`."""
        base = self.git("rev-parse", f"HEAD:{DOC_REL}").strip()
        held_text = f"# Роадмап\n\n{self.words(5)}\n"
        guide_text = f"# Руководство\n\n{self.words(5)}\n"
        self.open_window()
        self.hold_doc_commit(DOC_REL, held_text)
        self.hold_doc_commit(GUIDE_REL, guide_text)
        foreign = self.doc_text + "".join(
            f"{self.words(4)}\n" for _ in range(self.rng.randrange(3, 22)))
        self.advance_pin_and_origin(DOC_REL, foreign)
        origin_blob = self.origin_blob(DOC_REL)
        before = self.origin_head()
        self.close_window()

        out = send()

        self.assertIn(STALE_PHRASE, out, self.msg(out))
        self.assertIn(REBUILD_PHRASE, out, self.msg(out))
        self.assertIn(base[:7], out, self.msg(f"база {base} не названа: {out}"))
        self.assertIn(origin_blob[:7], out,
                      self.msg(f"blob origin {origin_blob} не назван: {out}"))
        self.assertEqual(self.origin_show(DOC_REL), foreign, self.msg(out))
        self.assertEqual(self.origin_commits_touching(before, DOC_REL), [],
                         self.msg(out))
        self.assertIn(DOC_REL, self.pending_paths(), self.msg(out))
        self.assertEqual(self.origin_show(GUIDE_REL), guide_text, self.msg(out))
        self.assertNotIn(GUIDE_REL, self.pending_paths(), self.msg(out))

    def test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others(self):
        """`doc-commit --flush` после сдвига пина на изменённый origin.

        Сценарий 02.10 (см. `_stale_scenario`): отказ называет «файл
        изменился в origin после сборки записи», базу и blob origin и
        «собери заново от origin»; чужой текст в origin цел, коммитов по
        пути нет, запись осталась удержанной, вторая запись прохода
        (другой документ) отправлена.

        Ловит мутацию: при отправке удержанной записи сверяется только
        origin против пина (как до задачи) — пин совпал с origin, чужие
        строки затёрты коммитом, отказа нет.
        """
        self._stale_scenario(
            lambda: run_command(notes.cmd_doc_commit, ["--flush"]))

    def test_ac2_note_flush_refuses_stale_base(self):
        """`note --flush` — тот же отказ сценария 02.10.

        Ловит мутацию: сверка базы заведена только в путь
        `cmd_doc_commit`, а не в общую отправку удержанных записей —
        `note --flush` затирает чужие строки.
        """
        self._stale_scenario(lambda: run_command(notes.cmd_note, ["--flush"]))

    def test_ac2_opportunistic_flush_refuses_stale_base(self):
        """Попутная отправка (обычная `note` вне окна) — тот же отказ.

        Ловит мутацию: сверка базы стоит только на явном флаше
        (`explicit=True`), попутная отправка идёт по-старому — ровно
        коммит 28b09389, стёрший чужие строки.
        """
        self._stale_scenario(lambda: run_command(
            notes.cmd_note,
            ["копилка", "--text", f"4 | 02.10 | {self.word()} | o.py"]))


class MatchingBaseSendTest(HeldBaseSandbox):

    def test_ac3_base_matching_origin_is_sent(self):
        """База совпадает с blob пути в origin — запись отправляется.

        Сценарий: запись удержана; origin уходит вперёд коммитом по
        ДРУГОМУ пути (blob пути прежний, пин отстал от origin); после
        закрытия окна `doc-commit --flush` — содержимое записи в origin,
        `pending_notes()` пуст.

        Ловит мутацию: база сравнивается не с blob'ом пути в origin, а с
        sha головы origin либо с blob'ом нового содержимого — запись
        отказывает «файл изменился» и висит.
        """
        held_text = f"# Роадмап\n\n{self.words(5)}\n"
        self.open_window()
        self.hold_doc_commit(DOC_REL, held_text)
        self.push_foreign_past_the_pin(GUIDE_REL, f"# другое\n{self.words(3)}\n")
        self.close_window()

        out = run_command(notes.cmd_doc_commit, ["--flush"])

        self.assertEqual(self.origin_show(DOC_REL), held_text, self.msg(out))
        self.assertEqual(notes.pending_notes(), [], self.msg(out))
        self.assertNotIn(STALE_PHRASE, out, self.msg(out))


class NewFileBaseTest(HeldBaseSandbox):

    def test_ac4_new_file_absent_in_origin_is_sent(self):
        """Новый файл: удержан с отметкой «файла не было», в origin файла
        нет — отправляется.

        Сценарий: путь `docs/research/<случайное>.md` нет ни в пине, ни в
        origin; запись удержана; после закрытия окна `doc-commit --flush`
        — файл появился в origin с содержимым записи, запись снята.

        Ловит мутацию: отметка «файла не было» сравнивается с отсутствием
        blob'а как с расхождением (или пишется пустой строкой, не равной
        «нет blob'а») — новый файл отказывает и висит.
        """
        rel = f"docs/research/{self.word().lower()}.md"
        text = f"# Новое\n\n{self.words(5)}\n"
        self.open_window()
        self.hold_doc_commit(rel, text)
        self.close_window()

        out = run_command(notes.cmd_doc_commit, ["--flush"])

        self.assertEqual(self.origin_show(rel), text, self.msg(out))
        self.assertEqual(notes.pending_notes(), [], self.msg(out))

    def test_ac4_new_file_appeared_in_origin_is_refused(self):
        """Новый файл появился в origin до отправки — отказ AC-2.

        Сценарий: запись нового пути удержана с отметкой «файла не было»;
        затем чужой коммит заводит этот путь, пин сдвинут на голову
        origin (сверка с пином прошла бы); флаш — отказ «файл изменился в
        origin после сборки записи», чужой файл в origin цел, коммитов по
        пути нет, запись удержана.

        Ловит мутацию: отметка «файла не было» трактуется как «базы нет»
        и запись идёт по пиновой сверке — пин совпал с origin, чужой файл
        затёрт.
        """
        rel = f"docs/research/{self.word().lower()}.md"
        self.open_window()
        self.hold_doc_commit(rel, f"# Моё\n\n{self.words(5)}\n")
        foreign = f"# Чужое\n\n{self.words(5)}\n"
        self.advance_pin_and_origin(rel, foreign)
        origin_blob = self.origin_blob(rel)
        before = self.origin_head()
        self.close_window()

        out = run_command(notes.cmd_doc_commit, ["--flush"])

        self.assertIn(STALE_PHRASE, out, self.msg(out))
        self.assertIn(origin_blob[:7], out, self.msg(out))
        self.assertEqual(self.origin_show(rel), foreign, self.msg(out))
        self.assertEqual(self.origin_commits_touching(before, rel), [],
                         self.msg(out))
        self.assertIn(rel, self.pending_paths(), self.msg(out))


class ImmediatePinCheckTest(HeldBaseSandbox):

    def test_ac5_immediate_send_still_refuses_on_pin(self):
        """Немедленная отправка при origin ≠ пин — отказ пиновой сверки.

        Сценарий: чужая правка пути ушла в origin мимо пина (пин прежний);
        окно закрыто; `doc-commit` этого пути — отказ с текстом
        `notes.DOC_COMMIT_BASE_REFUSAL`, чужой текст в origin цел, запись
        не удержана.

        Ловит мутацию: пиновая сверка немедленной отправки заменена новой
        сверкой с базой (или снята) — отказ приходит другим текстом либо
        чужая правка затёрта.
        """
        foreign = self.doc_text + f"{self.words(4)}\n"
        self.push_foreign_past_the_pin(DOC_REL, foreign)

        out = self.doc_commit(DOC_REL, f"# Роадмап\n\n{self.words(5)}\n")

        self.assertIn(notes.DOC_COMMIT_BASE_REFUSAL, out, self.msg(out))
        self.assertEqual(self.origin_show(DOC_REL), foreign, self.msg(out))
        self.assertEqual(notes.pending_notes(), [], self.msg(out))


class LegacyRecordTest(HeldBaseSandbox):

    def _hold_legacy(self, text: str) -> None:
        """Запись прежнего формата — без поля базы, как до этой задачи."""
        d = self.pending_dir()
        d.mkdir(parents=True, exist_ok=True)
        name = f"{int(time.time() * 1000):013d}-{uuid.uuid4().hex[:8]}.json"
        (d / name).write_text(json.dumps(
            {"kind": notes.DOC_COMMIT_KIND, "path": DOC_REL, "content": text,
             "message": self.words(2)}, ensure_ascii=False), encoding="utf-8")

    def test_ac6_legacy_record_pin_matches_is_sent_with_warning(self):
        """Запись без базы, origin совпадает с пином — отправлена с
        предупреждением «база не сохранена».

        Ловит мутацию: запись без базы молча идёт по пиновой сверке (нет
        предупреждения) либо отсутствие базы читается как отметка «файла
        не было» — отказ вместо отправки.
        """
        text = f"# Роадмап\n\n{self.words(5)}\n"
        self._hold_legacy(text)

        out = run_command(notes.cmd_doc_commit, ["--flush"])

        self.assertIn(NO_BASE_PHRASE, out, self.msg(out))
        self.assertEqual(self.origin_show(DOC_REL), text, self.msg(out))
        self.assertEqual(notes.pending_notes(), [], self.msg(out))

    def test_ac6_legacy_record_pin_differs_is_refused_with_warning(self):
        """Запись без базы, origin ушёл от пина — отказ
        `DOC_COMMIT_BASE_REFUSAL` и предупреждение «база не сохранена».

        Ловит мутацию: запись без базы пропускается без всякой сверки —
        чужая правка в origin затёрта, отказа нет; либо предупреждение
        печатается только на успешной отправке.
        """
        self._hold_legacy(f"# Роадмап\n\n{self.words(5)}\n")
        foreign = self.doc_text + f"{self.words(4)}\n"
        self.push_foreign_past_the_pin(DOC_REL, foreign)

        out = run_command(notes.cmd_doc_commit, ["--flush"])

        self.assertIn(NO_BASE_PHRASE, out, self.msg(out))
        self.assertIn(notes.DOC_COMMIT_BASE_REFUSAL, out, self.msg(out))
        self.assertEqual(self.origin_show(DOC_REL), foreign, self.msg(out))
        self.assertIn(DOC_REL, self.pending_paths(), self.msg(out))


class PendingListTest(HeldBaseSandbox):

    TIME_RE = re.compile(r"\d{1,2}:\d{2}|\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}")

    def test_ac7_pending_lists_each_record_with_truncated_content(self):
        """`note --pending` — строка на каждую удержанную запись.

        Сценарий: удержаны `doc-commit` документа с однострочным
        содержимым длиннее 80 знаков и заметка копилки с длинным текстом;
        в выводе для каждого id файла записи есть строка с этим id, где
        у `doc-commit` — вид и путь, у заметки — раздел, у обеих — время
        и первые 80 знаков содержимого, но не 81-й знак.

        Ловит мутацию: содержимое не обрезается (или режется по другой
        длине), либо строка записи не несёт id файла/пути/раздела — тест
        красен на строке записи.
        """
        doc_content = self.word(self.rng.randrange(90, 140))
        note_text = (f"4 | 02.10 | {self.word(self.rng.randrange(90, 140))} "
                     f"| o.py")
        self.open_window()
        self.hold_doc_commit(DOC_REL, doc_content)
        self.hold_note(note_text)
        by_kind = {}
        for path in self.pending_dir().glob("*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            by_kind[record["kind"]] = path.stem

        out = run_command(notes.cmd_note, ["--pending"])
        lines = out.split("\n")

        def line_of(record_id: str) -> str:
            found = [line for line in lines if record_id in line]
            self.assertEqual(len(found), 1,
                             self.msg(f"строка записи {record_id}: {out}"))
            return found[0]

        doc_line = line_of(by_kind[notes.DOC_COMMIT_KIND])
        self.assertIn(notes.DOC_COMMIT_KIND, doc_line, self.msg(doc_line))
        self.assertIn(DOC_REL, doc_line, self.msg(doc_line))
        self.assertIn(doc_content[:80], doc_line, self.msg(doc_line))
        self.assertNotIn(doc_content[:81], doc_line, self.msg(doc_line))
        note_line = line_of(by_kind["insert"])
        self.assertIn("копилка", note_line, self.msg(note_line))
        self.assertIn(note_text[:80], note_line, self.msg(note_line))
        self.assertNotIn(note_text[:81], note_line, self.msg(note_line))
        for line in (doc_line, note_line):
            stripped = line
            for record_id in by_kind.values():
                stripped = stripped.replace(record_id, "")
            self.assertRegex(stripped, self.TIME_RE,
                             self.msg(f"нет времени удержания: {line}"))
        self.assertEqual(len(notes.pending_notes()), 2, self.msg(out))


class DropPendingTest(HeldBaseSandbox):

    def test_ac8_drop_pending_removes_exactly_one_and_journals(self):
        """`note --drop-pending <id>` снимает ровно эту запись и пишет журнал.

        Сценарий: удержаны три записи (два документа и заметка), снимается
        случайно выбранная; две другие остаются в `pending_notes()`, файла
        снятой нет; в журнале `steps` появилась строка, называющая id
        снятой записи, с непустым актором.

        Ловит мутацию: снимаются все записи (как `--flush` без отправки)
        либо первая по порядку, а не по id; либо журнал не пишется — тест
        красен на составе `pending_notes()` или на пустом журнале.
        """
        self.open_window()
        self.hold_doc_commit(DOC_REL, f"# Роадмап\n\n{self.words(5)}\n")
        self.hold_doc_commit(GUIDE_REL, f"# Руководство\n\n{self.words(5)}\n")
        self.hold_note(f"4 | 02.10 | {self.words(3)} | o.py")
        ids = self.pending_ids()
        victim = self.rng.choice(ids)
        victim_record = json.loads(
            (self.pending_dir() / f"{victim}.json").read_text(encoding="utf-8"))
        before_rows = store.db().execute(
            "SELECT COUNT(*) FROM steps").fetchone()[0]

        out = run_command(notes.cmd_note, ["--drop-pending", victim])

        self.assertEqual(self.pending_ids(), [i for i in ids if i != victim],
                         self.msg(out))
        self.assertNotIn(victim_record, notes.pending_notes(), self.msg(out))
        self.assertEqual(len(notes.pending_notes()), 2, self.msg(out))
        rows = store.db().execute(
            "SELECT actor, action, detail FROM steps ORDER BY rowid").fetchall()
        new_rows = rows[before_rows:]
        naming = [r for r in new_rows
                  if victim in f"{r[1]} {r[2]}" and (r[0] or "").strip()]
        self.assertTrue(naming, self.msg(f"журнал не называет {victim}: "
                                         f"{new_rows}; вывод: {out}"))


class RoleRefusalTest(HeldBaseSandbox):

    def test_ac9_pending_and_drop_pending_refuse_under_role(self):
        """Под признаком шага роли `--pending` и `--drop-pending` отказывают.

        Сценарий: Оператор удержал две записи; затем из окружения роли
        (непустой маркер `ARTEL_ROLE` случайного имени) `note --pending` —
        отказ без id записей в выводе; `note --drop-pending <id>` — отказ,
        обе записи на месте.

        Ловит мутацию: ветки `--pending`/`--drop-pending` разобраны до
        рубежа `runner.in_role_environment()` — роль видит перечень записей
        или снимает запись.
        """
        self.open_window()
        self.hold_doc_commit(DOC_REL, f"# Роадмап\n\n{self.words(5)}\n")
        self.hold_note(f"4 | 02.10 | {self.words(3)} | o.py")
        ids = self.pending_ids()
        role_env = {config.ARTEL_ROLE_ENV: f"role_{self.word().lower()}"}

        for argv in (["--pending"], ["--drop-pending", self.rng.choice(ids)]):
            with mock.patch.dict(os.environ, role_env):
                buf = io.StringIO()
                with redirect_stdout(buf), redirect_stderr(buf):
                    with self.assertRaises(SystemExit, msg=self.msg(argv[0])):
                        notes.cmd_note(argv)
            for record_id in ids:
                self.assertNotIn(record_id, buf.getvalue(),
                                 self.msg(f"{argv[0]}: {buf.getvalue()}"))
            self.assertEqual(self.pending_ids(), ids, self.msg(argv[0]))


if __name__ == "__main__":
    unittest.main()
