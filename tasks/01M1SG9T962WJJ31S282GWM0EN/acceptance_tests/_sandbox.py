"""Общие real-git песочницы планки 01M1SG9T962WJJ31S282GWM0EN.

Обе песочницы строят на `tests.sandbox.RealGitSandbox` (настоящий git,
не заглушка `gitcmd.git`) — сама суть задачи (merge-base с
`refs/remotes/origin/<MAIN_BRANCH>` вместо локального `config.
MAIN_BRANCH`) требует настоящей git-истории с реальными точками
расхождения, заглушкой это не изобразить (тот же довод, что уже
приведён в докстринге `RealGitSandbox`).

`MergeBaseFixture` (AC-1, AC-7, AC-8): локальный `main` стоит на
`commit0`; параллельная ветка «уходит вперёд», как это делает
`origin/main` между локальными `git fetch` (файл вне зон); ветка
задачи создана от `commit0` и мержит эту параллельную ветку — точно
сценарий SPEC AC-7/AC-8: «origin/main ушёл вперёд локального main на
файл вне зон, ветка задачи влила origin/main». `CREATE_ORIGIN_REF`
(класс-атрибут подкласса) решает, регистрируется ли эта параллельная
история под `refs/remotes/origin/<MAIN_BRANCH>` (AC-7, ref есть) или
остаётся неименованным коммитом без ref вовсе (AC-8, репозиторий без
remote) — сама точка расхождения (`commit0`) и то, что унёс мерж,
одинаковы в обоих случаях, различается только видимость ref.

`JournalSourceFixture` (AC-6): более простой сценарий, где
`refs/remotes/origin/<MAIN_BRANCH>` (если создан) указывает НА ТОТ ЖЕ
коммит, что и локальный `main`, — sha базы сравнения в обоих случаях
совпадает, различается только заявленный источник в журнале
(«origin/main» или локальный «main»), что и проверяет AC-6.
"""
from pathlib import Path

from orchestrator import config, store
from tests.sandbox import RealGitSandbox

# Размер файла «вне зон», который в диффе снимка обязан провалить потолок
# `config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES` (262 144 байт) — тот же приём,
# что уже несут существующие `tests/test_capacity_gate.py` (`"x" * 300_000`):
# если база сравнения ошибочно включает этот файл, гейт ёмкости обязан
# отказать; если база его исключает — обязан пропустить.
OVERSIZED_FILE_BYTES = 300_000


class MergeBaseFixture(RealGitSandbox):
    """Ветка задачи, влившая «origin/main», локальный main — позади.

    `CREATE_ORIGIN_REF` — переопределяется подклассом: `True` — сценарий
    AC-7 (`refs/remotes/origin/<MAIN_BRANCH>` есть), `False` — AC-8 (ref
    отсутствует, фолбэк на локальный `config.MAIN_BRANCH`).
    """

    TASK_ID = "T001"
    BRANCH = "task/t001-x"
    IN_ZONE_REL = "orchestrator/widget.py"
    OUT_OF_ZONE_REL = "docs/roadmap.md"
    CREATE_ORIGIN_REF = True

    def setUp(self):
        super().setUp()  # main: один коммит (marker.txt) — это commit0
        self.local_main_sha = self.git("rev-parse", config.MAIN_BRANCH).strip()

        # Параллельная история — то, что «уйдёт вперёд» под именем
        # origin/main: отдельная ветка от commit0, свой коммит с файлом вне
        # заявленных зон задачи.
        self.checkout("origin-advance", create=True)
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        (self.root / self.OUT_OF_ZONE_REL).write_text(
            "x" * OVERSIZED_FILE_BYTES, encoding="utf-8")
        # `add <путь>`, не `-A`: `RealGitSandbox.setUp` уже создал
        # `.artel/state.db` (`store.create_schema`) на диске ДО этого
        # коммита — `-A` подобрал бы его как «свою правку» задачи и
        # ложно раздул бы дифф чужими файлами состояния теста.
        self.git("add", self.OUT_OF_ZONE_REL)
        self.git("commit", "-q", "-m", "origin: правка вне зон задачи")
        self.origin_sha = self.git("rev-parse", "HEAD").strip()

        # Назад на локальный main (остаётся на commit0 — «пин», который
        # НЕ подтянул эту правку) и убрать временную ветку: коммит остаётся
        # объектом в БД git, адресуемым по sha, вне зависимости от того,
        # заведён ли на него `refs/remotes/origin/<MAIN_BRANCH>` ниже.
        self.checkout(config.MAIN_BRANCH)
        self.git("branch", "-D", "origin-advance")
        if self.CREATE_ORIGIN_REF:
            self.git("update-ref",
                     f"refs/remotes/origin/{config.MAIN_BRANCH}", self.origin_sha)

        # Ветка задачи: от того же commit0, добавляет СВОЙ файл (в зоне) и
        # мержит origin (как это делает механика подтяжки перед verifying).
        self.checkout(self.BRANCH, create=True)
        (self.root / "orchestrator").mkdir(parents=True, exist_ok=True)
        (self.root / self.IN_ZONE_REL).write_text(
            "class Widget:\n    pass\n", encoding="utf-8")
        self.git("add", self.IN_ZONE_REL)
        self.git("commit", "-q", "-m", "задача: своя правка в зоне")
        self.git("merge", "-q", "--no-ff", "-m", "merge origin/main",
                 self.origin_sha)

        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK_ID, "Тест merge-base",
                          "in_dev", self.BRANCH, config.DEFAULT_TARGET, 10.0)
        self.t = {"title": "Тест merge-base", "branch": self.BRANCH,
                 "zones": self.IN_ZONE_REL, "zones_extension": None}

    def journal_details(self) -> list:
        return [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK_ID,))]


class JournalSourceFixture(RealGitSandbox):
    """AC-6: sha базы одинаков что с ref origin, что без него (оба указывают
    на commit0) — единственное, что меняется между подклассами, это
    заявленный в журнале источник."""

    TASK_ID = "T001"
    BRANCH = "task/t001-x"
    OUT_OF_ZONE_REL = "docs/out_of_zone.md"
    CREATE_ORIGIN_REF = True

    def setUp(self):
        super().setUp()
        self.local_main_sha = self.git("rev-parse", config.MAIN_BRANCH).strip()
        if self.CREATE_ORIGIN_REF:
            self.git("update-ref", f"refs/remotes/origin/{config.MAIN_BRANCH}",
                     self.local_main_sha)

        self.checkout(self.BRANCH, create=True)
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        (self.root / self.OUT_OF_ZONE_REL).write_text(
            "x" * OVERSIZED_FILE_BYTES, encoding="utf-8")
        # `add <путь>`, не `-A` — тот же довод, что в `MergeBaseFixture`
        # выше: `.artel/state.db` уже на диске к этому моменту.
        self.git("add", self.OUT_OF_ZONE_REL)
        self.git("commit", "-q", "-m", "правка вне заявленных зон")

        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK_ID, "Тест журнала",
                          "in_dev", self.BRANCH, config.DEFAULT_TARGET, 10.0)
        self.t = {"title": "Тест журнала", "branch": self.BRANCH,
                 "zones": "orchestrator/only.py", "zones_extension": None}

    def journal_details(self) -> list:
        return [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK_ID,))]
