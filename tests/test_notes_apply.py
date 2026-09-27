"""Юнит-тесты `note --apply <файл> --message "<основание>"`
(`orchestrator/notes.py`, tasks/01M3HST4SGX0SPKAGNHVY7DWHM, требования
9-12): замена `docs/backlog.md` заготовкой целиком одним изолированным
коммитом, сверка базы, сверка формы заготовки, перечень удалённых строк в
журнале, удержание окном тишины.

Стенд — настоящий bare `origin` по образцу
`tests/test_notes.py::NoteSilenceSandbox` и
`tests/test_doc_commit.py::DocCommitSandbox`: предмет проверки — что
именно приезжает в origin и что остаётся с главной копией, заглушкой
`gitcmd` этого не изобразить. Собственная фикстура документа нужна,
потому что `--apply` сверяет ТРИ раздела, а у обоих соседних стендов их
два.

Приёмочные тесты задачи материализуются только на её время; постоянный
регресс — здесь.
"""
import io
import contextlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, notes, store  # noqa: E402
from tests.sandbox import RealGitSandbox, capture  # noqa: E402

KOPILKA_HEADER = "| П | Дата | Наблюдение | Где | Состояние |"
KOPILKA_HEADER_WIDE = "| П | Дата | Наблюдение | Где | Состояние | Лишняя |"

# Ячейка «Наблюдение» первой снимаемой строки длиннее 80 знаков: маркер
# ХВОСТ стоит ЗА границей усечения записи журнала (требование 12), маркер
# СНЯТАЯОДИН — до неё.
LONG_DROPPED_CELL = "СНЯТАЯОДИН " + "х" * 70 + " ХВОСТ"

BACKLOG_TEXT = f"""# Бэклог пульта

## Копилка

{KOPILKA_HEADER}
|---|---|---|---|---|
| 1 | 01.01 | ОСТАЁТСЯ наблюдение | orchestrator/x.py | состояние |
| 3 | 07.07 | {LONG_DROPPED_CELL} | orchestrator/d1.py | состояние |
| 4 | 07.07 | СНЯТАЯДВА наблюдение | orchestrator/d2.py | состояние |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта |
|---|---|---|---|---|---|
| 1 | Кандидат А | Суть А | $10 | orchestrator/a.py | сразу |

## Очередь Оператора

| П | Действие | Условие |
|---|---|---|
| 1 | Действие А | сразу |
"""

REASON = "разнос бэклога по решению Оператора"


def draft_with_extra_row() -> str:
    """Корректная заготовка: те же три раздела и те же шапки, в «Копилке»
    на одну строку больше."""
    extra = ("| 2 | 27.09 | ЗАГОТОВКАПРИМЕНЕНА | orchestrator/n.py | новое |")
    lines = BACKLOG_TEXT.split("\n")
    lines.insert(lines.index(KOPILKA_HEADER) + 2, extra)
    return "\n".join(lines)


def draft_without_dropped_rows() -> str:
    """Корректная заготовка, потерявшая обе строки-маркера СНЯТАЯ*."""
    return "\n".join(line for line in BACKLOG_TEXT.split("\n")
                     if "СНЯТАЯ" not in line)


class ApplySandbox(RealGitSandbox):
    """Главная копия с трёхраздельным `docs/backlog.md`, синхронная с bare
    `origin`: сверка базы проходит, окно тишины закрыто (БД пуста)."""

    def setUp(self):
        super().setUp()
        self.origin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        self.git("init", "-q", "--bare", self.origin)
        self.git("remote", "add", "origin", self.origin)
        path = self.root / notes.BACKLOG_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(BACKLOG_TEXT, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "бэклог")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.source_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.source_dir, ignore_errors=True)

    def source_file(self, text: str, name: str = "draft-backlog.md") -> Path:
        path = Path(self.source_dir) / name
        path.write_text(text, encoding="utf-8")
        return path

    def apply_draft(self, text: str, message: str = REASON) -> str:
        return capture(notes.cmd_note,
                       ["--apply", str(self.source_file(text)),
                        "--message", message])

    def refusal(self, *argv: str) -> str:
        """Текст отказа `cmd_note` (`SystemExit`); stdout подавлен — отказ
        может печатать по дороге, и это не предмет проверки."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), \
                self.assertRaises(SystemExit) as ctx:
            notes.cmd_note(list(argv))
        return str(ctx.exception)

    def draft_refusal(self, text: str) -> str:
        return self.refusal("--apply", str(self.source_file(text)),
                            "--message", REASON)

    def origin_run(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", self.origin, *args],
                              capture_output=True, text=True)

    def origin_head(self) -> str:
        res = self.origin_run("rev-parse", config.MAIN_BRANCH)
        return res.stdout.strip() if res.returncode == 0 else ""

    def origin_commit_count(self) -> int:
        res = self.origin_run("rev-list", "--count", config.MAIN_BRANCH)
        return int(res.stdout.strip()) if res.returncode == 0 else -1

    def origin_backlog(self) -> str:
        res = self.origin_run("show",
                              f"{config.MAIN_BRANCH}:{notes.BACKLOG_REL}")
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def origin_message(self) -> str:
        return self.origin_run("log", "-1", "--format=%B",
                               config.MAIN_BRANCH).stdout

    def main_copy_snapshot(self) -> tuple:
        return (self.git("rev-parse", "HEAD").strip(),
                self.git("rev-parse", "--abbrev-ref", "HEAD").strip(),
                self.git("status", "--porcelain"))

    def journal_text(self) -> str:
        rows = store.db().execute(
            "SELECT actor, action, detail FROM steps ORDER BY id").fetchall()
        return "\n".join(" ".join(str(col) for col in row) for row in rows)

    def open_silence_window(self, task_id: str = "T-WIN") -> None:
        store.insert_task(store.db(), task_id, "окно тишины",
                          config.NOTE_SILENCE_WINDOW_STATES[0],
                          f"task/{task_id}", config.DEFAULT_TARGET, 10.0)

    def push_foreign_backlog_change(self, text: str) -> None:
        """Чужая правка `docs/backlog.md`, уехавшая в origin ПОЗЖЕ базы
        главной копии (тот же приём, что `tests/test_doc_commit.py::
        PinBaseCheckTest._push_foreign_change_past_the_pin`)."""
        (self.root / notes.BACKLOG_REL).write_text(text, encoding="utf-8")
        self.git("commit", "-a", "-q", "-m", "чужая правка бэклога")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.git("reset", "-q", "--hard", "HEAD~1")


class ApplySuccessTest(ApplySandbox):

    def test_draft_becomes_the_document_in_one_commit(self):
        """Корректная заготовка приезжает в `origin/main` целиком:
        содержимое пути равно заготовке байт-в-байт, добавлен РОВНО один
        коммит, сообщение коммита несёт основание `--message` целиком, а
        HEAD, ветка и рабочее дерево главной копии прежние (требование 9).

        Ловит мутацию: `--apply` правит и коммитит документ в рабочей
        копии пульта (`config.ROOT`) вместо изолированного рабочего
        репозитория — снимок главной копии меняется; либо основание
        усекается до 80 знаков, как у строки `note`.
        """
        draft = draft_with_extra_row()
        before_commits = self.origin_commit_count()
        before_main = self.main_copy_snapshot()

        output = self.apply_draft(draft)

        self.assertEqual(self.origin_backlog(), draft)
        self.assertEqual(self.origin_commit_count(), before_commits + 1)
        self.assertIn(REASON, self.origin_message())
        self.assertEqual(before_main, self.main_copy_snapshot())
        self.assertEqual(notes.pending_notes(), [])
        self.assertIn(self.origin_head(), output, output)

    def test_journal_names_dropped_row_count_and_truncated_rows(self):
        """Журнал пульта после успеха несёт число удалённых строк (2) и
        сами строки, причём длинная усечена — маркер за границей 80 знаков
        в журнал не попадает (требование 12).

        Ловит мутацию: перечисляются ДОБАВЛЕННЫЕ строки вместо удалённых
        (стороны сравнения перепутаны) — ни одного маркера СНЯТАЯ* в
        журнале нет; либо усечение снято — в журнал уезжает ХВОСТ.
        """
        draft = draft_without_dropped_rows()

        self.apply_draft(draft)

        journal = self.journal_text()
        self.assertIn("удалено строк: 2", journal, journal)
        self.assertIn("СНЯТАЯОДИН", journal, journal)
        self.assertIn("СНЯТАЯДВА", journal, journal)
        self.assertNotIn("ХВОСТ", journal, journal)

    def test_untouched_draft_counts_zero_dropped_rows(self):
        """Заготовка, которая ничего не снимает, даёт в журнале «удалено
        строк: 0» — запись пишется всегда, а не только когда есть что
        перечислять (требование 12).

        Ловит мутацию: запись журнала пишется только при непустом
        перечне — успешный `--apply` без удалений уходит бесследно, и
        Оператор не может отличить его от неисполненного.
        """
        self.apply_draft(draft_with_extra_row())

        self.assertIn("удалено строк: 0", self.journal_text())


class ApplyRefusalTest(ApplySandbox):

    def test_document_changed_in_origin_past_the_base_refuses(self):
        """Чужая правка документа уехала в origin позже базы главной
        копии: `--apply` отказывает, коммита нет, в origin чужой текст,
        удержанной записи не появилось (требование 10).

        Ловит мутацию: `--apply` коммитит заготовку поверх свежего origin,
        не сверяя базу (сверка доехала только до `doc-commit`) — чужая
        правка молча затирается ЦЕЛИКОМ, не одной строкой.
        """
        foreign = BACKLOG_TEXT + "\n<!-- чужая правка в origin -->\n"
        self.push_foreign_backlog_change(foreign)
        before = self.origin_head()

        message = self.draft_refusal(draft_with_extra_row())

        self.assertIn(notes.DOC_COMMIT_BASE_REFUSAL, message, message)
        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_backlog(), foreign)
        self.assertEqual(notes.pending_notes(), [])

    def test_draft_without_a_section_refuses_before_commit(self):
        """Заготовка, потерявшая раздел «## Очередь Оператора» целиком, —
        именованный отказ до коммита; документ в origin прежний, удержанной
        записи нет (требование 11).

        Ловит мутацию: проверяется только число колонок шапок, а наличие
        самих разделов — нет; тогда заготовка, из которой раздел выпал,
        доезжает до коммита и уносит его из документа.
        """
        before = self.origin_head()
        draft = BACKLOG_TEXT.split("## Очередь Оператора")[0]

        message = self.draft_refusal(draft)

        self.assertIn("Очередь Оператора", message, message)
        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_backlog(), BACKLOG_TEXT)
        self.assertEqual(notes.pending_notes(), [])

    def test_draft_with_section_heading_but_no_table_refuses(self):
        """Раздел на месте, а таблицы у него нет — тоже отказ (требование
        11: «у каждого есть таблица»).

        Ловит мутацию: проверка ограничена наличием заголовка раздела
        (`heading in draft`) — раздел без таблицы проходит, и следующий
        `note` в него отказывает уже на живом документе.
        """
        draft = BACKLOG_TEXT.replace(
            "| П | Действие | Условие |\n|---|---|---|\n"
            "| 1 | Действие А | сразу |\n", "текста таблицы больше нет\n")

        message = self.draft_refusal(draft)

        self.assertIn("Очередь Оператора", message, message)
        self.assertEqual(self.origin_backlog(), BACKLOG_TEXT)
        self.assertEqual(notes.pending_notes(), [])

    def test_draft_with_widened_header_refuses(self):
        """Шапка «Копилки» на одну колонку шире, чем в origin, —
        именованный отказ до коммита (требование 11).

        Ловит мутацию: сверяется только наличие разделов, а число колонок
        шапки — нет; расширенная шапка уезжает в документ, и все
        существующие строки раздела перестают ей соответствовать.
        """
        before = self.origin_head()

        message = self.draft_refusal(
            BACKLOG_TEXT.replace(KOPILKA_HEADER, KOPILKA_HEADER_WIDE))

        self.assertIn("Копилка", message, message)
        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_backlog(), BACKLOG_TEXT)
        self.assertEqual(notes.pending_notes(), [])

    def test_draft_equal_to_origin_refuses_instead_of_hanging_in_pending(self):
        """Заготовка байт-в-байт равна содержимому в origin — именованный
        отказ, а не три провала `git commit` с удержанием записи (тот же
        класс, что отказ «содержимое уже совпадает» у `doc-commit`).

        Ловит мутацию: проверка отсутствует — `_run` исчерпывает попытки,
        удерживает запись и отказывает текстом «не удалось отправить»;
        тест красен на непустом `pending_notes()`.
        """
        message = self.draft_refusal(BACKLOG_TEXT)

        self.assertIn("совпадает", message, message)
        self.assertEqual(notes.pending_notes(), [])

    def test_missing_message_and_missing_file_refuse_naming_the_flag(self):
        """`--apply` без `--message` и с пустым `--message` — отказ,
        называющий `--message` (требование 9); несуществующий файл — отказ,
        называющий `--apply`, а не соседний `--from` `doc-commit`.

        Ловит мутацию: `--message` получает дефолт либо пробельная строка
        проходит — документ заменяется коммитом без основания; текст
        отказа о файле захардкожен на `--from`, и Оператор читает про флаг,
        которым не пользовался.
        """
        before = self.origin_head()
        source = str(self.source_file(draft_with_extra_row()))

        self.assertIn("--message", self.refusal("--apply", source))
        self.assertIn("--message",
                      self.refusal("--apply", source, "--message", "  "))
        missing = self.refusal("--apply", str(Path(self.source_dir) / "нет.md"),
                               "--message", REASON)
        self.assertIn("--apply", missing, missing)
        self.assertIn("не найден", missing, missing)

        self.assertEqual(before, self.origin_head())
        self.assertEqual(notes.pending_notes(), [])


class ApplySilenceWindowTest(ApplySandbox):

    def test_open_window_holds_apply_until_flush(self):
        """Окно тишины открыто: `--apply` не двигает origin, печатает
        причину удержания и оставляет ОДНУ запись в общем каталоге
        удержанных; `note --flush` доводит заготовку до origin целиком
        (требование 10).

        Ловит мутацию: `--apply` проверяет окно ПОСЛЕ коммита и push (или
        не проверяет вовсе, отдельным от `_run` путём) — документ уезжает
        в origin сразу, ещё до `--flush`.
        """
        draft = draft_with_extra_row()
        self.open_silence_window()
        before = self.origin_head()

        output = self.apply_draft(draft, "разнос под окном")

        self.assertEqual(before, self.origin_head())
        self.assertIn("удержан", output, output)
        self.assertEqual(len(notes.pending_notes()), 1, notes.pending_notes())
        self.assertEqual(notes.pending_notes()[0]["kind"], notes.APPLY_KIND)

        capture(notes.cmd_note, ["--flush"])

        self.assertEqual(self.origin_backlog(), draft)
        self.assertEqual(notes.pending_notes(), [])

    def test_held_record_is_self_sufficient_without_the_source_file(self):
        """Удержанная запись несёт содержимое заготовки, а не путь к
        файлу: файл удалён до флаша — содержимое всё равно приезжает в
        origin (тот же контракт, что у удержанной записи `doc-commit`).

        Ловит мутацию: запись хранит путь `--apply` и перечитывает файл
        при флаше — запись висит, а документ в origin остаётся старым.
        """
        draft = draft_with_extra_row()
        source = self.source_file(draft)
        self.open_silence_window()
        capture(notes.cmd_note, ["--apply", str(source),
                                 "--message", "под окном"])
        source.unlink()

        capture(notes.cmd_note, ["--flush"])

        self.assertEqual(self.origin_backlog(), draft)
        self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
