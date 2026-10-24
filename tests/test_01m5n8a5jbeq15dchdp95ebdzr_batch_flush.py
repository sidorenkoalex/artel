"""Сброс удержанных записей (`note --flush`, `doc-commit --flush`, попутный
сброс) — одним push: каждая запись своим коммитом, сверки каждой записи —
как при последовательной отправке по одной.

Стенд — настоящий bare `origin`, главная копия-пин и клон артели
(`tests.sandbox.RealGitSandbox` + `clone_artel_from_origin`). Записи
удерживаются окном тишины (задача в состоянии из
`config.NOTE_SILENCE_WINDOW_STATES`) либо файлом удержания, который кладёт
сам тест (запись после сетевого отказа fetch, запись старого формата).

Наблюдения — на стороне git, не шпионом на `gitcmd`:
- принятые push считает хук `post-receive` origin (строка sha головы `main`
  на каждый push);
- отказ non-fast-forward git-клиент выносит сам, до origin он не доходит,
  поэтому origin сдвигает хук `post-commit` клона артели: чужой коммит из
  отдельного клона уходит в origin между построением записей и их push —
  push клона получает настоящий отказ `[rejected] (fetch first)`;
- попытки push считает хук `pre-push` клона (git зовёт его и на
  отклонённом push).

Чужой коммит узнаётся по теме `FOREIGN_SUBJECT` — не пультовой
(`notes.NOTE_COMMIT_SUBJECT_PREFIX`) и не пультовой идентичности.

Группа: долгоживущий
Красен до реализации: `_flush_pending` отправляет каждую удержанную запись своим `_attempt` — отдельным push, вывода строк с sha у сброса нет; тесты числа push (AC-1…AC-7, AC-9, AC-10, AC-11) и строк вывода (AC-6) падают.
"""
import io
import json
import os
import random
import re
import shutil
import sys
import tempfile
import time
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, config, notes, store
from tests.sandbox import RealGitSandbox, clone_artel_from_origin, init_bare_origin

MAIN = config.MAIN_BRANCH
DOC_REL = "docs/roadmap.md"
GUIDE_REL = "docs/guide.md"
FOREIGN_REL = "docs/foreign.md"
CONFIG_REL = "gates.yaml"
FOREIGN_SUBJECT = "чужая правка"
FOREIGN_EMAIL = "foreign@example.invalid"
STALE_PHRASE = notes.DOC_COMMIT_STALE_REFUSAL
NOT_SENT_PREFIX = "удержанная запись не отправлена: "
ALPHABET = "абвгдежзиклмнопрстуфхцчшщэюяabcdefghijklmnopqrstuvwxyz0123456789"

OLD_COPILKA_ROW = "| 1 | 01.01 | старое наблюдение | orchestrator/x.py |"
BACKLOG_TEXT = f"""# Бэклог

## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
{OLD_COPILKA_ROW}

## Бэклог

| П | Задача | Состояние |
|---|---|---|
| 2 | старая задача | — |

## Очередь Оператора

| П | Вопрос | Состояние |
|---|---|---|
| 3 | старый вопрос | — |
"""

# Хуки — на Python (интерпретатор теста): PATH окружения прогона может не
# нести утилит оболочки, а git и интерпретатор у теста есть всегда.

# Хук origin: sha новой головы `main` на каждый принятый push.
POST_RECEIVE = """#!{python}
import sys
with open({log!r}, "a", encoding="utf-8") as fh:
    for line in sys.stdin:
        old, new, ref = line.split()
        if ref == "refs/heads/" + {main!r}:
            fh.write(new + "\\n")
"""

# Хук клона артели: каждая попытка push — строка журнала попыток.
PRE_PUSH = """#!{python}
import sys
sys.stdin.read()
with open({log!r}, "a", encoding="utf-8") as fh:
    fh.write("push\\n")
"""

# Хук клона артели: пока бюджет не исчерпан (-1 — без предела), каждый
# коммит клона уводит origin вперёд чужим коммитом пути из `path`.
POST_COMMIT = """#!{python}
import os
import subprocess
from pathlib import Path

state = Path({state!r})
budget = int((state / "budget").read_text())
if budget != 0:
    if budget > 0:
        (state / "budget").write_text(str(budget - 1))
    env = dict((k, v) for k, v in os.environ.items()
               if not k.startswith("GIT_"))
    fc = Path({foreign!r})
    rel = (state / "path").read_text().strip()
    n = int((state / "count").read_text()) + 1
    (state / "count").write_text(str(n))

    def run(*args):
        return subprocess.run(["git", "-C", str(fc)] + list(args), env=env,
                              capture_output=True).returncode == 0

    if (run("fetch", "-q", "origin", {main!r})
            and run("checkout", "-q", "-f", "-B", {main!r}, "FETCH_HEAD")):
        target = fc / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write({subject!r} + " " + str(n) + "\\n")
        run("add", "--", rel)
        run("-c", "user.name=foreign", "-c", "user.email=" + {email!r},
            "commit", "-q", "-m", {subject!r} + " хук " + str(n))
        run("push", "-q", "origin", "HEAD:" + {main!r})
"""


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


def write_hook(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o755)


class BatchFlushSandbox(RealGitSandbox):
    """Главная копия с `docs/backlog.md` и двумя документами, bare origin с
    хуком счёта push, клон артели с хуками счёта попыток и сдвига origin,
    отдельный «чужой» клон; окно тишины закрыто."""

    def setUp(self):
        super().setUp()
        role_patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role_patcher.start()
        self.addCleanup(role_patcher.stop)
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.scratch = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.origin = self.scratch / "origin.git"
        init_bare_origin(self.origin, self.git)
        self.git("remote", "add", "origin", str(self.origin))
        for rel, text in ((notes.BACKLOG_REL, BACKLOG_TEXT),
                          (DOC_REL, f"# Роадмап\n\n{self.words(6)}\n"),
                          (GUIDE_REL, f"# Руководство\n\n{self.words(6)}\n")):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "документы")
        self.git("push", "-q", "origin", f"{MAIN}:{MAIN}")
        self.clone = clone_artel_from_origin(self.origin)
        self.foreign = self.scratch / "foreign"
        self.git("clone", "-q", str(self.origin), str(self.foreign))

        self.push_log = self.scratch / "pushes.log"
        self.attempt_log = self.scratch / "attempts.log"
        self.push_log.write_text("", encoding="utf-8")
        self.attempt_log.write_text("", encoding="utf-8")
        python = sys.executable
        write_hook(self.origin / "hooks" / "post-receive", POST_RECEIVE.format(
            python=python, main=MAIN, log=str(self.push_log)))
        self.mover = self.scratch / "mover"
        self.mover.mkdir()
        self.arm_mover(0, FOREIGN_REL)
        (self.mover / "count").write_text("0\n", encoding="utf-8")
        hooks = self.scratch / "clone-hooks"
        write_hook(hooks / "pre-push", PRE_PUSH.format(
            python=python, log=str(self.attempt_log)))
        write_hook(hooks / "post-commit", POST_COMMIT.format(
            python=python, state=str(self.mover), foreign=str(self.foreign),
            main=MAIN, subject=FOREIGN_SUBJECT, email=FOREIGN_EMAIL))
        self.git("-C", str(self.clone), "config", "core.hooksPath", str(hooks))
        self.source_dir = self.scratch / "sources"
        self.source_dir.mkdir()

    # --- случайные входы ---

    def word(self, n: int = 10) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(n))

    def words(self, k: int) -> str:
        return " ".join(self.word(self.rng.randrange(3, 10)) for _ in range(k))

    def token(self) -> str:
        """Метка записи: по ней находятся её коммит, файл удержания и строки
        вывода."""
        return f"м{self.word(12)}"

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # --- git ---

    def origin_git(self, *args) -> str:
        return self.git("-C", str(self.origin), *args)

    def origin_head(self) -> str:
        return self.origin_git("rev-parse", MAIN).strip()

    def origin_show(self, rel: str) -> str:
        return self.origin_git("show", f"{MAIN}:{rel}")

    def origin_log(self, since: str) -> list:
        """(sha, тема) коммитов origin после `since`, от старых к новым,
        по первому родителю."""
        out = self.origin_git("log", "--first-parent", "--reverse",
                              "--format=%H%x00%s", f"{since}..{MAIN}")
        return [tuple(line.split("\0", 1)) for line in out.split("\n")
                if line.strip()]

    def subject_of(self, sha: str) -> str:
        return self.origin_git("log", "-1", "--format=%s", sha).strip()

    def is_foreign(self, sha: str) -> bool:
        return self.subject_of(sha).startswith(FOREIGN_SUBJECT)

    def pushes(self) -> list:
        """sha головы `main` каждого принятого origin push клона артели
        (чужие push отброшены), по порядку."""
        lines = [line.strip() for line in
                 self.push_log.read_text(encoding="utf-8").split("\n")
                 if line.strip()]
        return [sha for sha in lines if not self.is_foreign(sha)]

    def attempts(self) -> int:
        return len([line for line in
                    self.attempt_log.read_text(encoding="utf-8").split("\n")
                    if line.strip()])

    def arm_mover(self, budget: int, rel: str) -> None:
        """Хук `post-commit` клона: `budget` коммитов клона (-1 — все)
        уводят origin чужим коммитом пути `rel`."""
        (self.mover / "budget").write_text(f"{budget}\n", encoding="utf-8")
        (self.mover / "path").write_text(rel, encoding="utf-8")

    def foreign_commit(self, rel: str) -> str:
        """Чужая правка пути `rel` в origin — мимо клона артели (его
        `origin/<main>` её не знает)."""
        fc = str(self.foreign)
        self.git("-C", fc, "fetch", "-q", "origin", MAIN)
        self.git("-C", fc, "checkout", "-q", "-f", "-B", MAIN, "FETCH_HEAD")
        path = self.foreign / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n{FOREIGN_SUBJECT} {self.words(3)}\n")
        self.git("-C", fc, "add", "--", rel)
        self.git("-C", fc, "-c", "user.name=foreign",
                 "-c", f"user.email={FOREIGN_EMAIL}", "commit", "-q",
                 "-m", f"{FOREIGN_SUBJECT} {self.word()}")
        self.git("-C", fc, "push", "-q", "origin", f"HEAD:{MAIN}")
        return self.origin_head()

    def commit_with(self, since: str, token: str) -> str | None:
        found = [sha for sha, subject in self.origin_log(since)
                 if token in subject]
        self.assertLessEqual(len(found), 1, self.msg(f"{token}: {found}"))
        return found[0] if found else None

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
        path = self.source_dir / f"{self.word()}.md"
        path.write_bytes(text.encode("utf-8"))
        return path

    def _held(self, argv, fn) -> None:
        before = len(notes.pending_notes())
        out = run_command(fn, argv)
        self.assertEqual(len(notes.pending_notes()), before + 1,
                         self.msg(f"запись не удержана: {argv}: {out}"))

    def hold_note(self, section: str, token: str) -> str:
        """Удержать заметку-вставку раздела; текст строки — с меткой."""
        text = {"копилка": f"4 | 02.10 | {token} | o.py",
                "бэклог": f"2 | {token} | —",
                "очередь": f"3 | {token} | —"}[section]
        self._held([section, "--text", text], notes.cmd_note)
        return text

    def hold_doc(self, rel: str, token: str, content: str | None = None) -> str:
        """Удержать `doc-commit`; основание — с меткой."""
        message = f"{token} {self.words(2)}"
        if content is None:
            content = f"# Документ\n\n{token} {self.words(4)}\n"
        self._held([rel, "--from", str(self.source(content)),
                    "--message", message], notes.cmd_doc_commit)
        return message

    def hold_apply(self, token: str, draft: str | None = None) -> str:
        """Удержать `note --apply` (несёт `base_blob` построения); основание
        — с меткой."""
        message = f"{token} {self.words(2)}"
        self._held(["--apply", str(self.source(draft or self.draft(token))),
                    "--message", message], notes.cmd_note)
        return message

    def draft(self, token: str) -> str:
        """Заготовка `--apply`: документ origin с новой строкой копилки."""
        return BACKLOG_TEXT.replace(
            OLD_COPILKA_ROW, f"{OLD_COPILKA_ROW}\n| 2 | 03.10 | {token} | o.py |")

    def lay_record(self, request: dict) -> str:
        """Файл удержания, положенный тестом, — последним в порядке
        удержания на момент вызова; id файла."""
        d = config.ROOT / ".artel" / "notes-pending"
        d.mkdir(parents=True, exist_ok=True)
        stamps = [int(p.stem.split("-", 1)[0]) for p in d.glob("*.json")]
        stamp = max(stamps + [int(time.time() * 1000)]) + 1
        name = f"{stamp:013d}-{uuid.uuid4().hex[:8]}"
        (d / f"{name}.json").write_text(json.dumps(request, ensure_ascii=False),
                                        encoding="utf-8")
        return name

    def pending_ids(self) -> list:
        d = config.ROOT / ".artel" / "notes-pending"
        return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []

    def assert_hold_order(self, tokens: list) -> None:
        """Предусловие: записи удержаны ровно в порядке `tokens`."""
        records = [json.dumps(r, ensure_ascii=False)
                   for r in notes.pending_notes()]
        self.assertEqual(len(records), len(tokens), self.msg(str(records)))
        for token, record in zip(tokens, records):
            self.assertIn(token, record, self.msg(f"порядок удержания: {records}"))

    def journal_actions(self) -> list:
        return [row[0] for row in store.db().execute(
            "SELECT action FROM steps ORDER BY rowid").fetchall()]

    def flush(self) -> str:
        self.close_window()
        return run_command(notes.cmd_note, ["--flush"])


class OnePushTest(BatchFlushSandbox):

    def test_ac1_three_records_one_push_in_hold_order_with_own_messages(self):
        """Заметка копилки, заметка бэклога и `doc-commit` `docs/**`.

        Сценарий: три записи удержаны окном тишины в случайном порядке;
        `note --flush`. Origin принял ровно один push, его голова —
        последний из трёх новых коммитов поверх прежней головы; темы
        коммитов — прежние сообщения записей (`оператор: <раздел> —
        <текст>` / `docs: <путь> — <основание>`) в порядке удержания;
        файлов удержания нет.

        Ловит мутацию: `_flush_pending` по-прежнему зовёт `_attempt` на
        каждую запись — origin видит три push; либо пакет собран в одном
        коммите/в обратном порядке — темы и их порядок расходятся с
        удержанием.
        """
        kinds = ["копилка", "бэклог", "doc"]
        self.rng.shuffle(kinds)
        self.open_window()
        tokens, expected = [], []
        for kind in kinds:
            token = self.token()
            tokens.append(token)
            if kind == "doc":
                message = self.hold_doc(DOC_REL, token)
                expected.append(f"docs: {DOC_REL} — {message}")
            else:
                text = self.hold_note(kind, token)
                expected.append(
                    f"{notes.NOTE_COMMIT_SUBJECT_PREFIX}{kind} — {text[:80]}")
        self.assert_hold_order(tokens)
        before, pushes = self.origin_head(), len(self.pushes())

        out = self.flush()

        log = self.origin_log(before)
        self.assertEqual([subject for _sha, subject in log], expected,
                         self.msg(out))
        self.assertEqual(self.pushes()[pushes:], [log[-1][0]], self.msg(out))
        self.assertEqual(self.pending_ids(), [], self.msg(out))


class InvalidRecordTest(BatchFlushSandbox):

    def test_ac2_invalid_record_stays_held_others_go_in_one_push(self):
        """Одна из трёх записей не проходит собственную валидацию.

        Сценарий: удержаны заметка копилки и `doc-commit`, а на случайном
        месте порядка — заметка, удержанная без построения (сетевой отказ
        fetch), с неверным числом колонок; `note --flush`. Две годные
        записи — в origin одним push; файл удержания негодной на месте,
        коммита с её меткой нет, вывод несёт `удержанная запись не
        отправлена: …`.

        Ловит мутацию: отказ валидации одной записи (`SystemExit` при
        построении) рушит весь пакет — годные записи не отправлены; либо
        пакет снимает файлы всех записей, включая негодную; либо годные
        записи уходят по одной — два push.
        """
        bad_at = self.rng.randrange(3)
        self.open_window()
        tokens, bad_id, bad_token = [], None, None
        good = iter(["копилка", "doc"])
        for i in range(3):
            token = self.token()
            tokens.append(token)
            if i == bad_at:
                bad_token = token
                bad_id = self.lay_record({"kind": "insert", "section": "копилка",
                                          "text": f"{token} | o.py"})
            elif next(good) == "doc":
                self.hold_doc(DOC_REL, token)
            else:
                self.hold_note("копилка", token)
        self.assert_hold_order(tokens)
        before, pushes = self.origin_head(), len(self.pushes())

        out = self.flush()

        self.assertIn(NOT_SENT_PREFIX, out, self.msg(out))
        self.assertEqual(self.pending_ids(), [bad_id], self.msg(out))
        self.assertIsNone(self.commit_with(before, bad_token), self.msg(out))
        sent = [self.commit_with(before, t) for t in tokens if t != bad_token]
        self.assertNotIn(None, sent, self.msg(out))
        self.assertEqual(len(self.pushes()) - pushes, 1, self.msg(out))


class NonFastForwardRebuildTest(BatchFlushSandbox):

    def test_ac3_foreign_commit_before_push_rebuilds_batch_on_top(self):
        """Чужой коммит между построением пакета и push.

        Сценарий: удержаны три записи (заметки копилки и бэклога,
        `doc-commit`); хук `post-commit` клона уводит origin чужим коммитом
        после первого коммита пакета, push пакета отказывает (fetch first);
        `note --flush`. В origin — чужой коммит, поверх него три коммита
        записей в порядке удержания; клон артели сделал не меньше двух
        попыток push, origin принял один его push; файлов удержания нет.

        Ловит мутацию: отказ push пакета не перестраивает его от свежего
        `origin/main` (пакет брошен либо записи удержаны) — коммитов
        записей в origin нет, файлы удержания остались.
        """
        kinds = ["копилка", "бэклог", "doc"]
        self.rng.shuffle(kinds)
        self.open_window()
        tokens = []
        for kind in kinds:
            token = self.token()
            tokens.append(token)
            if kind == "doc":
                self.hold_doc(DOC_REL, token)
            else:
                self.hold_note(kind, token)
        before, pushes, attempts = (self.origin_head(), len(self.pushes()),
                                    self.attempts())
        self.arm_mover(1, FOREIGN_REL)

        out = self.flush()

        log = self.origin_log(before)
        self.assertEqual(len(log), 4, self.msg(f"{log}; {out}"))
        self.assertTrue(log[0][1].startswith(FOREIGN_SUBJECT),
                        self.msg(f"{log}; {out}"))
        for (_sha, subject), token in zip(log[1:], tokens):
            self.assertIn(token, subject, self.msg(f"{log}; {out}"))
        self.assertGreaterEqual(self.attempts() - attempts, 2, self.msg(out))
        self.assertEqual(self.pushes()[pushes:], [log[-1][0]], self.msg(out))
        self.assertEqual(self.pending_ids(), [], self.msg(out))


class ConfigRecordAfterBatchTest(BatchFlushSandbox):

    def test_ac4_config_record_goes_after_batch_by_separate_push_with_gate(self):
        """Правка конфигурации среди удержанных — отдельным push после пакета.

        Сценарий (для `note --flush` и для `doc-commit --flush`):
        удержаны правка `gates.yaml` (первой), заметка копилки и
        `doc-commit` `docs/**`; полный набор подменён зелёным шпионом.
        Origin принял два push: первый — пакет заметки и документа (его
        голова — коммит документа), второй — коммит конфигурации; шпион
        набора позван ровно раз и уже после push пакета.

        Ловит мутацию: правка конфигурации вошла в пакет (один push, набор
        гоняется посреди пакета) либо ушла раньше пакета в порядке
        удержания — число push, порядок коммитов или момент прогона
        набора расходятся.
        """
        self.assertIn(CONFIG_REL, notes.DOC_COMMIT_CONFIG_PATHS)
        for name, fn in (("note", notes.cmd_note),
                         ("doc-commit", notes.cmd_doc_commit)):
            with self.subTest(entry=name):
                self.open_window()
                cfg, note, doc = self.token(), self.token(), self.token()
                self.hold_doc(CONFIG_REL, cfg, f"gates: {cfg}\n")
                self.hold_note("копилка", note)
                self.hold_doc(DOC_REL, doc)
                self.assert_hold_order([cfg, note, doc])
                self.close_window()
                before, pushes = self.origin_head(), len(self.pushes())
                gate_calls = []

                def suite(work_dir, **_kwargs):
                    gate_calls.append(len(self.pushes()) - pushes)
                    return True, ""

                with mock.patch.object(acceptance, "run_full_suite", suite):
                    out = run_command(fn, ["--flush"])

                log = self.origin_log(before)
                self.assertEqual(len(log), 3, self.msg(f"{log}; {out}"))
                for (_sha, subject), token in zip(log, (note, doc, cfg)):
                    self.assertIn(token, subject, self.msg(f"{log}; {out}"))
                self.assertEqual(self.pushes()[pushes:],
                                 [log[1][0], log[2][0]], self.msg(out))
                self.assertEqual(gate_calls, [1], self.msg(out))
                self.assertEqual(self.pending_ids(), [], self.msg(out))


class OpportunisticFlushTest(BatchFlushSandbox):

    def test_ac5_opportunistic_flush_one_push_then_new_note_separately(self):
        """Попутный сброс в начале очередной `note` вне окна тишины.

        Сценарий: удержаны от двух до четырёх записей (заметки копилки и
        `doc-commit` новых документов) в случайном составе; окно закрыто;
        `note бэклог --text …`. Origin принял два push: первый — все
        удержанные записи (голова — коммит последней из них), второй —
        коммит новой заметки поверх них; файлов удержания нет.

        Ловит мутацию: попутный сброс идёт старым путём по одной записи —
        push больше двух; либо новая заметка вошла в пакет удержанных —
        push один.
        """
        self.open_window()
        tokens = []
        for _ in range(self.rng.randint(2, 4)):
            token = self.token()
            tokens.append(token)
            if self.rng.random() < 0.5:
                self.hold_note("копилка", token)
            else:
                self.hold_doc(f"docs/research/{self.word().lower()}.md", token)
        self.close_window()
        before, pushes = self.origin_head(), len(self.pushes())
        new = self.token()

        out = run_command(notes.cmd_note, ["бэклог", "--text", f"2 | {new} | —"])

        log = self.origin_log(before)
        self.assertEqual(len(log), len(tokens) + 1, self.msg(f"{log}; {out}"))
        for (_sha, subject), token in zip(log, tokens + [new]):
            self.assertIn(token, subject, self.msg(f"{log}; {out}"))
        self.assertEqual(self.pushes()[pushes:], [log[-2][0], log[-1][0]],
                         self.msg(out))
        self.assertEqual(self.pending_ids(), [], self.msg(out))


class OutputAndJournalTest(BatchFlushSandbox):

    def test_ac6_each_sent_record_prints_own_sha_and_journals_it(self):
        """Строки вывода и журнал пакета `doc-commit`, `--apply` и заметки.

        Сценарий: удержаны `doc-commit` `docs/**`, `note --apply` и заметка
        бэклога (заготовка раньше заметки), а на случайном месте — заметка
        очереди с неверным числом колонок; `note --flush`. Один push;
        вывод несёт ровно по одной строке `<путь> закоммичен в
        origin/main: <sha>`, `docs/backlog.md заменён заготовкой в
        origin/main: <sha>`, `заметка (бэклог) отправлена в origin/main:
        <sha>`; sha разные и равны коммитам этих записей в origin; журнал
        несёт `docs/backlog.md заменён заготовкой <sha>` и `заметка: бэклог
        <sha>` с теми же sha; у отказавшей заметки очереди нет ни строки об
        отправке, ни записи журнала.

        Ловит мутацию: строки печатаются sha головы пакета вместо sha
        коммита записи (все sha равны) либо не печатаются вовсе; журнал
        пишется до push или с sha головы пакета; отказавшая запись
        печатает строку об отправке.
        """
        order = ["doc", "apply", "note"]
        self.rng.shuffle(order)
        if order.index("apply") > order.index("note"):
            i, j = order.index("apply"), order.index("note")
            order[i], order[j] = order[j], order[i]
        order.insert(self.rng.randrange(4), "bad")
        self.open_window()
        tok = {kind: self.token() for kind in order}
        for kind in order:
            if kind == "doc":
                self.hold_doc(DOC_REL, tok[kind])
            elif kind == "apply":
                self.hold_apply(tok[kind])
            elif kind == "note":
                self.hold_note("бэклог", tok[kind])
            else:
                self.lay_record({"kind": "insert", "section": "очередь",
                                 "text": f"{tok[kind]} | —"})
        self.assert_hold_order([tok[kind] for kind in order])
        before, pushes = self.origin_head(), len(self.pushes())
        journal_before = len(self.journal_actions())

        out = self.flush()

        self.assertEqual(len(self.pushes()) - pushes, 1, self.msg(out))
        sha_re = "([0-9a-f]{7,64})"
        lines = {
            "doc": re.findall(rf"^{re.escape(DOC_REL)} закоммичен в "
                              rf"origin/{MAIN}: {sha_re}\s*$", out, re.M),
            "apply": re.findall(rf"^{re.escape(notes.BACKLOG_REL)} заменён "
                                rf"заготовкой в origin/{MAIN}: {sha_re}\s*$",
                                out, re.M),
            "note": re.findall(rf"^заметка \(бэклог\) отправлена в "
                               rf"origin/{MAIN}: {sha_re}\s*$", out, re.M),
        }
        commits = {kind: self.commit_with(before, tok[kind])
                   for kind in ("doc", "apply", "note")}
        for kind, found in lines.items():
            self.assertEqual(found, [commits[kind]],
                             self.msg(f"{kind}: {found} против {commits}; {out}"))
        self.assertEqual(len(set(commits.values())), 3, self.msg(str(commits)))
        self.assertNotRegex(out, r"заметка \(очередь\) отправлена", self.msg(out))
        self.assertIsNone(self.commit_with(before, tok["bad"]), self.msg(out))
        journal = self.journal_actions()[journal_before:]
        self.assertIn(f"{notes.BACKLOG_REL} заменён заготовкой {commits['apply']}",
                      journal, self.msg(f"{journal}; {out}"))
        self.assertIn(f"заметка: бэклог {commits['note']}", journal,
                      self.msg(f"{journal}; {out}"))
        self.assertFalse([a for a in journal if a.startswith("заметка: очередь")],
                         self.msg(f"{journal}; {out}"))


class AttemptsExhaustedTest(BatchFlushSandbox):

    def test_ac7_every_push_refused_makes_max_attempts_and_keeps_all_held(self):
        """Origin уходит вперёд перед каждым push пакета.

        Сценарий: удержаны `doc-commit`, `note --apply` и заметка копилки;
        хук `post-commit` клона уводит origin чужим коммитом после каждого
        коммита клона — каждый push пакета отказывает; `note --flush`. Клон
        сделал ровно `notes.MAX_PUSH_ATTEMPTS` попыток push; набор файлов
        удержания прежний; в origin после прежней головы только чужие
        коммиты; ни строки об отправке с sha, ни записи журнала
        `_journal_commit` (`… заменён заготовкой …`, `заметка: …`).

        Ловит мутацию: повторы пакета не ограничены `MAX_PUSH_ATTEMPTS`
        (на одну больше/меньше либо по попыткам на каждую запись); файлы
        удержания снимаются до успешного push; строки вывода или журнал
        пишутся до push пакета.
        """
        self.open_window()
        doc, apply, note = self.token(), self.token(), self.token()
        self.hold_doc(DOC_REL, doc)
        self.hold_apply(apply)
        self.hold_note("копилка", note)
        held = self.pending_ids()
        before, attempts = self.origin_head(), self.attempts()
        journal_before = len(self.journal_actions())
        self.arm_mover(-1, FOREIGN_REL)

        out = self.flush()

        self.assertEqual(self.attempts() - attempts, notes.MAX_PUSH_ATTEMPTS,
                         self.msg(out))
        self.assertEqual(self.pending_ids(), held, self.msg(out))
        log = self.origin_log(before)
        self.assertTrue(log, self.msg(out))
        for _sha, subject in log:
            self.assertTrue(subject.startswith(FOREIGN_SUBJECT),
                            self.msg(f"{log}; {out}"))
        self.assertNotRegex(out, rf"в origin/{MAIN}: [0-9a-f]{{7,}}", self.msg(out))
        journal = self.journal_actions()[journal_before:]
        self.assertFalse([a for a in journal if "заменён заготовкой" in a
                          or a.startswith("заметка:")],
                         self.msg(f"{journal}; {out}"))


class SamePathSameBaseTest(BatchFlushSandbox):

    def test_ac8_second_doc_commit_of_same_path_and_base_gets_stale_refusal(self):
        """Две записи `doc-commit` одного пути с одной базой.

        Сценарий: удержаны два `doc-commit` `docs/roadmap.md` с разным
        содержимым, у обеих одна `held_base`; `note --flush`. Первая — в
        origin (путь несёт её содержимое); вторая удержана, коммита с её
        меткой нет, вывод несёт `файл изменился в origin после сборки
        записи`.

        Ловит мутацию: сверка второй записи пакета идёт от свежего
        `origin/main` (до пакета), а не от головы пакета перед ней — база
        совпадает, вторая запись затирает первую.
        """
        first, second = self.token(), self.token()
        first_text = f"# Роадмап\n\n{first} {self.words(4)}\n"
        self.open_window()
        self.hold_doc(DOC_REL, first, first_text)
        self.hold_doc(DOC_REL, second)
        records = notes.pending_notes()
        self.assertEqual(records[0][notes.HELD_BASE_KEY],
                         records[1][notes.HELD_BASE_KEY], self.msg(str(records)))
        second_id = self.pending_ids()[1]
        before = self.origin_head()

        out = self.flush()

        self.assertIsNotNone(self.commit_with(before, first), self.msg(out))
        self.assertEqual(self.origin_show(DOC_REL), first_text, self.msg(out))
        self.assertIsNone(self.commit_with(before, second), self.msg(out))
        self.assertEqual(self.pending_ids(), [second_id], self.msg(out))
        self.assertIn(STALE_PHRASE, out, self.msg(out))


class BatchHeadReferenceTest(BatchFlushSandbox):
    """AC-9: сверка записи k > 1 — от головы пакета перед ней."""

    def flush_expecting_refusal(self, refused_token: str, sent: list,
                                phrase: str) -> None:
        refused_id = [p for p, r in zip(self.pending_ids(), notes.pending_notes())
                      if refused_token in json.dumps(r, ensure_ascii=False)]
        before, pushes = self.origin_head(), len(self.pushes())

        out = self.flush()

        self.assertIn(phrase, out, self.msg(out))
        self.assertEqual(self.pending_ids(), refused_id, self.msg(out))
        self.assertIsNone(self.commit_with(before, refused_token), self.msg(out))
        for token in sent:
            self.assertIsNotNone(self.commit_with(before, token), self.msg(out))
        self.assertEqual(len(self.pushes()) - pushes, 1, self.msg(out))

    def test_ac9_held_apply_after_backlog_note_gets_stale_base_refusal(self):
        """Заметка бэклога, за ней удержанная `note --apply`.

        Сценарий: окно тишины удерживает заметку бэклога, затем `--apply`
        (её `base_blob` — документ без заметки); `note --flush`. Строка
        заметки — в `docs/backlog.md` origin; `--apply` удержана с отказом
        `APPLY_STALE_BASE_REFUSAL`, коммита заготовки нет.

        Ловит мутацию: `base_blob` записи пакета сверяется со свежим
        `origin/main` до пакета, а не с головой пакета перед ней —
        заготовка проходит и стирает только что вставленную заметку.
        """
        note, apply = self.token(), self.token()
        self.open_window()
        self.hold_note("бэклог", note)
        self.hold_apply(apply)
        self.flush_expecting_refusal(apply, [note],
                                     notes.APPLY_STALE_BASE_REFUSAL)
        self.assertIn(note, self.origin_show(notes.BACKLOG_REL))

    def test_ac9_second_apply_without_base_blob_has_nothing_to_commit(self):
        """Пример (а): две `--apply` без `base_blob` с одной заготовкой.

        Сценарий: файлы удержания двух `--apply` без `base_blob` (удержаны
        после сетевого отказа fetch) с одной заготовкой и разными
        основаниями, за ними — удержанный `doc-commit`; `note --flush`.
        Первая и `doc-commit` — в origin одним push; вторая удержана с
        отказом `заготовка совпадает с содержимым в origin/main —
        коммитить нечего`.

        Ловит мутацию: «содержимое уже в origin» второй записи сверяется
        со свежим `origin/main` до пакета — заготовка отличается, вторая
        запись делает пустой коммит/отказ другого текста; либо `known`
        записи k > 1 — прежняя голова клона, и она отказывает чужой базой.
        """
        first, second, doc = self.token(), self.token(), self.token()
        draft = self.draft(self.token())
        self.lay_record({"kind": notes.APPLY_KIND, "content": draft,
                         "message": f"{first} {self.words(2)}"})
        self.lay_record({"kind": notes.APPLY_KIND, "content": draft,
                         "message": f"{second} {self.words(2)}"})
        self.open_window()
        self.hold_doc(DOC_REL, doc)
        self.assert_hold_order([first, second, doc])
        self.flush_expecting_refusal(
            second, [first, doc],
            f"заготовка совпадает с содержимым в origin/{MAIN} — коммитить нечего")

    def test_ac9_second_legacy_doc_commit_same_content_has_nothing_to_commit(self):
        """Пример (б): два `doc-commit` старого формата с одним содержимым.

        Сценарий: файлы удержания двух `doc-commit` `docs/roadmap.md` без
        `held_base` с одним содержимым и разными основаниями, за ними —
        удержанная заметка копилки; `note --flush`. Первый и заметка — в
        origin одним push; второй удержан с отказом `содержимое уже
        совпадает с origin/main — коммитить нечего`.

        Ловит мутацию: пиновая сверка записи k > 1 берёт `known` прежней
        головы клона — второй получает `DOC_COMMIT_BASE_REFUSAL` вместо
        «коммитить нечего»; либо «уже в origin» сверяется со свежим
        `origin/main` до пакета — второй коммитится.
        """
        first, second, note = self.token(), self.token(), self.token()
        content = f"# Роадмап\n\n{self.token()} {self.words(4)}\n"
        for token in (first, second):
            self.lay_record({"kind": notes.DOC_COMMIT_KIND, "path": DOC_REL,
                             "content": content,
                             "message": f"{token} {self.words(2)}"})
        self.open_window()
        self.hold_note("копилка", note)
        self.assert_hold_order([first, second, note])
        self.flush_expecting_refusal(
            second, [first, note],
            f"содержимое уже совпадает с origin/{MAIN} — коммитить нечего")

    def test_ac9_held_doc_commit_equal_to_batch_head_gets_stale_refusal(self):
        """Пример (в), `doc-commit` с `held_base`: содержимое равно голове
        пакета перед ним.

        Сценарий: окно тишины удерживает два `doc-commit` `docs/guide.md` с
        одним содержимым (одна `held_base`) и заметку копилки; `note
        --flush`. Первый и заметка — в origin одним push; второй удержан с
        отказом `файл изменился в origin после сборки записи` (сверка базы
        раньше «коммитить нечего»).

        Ловит мутацию: в пакете «коммитить нечего» проверяется раньше
        сверки `held_base` — второй получает отказ другого текста; либо
        сверка идёт от свежего `origin/main` — второй проходит базу.
        """
        first, second, note = self.token(), self.token(), self.token()
        content = f"# Руководство\n\n{self.token()} {self.words(4)}\n"
        self.open_window()
        self.hold_doc(GUIDE_REL, first, content)
        self.hold_doc(GUIDE_REL, second, content)
        self.hold_note("копилка", note)
        self.flush_expecting_refusal(second, [first, note], STALE_PHRASE)

    def test_ac9_held_apply_equal_to_batch_head_gets_stale_refusal(self):
        """Пример (в), `--apply` с `base_blob`: заготовка равна голове пакета
        перед ней.

        Сценарий: окно тишины удерживает две `--apply` с одной заготовкой
        (у обеих `base_blob` — прежний документ) и `doc-commit`; `note
        --flush`. Первая и `doc-commit` — в origin одним push; вторая
        удержана с отказом `APPLY_STALE_BASE_REFUSAL`.

        Ловит мутацию: сверка `base_blob` записи пакета идёт от свежего
        `origin/main` до пакета либо «коммитить нечего» проверяется раньше
        неё — вторая получает отказ другого текста.
        """
        first, second, doc = self.token(), self.token(), self.token()
        draft = self.draft(self.token())
        self.open_window()
        self.hold_apply(first, draft)
        self.hold_apply(second, draft)
        self.hold_doc(DOC_REL, doc)
        self.flush_expecting_refusal(second, [first, doc],
                                     notes.APPLY_STALE_BASE_REFUSAL)


class RebuildRefusesStaleTest(BatchFlushSandbox):

    def test_ac10_foreign_change_of_held_path_refuses_it_on_rebuild(self):
        """Чужой коммит меняет путь удержанного `doc-commit` до push пакета.

        Сценарий: удержаны `doc-commit` `docs/roadmap.md` (с `held_base`),
        заметка копилки и `doc-commit` `docs/guide.md` в случайном порядке;
        хук `post-commit` клона после первого коммита пакета уводит origin
        чужой правкой `docs/roadmap.md`, push пакета отказывает; `note
        --flush`. `doc-commit` `docs/roadmap.md` удержан с отказом `файл
        изменился в origin после сборки записи`, его коммита нет, путь в
        origin — с чужой правкой; две другие записи — одним push поверх
        чужого коммита.

        Ловит мутацию: перестройка переносит прежние коммиты пакета
        (rebase/cherry-pick) либо сверяет `held_base` только в первом
        построении — чужая правка затёрта, запись снята.
        """
        kinds = ["roadmap", "копилка", "guide"]
        self.rng.shuffle(kinds)
        self.open_window()
        tok = {kind: self.token() for kind in kinds}
        for kind in kinds:
            if kind == "копилка":
                self.hold_note("копилка", tok[kind])
            else:
                self.hold_doc(DOC_REL if kind == "roadmap" else GUIDE_REL,
                              tok[kind])
        roadmap_id = self.pending_ids()[kinds.index("roadmap")]
        before, pushes = self.origin_head(), len(self.pushes())
        self.arm_mover(1, DOC_REL)

        out = self.flush()

        self.assertIn(STALE_PHRASE, out, self.msg(out))
        self.assertEqual(self.pending_ids(), [roadmap_id], self.msg(out))
        self.assertIsNone(self.commit_with(before, tok["roadmap"]), self.msg(out))
        self.assertIn(FOREIGN_SUBJECT, self.origin_show(DOC_REL), self.msg(out))
        log = self.origin_log(before)
        self.assertEqual(len(log), 3, self.msg(f"{log}; {out}"))
        self.assertTrue(log[0][1].startswith(FOREIGN_SUBJECT),
                        self.msg(f"{log}; {out}"))
        sent = [kind for kind in kinds if kind != "roadmap"]
        for (_sha, subject), kind in zip(log[1:], sent):
            self.assertIn(tok[kind], subject, self.msg(f"{log}; {out}"))
        self.assertEqual(self.pushes()[pushes:], [log[-1][0]], self.msg(out))


class FirstRecordKnownBaseTest(BatchFlushSandbox):
    """AC-11: `known` первой записи — голова, известная клону до fetch."""

    def check_first_refused(self, first: str, sent: list, phrase: str) -> None:
        first_id = self.pending_ids()[0]
        before, pushes = self.origin_head(), len(self.pushes())

        out = self.flush()

        self.assertIn(phrase, out, self.msg(out))
        self.assertEqual(self.pending_ids(), [first_id], self.msg(out))
        self.assertIsNone(self.commit_with(before, first), self.msg(out))
        for token in sent:
            self.assertIsNotNone(self.commit_with(before, token), self.msg(out))
        self.assertEqual(len(self.pushes()) - pushes, 1, self.msg(out))

    def test_ac11_first_apply_without_base_blob_refused_by_foreign_change(self):
        """Первой — `--apply` без `base_blob`; в origin чужая правка бэклога.

        Сценарий: файл удержания `--apply` без `base_blob` первым, затем
        окно тишины удерживает заметку копилки и `doc-commit`; после этого
        чужой коммит меняет `docs/backlog.md` в origin мимо клона; `note
        --flush`. `--apply` удержана с отказом `APPLY_FOREIGN_BASE_REFUSAL`,
        её коммита нет; две другие — в origin одним push.

        Ловит мутацию: `known` первой записи пакета — свежий `origin/main`
        этого же сброса, а не `_known_origin_main` до fetch — сверка чужой
        базы проходит, заготовка стирает чужую правку.
        """
        apply, note, doc = self.token(), self.token(), self.token()
        self.lay_record({"kind": notes.APPLY_KIND,
                         "content": self.draft(self.token()),
                         "message": f"{apply} {self.words(2)}"})
        self.open_window()
        self.hold_note("копилка", note)
        self.hold_doc(DOC_REL, doc)
        self.assert_hold_order([apply, note, doc])
        self.foreign_commit(notes.BACKLOG_REL)
        self.check_first_refused(apply, [note, doc],
                                 notes.APPLY_FOREIGN_BASE_REFUSAL)

    def test_ac11_first_legacy_doc_commit_refused_by_foreign_change(self):
        """Первым — `doc-commit` без `held_base`; в origin чужая правка его
        файла.

        Сценарий: файл удержания `doc-commit` `docs/roadmap.md` старого
        формата первым, затем окно тишины удерживает заметку копилки и
        `doc-commit` `docs/guide.md`; после этого чужой коммит меняет
        `docs/roadmap.md` в origin мимо клона; `note --flush`. Запись
        удержана с отказом `DOC_COMMIT_BASE_REFUSAL`, её коммита нет; две
        другие — в origin одним push.

        Ловит мутацию: пиновая сверка первой записи берёт `known` от
        свежего `origin/main` этого сброса — сверка проходит, чужая правка
        файла затёрта.
        """
        first, note, doc = self.token(), self.token(), self.token()
        self.lay_record({"kind": notes.DOC_COMMIT_KIND, "path": DOC_REL,
                         "content": f"# Роадмап\n\n{self.token()}\n",
                         "message": f"{first} {self.words(2)}"})
        self.open_window()
        self.hold_note("копилка", note)
        self.hold_doc(GUIDE_REL, doc)
        self.assert_hold_order([first, note, doc])
        self.foreign_commit(DOC_REL)
        self.check_first_refused(first, [note, doc],
                                 notes.DOC_COMMIT_BASE_REFUSAL)


if __name__ == "__main__":
    unittest.main()
