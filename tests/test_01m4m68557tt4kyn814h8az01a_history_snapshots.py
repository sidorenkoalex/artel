"""Команда Оператора `artifact-history-snapshots`: исторические снимки ссылок документов для каталогов задач `origin/main` без ссылки.

Группа: долгоживущий
Красен до реализации: команды `artifact-history-snapshots` в таблице `artel.py` нет — вызов кончается отказом «Неизвестная команда», ссылки не создаются, `docs` не находит документов исторической задачи, `doctor` историческую ссылку не сверяет.

Имени команды и флага пробного режима SPEC не называет; планка фиксирует
их так: `artel.py artifact-history-snapshots` создаёт снимки,
`artel.py artifact-history-snapshots --dry-run` — пробный режим. Команда
зовётся публичным входом `artel.main` с подменённым `sys.argv`.

Песочница — настоящий git: репозиторий песочницы `RealGitSandbox` (он же
клон артели) и bare `origin` рядом. Каталоги задач кладутся в `origin/main`
коммитами вспомогательного клона, локальная `main` песочницы остаётся на
исходном коммите: источник дерева — `origin/main`, не локальная ветка.
Существующий снимок — коммит в `refs/artifacts/<id>`, присутствующий
локально и в `origin`, только локально или только в `origin` (вид — по
зерну). Связка, которую держат тесты: команда — git (ссылки локально и в
`origin`) — журнал `steps` — `doctor` — `docs`.
"""

import contextlib
import io
import os
import random
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artel, config, docs_fetch, doctor, stack, store
from tests.sandbox import OriginRealGitSandbox

COMMAND = "artifact-history-snapshots"
DRY_RUN = "--dry-run"
TASKS_DIR = "tasks"
REF_PREFIX = "refs/artifacts/"
HISTORY_MARK = "исторический снимок"
ID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
OPTIONAL_DOCS = ("PLAN.md", "REVIEW.md", "ANSWER-1.md", "QUESTIONS.md",
                 "acceptance_tests/test_ac1_case.py",
                 "acceptance_tests/_sandbox.py")
# Вид существующей ссылки: где она есть до запуска команды.
EXISTING_KINDS = ("локально и в origin", "только локально", "только в origin")
ALARMS = ("warn", "fail")
HEX = re.compile(r"[0-9a-f]{7,40}")

DATE_MAIN = "2026-01-10T10:00:00+00:00"
DATE_SNAPSHOT = "2026-01-11T10:00:00+00:00"
DATE_MAIN_EDIT = "2026-02-01T10:00:00+00:00"
DATE_MAIN_CLEANUP = "2026-03-01T10:00:00+00:00"


def ref_of(task_id: str) -> str:
    return REF_PREFIX + task_id


def task_rel(task_id: str, rel: str = "") -> str:
    return "/".join(p for p in (TASKS_DIR, task_id, rel) if p)


class HistorySandbox(OriginRealGitSandbox):
    """Клон артели — репозиторий песочницы, `origin` — bare рядом с ним;
    каталоги задач — только в `origin/main`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2**32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.add_origin()
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.conn = store.db()
        scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        self.scratch = str(Path(scratch) / "clone")
        self.git("clone", "-q", self.bare, self.scratch)
        self.sgit("config", "user.name", "artel tests")
        self.sgit("config", "user.email", "tests@artel.invalid")
        self.used_ids: set = set()

    # --- помощники сценария -------------------------------------------------

    def note(self, text: str) -> str:
        return f"{text}\nзерно: {self.seed}"

    def sgit(self, *args: str, date: str | None = None) -> str:
        """git во вспомогательном клоне; `date` — дата автора и коммита."""
        env = ({"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
               if date else {})
        with mock.patch.dict(os.environ, env):
            return self.git("-C", self.scratch, *args)

    def new_id(self, kind: str | None = None) -> str:
        """Id задачи: исторический `Tnnn` либо ULID (вид — по зерну)."""
        kind = kind or self.rng.choice(("T", "ULID"))
        while True:
            if kind == "T":
                task_id = f"T{self.rng.randrange(1, 1000):03d}"
            else:
                task_id = "01" + "".join(self.rng.choice(ID_ALPHABET)
                                         for _ in range(24))
            if task_id not in self.used_ids:
                self.used_ids.add(task_id)
                return task_id

    def docs_of(self, task_id: str) -> dict:
        """{путь внутри каталога задачи: текст}: SPEC.md и случайные
        прочие документы со случайным содержимым."""
        rels = ["SPEC.md"] + self.rng.sample(
            OPTIONAL_DOCS, self.rng.randint(1, len(OPTIONAL_DOCS)))
        return {rel: f"{task_id} {rel} {self.rng.getrandbits(64):x}\n"
                for rel in rels}

    def write_scratch(self, task_id: str, docs: dict) -> None:
        for rel, text in docs.items():
            path = Path(self.scratch) / task_rel(task_id, rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def commit_main(self, dirs: dict, message: str, date: str) -> str:
        """Каталоги задач {id: {путь: текст}} коммитом в `origin/main`;
        локальная `main` песочницы не двигается, ссылка `origin/main` —
        подтягивается. Возвращает sha нового `origin/main`."""
        for task_id, docs in dirs.items():
            self.write_scratch(task_id, docs)
        self.sgit("add", "-A")
        self.sgit("commit", "-q", "-m", message, date=date)
        self.sgit("push", "-q", "origin", f"HEAD:{config.MAIN_BRANCH}")
        self.git("fetch", "-q", "origin")
        return self.origin_main()

    def drop_tasks_from_main(self) -> str:
        """Коммит в `origin/main`, убирающий каталог задач целиком."""
        self.sgit("rm", "-r", "-q", TASKS_DIR)
        self.sgit("commit", "-q", "-m", "уборка каталога задач",
                  date=DATE_MAIN_CLEANUP)
        self.sgit("push", "-q", "origin", f"HEAD:{config.MAIN_BRANCH}")
        self.git("fetch", "-q", "origin")
        return self.origin_main()

    def place_snapshot(self, task_id: str, docs: dict, kind: str) -> str:
        """Существующий снимок задачи — коммит с деревом `docs` под
        каталогом задачи в `refs/artifacts/<id>`; `kind` — где ссылка
        есть (`EXISTING_KINDS`). Возвращает sha снимка."""
        ref = ref_of(task_id)
        self.sgit("checkout", "-q", "--orphan", f"snapshot-{task_id}")
        self.sgit("rm", "-r", "-q", "-f", "--ignore-unmatch", ".")
        self.write_scratch(task_id, docs)
        self.sgit("add", "-A")
        self.sgit("commit", "-q", "-m", f"{task_id}: документы задачи",
                  date=DATE_SNAPSHOT)
        sha = self.sgit("rev-parse", "HEAD").strip()
        self.sgit("push", "-q", "origin", f"HEAD:{ref}")
        self.sgit("checkout", "-q", "-f", config.MAIN_BRANCH)
        if kind != "только в origin":
            self.git("fetch", "-q", "origin", f"{ref}:{ref}")
        if kind == "только локально":
            self.git("-C", self.bare, "update-ref", "-d", ref)
        return sha

    def origin_main(self) -> str:
        return self.git("-C", self.bare, "rev-parse",
                        config.MAIN_BRANCH).strip()

    def refs_in(self, *where: str) -> dict:
        out = self.git(*where, "for-each-ref",
                       "--format=%(refname) %(objectname)", REF_PREFIX)
        return dict(line.split(" ", 1) for line in out.splitlines() if line)

    def local_refs(self) -> dict:
        return self.refs_in()

    def origin_refs(self) -> dict:
        return self.refs_in("-C", self.bare)

    def run_cli(self, *argv: str) -> tuple:
        """(код выхода, вывод) `artel.py <argv>` вне окружения роли; код 0 —
        успех."""
        out = io.StringIO()
        code = 0
        with mock.patch.dict(os.environ), \
                mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            os.environ.pop(config.ARTEL_ROLE_ENV, None)
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code is None:
                    code = 0
                elif isinstance(exc.code, int):
                    code = exc.code
                else:
                    code = 1
                    out.write(f"\n{exc.code}")
        return code, out.getvalue()

    def run_command(self, *flags: str) -> str:
        code, out = self.run_cli(COMMAND, *flags)
        self.assertEqual(code, 0, self.note(
            f"{COMMAND} {' '.join(flags)} завершилась кодом {code}:\n{out}"))
        return out

    def assert_existing_kept(self, ref: str, kind: str, local_before: dict,
                             origin_before: dict, context: str) -> None:
        """Существующая ссылка не изменена: где она была — голова прежняя;
        где её не было — она либо так и отсутствует, либо равна прежней
        голове (подтянута/дослана без нового коммита)."""
        head = local_before.get(ref) or origin_before.get(ref)
        local, origin = self.local_refs(), self.origin_refs()
        if kind == "только в origin":
            self.assertEqual(origin.get(ref), head, self.note(
                f"{context}: {ref} в origin изменилась"))
            self.assertIn(local.get(ref), (None, head), self.note(
                f"{context}: локально {ref} указывает на новый коммит"))
        elif kind == "только локально":
            self.assertEqual(local.get(ref), head, self.note(
                f"{context}: локальная {ref} изменилась"))
            self.assertIn(origin.get(ref), (None, head), self.note(
                f"{context}: в origin {ref} указывает на новый коммит"))
        else:
            self.assertEqual(local.get(ref), head, self.note(
                f"{context}: локальная {ref} изменилась"))
            self.assertEqual(origin.get(ref), head, self.note(
                f"{context}: {ref} в origin изменилась"))


class ThreeDirsSandbox(HistorySandbox):
    """В `origin/main` три каталога задач: у `self.new_a` (задачи нет в
    таблице `tasks`) и `self.new_b` (закрытая задача в таблице, без записи
    о коммите закрытия) ссылки нет, у `self.old` — есть (снимок полнее
    main: те же файлы плюс RETRO.md, вид присутствия — по зерну)."""

    def setUp(self):
        super().setUp()
        self.new_a = self.new_id()
        self.new_b = self.new_id("ULID")
        self.old = self.new_id()
        store.insert_task(self.conn, self.new_b, "Историческая задача",
                          "done", f"task/{self.new_b.lower()}-x",
                          config.DEFAULT_TARGET, 25.0)
        self.docs = {tid: self.docs_of(tid)
                     for tid in (self.new_a, self.new_b, self.old)}
        self.main_sha = self.commit_main(self.docs, "каталоги задач",
                                         DATE_MAIN)
        self.old_kind = self.rng.choice(EXISTING_KINDS)
        fuller = dict(self.docs[self.old])
        fuller["RETRO.md"] = f"ретро {self.rng.getrandbits(64):x}\n"
        self.old_sha = self.place_snapshot(self.old, fuller, self.old_kind)
        self.new_ids = (self.new_a, self.new_b)

    def assert_created(self, task_id: str, local: dict, origin: dict) -> None:
        ref = ref_of(task_id)
        context = f"{ref} (вид существующей: {self.old_kind})"
        self.assertIn(ref, local, self.note(f"{context}: нет локально"))
        self.assertEqual(origin.get(ref), local[ref], self.note(
            f"{context}: в origin {origin.get(ref)}, локально {local[ref]}"))
        sha = local[ref]
        self.assertEqual(
            self.git("rev-parse", f"{sha}:{task_rel(task_id)}").strip(),
            self.git("rev-parse", f"{self.main_sha}:{task_rel(task_id)}").strip(),
            self.note(f"{context}: дерево каталога задачи не совпадает с "
                      f"origin/main {self.main_sha}"))
        names = self.git("ls-tree", "-r", "--name-only", sha).splitlines()
        foreign = [n for n in names if not n.startswith(task_rel(task_id) + "/")]
        self.assertEqual(foreign, [], self.note(
            f"{context}: в дереве снимка файлы вне каталога задачи"))
        message = self.git("log", "-1", "--format=%B", sha)
        self.assertIn(HISTORY_MARK, message.lower(), self.note(
            f"{context}: коммит не помечен как исторический снимок:\n{message}"))
        tokens = HEX.findall(message.lower())
        self.assertTrue(any(self.main_sha.startswith(t) for t in tokens),
                        self.note(f"{context}: коммит не называет sha "
                                  f"origin/main {self.main_sha}:\n{message}"))


class CreateSnapshotsTest(ThreeDirsSandbox):

    def test_ac1_creates_two_refs_from_origin_main_and_keeps_third(self):
        """Команда создаёт ровно две ссылки — для каталогов без ссылки, локально и в origin; третья ссылка прежняя.

        Сценарий: в `origin/main` три каталога задач со случайными
        документами (локальная `main` их не содержит); у двух ссылки
        `refs/artifacts/<id>` нет нигде, у третьей есть (локально и в
        origin, только локально или только в origin — по зерну). После
        команды новые ссылки — ровно эти две (локально и в origin, с одной
        головой); дерево снимка — каталог задачи из `origin/main` и только
        он; сообщение коммита содержит «исторический снимок» и sha
        `origin/main`; ссылка третьей задачи не изменилась.

        Ловит мутацию: команда переписывает существующую ссылку третьей
        задачи деревом main — голова третьей ссылки меняется; созданная
        ссылка не отправлена в
        origin — в origin её нет; дерево берётся из локальной `main` — в
        ней каталогов нет, ссылка не создаётся либо пуста; в сообщение
        коммита не попадает sha источника.
        """
        local_before, origin_before = self.local_refs(), self.origin_refs()

        out = self.run_command()

        local, origin = self.local_refs(), self.origin_refs()
        old_ref = ref_of(self.old)
        expected = {ref_of(t) for t in self.new_ids}
        self.assertEqual(set(local) - set(local_before) - {old_ref}, expected,
                         self.note(f"новые локальные ссылки; вывод:\n{out}"))
        self.assertEqual(set(origin) - set(origin_before) - {old_ref},
                         expected,
                         self.note(f"новые ссылки в origin; вывод:\n{out}"))
        for task_id in self.new_ids:
            self.assert_created(task_id, local, origin)
        self.assert_existing_kept(old_ref, self.old_kind, local_before,
                                  origin_before, "ссылка с прежним снимком")


class DryRunTest(ThreeDirsSandbox):

    def test_ac2_dry_run_lists_two_refs_and_writes_nothing(self):
        """Пробный режим называет две ссылки к созданию и ничего не пишет — ни ссылок, ни журнала.

        Сценарий: та же песочница, что в AC-1. `--dry-run` завершается
        успешно, его вывод называет обе задачи без ссылки; наборы
        `refs/artifacts/*` локально и в origin те же, что до вызова,
        число записей журнала `steps` прежнее. Затем обычный запуск
        создаёт обе ссылки — пробный режим описал ровно то, что сделал бы.

        Ловит мутацию: флаг пробного режима не учитывается — ссылки
        созданы и отправлены; пробный режим пишет в журнал запись о каждом
        кандидате — число записей `steps` растёт; перечень пробного режима
        не печатается — id задач нет в выводе.
        """
        local_before, origin_before = self.local_refs(), self.origin_refs()
        steps_before = len(store.all_steps(self.conn))

        out = self.run_command(DRY_RUN)

        for task_id in self.new_ids:
            self.assertIn(task_id, out, self.note(
                f"пробный режим не назвал {task_id}:\n{out}"))
        self.assertEqual(self.local_refs(), local_before, self.note(
            f"пробный режим изменил локальные ссылки:\n{out}"))
        self.assertEqual(self.origin_refs(), origin_before, self.note(
            f"пробный режим изменил ссылки в origin:\n{out}"))
        self.assertEqual(len(store.all_steps(store.db())), steps_before,
                         self.note(f"пробный режим писал в журнал:\n{out}"))

        self.run_command()
        local = self.local_refs()
        for task_id in self.new_ids:
            self.assertIn(ref_of(task_id), local, self.note(
                f"обычный запуск после пробного не создал {task_id}"))


class RepeatRunTest(ThreeDirsSandbox):

    def test_ac3_second_run_creates_nothing_and_keeps_heads(self):
        """Повторный запуск не создаёт новых ссылок и не двигает головы всех трёх.

        Сценарий: песочница AC-1, команда запущена и создала две ссылки.
        Второй запуск завершается успешно; наборы `refs/artifacts/*`
        локально и в origin и головы всех ссылок те же, что после
        первого запуска.

        Ловит мутацию: команда не узнаёт созданную ею ссылку и пишет
        поверх новый коммит снимка (новый sha коммита из-за даты или
        родителя) — голова исторической ссылки меняется; команда
        переписывает существующую ссылку — голова третьей меняется.
        """
        self.run_command()
        local_first, origin_first = self.local_refs(), self.origin_refs()
        for task_id in self.new_ids:
            self.assertIn(ref_of(task_id), local_first, self.note(
                f"предусловие: первый запуск создал {task_id}"))

        out = self.run_command()

        self.assertEqual(self.local_refs(), local_first, self.note(
            f"второй запуск изменил локальные ссылки:\n{out}"))
        self.assertEqual(self.origin_refs(), origin_first, self.note(
            f"второй запуск изменил ссылки в origin:\n{out}"))


class NewerInMainSandbox(HistorySandbox):
    """Каталог задачи со снимком, после которого в main правили файлы:
    `self.newer` — {путь внутри каталога: (текст снимка, текст main)}."""

    def setUp(self):
        super().setUp()
        self.task = self.new_id()
        docs = self.docs_of(self.task)
        self.commit_main({self.task: docs}, "каталог задачи", DATE_MAIN)
        self.kind = "локально и в origin"
        snapshot = dict(docs)
        snapshot["RETRO.md"] = f"ретро {self.rng.getrandbits(64):x}\n"
        self.snap_sha = self.place_snapshot(self.task, snapshot, self.kind)
        changed = self.rng.sample(sorted(docs),
                                  self.rng.randint(1, min(2, len(docs))))
        edited = {rel: docs[rel] + f"правка {self.rng.getrandbits(64):x}\n"
                  for rel in changed}
        self.main_sha = self.commit_main({self.task: edited},
                                         "правка после мержа", DATE_MAIN_EDIT)
        self.newer = {rel: (docs[rel], edited[rel]) for rel in changed}

    def candidates(self, rev: str, rel: str, where: tuple) -> set:
        blob = self.git(*where, "rev-parse",
                        f"{rev}:{task_rel(self.task, rel)}").strip()
        return {blob, rev}


class NewerInMainReportTest(NewerInMainSandbox):

    def test_ac4_newer_main_file_reported_and_ref_kept(self):
        """Файл, который в main новее снимка, попадает в отчёт строкой «путь, sha main, sha снимка»; ссылка задачи не меняется.

        Сценарий: каталог задачи коммитом в `origin/main`, затем снимок
        задачи (те же файлы плюс RETRO.md) локально и в origin, затем в
        `origin/main` правят один-два файла каталога. После команды для
        каждого такого файла в выводе есть строка с его путём (полным или
        внутри каталога рядом с id задачи), sha в main (sha блоба файла или
        коммита `origin/main`) и sha в снимке (sha блоба файла или коммита
        снимка); голова ссылки задачи локально и в origin прежняя.

        Ловит мутацию: команда «обновляет» снимок новым файлом из main —
        голова ссылки меняется; файлы, где main новее, не перечисляются —
        строки с путём нет; в строке отчёта один sha вместо двух.
        """
        local_before, origin_before = self.local_refs(), self.origin_refs()
        ref = ref_of(self.task)

        out = self.run_command()

        lines = out.lower().splitlines()
        for rel in self.newer:
            main_shas = self.candidates(self.main_sha, rel, ("-C", self.bare))
            snap_shas = self.candidates(self.snap_sha, rel, ("-C", self.bare))
            full = task_rel(self.task, rel).lower()
            rows = [line for line in lines
                    if full in line or (self.task.lower() in line
                                        and rel.lower() in line)]
            matched = [line for line in rows
                       if any(c.startswith(t) for t in HEX.findall(line)
                              for c in main_shas)
                       and any(c.startswith(t) for t in HEX.findall(line)
                               for c in snap_shas)]
            self.assertTrue(matched, self.note(
                f"{rel}: нет строки отчёта с путём, sha main ({main_shas}) и "
                f"sha снимка ({snap_shas}):\n{out}"))
        self.assert_existing_kept(ref, self.kind, local_before, origin_before,
                                  "снимок, где main новее")


class ExistingRefNeverRewrittenTest(HistorySandbox):

    def test_ac8_existing_ref_kept_whatever_main_holds(self):
        """Ссылку, которая уже есть, команда не переписывает, как бы main ни расходился со снимком, — ни первым, ни повторным запуском.

        Сценарий: три каталога задач в `origin/main` и снимок каждой —
        по одной задаче на каждый вид присутствия ссылки (локально и в
        origin, только локально, только в origin); затем main расходится
        со снимками всеми способами сразу: файл правлен после снимка, в
        main добавлен файл, которого в снимке нет, а в снимке есть
        RETRO.md, которого нет в main. Два запуска команды подряд; после
        каждого голова каждой ссылки там, где она была, прежняя, а там, где
        её не было, — отсутствует или равна прежней голове.

        Ловит мутацию: команда переписывает существующую ссылку
        `refs/artifacts/<id>` (дополняет снимок файлами main или заменяет
        его деревом main) — голова ссылки меняется; наличие ссылки
        проверяется в одном месте из двух — задаче со ссылкой только в
        origin (или только локально) пишется новый коммит.
        """
        tasks = {self.new_id(): kind for kind in EXISTING_KINDS}
        docs = {task_id: self.docs_of(task_id) for task_id in tasks}
        self.commit_main(docs, "каталоги задач", DATE_MAIN)
        edits = {}
        for task_id, kind in tasks.items():
            snapshot = dict(docs[task_id])
            snapshot["RETRO.md"] = f"ретро {self.rng.getrandbits(64):x}\n"
            self.place_snapshot(task_id, snapshot, kind)
            rel = self.rng.choice(sorted(docs[task_id]))
            edits[task_id] = {rel: docs[task_id][rel] + "правка\n",
                              "ANSWER-9.md": f"новый {task_id}\n"}
        self.commit_main(edits, "правка после мержа", DATE_MAIN_EDIT)
        local_before, origin_before = self.local_refs(), self.origin_refs()

        for attempt in ("первый запуск", "повторный запуск"):
            out = self.run_command()
            for task_id, kind in tasks.items():
                self.assert_existing_kept(ref_of(task_id), kind, local_before,
                                          origin_before,
                                          f"{attempt} ({kind}); вывод:\n{out}")


class DoctorSandbox(ThreeDirsSandbox):
    """`doctor` в песочнице с настоящим git: проверка стека — заглушкой,
    как в `TmpRootTest` (она ставит окружение, а не смотрит в ссылки)."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(stack, "check_stack", lambda: [])
        patcher.start()
        self.addCleanup(patcher.stop)

    def alarms(self) -> list:
        return [c for c in doctor.all_checks(store.db()) if c.status in ALARMS]

    @staticmethod
    def render(checks) -> str:
        return "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks)


class DoctorQuietTest(DoctorSandbox):

    def test_ac5_doctor_raises_no_alarm_after_snapshots(self):
        """После создания исторических снимков `doctor` не поднимает тревог ни о ссылках документов, ни из-за записей журнала.

        Сценарий: песочница AC-1 (одна историческая задача без строки в
        таблице `tasks`, другая — закрытая задача в таблице без записи о
        коммите закрытия, третья — со снимком). Снимаются тревоги
        (`warn`/`fail`) `doctor.all_checks` до команды; команда создаёт две
        ссылки. После неё среди тревог нет ни одной новой, называющей
        какую-либо из трёх задач или ссылку документов.

        Ловит мутацию: `doctor` разбирает коммит снимка из записи журнала
        не в том виде, в каком его пишет команда (берёт всю деталь записи
        вместо sha), — тревога о расхождении ссылки с id задачи; запись
        журнала сделана, а ссылка в origin не отправлена — тревога «нет в
        origin» с id задачи; запись исторического снимка принята за шаг
        живой задачи без строки в `tasks` — тревога, называющая id.
        """
        ids = (self.new_a, self.new_b, self.old)
        before = {(c.name, c.status, c.detail) for c in self.alarms()}

        out = self.run_command()
        local = self.local_refs()
        for task_id in self.new_ids:
            self.assertIn(ref_of(task_id), local, self.note(
                f"предусловие: команда создала {task_id}:\n{out}"))

        after = self.alarms()
        new = [c for c in after if (c.name, c.status, c.detail) not in before
               and (any(t in c.detail for t in ids) or REF_PREFIX in c.detail)]
        self.assertEqual(new, [], self.note(
            f"новые тревоги doctor после исторических снимков:\n"
            f"{self.render(new)}"))


class DoctorTamperTest(DoctorSandbox):

    def test_ac6_doctor_alarms_on_swapped_historical_ref(self):
        """Подмена головы исторической ссылки — локально или в origin — даёт тревогу `doctor`, называющую задачу.

        Сценарий: песочница AC-1, команда создала две исторические ссылки
        (задачи без строки в `tasks` и закрытой задачи со строкой). Два
        раунда: в первом одной задаче (какой — по зерну) голову ссылки
        переставляют локально, другой — в origin, на дочерний коммит
        снимка; во втором места подмены меняются. В каждом раунде среди
        тревог (`warn`/`fail`) `doctor.all_checks` есть строка с id каждой
        из двух задач; после раунда головы возвращаются.

        Ловит мутацию: `doctor` сверяет исторические ссылки только с
        origin (или только локальную голову) — подмена в другом месте
        тревоги не даёт; запись об историческом снимке не сверяется вовсе
        («записи нет — не сверяется») — тревоги нет ни в одном случае;
        сверяются только задачи из таблицы `tasks` — задача T-серии без
        строки не даёт тревоги.
        """
        self.run_command()
        local = self.local_refs()
        for task_id in self.new_ids:
            self.assertIn(ref_of(task_id), local, self.note(
                f"предусловие: команда создала {task_id}"))
        first, second = self.rng.sample(self.new_ids, 2)
        for places in ({first: "локально", second: "в origin"},
                       {first: "в origin", second: "локально"}):
            with self.subTest(places=places, seed=self.seed):
                for task_id, where in places.items():
                    self.swap(task_id, where, local[ref_of(task_id)])
                alarms = self.alarms()
                for task_id, where in places.items():
                    self.assertTrue(
                        [c for c in alarms if task_id in c.detail],
                        self.note(f"{ref_of(task_id)} подменена {where} — "
                                  f"тревоги doctor с {task_id} нет:\n"
                                  f"{self.render(alarms)}"))
                for task_id, where in places.items():
                    repo = () if where == "локально" else ("-C", self.bare)
                    self.git(*repo, "update-ref", ref_of(task_id),
                             local[ref_of(task_id)])

    def swap(self, task_id: str, where: str, head: str) -> None:
        """Голова ссылки — дочерний коммит снимка, локально или в origin."""
        ref = ref_of(task_id)
        tree = self.git("rev-parse", f"{head}^{{tree}}").strip()
        other = self.git("commit-tree", tree, "-p", head, "-m",
                         f"{task_id}: подмена").strip()
        if where == "в origin":
            self.git("push", "-q", self.bare, f"{other}:{ref}")
        else:
            self.git("update-ref", ref, other)


class DocsWithoutMainTest(ThreeDirsSandbox):

    def test_ac7_docs_reads_historical_task_without_tasks_in_main(self):
        """Документ исторической задачи читается `docs_fetch` из её ссылки, когда в `origin/main` каталога задач уже нет.

        Сценарий: песочница AC-1, команда создала исторические ссылки;
        затем из `origin/main` убирают каталог задач целиком. Для каждой
        из двух исторических задач (без строки в `tasks` и со строкой)
        `docs_fetch.cmd_docs([id, файл])` для случайного документа
        печатает его текст байт в байт.

        Ловит мутацию: снимок пишется не под путём каталога задачи в
        дереве ссылки (например, файлы в корне дерева) — `docs` не
        находит файл; ссылка создаётся только в origin без локальной копии
        и без отправки — `docs` не находит ссылку; команда не создаёт
        ссылку задаче без строки в `tasks` — `docs` отказывает.
        """
        self.run_command()
        self.drop_tasks_from_main()
        for task_id in self.new_ids:
            rel = self.rng.choice(sorted(self.docs[task_id]))
            with self.subTest(task=task_id, file=rel, seed=self.seed):
                buf = io.StringIO()
                code = 0
                with contextlib.redirect_stdout(buf), \
                        contextlib.redirect_stderr(io.StringIO()) as err:
                    try:
                        docs_fetch.cmd_docs([task_id, rel])
                    except SystemExit as exc:
                        code = exc.code
                self.assertIn(code, (None, 0), self.note(
                    f"docs {task_id} {rel}: отказ {code}\n{err.getvalue()}"))
                self.assertEqual(buf.getvalue(), self.docs[task_id][rel],
                                 self.note(f"docs {task_id} {rel}"))


if __name__ == "__main__":
    unittest.main()
