"""Юнит-тесты команды `doc-commit` (`orchestrator/notes.py::cmd_doc_commit`,
tasks/01M2XMCG167615YS9EZD9TYJWV): чистые функции допустимых путей и
сообщения коммита без git, полный сценарий (сверка базы с пином,
удержание окном тишины, общий флаш обоих видов записей, вывод sha,
неприкосновенность главной копии) — стендом с настоящим bare origin по
образцу `tests/test_notes.py::NoteSilenceSandbox`.

Приёмочные тесты `tasks/01M2XMCG167615YS9EZD9TYJWV/acceptance_tests/`
материализуются только на время задачи; постоянный регресс — здесь.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel, config, notes, store  # noqa: E402
from tests.sandbox import RealGitSandbox, capture  # noqa: E402

BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое УНИКАЛЬНЫЙКЛЮЧ | orchestrator/x.py |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта | Заметка |
|---|---|---|---|---|---|---|
| 1 | Кандидат A | Суть A | $10 | orchestrator/a.py | сразу | — |
"""
ROADMAP_TEXT = "# Роадмап\n\nСтарый раздел.\n"
ROLES_TEXT = "developer:\n  model: opus\n"
DOC_REL = "docs/roadmap.md"


class PathRefusalTest(unittest.TestCase):

    def test_docs_paths_and_operator_config_are_allowed(self):
        """`docs/**` любой глубины и ровно три файла конфигурации Оператора
        проходят без отказа.

        Ловит мутацию: список допустимых путей сведён к `docs/**` (конфиг
        забыт) либо к плоскому `docs/<файл>` без подкаталогов — тест
        красен на непустом отказе для `roles.yaml` или
        `docs/research/x.md`."""
        for rel in (DOC_REL, "docs/research/x.md", "docs/adr/0001.md",
                    "roles.yaml", "gates.yaml", "targets.yaml"):
            self.assertIsNone(notes._doc_commit_path_refusal(rel), rel)

    def test_backlog_is_refused_naming_note(self):
        """`docs/backlog.md` — путь `note`, отказ называет `note`.

        Ловит мутацию: проверка смотрит только на префикс `docs/` — тест
        красен на `None` вместо отказа."""
        refusal = notes._doc_commit_path_refusal("docs/backlog.md")
        self.assertIsNotNone(refusal)
        self.assertIn("note", refusal)

    def test_code_tests_skills_templates_tasks_refused_with_named_text(self):
        """Код, тесты, скилы, шаблоны, `tasks/`, чужой yaml в корне —
        именованный отказ «код и артефакты меняются задачами».

        Ловит мутацию: допустимость определяется расширением (`.md`/
        `.yaml`), не расположением — тест красен на `skills/x.md` и
        `other.yaml`."""
        for rel in ("orchestrator/notes.py", "tests/test_notes.py",
                    "skills/x.md", "templates/SPEC.md",
                    "tasks/01M2XMCG167615YS9EZD9TYJWV/SPEC.md", "other.yaml",
                    "README.md"):
            refusal = notes._doc_commit_path_refusal(rel)
            self.assertIsNotNone(refusal, rel)
            self.assertIn(notes.DOC_COMMIT_FOREIGN_REFUSAL, refusal, rel)

    def test_absolute_dotdot_empty_and_bare_docs_dir_refused(self):
        """Абсолютный путь, `..`, пустая строка и голый каталог `docs`
        отказываются раньше сверки со списком.

        Ловит мутацию: `docs/../roles.yaml`-подобный путь пропускается
        как `docs/**` по строковому префиксу — тест красен на `None`."""
        for rel in ("/docs/x.md", "docs/../orchestrator/notes.py", "",
                    "docs", "docs/", "../docs/x.md"):
            self.assertIsNotNone(notes._doc_commit_path_refusal(rel), rel)


class CommitMessageTest(unittest.TestCase):

    def test_prefix_by_path_kind_without_truncation(self):
        """`docs:` для `docs/**`, `config:` для конфигурации, текст
        `--message` целиком (не усечён до 80 символов, как у `note`).

        Ловит мутацию: ветка `doc-commit` в `_commit_message` отсутствует
        и сообщение уходит в общий `оператор: …` — тест красен на
        несовпадении строки."""
        long_message = "о" * 120
        docs = notes._commit_message(DOC_REL, {
            "kind": notes.DOC_COMMIT_KIND, "path": DOC_REL,
            "content": "", "message": long_message}, None)
        self.assertEqual(docs, f"docs: {DOC_REL} — {long_message}")
        cfg = notes._commit_message("gates.yaml", {
            "kind": notes.DOC_COMMIT_KIND, "path": "gates.yaml",
            "content": "", "message": "порог"}, None)
        self.assertEqual(cfg, "config: gates.yaml — порог")

    def test_target_rel_is_own_path_for_doc_commit_and_backlog_for_note(self):
        """`_target_rel`: запись `doc-commit` пишет свой путь, любой вид
        `note` — `docs/backlog.md`.

        Ловит мутацию: `_commit_and_push` пишет и добавляет в индекс
        всегда `BACKLOG_REL` — тест красен на пути записи `doc-commit`."""
        self.assertEqual(notes._target_rel(
            {"kind": notes.DOC_COMMIT_KIND, "path": "roles.yaml"}),
            "roles.yaml")
        self.assertEqual(notes._target_rel(
            {"kind": "insert", "section": "копилка", "text": "x"}),
            notes.BACKLOG_REL)


class DocCommitSandbox(RealGitSandbox):
    """Главная копия с `docs/backlog.md`, `docs/roadmap.md`, `roles.yaml`,
    синхронная с bare `origin`: сверка базы по умолчанию проходит, окно
    тишины закрыто (БД пуста)."""

    def setUp(self):
        super().setUp()
        self.origin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        self.git("init", "-q", "--bare", self.origin)
        self.git("remote", "add", "origin", self.origin)
        for rel, text in ((notes.BACKLOG_REL, BACKLOG_TEXT),
                          (DOC_REL, ROADMAP_TEXT),
                          ("roles.yaml", ROLES_TEXT)):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "документы")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.source_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.source_dir, ignore_errors=True)

    def source_file(self, text: str, name: str = "draft.md") -> Path:
        path = Path(self.source_dir) / name
        path.write_text(text, encoding="utf-8")
        return path

    def doc_commit(self, *argv: str) -> str:
        return capture(notes.cmd_doc_commit, list(argv))

    def origin_run(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", self.origin, *args],
                              capture_output=True, text=True)

    def origin_head(self) -> str:
        res = self.origin_run("rev-parse", config.MAIN_BRANCH)
        return res.stdout.strip() if res.returncode == 0 else ""

    def origin_show_bytes(self, rel: str) -> bytes:
        res = subprocess.run(
            ["git", "-C", self.origin, "show", f"{config.MAIN_BRANCH}:{rel}"],
            capture_output=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def origin_show(self, rel: str) -> str:
        return self.origin_show_bytes(rel).decode("utf-8")

    def origin_subject(self) -> str:
        res = self.origin_run("log", "-1", "--format=%s", config.MAIN_BRANCH)
        return res.stdout.strip()

    def main_copy_snapshot(self) -> tuple:
        return (self.git("rev-parse", "HEAD").strip(),
                self.git("rev-parse", "--abbrev-ref", "HEAD").strip(),
                self.git("status", "--porcelain"))

    def open_silence_window(self, task_id: str = "T-WIN") -> None:
        store.insert_task(store.db(), task_id, "окно тишины",
                          config.NOTE_SILENCE_WINDOW_STATES[0],
                          f"task/{task_id}", config.DEFAULT_TARGET, 10.0)

    def close_silence_window(self, task_id: str = "T-WIN") -> None:
        conn = store.db()
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()


class DocCommitPushTest(DocCommitSandbox):

    def test_content_lands_in_origin_output_names_sha_main_copy_untouched(self):
        """Успешный вызов: содержимое `--from` становится содержимым пути в
        origin, вывод называет sha нового `origin/<MAIN_BRANCH>`, HEAD/
        ветка/рабочее дерево главной копии и файл на её диске прежние.

        Ловит мутацию: команда правит и коммитит файл прямо в
        `config.ROOT` (мимо `.artel/notes-work`) либо печатает только
        путь без sha — тест красен на снимке главной копии или на
        отсутствии sha в выводе."""
        new_text = "# Роадмап\n\nНовый раздел.\n"
        source = self.source_file(new_text)
        before_origin = self.origin_head()
        before_main = self.main_copy_snapshot()

        output = self.doc_commit(DOC_REL, "--from", str(source),
                                 "--message", "перенос раздела")

        head = self.origin_head()
        self.assertNotEqual(before_origin, head)
        self.assertEqual(self.origin_show(DOC_REL), new_text)
        self.assertIn(head, output)
        self.assertEqual(before_main, self.main_copy_snapshot())
        self.assertEqual((self.root / DOC_REL).read_text(encoding="utf-8"),
                         ROADMAP_TEXT)
        self.assertEqual(notes.pending_notes(), [])

    def test_bytes_preserved_crlf_not_translated(self):
        """Содержимое переносится байт-в-байт: CRLF в `--from` остаётся
        CRLF в origin.

        Ловит мутацию: чтение `--from` через `read_text` (универсальные
        переводы строк) превращает CRLF в LF — тест красен на
        несовпадении байтов."""
        source = Path(self.source_dir) / "crlf.md"
        source.write_bytes(b"# CRLF\r\n\r\nstroka\r\n")

        self.doc_commit(DOC_REL, "--from", str(source), "--message", "crlf")

        self.assertEqual(self.origin_show_bytes(DOC_REL),
                         b"# CRLF\r\n\r\nstroka\r\n")

    def test_no_journal_row_for_doc_commit(self):
        """Требование 7: журнал пульта `doc-commit` не пишет — таблица
        steps после успешного вызова пуста.

        Ловит мутацию: `_commit_and_push` журналирует оба вида записи
        одинаково — тест красен на непустом журнале."""
        source = self.source_file("# Роадмап\n\nбез журнала\n")

        self.doc_commit(DOC_REL, "--from", str(source), "--message", "тихо")

        rows = store.db().execute("SELECT COUNT(*) FROM steps").fetchone()[0]
        self.assertEqual(rows, 0)

    def test_config_path_gets_config_prefix_docs_path_gets_docs_prefix(self):
        """Сообщение коммита в origin: `config: roles.yaml — …` и
        `docs: docs/roadmap.md — …` целиком.

        Ловит мутацию: префикс один на оба вида путей — тест красен на
        одном из двух сравнений."""
        self.doc_commit("roles.yaml", "--from",
                        str(self.source_file("developer:\n  model: sonnet\n",
                                             "roles.yaml")),
                        "--message", "модель")
        self.assertEqual(self.origin_subject(), "config: roles.yaml — модель")

        self.doc_commit(DOC_REL, "--from",
                        str(self.source_file("# Роадмап\n\nещё\n")),
                        "--message", "раздел")
        self.assertEqual(self.origin_subject(), f"docs: {DOC_REL} — раздел")


class DocCommitRefusalTest(DocCommitSandbox):

    def assert_refused(self, argv: list, phrase: str) -> None:
        with self.assertRaises(SystemExit) as ctx:
            notes.cmd_doc_commit(argv)
        self.assertIn(phrase, str(ctx.exception), str(ctx.exception))

    def test_foreign_path_refused_without_commit_or_hold(self):
        """Путь вне допустимых — отказ до git: origin на месте, удержанной
        записи нет.

        Ловит мутацию: проверка пути перенесена после `_run` (запись
        успевает удержаться/закоммититься) — тест красен на непустом
        `pending_notes()` или сдвинувшемся origin."""
        source = self.source_file("любое\n")
        before = self.origin_head()

        self.assert_refused(["orchestrator/notes.py", "--from", str(source),
                             "--message", "правка"],
                            notes.DOC_COMMIT_FOREIGN_REFUSAL)

        self.assertEqual(before, self.origin_head())
        self.assertEqual(notes.pending_notes(), [])

    def test_backlog_path_refused_origin_keeps_backlog(self):
        """`docs/backlog.md` отказывается, бэклог в origin цел.

        Ловит мутацию: `docs/**` принимает и бэклог — тест красен на
        подменённом содержимом бэклога в origin."""
        source = self.source_file("# затёртый бэклог\n")

        self.assert_refused([notes.BACKLOG_REL, "--from", str(source),
                             "--message", "правка"], "note")

        self.assertEqual(self.origin_show(notes.BACKLOG_REL), BACKLOG_TEXT)

    def test_missing_message_refused_without_commit_or_hold(self):
        """Без `--message` — отказ; пустой/пробельный `--message` — тот же
        отказ; origin и каталог удержания нетронуты.

        Ловит мутацию: `--message` получает дефолт либо пробельная строка
        проходит — тест красен на сдвинувшемся origin."""
        source = self.source_file("# Роадмап\n\nбез основания\n")
        before = self.origin_head()

        self.assert_refused([DOC_REL, "--from", str(source)], "--message")
        self.assert_refused([DOC_REL, "--from", str(source), "--message", "  "],
                            "--message")

        self.assertEqual(before, self.origin_head())
        self.assertEqual(notes.pending_notes(), [])

    def test_missing_or_absent_source_file_refused(self):
        """Без `--from` и с несуществующим `--from` — отказ, называющий
        `--from`; origin на месте.

        Ловит мутацию: отсутствие файла не проверяется и падает
        `FileNotFoundError` вместо именованного отказа — тест красен на
        типе исключения."""
        before = self.origin_head()

        self.assert_refused([DOC_REL, "--message", "основание"], "--from")
        self.assert_refused([DOC_REL, "--from",
                             str(Path(self.source_dir) / "нет.md"),
                             "--message", "основание"], "не найден")

        self.assertEqual(before, self.origin_head())

    def test_identical_content_refused_instead_of_hanging_in_pending(self):
        """Содержимое `--from` уже равно содержимому пути в origin —
        именованный отказ, не три провала `git commit` с удержанием.

        Ловит мутацию: проверка «уже совпадает» отсутствует — `_run`
        исчерпывает попытки, удерживает запись и отказывает текстом «не
        удалось отправить»; тест красен на непустом `pending_notes()`."""
        source = self.source_file(ROADMAP_TEXT)

        self.assert_refused([DOC_REL, "--from", str(source),
                             "--message", "то же"], "уже совпадает")

        self.assertEqual(notes.pending_notes(), [])

    def test_role_environment_refused_before_work_repo_exists(self):
        """`runner.in_role_environment()` истинна — отказ первым действием:
        `.artel/notes-work` не заводится, origin на месте.

        Ловит мутацию: рубеж стоит после `_ensure_work_repo()` — тест
        красен на существующем рабочем репозитории."""
        source = self.source_file("# Роадмап\n\nиз-под роли\n")
        before = self.origin_head()

        with mock.patch.object(notes.runner, "in_role_environment",
                               return_value=True):
            self.assert_refused([DOC_REL, "--from", str(source),
                                 "--message", "правка"], "окружения роли")

        self.assertEqual(before, self.origin_head())
        self.assertFalse((config.ROOT / ".artel" / "notes-work").exists())

    def test_role_environment_markers_from_env_are_honoured(self):
        """Те же маркеры окружения роли, что ставит `runner.role_env`
        (HOME/CLAUDE_CONFIG_DIR на курируемый слой), без патча функции —
        отказ.

        Ловит мутацию: рубеж читает собственный признак (например
        `ARTEL_ROLE`), а не `runner.in_role_environment` — тест красен на
        отсутствии `SystemExit`."""
        source = self.source_file("# Роадмап\n\nиз-под роли\n")
        role_env = {"HOME": str(config.ROLE_HOME),
                    "CLAUDE_CONFIG_DIR": str(config.ROLE_CONFIG_DIR)}

        with mock.patch.dict(os.environ, role_env):
            self.assert_refused([DOC_REL, "--from", str(source),
                                 "--message", "правка"], "окружения роли")


class PinBaseCheckTest(DocCommitSandbox):

    def _push_foreign_change_past_the_pin(self, rel: str, text: str) -> None:
        (self.root / rel).write_text(text, encoding="utf-8")
        self.git("commit", "-a", "-q", "-m", "чужая правка")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.git("reset", "-q", "--hard", "HEAD~1")

    def test_origin_diverged_from_pin_refuses_naming_pin_update(self):
        """origin несёт чужую версию пути, пин — старую: отказ «сначала
        pin-update», чужой текст в origin цел, удержанной записи нет.

        Ловит мутацию: сверка сравнивает origin с содержимым `--from` или
        отсутствует — тест красен на подменённом `origin_show`."""
        foreign = "# Роадмап\n\nчужой раздел\n"
        self._push_foreign_change_past_the_pin(DOC_REL, foreign)
        source = self.source_file("# Роадмап\n\nмоя правка\n")

        with self.assertRaises(SystemExit) as ctx:
            notes.cmd_doc_commit([DOC_REL, "--from", str(source),
                                  "--message", "моя"])

        self.assertIn(notes.DOC_COMMIT_BASE_REFUSAL, str(ctx.exception))
        self.assertEqual(self.origin_show(DOC_REL), foreign)
        self.assertEqual(notes.pending_notes(), [])

    def test_new_path_absent_everywhere_is_committed(self):
        """Пути нет ни в origin, ни в пине — новый файл заводится
        коммитом, каталог создаётся по дороге.

        Ловит мутацию: «нет в origin» трактуется как расхождение с пином
        — тест красен на отказе вместо коммита."""
        rel = "docs/research/new-note.md"
        text = "# Заметка\n\nновый файл\n"
        source = self.source_file(text, "new-note.md")

        self.doc_commit(rel, "--from", str(source), "--message", "новая")

        self.assertEqual(self.origin_show(rel), text)

    def test_path_added_in_origin_after_pin_refuses(self):
        """Путь появился в origin после пина (в HEAD главной копии его нет)
        — это тоже чужая правка после пина: отказ, а не затирание.

        Ловит мутацию: сверка пропускает случай «в пине нет» как новый
        файл — тест красен на подменённом содержимом в origin."""
        rel = "docs/research/foreign.md"
        foreign = "# чужой новый файл\n"
        (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / rel).write_text(foreign, encoding="utf-8")
        self.git("add", rel)
        self.git("commit", "-q", "-m", "чужой новый файл")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.git("reset", "-q", "--hard", "HEAD~1")
        source = self.source_file("# мой файл\n")

        with self.assertRaises(SystemExit):
            notes.cmd_doc_commit([rel, "--from", str(source),
                                  "--message", "мой"])

        self.assertEqual(self.origin_show(rel), foreign)


class SilenceWindowAndFlushTest(DocCommitSandbox):

    def test_open_window_holds_json_with_kind_and_flush_after_close_pushes(self):
        """Окно тишины открыто: запись удерживается в общем каталоге как
        JSON с `kind: doc-commit`, origin не сдвигается, вывод называет
        удержание и `doc-commit --flush`; после закрытия окна
        `doc-commit --flush` доводит содержимое до origin.

        Ловит мутацию: `_run` для `doc-commit` не проверяет окно и пушит
        сразу — тест красен на сдвинувшемся origin до закрытия окна."""
        new_text = "# Роадмап\n\nпосле окна\n"
        source = self.source_file(new_text)
        self.open_silence_window()
        before = self.origin_head()

        output = self.doc_commit(DOC_REL, "--from", str(source),
                                 "--message", "под окном")

        self.assertEqual(before, self.origin_head())
        self.assertIn("doc-commit удержан:", output)
        self.assertIn("doc-commit --flush", output)
        pending = notes.pending_notes()
        self.assertEqual(len(pending), 1, pending)
        self.assertEqual(pending[0]["kind"], notes.DOC_COMMIT_KIND)
        self.assertEqual(pending[0]["path"], DOC_REL)
        self.assertEqual(pending[0]["content"], new_text)

        self.close_silence_window()
        self.doc_commit("--flush")

        self.assertEqual(self.origin_show(DOC_REL), new_text)
        self.assertEqual(notes.pending_notes(), [])

    def test_flush_does_not_need_source_file_anymore(self):
        """Удержанная запись самодостаточна: `--from`-файл удалён до флаша,
        содержимое всё равно приезжает в origin.

        Ловит мутацию: запись хранит путь к `--from` и перечитывает файл
        при флаше — тест красен на висящей записи и старом origin."""
        new_text = "# Роадмап\n\nисточник исчез\n"
        source = self.source_file(new_text)
        self.open_silence_window()
        self.doc_commit(DOC_REL, "--from", str(source), "--message", "х")
        source.unlink()
        self.close_silence_window()

        self.doc_commit("--flush")

        self.assertEqual(self.origin_show(DOC_REL), new_text)
        self.assertEqual(notes.pending_notes(), [])

    def _hold_both_kinds(self) -> None:
        self.open_silence_window()
        capture(notes.cmd_note,
                ["копилка", "--text", "9 | 09.09 | из окна ОБЩИЙФЛАШ | o.py"])
        self.doc_commit(DOC_REL, "--from",
                        str(self.source_file("# Роадмап\n\nобщий флаш\n")),
                        "--message", "общий флаш")
        kinds = sorted(p["kind"] for p in notes.pending_notes())
        self.assertEqual(kinds, [notes.DOC_COMMIT_KIND, "insert"])
        self.close_silence_window()

    def _assert_both_arrived(self) -> None:
        self.assertIn("ОБЩИЙФЛАШ", self.origin_show(notes.BACKLOG_REL))
        self.assertEqual(self.origin_show(DOC_REL), "# Роадмап\n\nобщий флаш\n")
        self.assertEqual(notes.pending_notes(), [])

    def test_note_flush_sends_both_kinds(self):
        """`note --flush` отправляет и запись `note`, и запись `doc-commit`
        из одного каталога.

        Ловит мутацию: `_fetch_and_build` разбирает запись с `kind:
        doc-commit` старым путём `_build_for` и спотыкается — тест красен
        на висящей записи и старом роадмапе в origin."""
        self._hold_both_kinds()
        capture(notes.cmd_note, ["--flush"])
        self._assert_both_arrived()

    def test_doc_commit_flush_sends_both_kinds(self):
        """`doc-commit --flush` симметрично отправляет обе записи.

        Ловит мутацию: `doc-commit --flush` фильтрует каталог по своему
        виду — тест красен на висящей записи `note`."""
        self._hold_both_kinds()
        self.doc_commit("--flush")
        self._assert_both_arrived()

    def test_flush_ignores_open_window_but_new_record_is_still_held(self):
        """`doc-commit --flush` обходит окно явно; обычный вызов при
        открытом окне не допушивает ранее удержанную запись (обе висят).

        Ловит мутацию: оппортунистический флаш в `cmd_doc_commit`
        безусловен — тест красен на сдвинувшемся origin при открытом
        окне."""
        notes._hold_pending({"kind": "insert", "section": "копилка",
                             "text": "9 | 09.09 | старая | o.py"})
        self.open_silence_window()
        before = self.origin_head()

        self.doc_commit(DOC_REL, "--from",
                        str(self.source_file("# Роадмап\n\nновая\n")),
                        "--message", "новая")

        self.assertEqual(before, self.origin_head())
        self.assertEqual(len(notes.pending_notes()), 2)

        self.doc_commit("--flush")

        self.assertNotEqual(before, self.origin_head())
        self.assertEqual(notes.pending_notes(), [])

    def test_note_hold_texts_unchanged(self):
        """Тексты удержания `note` не изменились от параметризации по виду
        записи (требование 9 — совместимость `note`).

        Ловит мутацию: общий текст удержания переписан под оба вида
        («запись удержана») — тест красен на отсутствии «заметка
        удержана:»."""
        self.open_silence_window()
        output = capture(notes.cmd_note,
                         ["копилка", "--text", "9 | 09.09 | текст | o.py"])
        self.assertIn("заметка удержана:", output)
        self.assertIn("отправка — note --flush либо автоматически "
                      "следующим note вне окна", output)


class DispatcherTest(DocCommitSandbox):

    def test_artel_dispatches_doc_commit_with_rest_argv(self):
        """`artel.py doc-commit …` доходит до `notes.cmd_doc_commit` с
        остатком argv.

        Ловит мутацию: команда не заведена в таблице диспетчера — тест
        красен на `SystemExit(«Неизвестная команда»)`."""
        seen = []
        with mock.patch.object(notes, "cmd_doc_commit",
                               side_effect=seen.append), \
                mock.patch.object(sys, "argv",
                                  ["artel.py", "doc-commit", "--flush"]):
            artel.main()
        self.assertEqual(seen, [["--flush"]])

    def test_help_text_names_doc_commit(self):
        """Справка `artel.py` называет `doc-commit`.

        Ловит мутацию: команда заведена в таблице, но не в справке —
        тест красен на отсутствии слова в docstring."""
        self.assertIn("doc-commit", artel.__doc__)


if __name__ == "__main__":
    unittest.main()
