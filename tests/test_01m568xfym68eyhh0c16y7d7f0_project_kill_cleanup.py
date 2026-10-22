"""`kill` задачи внешнего проекта убирает её черновой PR и ветку в `origin` проекта.

Группа: долгоживущий

Красен до реализации: уборки в репозитории проекта у `kill` ещё нет — ветка задачи остаётся в `origin` проекта, `gh pr close` не зовётся, заметок «PR …»/«ветка origin …» в журнале уборки нет, текст «перейди на … и повтори kill» называет `config.MAIN_BRANCH`; методы AC-7 и AC-9 (а), (б) держат то, чего уборка делать не должна, и зелёные с рождения.

Сценарий на настоящем git: пульт (`self.root`, он же клон артели) со своим
bare-`origin`; внешний проект — клон по адресу `repo_context.resolve(<проект>)
.path` со своим bare-`origin` (путь на диске либо подставной HTTP-хостинг на
`127.0.0.1` поверх `git http-backend`). Ветка задачи и `refs/artifacts/<id>`
опубликованы в `origin` проекта до `kill`.

Подставной `gh` — исполняемый скрипт в начале `PATH` (`ci.gh` зовёт `gh` по
имени): пишет свой argv и `GH_TOKEN` окружения в общий журнал событий и
отвечает успехом, ошибкой «нет PR» или молчанием. Хук `pre-receive` bare-
`origin` проекта пишет в тот же журнал каждую принятую к разбору запись ссылки
(порядок строк журнала — порядок событий) и по флагу отклоняет удаление веток
задач. Подставной HTTP-хостинг молчит только на пуше удаления ветки задачи:
сверка документов и коммит закрытия `kill` ходят в тот же `origin` и обязаны
получать ответ.

Имя проекта, его база, id задач и значение токена слота — из `random`, зерно
печатается и входит в текст провала.
"""
import gzip
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from orchestrator import cleanup, config, fsm, keychain, repo_context, store
from tests.sandbox import ARTEL_TEST_PROFILE, AutoOriginSandbox, capture

ZERO_OID = "0" * 40
CLEANUP_ACTION = "уборка"
PR_PREFIX = "PR"
BRANCH_PREFIX = "ветка origin"
LEFT = ": оставлено — "
REFUSAL = "отказ: "
SILENT = "не ответил"
PROJECT_NAMES = ("sled", "sani", "drovni", "rozvalni", "kibitka")
OTHER_BASES = ("trunk", "develop", "stable", "osnova")
ID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
# Предел `ci.gh` и пуша удаления на время сценария молчащего хостинга
# (AC-6): одна константа `config.GH_TIMEOUT_SEC` задаёт оба.
SHORT_TIMEOUT_SEC = 2
# Сколько подставной `gh` молчит в режиме «молчание»: дольше предела
# `ci.gh`, но меньше исходного `config.GH_TIMEOUT_SEC` — `gh`, снятый чужим
# пределом, успевает досыпать и записать конец сна.
GH_SILENT_SEC = 2 * SHORT_TIMEOUT_SEC + 15
# Срок молчания хостинга на пуше удаления: заведомо дольше предела пуша и
# меньше таймаута теста (`pyproject.toml`) с запасом на остальной `kill` —
# пуш без предела краснит тест флагом истечения, а не таймаутом pytest.
SILENCE_LIMIT_SEC = 75
# Диапазон случайного предела сценария перехвата.
INTERCEPT_LIMITS = (7, 300)
# Исполняемый git серверной стороны подставного HTTP-хостинга
# (`git http-backend` — это «origin», не вопрос к репозиторию задачи).
GIT_BIN = shutil.which("git") or "git"


def _targets_yaml(external: str, *, forge: str, base: str) -> str:
    entry = ("    forge: {forge}\n    url: file:///nonexistent/{name}\n"
             "    base: {base}\n    token_slot: {name}-token\n"
             "    no_paths: []\n    project_skills: []\n"
             "    merge_gate: operator\n")
    return ("targets:\n"
            f"  {config.DEFAULT_TARGET}:\n"
            + entry.format(forge="github", name=config.DEFAULT_TARGET,
                           base=config.MAIN_BRANCH)
            + ARTEL_TEST_PROFILE
            + f"  {external}:\n"
            + entry.format(forge=forge, name=external, base=base))


FAKE_GH = '''#!{python}
import json, os, sys, time
with open({log!r}, "a", encoding="utf-8") as f:
    f.write(json.dumps({{"kind": "gh", "argv": sys.argv[1:],
                        "token": os.environ.get("GH_TOKEN")}}) + "\\n")
with open({mode!r}, encoding="utf-8") as f:
    mode = f.read().strip()
if mode == "fail":
    sys.stderr.write({fail!r} + "\\n")
    sys.exit(1)
if mode == "silent":
    time.sleep({silent})
    with open({log!r}, "a", encoding="utf-8") as f:
        f.write(json.dumps({{"kind": "gh_slept"}}) + "\\n")
'''

PRE_RECEIVE = '''#!{python}
import json, os, sys
reject = os.path.exists({flag!r})
bad = []
with open({log!r}, "a", encoding="utf-8") as f:
    for line in sys.stdin:
        old, new, ref = line.split()
        f.write(json.dumps({{"kind": "push", "old": old, "new": new,
                            "ref": ref}}) + "\\n")
        if reject and new == "0" * 40 and ref.startswith("refs/heads/task/"):
            bad.append(ref)
if bad:
    sys.stderr.write({text!r} + " ".join(bad) + "\\n")
    sys.exit(1)
'''


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _has_pair(args, flag: str, value: str) -> bool:
    return any(args[i] == flag and args[i + 1] == value
               for i in range(len(args) - 1))


class Silence:
    """Правило молчания подставного HTTP-хостинга: тело POST
    `git-receive-pack`, несущее `pattern`, остаётся без ответа до
    `release` либо `limit` секунд — дальше соединение закрывается.
    `expired` поднят, только когда срок `limit` вышел без `release`: клиент
    ждал ответа весь срок молчания."""

    def __init__(self):
        self.pattern = b""
        self.limit = 0.0
        self.hits = 0
        self.expired = False
        self.release = threading.Event()


class GitHttpHosting(BaseHTTPRequestHandler):
    """CGI-мост к `git http-backend` над каталогом bare-репозиториев
    `server.project_root`; правило молчания — `server.silence`."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.serve()

    def do_POST(self):
        self.serve()

    def read_body(self) -> bytes:
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            parts = []
            while True:
                size = int(self.rfile.readline().split(b";")[0].strip(), 16)
                if size == 0:
                    self.rfile.readline()
                    return b"".join(parts)
                parts.append(self.rfile.read(size))
                self.rfile.readline()
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def serve(self) -> None:
        path, _, query = self.path.partition("?")
        body = self.read_body()
        encoding = self.headers.get("Content-Encoding", "")
        plain = gzip.decompress(body) if encoding == "gzip" and body else body
        silence = self.server.silence
        if (path.endswith("/git-receive-pack") and silence.pattern
                and silence.pattern in plain):
            silence.hits += 1
            if not silence.release.wait(silence.limit):
                silence.expired = True
            return
        env = dict(os.environ, GIT_PROJECT_ROOT=str(self.server.project_root),
                   GIT_HTTP_EXPORT_ALL="1", PATH_INFO=path,
                   QUERY_STRING=query, REQUEST_METHOD=self.command,
                   CONTENT_TYPE=self.headers.get("Content-Type", ""),
                   CONTENT_LENGTH=str(len(body)), REMOTE_ADDR="127.0.0.1")
        if encoding:
            env["HTTP_CONTENT_ENCODING"] = encoding
        if self.headers.get("Git-Protocol"):
            env["GIT_PROTOCOL"] = self.headers["Git-Protocol"]
        res = subprocess.run([GIT_BIN, "http-backend"], input=body, env=env,
                             capture_output=True)
        out = res.stdout
        sep = b"\r\n\r\n" if b"\r\n\r\n" in out else b"\n\n"
        head, _, payload = out.partition(sep)
        status, headers = 200, []
        for line in head.decode("latin-1").splitlines():
            name, _, value = line.partition(":")
            if name.lower() == "status":
                status = int(value.strip().split()[0])
            elif name:
                headers.append((name, value.strip()))
        self.send_response(status)
        for name, value in headers:
            if name.lower() != "content-length":
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class ProjectKillSandbox(AutoOriginSandbox):
    """Пульт с `origin`, внешний проект со своим `origin`, задача проекта
    `self.ext` в `verifying` с веткой `self.branch`, опубликованной в
    `origin` проекта вместе с `refs/artifacts/<id>`.

    `FORGE` — `forge` записи проекта; `OTHER_BASE` — база проекта не
    `config.MAIN_BRANCH`; `HTTP_ORIGIN` — `origin` проекта — подставной
    HTTP-хостинг, а не путь на диске."""

    FORGE = "github"
    OTHER_BASE = False
    HTTP_ORIGIN = False

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.target = (self.rng.choice(PROJECT_NAMES)
                       + str(self.rng.randrange(10, 100)))
        self.base = (self.rng.choice(OTHER_BASES) if self.OTHER_BASE
                     else config.MAIN_BRANCH)
        self.url = f"file:///nonexistent/{self.target}"
        self.slot = f"{self.target}-token"
        self.token = f"tok-{self.rng.randrange(10 ** 12)}"
        config.TARGETS.write_text(
            _targets_yaml(self.target, forge=self.FORGE, base=self.base),
            encoding="utf-8")

        self.fixture = Path(tempfile.mkdtemp(prefix="artel-kill-")).resolve()
        self.addCleanup(shutil.rmtree, self.fixture, ignore_errors=True)
        self.events = self.fixture / "events.jsonl"
        self.events.write_text("", encoding="utf-8")
        self.mark = 0
        self.install_fake_gh()
        self.slot_empty_when_killed = False
        patcher = mock.patch.object(keychain, "token", self.fake_token)
        patcher.start()
        self.addCleanup(patcher.stop)

        ctx = repo_context.resolve(self.target)
        self.assertIsNotNone(ctx, self.why("предусловие: контекст проекта"))
        self.project = Path(ctx.path)
        self.project.mkdir(parents=True, exist_ok=True)
        self.pgit("init", "-q", "-b", self.base)
        self.pgit("config", "user.email", "project@example.invalid")
        self.pgit("config", "user.name", "project tests")
        (self.project / "README.md").write_text("проект\n", encoding="utf-8")
        self.pgit("add", "README.md")
        self.pgit("commit", "-q", "-m", "init")

        hosting = self.fixture / "hosting"
        hosting.mkdir()
        self.project_bare = hosting / "origin.git"
        self.git("init", "-q", "--bare", "-b", self.base, str(self.project_bare))
        self.reject_flag = self.fixture / "reject-delete"
        self.install_hook(self.project_bare)
        if self.HTTP_ORIGIN:
            remote = self.start_http_hosting(hosting)
        else:
            remote = str(self.project_bare)
        self.pgit("remote", "add", "origin", remote)
        self.pgit("push", "-q", "origin", f"{self.base}:{self.base}")

        self.ext, self.branch = self.new_project_task()

    # --- фикстура ---------------------------------------------------------

    def why(self, text: str) -> str:
        return f"{text} (зерно {self.seed}, проект {self.target})"

    def pgit(self, *args: str) -> str:
        return self.git("-C", str(self.project), *args)

    def install_fake_gh(self) -> None:
        bin_dir = self.fixture / "bin"
        bin_dir.mkdir()
        self.gh_mode = self.fixture / "gh-mode"
        self.gh_mode.write_text("ok", encoding="utf-8")
        self.gh_fail_text = (f"no pull requests found for branch "
                             f"(фикстура {self.seed})")
        _write_executable(bin_dir / "gh", FAKE_GH.format(
            python=sys.executable, log=str(self.events),
            mode=str(self.gh_mode), fail=self.gh_fail_text,
            silent=GH_SILENT_SEC))
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")

    def install_hook(self, bare: Path) -> None:
        _write_executable(bare / "hooks" / "pre-receive", PRE_RECEIVE.format(
            python=sys.executable, log=str(self.events),
            flag=str(self.reject_flag),
            text="удаление ветки задачи отклонено хостингом фикстуры: "))

    def start_http_hosting(self, root: Path) -> str:
        self.git("-C", str(self.project_bare), "config", "http.receivepack",
                 "true")
        server = ThreadingHTTPServer(("127.0.0.1", 0), GitHttpHosting)
        server.daemon_threads = True
        server.project_root = root
        server.silence = Silence()
        self.silence = server.silence
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.addCleanup(server.silence.release.set)
        return f"http://127.0.0.1:{server.server_address[1]}/origin.git"

    def fake_token(self, slot: str) -> str:
        """Подмена `keychain.token`: свой токен у слота проекта; слот
        пустеет, когда задача уже `killed`, если так велит сценарий."""
        if self.slot_empty_when_killed and self.state(self.ext) == "killed":
            return ""
        return self.token if slot == self.slot else f"other-{slot}"

    def new_project_task(self, state: str = "in_dev",
                         move_to: str | None = "verifying") -> tuple[str, str]:
        """Задача проекта в `move_to` (по умолчанию `verifying`): ветка с
        собственным коммитом опубликована в `origin` проекта, ссылка
        документов — тоже (её пишет переход)."""
        task_id = "01UNITKILLEXT" + "".join(
            self.rng.choice(ID_ALPHABET) for _ in range(9))
        branch = f"task/{task_id.lower()}-x"
        here = self.pgit("rev-parse", "--abbrev-ref", "HEAD").strip()
        self.pgit("checkout", "-q", "-b", branch, self.base)
        (self.project / f"{task_id}.txt").write_text("работа\n",
                                                     encoding="utf-8")
        self.pgit("add", f"{task_id}.txt")
        self.pgit("commit", "-q", "-m", f"{task_id}: работа")
        self.pgit("checkout", "-q", here)
        self.pgit("push", "-q", "origin", branch)
        store.insert_task(store.db(), task_id, "Задача проекта", state,
                          branch, self.target, 25.0)
        if move_to:
            self.move(task_id, move_to)
        return task_id, branch

    def publish_docs(self, task_id: str, files: dict) -> None:
        """Ссылка документов задачи в клоне проекта и в его `origin` —
        коммит без родителя с файлами `files` (путь внутри каталога
        документов задачи -> текст), как первый коммит документов."""
        src = self.fixture / f"docs-{task_id}"
        for name, text in files.items():
            path = src.joinpath("tasks", task_id, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(src), "init", "-q")
        self.git("-C", str(src), "add", "-A")
        self.git("-C", str(src), "-c", "user.name=t", "-c",
                 "user.email=t@t.invalid", "commit", "-q", "-m",
                 f"{task_id}: документы")
        ref = f"refs/artifacts/{task_id}"
        self.pgit("fetch", "-q", str(src), f"HEAD:{ref}")
        self.pgit("push", "-q", "origin", f"{ref}:{ref}")

    # --- наблюдения -------------------------------------------------------

    def state(self, task_id: str) -> str:
        return store.get_task(store.db(), task_id)["state"]

    def move(self, task_id: str, to: str) -> None:
        frm = self.state(task_id)
        capture(lambda: store.set_state(store.db(), task_id, to, "fsm",
                                        expected_state=frm,
                                        detail="переход теста"))

    def kill(self, task_id: str) -> str:
        """`kill` без перехвата исключений: исключение — провал теста."""
        self.mark = len(self.all_events())
        return capture(cleanup.cmd_kill, task_id)

    def all_events(self) -> list:
        return [json.loads(line) for line in
                self.events.read_text(encoding="utf-8").splitlines() if line]

    def new_events(self) -> list:
        return self.all_events()[self.mark:]

    def gh_calls(self) -> list:
        return [e for e in self.new_events() if e["kind"] == "gh"]

    def pr_closes(self, branch: str) -> list:
        return [e for e in self.gh_calls()
                if e["argv"][:2] == ["pr", "close"] and branch in e["argv"]]

    def deletions(self, branch: str) -> list:
        return [e for e in self.new_events()
                if e["kind"] == "push" and e["new"] == ZERO_OID
                and e["ref"] == f"refs/heads/{branch}"]

    def origin_has(self, ref: str) -> bool:
        return bool(self.git("--git-dir", str(self.project_bare),
                             "for-each-ref", ref).strip())

    def clone_has(self, ref: str) -> bool:
        return bool(self.pgit("for-each-ref", ref).strip())

    def cleanup_notes(self, task_id: str) -> list:
        notes = []
        for row in store.task_steps(store.db(), task_id):
            if row["action"] == CLEANUP_ACTION:
                notes += (row["detail"] or "").split("; ")
        return notes

    def journal_text(self, task_id: str) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in store.task_steps(store.db(), task_id))

    def left_reason(self, task_id: str, prefix: str) -> str:
        """Причина заметки «<prefix> <…>: оставлено — <причина>» журнала
        уборки задачи; провал — заметки нет."""
        for note in self.cleanup_notes(task_id):
            if note.startswith(prefix + " ") and LEFT in note:
                return note.split(LEFT, 1)[1]
        self.fail(self.why(f"нет заметки «{prefix} …{LEFT}…» в журнале "
                           f"уборки:\n{self.journal_text(task_id)}"))


class ProjectBranchAndPrTest(ProjectKillSandbox):

    def test_ac1_kill_removes_task_branch_in_origin_keeps_docs_ref(self):
        """`kill` задачи проекта из `verifying`: ветки задачи в `origin` нет, ссылка документов цела в клоне и в `origin`.

        Сценарий: до `kill` ветка задачи и `refs/artifacts/<id>` есть в
        bare-`origin` проекта (проверяется); после `kill` задача в
        `killed`, `refs/heads/<ветка>` в `origin` нет, `refs/artifacts/<id>`
        есть и в клоне проекта, и в `origin`.

        Ловит мутацию: пуш удаления не делается (уборка ограничена
        локальной веткой клона, как до задачи) — ветка задачи остаётся в
        `origin`; либо уборка удаляет вместе с веткой и ссылку документов
        задачи (`push --delete` по шаблону с id задачи) — ссылки в `origin`
        нет.
        """
        docs = f"refs/artifacts/{self.ext}"
        head = f"refs/heads/{self.branch}"
        self.assertTrue(self.origin_has(head), self.why("предусловие: ветка в origin"))
        self.assertTrue(self.origin_has(docs), self.why("предусловие: ссылка в origin"))

        out = self.kill(self.ext)

        self.assertEqual(self.state(self.ext), "killed", self.why(out))
        self.assertFalse(self.origin_has(head), self.why(
            f"ветка задачи осталась в origin проекта:\n{out}\n"
            f"{self.journal_text(self.ext)}"))
        self.assertTrue(self.clone_has(docs), self.why("ссылки документов нет в клоне"))
        self.assertTrue(self.origin_has(docs), self.why("ссылки документов нет в origin"))

    def test_ac2_pr_close_with_repo_comment_token_before_branch_delete(self):
        """`kill` задачи проекта на GitHub зовёт `gh pr close` ветки с `--repo`, комментарием и токеном слота — раньше пуша удаления.

        Сценарий: подставной `gh` отвечает успехом. После `kill` в журнале
        событий есть вызов `gh pr close` с веткой задачи, `--repo <url
        записи проекта>`, аргументом с текстом «задача ликвидирована в
        пульте: <id>» и `GH_TOKEN`, равным токену слота `token_slot`
        записи; строка этого вызова стоит раньше строки пуша удаления
        ветки задачи в `origin`.

        Ловит мутацию: порядок операций обратный (сначала пуш удаления,
        потом `gh pr close`) — строка удаления в журнале раньше; либо `gh`
        зовётся без `repo=` (`--repo` нет, токен слота не выставлен) — у
        вызова нет `--repo <url>` и `GH_TOKEN`; либо комментарий не
        передан.
        """
        out = self.kill(self.ext)

        closes = self.pr_closes(self.branch)
        self.assertTrue(closes, self.why(
            f"gh pr close ветки не вызван: {self.gh_calls()}\n{out}"))
        call = closes[0]
        argv = call["argv"]
        self.assertIn("--repo", argv, self.why(f"нет --repo: {argv}"))
        self.assertEqual(argv[argv.index("--repo") + 1], self.url,
                         self.why(f"--repo не url записи: {argv}"))
        comment = f"задача ликвидирована в пульте: {self.ext}"
        self.assertTrue(any(comment in arg for arg in argv),
                        self.why(f"нет комментария «{comment}»: {argv}"))
        self.assertEqual(call["token"], self.token,
                         self.why("GH_TOKEN — не токен слота проекта"))

        events = self.new_events()
        deletions = self.deletions(self.branch)
        self.assertTrue(deletions, self.why(f"пуша удаления нет: {events}"))
        self.assertLess(events.index(call), events.index(deletions[0]),
                        self.why(f"gh pr close не раньше пуша удаления: {events}"))


class CleanupFailuresTest(ProjectKillSandbox):

    def test_ac3_gh_refusal_noted_branch_still_deleted(self):
        """`gh` отвечает ошибкой «нет PR»: заметка «PR …: оставлено — отказ: <текст>», ветка в `origin` всё равно удалена.

        Сценарий: подставной `gh` выходит с кодом 1 и текстом «no pull
        requests found …». После `kill` без исключения задача в `killed`;
        в журнале уборки есть заметка по PR с причиной «отказ: …»,
        несущей текст ошибки `gh`, без слов «не ответил»; ветки задачи в
        `origin` нет.

        Ловит мутацию: сбой закрытия PR обрывает уборку (удаление ветки
        не пробуется) — ветка остаётся в `origin`; либо любой сбой `gh`
        пишется как «не ответил» — причина несёт эти слова; либо текст
        ошибки `gh` в заметку не попадает.
        """
        self.gh_mode.write_text("fail", encoding="utf-8")

        out = self.kill(self.ext)

        self.assertEqual(self.state(self.ext), "killed", self.why(out))
        reason = self.left_reason(self.ext, PR_PREFIX)
        self.assertTrue(reason.startswith(REFUSAL), self.why(f"причина: {reason}"))
        self.assertIn("no pull requests found", reason, self.why(f"причина: {reason}"))
        self.assertNotIn(SILENT, reason, self.why(f"причина: {reason}"))
        self.assertFalse(self.origin_has(f"refs/heads/{self.branch}"), self.why(
            f"ветка задачи осталась в origin:\n{self.journal_text(self.ext)}"))

    def test_ac4_branch_delete_refused_noted(self):
        """`origin` отклоняет удаление ветки: заметка «ветка origin …: оставлено — отказ: <текст>» без «не ответил».

        Сценарий: хук `pre-receive` bare-`origin` проекта отклоняет
        удаление веток задач. После `kill` без исключения задача в
        `killed`; в журнале уборки есть заметка по ветке origin с
        непустой причиной «отказ: …» без слов «не ответил».

        Ловит мутацию: код возврата пуша удаления не проверяется — заметки
        «оставлено» нет; либо отказ пуша пишется как «не ответил»; либо
        отказ поднимает исключение из `kill`.
        """
        self.reject_flag.write_text("1", encoding="utf-8")

        out = self.kill(self.ext)

        self.assertEqual(self.state(self.ext), "killed", self.why(out))
        reason = self.left_reason(self.ext, BRANCH_PREFIX)
        self.assertTrue(reason.startswith(REFUSAL), self.why(f"причина: {reason}"))
        self.assertTrue(reason[len(REFUSAL):].strip(),
                        self.why(f"текст отказа пуст: {reason}"))
        self.assertNotIn(SILENT, reason, self.why(f"причина: {reason}"))
        self.assertTrue(self.origin_has(f"refs/heads/{self.branch}"),
                        self.why("предпосылка сценария: origin не удалил ветку"))

    def test_ac5_empty_token_slot_launches_nothing_notes_both(self):
        """Слот токена проекта пуст на уборке: ни `gh`, ни пуш к хостингу не запускаются, обе заметки «оставлено».

        Сценарий: связка ключей отдаёт пустой слот проекта, как только
        задача в `killed` (сверка документов до перехода идёт с токеном —
        иначе `kill` отказал бы раньше уборки). После `kill` без
        исключения задача в `killed`; подставной `gh` не запускался ни
        разу, хук `origin` не видел удаления ветки задачи, ветка в
        `origin` есть; в журнале уборки есть заметки «PR …: оставлено —
        …» и «ветка origin …: оставлено — …».

        Ловит мутацию: `gh` зовётся без `repo=` (мимо механизма токена
        проекта) — подставной `gh` запускается; либо пуш удаления идёт
        мимо `gitcmd` (сырой `subprocess`, без отказа по слоту) — ветка
        удалена; либо отказ механизма токена не записан заметкой.
        """
        self.slot_empty_when_killed = True

        out = self.kill(self.ext)

        self.assertEqual(self.state(self.ext), "killed", self.why(out))
        self.assertEqual(self.gh_calls(), [], self.why("gh запущен при пустом слоте"))
        self.assertEqual(self.deletions(self.branch), [],
                         self.why("пуш удаления дошёл до origin при пустом слоте"))
        self.assertTrue(self.origin_has(f"refs/heads/{self.branch}"),
                        self.why("ветка удалена при пустом слоте"))
        self.left_reason(self.ext, PR_PREFIX)
        self.left_reason(self.ext, BRANCH_PREFIX)


class SilentHostingTest(ProjectKillSandbox):

    HTTP_ORIGIN = True

    def test_ac6_silent_gh_and_origin_bounded_and_noted(self):
        """Молчащие `gh` и `origin`: пуш удаления и `gh pr close` обрывает их предел раньше срока молчания хостинга (флаг истечения не поднят), ровно по одному вызову, обе заметки — «не ответил».

        Сценарий: `config.GH_TIMEOUT_SEC` уменьшен до 2 с; подставной `gh`
        молчит 2 × 2 + 15 с и после сна пишет в журнал событие конца сна;
        подставной HTTP-хостинг `origin` принимает соединение и не отвечает
        на пуш удаления ветки задачи 75 с (прочие запросы обслуживает).
        После `kill` задача в `killed`, хостинг получил ровно один пуш
        удаления (`silence.hits`), флаг истечения молчания хостинга не
        поднят — пуш оборвал сам клиент; `gh pr close` запущен ровно один
        раз, события конца сна `gh` нет — его снял предел; в журнале уборки
        заметки «PR …: оставлено — … не ответил…» и «ветка origin …:
        оставлено — … не ответил…».

        Ловит мутацию: пуш удаления без `-c http.lowSpeedLimit=1 -c
        http.lowSpeedTime=<GH_TIMEOUT_SEC>` — пуш ждёт, пока хостинг сам не
        закроет соединение, и флаг истечения молчания поднят; либо предел
        пуша или `gh` зашит числом, а не прочитан из `config.GH_TIMEOUT_SEC`
        в момент вызова — сценарий перехвата
        (`test_ac6_limit_arguments_follow_gh_timeout`) видит в аргументах
        чужое значение, а подставной `gh`, снятый чужим пределом, досыпает
        и пишет конец сна; либо срабатывание предела пишется как «отказ»,
        без «не ответил»; либо уборка повторяет пуш или `gh pr close` —
        счёт вызовов не равен одному.
        """
        self.gh_mode.write_text("silent", encoding="utf-8")
        self.silence.pattern = (f" {ZERO_OID} refs/heads/{self.branch}"
                                .encode())
        self.silence.limit = SILENCE_LIMIT_SEC

        with mock.patch.object(config, "GH_TIMEOUT_SEC", SHORT_TIMEOUT_SEC):
            out = self.kill(self.ext)

        self.assertEqual(self.state(self.ext), "killed", self.why(out))
        self.assertGreaterEqual(self.silence.hits, 1,
                                self.why("пуш удаления до хостинга не дошёл"))
        self.assertFalse(self.silence.expired, self.why(
            "хостинг домолчал весь срок: пуш удаления ждал ответа без предела"))
        self.assertEqual(self.silence.hits, 1, self.why("пуш удаления не один"))
        self.assertEqual(len(self.pr_closes(self.branch)), 1,
                         self.why(f"запуски gh pr close: {self.gh_calls()}"))
        self.assertEqual([e for e in self.new_events() if e["kind"] == "gh_slept"],
                         [], self.why("gh досыпал: предел gh не сработал"))
        self.assertIn(SILENT, self.left_reason(self.ext, PR_PREFIX))
        self.assertIn(SILENT, self.left_reason(self.ext, BRANCH_PREFIX))

    def test_ac6_limit_arguments_follow_gh_timeout(self):
        """Предел пуша удаления, `gh pr close` и текст заметок «не ответил за N с» берут значение `config.GH_TIMEOUT_SEC` в момент вызова.

        Сценарий: `config.GH_TIMEOUT_SEC` подменён случайным значением из
        7…300, отличным от исходного; `subprocess.run` перехвачен без
        настоящего ожидания: запуск `gh` поднимает `TimeoutExpired`, пуш
        удаления ветки задачи отвечает молчанием curl («Operation too
        slow»), прочие вызовы идут настоящими. Задача в `killed`; пуш
        удаления один и несёт пары `-c http.lowSpeedLimit=1` и
        `-c http.lowSpeedTime=<значение>`; `gh pr close` вызван один раз с
        `timeout=<значение>`; обе заметки несут «не ответил за <значение> с».

        Ловит мутацию: пуш удаления без пар `-c`; предел пуша, `gh` или
        текста заметки зашит числом вместо `config.GH_TIMEOUT_SEC` — в
        аргументах или тексте исходное значение, а не подменённое.
        """
        low, high = INTERCEPT_LIMITS
        value = self.rng.randrange(low, high + 1)
        while value == config.GH_TIMEOUT_SEC:
            value = self.rng.randrange(low, high + 1)
        real_run = subprocess.run
        pushes, gh_runs = [], []

        def spy(argv, *args, **kwargs):
            if argv[:1] == ["gh"]:
                gh_runs.append((list(argv), kwargs.get("timeout")))
                raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))
            if argv[:1] == ["git"] and "push" in argv and "--delete" in argv \
                    and self.branch in argv:
                pushes.append(list(argv))
                return subprocess.CompletedProcess(argv, 128, "", (
                    f"error: RPC failed; curl 28 Operation too slow. Less than "
                    f"1 bytes/sec transferred the last {value} seconds\n"))
            return real_run(argv, *args, **kwargs)

        with mock.patch.object(config, "GH_TIMEOUT_SEC", value), \
                mock.patch.object(subprocess, "run", spy):
            out = self.kill(self.ext)

        self.assertEqual(self.state(self.ext), "killed", self.why(out))
        self.assertEqual(len(pushes), 1, self.why(f"пуши удаления: {pushes}"))
        self.assertTrue(_has_pair(pushes[0], "-c", "http.lowSpeedLimit=1"),
                        self.why(f"пуш удаления: {pushes[0]}"))
        self.assertTrue(_has_pair(pushes[0], "-c", f"http.lowSpeedTime={value}"),
                        self.why(f"пуш удаления: {pushes[0]}"))
        closes = [timeout for argv, timeout in gh_runs if argv[1:3] == ["pr", "close"]]
        self.assertEqual(closes, [value], self.why(f"запуски gh: {gh_runs}"))
        self.assertIn(f"{SILENT} за {value} с", self.left_reason(self.ext, PR_PREFIX))
        self.assertIn(f"{SILENT} за {value} с",
                      self.left_reason(self.ext, BRANCH_PREFIX))


class ArtelKillUnchangedTest(ProjectKillSandbox):

    def test_ac7_artel_kill_no_pr_close_no_branch_delete_in_origin(self):
        """`kill` задачи артели не зовёт `gh pr close` и не пушит удаление её ветки в `origin` пульта.

        Сценарий: задача артели в `verifying`, её ветка опубликована в
        bare-`origin` пульта с тем же хуком журнала. После `kill` задача
        в `killed`, вызовов `gh pr close` нет, хук `origin` пульта не видел
        удаления ветки, ветка в `origin` пульта есть.

        Ловит мутацию: уборка в репозитории проекта зовётся для любой
        задачи (нет проверки, что target — не артель) — `gh pr close` в
        журнале и ветка артели удалена из `origin` пульта.
        """
        self.install_hook(Path(self.bare))
        art = "01UNITKILLART" + "".join(
            self.rng.choice(ID_ALPHABET) for _ in range(9))
        branch = f"task/{art.lower()}-x"
        self.git("branch", branch, config.MAIN_BRANCH)
        self.git("push", "-q", "origin", branch)
        store.insert_task(store.db(), art, "Задача артели", "in_dev",
                          branch, config.DEFAULT_TARGET, 25.0)
        self.move(art, "verifying")

        self.mark = len(self.all_events())
        out = capture(cleanup.cmd_kill, art)

        self.assertEqual(self.state(art), "killed", self.why(out))
        closes = [e for e in self.gh_calls() if e["argv"][:2] == ["pr", "close"]]
        self.assertEqual(closes, [], self.why("gh pr close при kill артели"))
        self.assertEqual(self.deletions(branch), [],
                         self.why("пуш удаления ветки артели"))
        self.assertTrue(self.git("--git-dir", str(self.bare), "for-each-ref",
                                 f"refs/heads/{branch}").strip(),
                        self.why("ветка артели удалена из origin пульта"))


class OtherBaseTest(ProjectKillSandbox):

    OTHER_BASE = True

    def test_ac8_checked_out_branch_names_project_base_still_cleans_remote(self):
        """База проекта не `main`, ветка задачи checked out в клоне: текст называет базу проекта, PR закрыт, ветки в `origin` нет.

        Сценарий: запись проекта с базой из `random` (`trunk`, `develop`,
        …), ветка задачи зачекаучена в клоне проекта. После `kill` текст
        уборки (вывод и журнал) несёт «перейди на <база проекта> и повтори
        kill», а не «перейди на main…»; подставной `gh` получил `pr close`
        ветки задачи; ветки задачи в `origin` нет.

        Ловит мутацию: текст по-прежнему называет `config.MAIN_BRANCH` —
        в выводе «перейди на main»; либо уборка в репозитории проекта
        зовётся только при удачной локальной уборке — `gh pr close` нет,
        ветка в `origin` осталась.
        """
        self.pgit("checkout", "-q", self.branch)

        out = self.kill(self.ext)
        text = out + "\n" + self.journal_text(self.ext)

        self.assertEqual(self.state(self.ext), "killed", self.why(out))
        self.assertIn(f"перейди на {self.base} и повтори kill", text, self.why(text))
        self.assertNotIn(f"перейди на {config.MAIN_BRANCH} и повтори kill", text,
                         self.why(text))
        self.assertTrue(self.pr_closes(self.branch),
                        self.why(f"gh pr close не вызван: {self.gh_calls()}"))
        self.assertFalse(self.origin_has(f"refs/heads/{self.branch}"),
                         self.why(f"ветка осталась в origin:\n{text}"))


class RepeatedKillTest(ProjectKillSandbox):

    def test_ac9_repeated_kill_of_done_and_killed_touches_nothing_remote(self):
        """Повторный `kill` задачи проекта в `done` и в `killed` не зовёт `gh pr close` и не пушит удаление ветки.

        Сценарий: две задачи проекта с опубликованными ветками переведены
        в `done` и в `killed` переходом, не `kill`. `kill` каждой: вызовов
        `gh pr close` её ветки нет, хук `origin` не видел удаления, ветка
        в `origin` есть, состояние прежнее.

        Ловит мутацию: уборка в репозитории проекта зовётся безусловно
        после `cleanup_killed_task` (а не только при выигранном переходе
        в `killed`) — `gh pr close` в журнале и ветка удалена из `origin`.
        """
        for terminal in ("done", "killed"):
            with self.subTest(state=terminal):
                task_id, branch = self.new_project_task()
                self.move(task_id, terminal)

                out = self.kill(task_id)

                self.assertEqual(self.state(task_id), terminal, self.why(out))
                self.assertEqual(self.pr_closes(branch), [],
                                 self.why(f"gh pr close в {terminal}"))
                self.assertEqual(self.deletions(branch), [],
                                 self.why(f"пуш удаления в {terminal}"))
                self.assertTrue(self.origin_has(f"refs/heads/{branch}"),
                                self.why(f"ветка удалена в {terminal}"))


DIVISION_ZONE = "src/division_zone.py"

DIVISION_SPEC = """---
task: {task_id}
type: spec
author_role: analyst
status: ready
schema_version: 1
budget_usd: 15
zones: {zone}
---

# SPEC: Родитель, поделённый на гейте SPEC

## Контекст
Фикстура деления внешней задачи — короткий безобидный текст.

## Требования
1. Первое требование фикстуры.

## Критерии приёмки
AC-1. Первый критерий фикстуры.

## Деление

### Первая часть фикстуры

Зоны: {zone}
Порядок: первая, без зависимостей

Текст ТЗ первой части.

### Вторая часть фикстуры

Зоны: {zone}
Порядок: после части 1

Текст ТЗ второй части.

## Не входит
- Всё остальное.
"""


class DivisionTest(ProjectKillSandbox):

    def test_ac9_division_on_spec_gate_touches_nothing_remote(self):
        """`approve` деления задачи проекта на гейте SPEC убирает родителя без `gh pr close` и без пуша удаления ветки.

        Сценарий: задача проекта с опубликованной веткой и SPEC с разделом
        «## Деление» в ссылке документов доведена `advance` до гейта SPEC;
        `approve` зафиксированного sha делит её — родитель в `killed`,
        его уборка записана в журнал. Вызовов `gh pr close` ветки
        родителя нет, хук `origin` не видел удаления, ветка родителя в
        `origin` есть.

        Ловит мутацию: уборка в репозитории проекта вызвана из
        `cleanup_killed_task` (общего для `kill` и деления) — `gh pr close`
        ветки родителя в журнале и ветка удалена из `origin`.
        """
        parent, branch = self.new_project_task(state="spec_writing",
                                               move_to=None)
        self.publish_docs(parent, {"SPEC.md": DIVISION_SPEC.format(
            task_id=parent, zone=DIVISION_ZONE)})
        out = capture(fsm.cmd_advance, parent)
        sha = store.get_task(store.db(), parent)["fixed_sha"]
        self.assertEqual(self.state(parent), "spec_gate",
                         self.why(f"предусловие: гейт SPEC\n{out}"))

        self.mark = len(self.all_events())
        out = capture(fsm.cmd_approve, parent, sha)

        self.assertEqual(self.state(parent), "killed", self.why(
            f"деление не прошло:\n{out}\n{self.journal_text(parent)}"))
        self.assertTrue(self.cleanup_notes(parent),
                        self.why("уборки родителя нет в журнале"))
        self.assertEqual(self.pr_closes(branch), [],
                         self.why("gh pr close при делении"))
        self.assertEqual(self.deletions(branch), [],
                         self.why("пуш удаления ветки родителя при делении"))
        self.assertTrue(self.origin_has(f"refs/heads/{branch}"),
                        self.why("ветка родителя удалена из origin при делении"))


class NotGithubTest(ProjectKillSandbox):

    FORGE = "gitlab"

    def test_ac9_not_github_no_gh_branch_still_deleted(self):
        """Проект не на GitHub: `gh` при `kill` не вызывается, ветка задачи в `origin` удалена.

        Сценарий: запись проекта с `forge: gitlab`. После `kill` задача в
        `killed`, подставной `gh` не запускался ни разу, ветки задачи в
        `origin` проекта нет.

        Ловит мутацию: проверки `forge` нет — `gh pr close` зовётся и для
        проекта не на GitHub; либо удаление ветки привязано к `forge:
        github` — ветка осталась в `origin`.
        """
        out = self.kill(self.ext)

        self.assertEqual(self.state(self.ext), "killed", self.why(out))
        self.assertEqual(self.gh_calls(), [], self.why("gh вызван для gitlab"))
        self.assertFalse(self.origin_has(f"refs/heads/{self.branch}"), self.why(
            f"ветка осталась в origin:\n{self.journal_text(self.ext)}"))


if __name__ == "__main__":
    unittest.main()
