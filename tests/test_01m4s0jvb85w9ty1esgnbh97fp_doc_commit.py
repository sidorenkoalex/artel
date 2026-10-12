"""`doc-commit` файла карточек `knowledge/<имя>.yaml`: проверка формы до
коммита, окна тишины и удержания записи.

Держит связку «команда `doc-commit` / `notes.doc_commit_content` — проверка
формы `knowledge_cards` — клон артели — bare `origin` — каталог удержанных
записей»: песочница `tests.sandbox.RealGitSandbox` с настоящим bare
`origin` и клоном артели из него (`clone_artel_from_origin`), как у
`doc-commit` пульта. Прогон полного набора `tests/` подменён шпионом
`acceptance.run_full_suite` (зелёный ответ): предмет — заводится ли гейт,
а не сам прогон. Имена файлов карточек, ключи и основания коммитов —
случайные при каждом запуске; зерно печатается и входит в текст провала.

Группа: долгоживущий
Красен до реализации: модуля orchestrator/knowledge_cards.py ещё нет — импорт падает; без него `doc-commit` отвергает путь `knowledge/…` как «код и артефакты» и не проверяет форму.
"""
import io
import os
import random
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, config, notes, store
from orchestrator import knowledge_cards as kc
from tests.sandbox import RealGitSandbox, clone_artel_from_origin, init_bare_origin

LATIN = "abcdefghijklmnopqrstuvwxyz"
DOC_REL = "docs/roadmap.md"
ROLES_TEXT = "developer:\n  model: opus\n"


def run_command(fn, *args) -> tuple:
    """(вывод вместе с текстом отказа, был ли выход `SystemExit`)."""
    buf = io.StringIO()
    exit_text, exited = "", False
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            fn(*args)
        except SystemExit as exc:
            exited = True
            exit_text = "" if exc.code is None else str(exc.code)
    return buf.getvalue() + "\n" + exit_text, exited


class KnowledgeDocCommitSandbox(RealGitSandbox):
    """Главная копия с документом и `roles.yaml`, синхронная с bare origin;
    клон артели из origin; окно тишины закрыто; шпион полного набора."""

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
        init_bare_origin(self.origin, self.git)
        self.git("remote", "add", "origin", self.origin)
        for rel, text in ((DOC_REL, "# Роадмап\n\nстарое\n"),
                          ("roles.yaml", ROLES_TEXT)):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "документы")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.clone = clone_artel_from_origin(self.origin)
        self.source_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.source_dir, ignore_errors=True)
        suite = mock.patch.object(acceptance, "run_full_suite",
                                  return_value=(True, "набор зелёный"))
        self.suite = suite.start()
        self.addCleanup(suite.stop)

    # --- случайные входы ---

    def name(self) -> str:
        return "".join(self.rng.choice(LATIN)
                       for _ in range(self.rng.randrange(4, 10)))

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def valid_text(self) -> str:
        lines = ["cards:"]
        for _ in range(self.rng.randrange(2, 4)):
            lines += [f"  {self.name()}:", f"    where: [{self.name()}/*.py]",
                      f"    rule: правило {self.name()}",
                      f"    why: причина {self.name()}"]
        return "\n".join(lines) + "\n"

    def invalid_text(self) -> str:
        key = self.name()
        card = (f"  {key}:\n    where: [a.py]\n    rule: правило\n"
                f"    why: причина\n")
        variants = (
            "cards:\n" + card + card,
            "cards:\n" + card.replace("    why:", "    owner: x\n    why:"),
            "cards:\n" + card.replace("    rule: правило", '    rule: ""'),
            "cards:\n" + card.replace(f"  {key}:", f"  {key.upper()}_x:"),
            f"{self.name()}: x\ncards:\n" + card,
        )
        return self.rng.choice(variants)

    # --- origin и удержание ---

    def origin_head(self) -> str:
        return self.git("-C", self.origin, "rev-parse", config.MAIN_BRANCH).strip()

    def origin_has(self, rel: str) -> bool:
        return bool(self.git("-C", self.origin, "ls-tree", "--name-only",
                             config.MAIN_BRANCH, "--", rel).strip())

    def origin_show(self, rel: str) -> str:
        return self.git("-C", self.origin, "show", f"{config.MAIN_BRANCH}:{rel}")

    def origin_subject(self) -> str:
        return self.git("-C", self.origin, "log", "-1", "--format=%s",
                        config.MAIN_BRANCH).strip()

    def pending_files(self) -> list:
        d = config.ROOT / ".artel" / "notes-pending"
        return sorted(d.glob("*")) if d.exists() else []

    def open_window(self) -> None:
        store.insert_task(store.db(), "T-WIN", "окно тишины",
                          config.NOTE_SILENCE_WINDOW_STATES[0], "task/t-win",
                          config.DEFAULT_TARGET, 10.0)

    def break_fetch(self) -> None:
        missing = Path(self.source_dir) / f"нет-{self.name()}"
        self.git("-C", str(self.clone), "remote", "set-url", "origin", str(missing))

    # --- вызовы ---

    def via_command(self, rel: str, text: str, message: str) -> tuple:
        source = Path(self.source_dir) / f"{self.name()}.yaml"
        source.write_bytes(text.encode("utf-8"))
        return run_command(notes.cmd_doc_commit,
                           [rel, "--from", str(source), "--message", message])

    def via_content(self, rel: str, text: str, message: str) -> tuple:
        return run_command(notes.doc_commit_content, rel, text, message)

    def assert_nothing_sent(self, before: str, out: str) -> None:
        self.assertEqual(self.origin_head(), before, self.msg(out))
        self.assertEqual(self.pending_files(), [], self.msg(out))
        self.assertEqual(notes.pending_notes(), [], self.msg(out))


class KnowledgeCommitTest(KnowledgeDocCommitSandbox):

    def test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite(self):
        """Верный новый файл в отсутствующем ранее каталоге `knowledge/`
        коммитится в origin с префиксом `knowledge`, без запуска полного
        набора `tests/`, без удержанной записи.

        Ловит мутацию: путь `knowledge/<имя>.yaml` добавлен в
        `DOC_COMMIT_CONFIG_PATHS` (заведён гейт полного набора, префикс
        `config`) либо префикс по-прежнему `config` для всего вне `docs/`
        — шпион набора вызван или тема коммита иная.
        """
        rel = f"knowledge/{self.name()}.yaml"
        text = self.valid_text()
        message = f"карточки {self.name()}"
        self.assertFalse(self.origin_has("knowledge"))

        out, exited = self.via_command(rel, text, message)

        self.assertFalse(exited, self.msg(out))
        self.assertEqual(self.origin_show(rel), text, self.msg(out))
        self.assertEqual(self.origin_subject(), f"knowledge: {rel} — {message}",
                         self.msg(out))
        self.suite.assert_not_called()
        self.assertEqual(self.pending_files(), [], self.msg(out))

    def test_ac14_knowledge_paths_not_in_config_paths(self):
        """Ни один путь под `knowledge/` не входит в
        `notes.DOC_COMMIT_CONFIG_PATHS`.

        Ловит мутацию: системный файл карточек внесён в перечень
        конфигурации Оператора — его `doc-commit` гоняет полный набор.
        """
        for path in notes.DOC_COMMIT_CONFIG_PATHS:
            self.assertFalse(path == "knowledge" or path.startswith("knowledge/"),
                             path)

    def test_ac14_invalid_form_refused_without_commit_or_hold(self):
        """Файл неверной формы отвергнут с кодом причины и подробностью;
        коммита нет, запись не удержана — при доступном origin, при
        открытом окне тишины и при отказе `fetch`, через команду и через
        публичную `notes.doc_commit_content`.

        Сценарий: случайный дефект (повтор ключа, неизвестное поле, пустой
        `rule`, ключ не по форме, неизвестный раздел); ожидаемые код и
        подробность — ответ `check_text` на тот же текст; каталог
        `.artel/notes-pending/` после каждого отказа пуст.

        Ловит мутацию: форма проверяется в `_build_doc_commit` — на ветке
        отказа `fetch` он не вызывается, и запись удерживается; либо
        проверка стоит только в `cmd_doc_commit` — `doc_commit_content`
        коммитит неверный файл; либо проверка после окна тишины — запись
        удержана.
        """
        conditions = (("origin доступен", lambda: None),
                      ("окно тишины открыто", self.open_window),
                      ("отказ fetch", self.break_fetch))
        for label, prepare in conditions:
            prepare()
            for entry in (self.via_command, self.via_content):
                rel = f"knowledge/{self.name()}.yaml"
                text = self.invalid_text()
                expected = kc.check_text(text, rel, kc.SYSTEM)
                self.assertIsInstance(expected, kc.Refusal, self.msg(text))
                before = self.origin_head()
                with self.subTest(condition=label, entry=entry.__name__):
                    out, exited = entry(rel, text, f"основание {self.name()}")
                    self.assertTrue(exited, self.msg(out))
                    self.assertIn(expected.code, out, self.msg(out))
                    self.assertIn(expected.detail, out, self.msg(out))
                    self.assert_nothing_sent(before, out)

    def test_ac14_nested_and_non_yaml_paths_refused(self):
        """Пути `knowledge/a/b.yaml` и `knowledge/x.md` отвергнуты — через
        команду и через `doc_commit_content`, без коммита и удержания.

        Ловит мутацию: допуск пути — префикс `knowledge/` без проверки
        уровня и суффикса — вложенный файл или `.md` закоммичен.
        """
        text = self.valid_text()
        for rel in (f"knowledge/{self.name()}/{self.name()}.yaml",
                    f"knowledge/{self.name()}.md"):
            for entry in (self.via_command, self.via_content):
                before = self.origin_head()
                with self.subTest(rel=rel, entry=entry.__name__):
                    out, exited = entry(rel, text, "основание")
                    self.assertTrue(exited, self.msg(out))
                    self.assertFalse(self.origin_has(rel), self.msg(out))
                    self.assert_nothing_sent(before, out)

    def test_ac14_role_environment_refused(self):
        """Вызов из окружения роли отказывает `DOC_COMMIT_ROLE_REFUSAL` и
        для `knowledge/<имя>.yaml` — команда и `doc_commit_content`.

        Ловит мутацию: ветка `knowledge/` разобрана до рубежа
        `runner.in_role_environment()` — роль коммитит карточки.
        """
        rel = f"knowledge/{self.name()}.yaml"
        role = {config.ARTEL_ROLE_ENV: f"role_{self.name()}"}
        for entry in (self.via_command, self.via_content):
            before = self.origin_head()
            with self.subTest(entry=entry.__name__), \
                    mock.patch.dict(os.environ, role):
                out, exited = entry(rel, self.valid_text(), "основание")
                self.assertTrue(exited, self.msg(out))
                self.assertIn(notes.DOC_COMMIT_ROLE_REFUSAL, out, self.msg(out))
                self.assert_nothing_sent(before, out)

    def test_ac14_previous_paths_behave_as_before(self):
        """`docs/**` коммитится с префиксом `docs` без полного набора;
        `roles.yaml` из `DOC_COMMIT_CONFIG_PATHS` — с префиксом `config` и
        через гейт полного набора.

        Ловит мутацию: проверка формы карточек применена ко всем путям
        `doc-commit` (документ `docs/` отвергнут как «файл не разобран»)
        либо ветка `knowledge` перехватила префикс `config`.
        """
        doc_text = f"# Роадмап\n\n{self.name()}\n"
        out, exited = self.via_command(DOC_REL, doc_text, "раздел")
        self.assertFalse(exited, self.msg(out))
        self.assertEqual(self.origin_show(DOC_REL), doc_text, self.msg(out))
        self.assertEqual(self.origin_subject(), f"docs: {DOC_REL} — раздел")
        self.suite.assert_not_called()

        roles_text = f"developer:\n  model: {self.name()}\n"
        out, exited = self.via_command("roles.yaml", roles_text, "модель")
        self.assertFalse(exited, self.msg(out))
        self.assertEqual(self.origin_show("roles.yaml"), roles_text, self.msg(out))
        self.assertEqual(self.origin_subject(), "config: roles.yaml — модель")
        self.assertTrue(self.suite.called, self.msg(out))


if __name__ == "__main__":
    unittest.main()
