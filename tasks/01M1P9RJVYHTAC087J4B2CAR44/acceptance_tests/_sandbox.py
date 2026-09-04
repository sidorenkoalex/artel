"""Общая песочница приёмочных тестов 01M1P9RJVYHTAC087J4B2CAR44
(инкрементальный diff ревью после A7: база из кодовой ветки, регрессия №10).

`IncrementalDiffSandbox` расширяет `tests.sandbox.RealGitSandbox`
(`self.root` — реальный git-репозиторий пульта, ветка `main`, один
коммит) реальными коммитами на кодовой ветке задачи и прямой записью
журнала «sha зафиксирован» — тем же форматом `detail`, который несёт
`orchestrator/store.py::record_fixation` (SPEC, требование 1: поле
`код=` — «sha кодовой ветки» — несёт уже сегодня НЕ-default target, для
default заводится/выравнивается этой задачей, тем же именем поля).
Настоящий git обязателен для AC-2/AC-3: заглушкой (FakeGit с заготовкой)
непустой diff МЕЖДУ ДВУМЯ РЕАЛЬНЫМИ коммитами достоверно не изобразить —
предмет проверки как раз и есть «git не находит объект `sha=` в чужом
репозитории», а не текст ответа.

`RecordingGit` — лёгкая заглушка `gitcmd.git` для тестов, которым
реальный git не нужен (AC-4/AC-5: наблюдаемое — АРГУМЕНТЫ вызова
`git diff`/сам текст пакета, не факт непустого diff): помнит вызовы,
отвечает на `show`/`diff`/`rev-parse` заготовками, без файловой системы.
"""
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TASK = "T001"

# Sha «фиксационного/артефактного репозитория target'а» (поле `sha=`
# записи «sha зафиксирован») — синтаксически валидный hex, но заведомо НЕ
# существующий объект НИ В ОДНОМ репозитории песочницы: воспроизводит
# реальный класс сбоя из SPEC («Контекст») — `git diff <base>...<ветка>`
# в репозитории ПУЛЬТА не находит sha из ЧУЖОГО (артефактного) репозитория
# и отвечает «Invalid symmetric difference expression», а не просто
# «редко используемый, но существующий предок».
FOREIGN_FIXATION_SHA = "d" * 40


class IncrementalDiffSandbox(RealGitSandbox):
    """Кодовая ветка задачи с реальными коммитами + журнал фиксации,
    заполненный НАПРЯМУЮ через `store.journal` — в обход `fixation.fix`/
    `store.record_fixation` (эта задача проверяет `review.
    previous_verdict_sha`/`review.review_package`, читающие уже
    СУЩЕСТВУЮЩИЙ журнал, а не саму запись фиксации, требование 3 SPEC)."""

    TASK = TASK

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def write_and_commit(self, rel: str, text: str, message: str) -> str:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("add", rel)
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").strip()

    def fixate(self, target: str, code_sha: str,
              fixation_sha: str = FOREIGN_FIXATION_SHA,
              artifact_sha: str = "e" * 40) -> None:
        """Одна запись «sha зафиксирован» в формате `record_fixation`
        (требование 1: поле `код=` — одинаково для ЛЮБОГО target)."""
        store.journal(
            self.conn, self.TASK, "fsm", "sha зафиксирован",
            f"target={target}, sha={fixation_sha}, чисто=True, "
            f"код={code_sha}, артефакты={artifact_sha}")


class RecordingGit:
    """Подмена `gitcmd.git`: помнит вызовы, отвечает на `diff`/`show`/
    `rev-parse` заготовками — без файловой системы и без реального git.

    `diff_ok`/`stat_ok` — фиксированный «успешный» ответ на ЛЮБОЙ
    запрошенный `base...branch` (тест этого файла не про содержимое
    diff, а про то, КАКОЙ `base` реально ушёл в команду — см. `calls`).
    """

    def __init__(self, diff_ok: str = "diff --git a b",
                 stat_ok: str = "orchestrator/artel.py | 2 +-"):
        self.diff_ok = diff_ok
        self.stat_ok = stat_ok
        self.files: dict[str, str] = {}
        self.calls: list[list[str]] = []

    def __call__(self, *args: str) -> subprocess.CompletedProcess:
        self.calls.append(list(args))
        if args and args[0] == "show":
            _, rel = args[1].split(":", 1)
            if rel not in self.files:
                return subprocess.CompletedProcess(
                    list(args), 128, "",
                    f"fatal: path '{rel}' does not exist in '{args[1]}'")
            return subprocess.CompletedProcess(list(args), 0, self.files[rel], "")
        if args and args[0] == "ls-tree":
            return subprocess.CompletedProcess(list(args), 0, "", "")
        if (len(args) >= 3 and args[0] == "rev-parse" and args[1] == "--verify"
                and args[-1].startswith("refs/heads/")):
            return subprocess.CompletedProcess(list(args), 1, "", "")
        if args and args[0] == "rev-parse":
            return subprocess.CompletedProcess(list(args), 0, "", "")
        if args and args[0] == "diff":
            stdout = self.stat_ok if "--stat" in args else self.diff_ok
            return subprocess.CompletedProcess(list(args), 0, stdout, "")
        return subprocess.CompletedProcess(list(args), 0, "", "")

    def diff_bases(self) -> list[str]:
        """`base` каждого вызова `git diff [--stat] <base>...<branch>` по
        порядку — последний позиционный аргумент до `...`."""
        bases = []
        for call in self.calls:
            if call and call[0] == "diff":
                spec = call[-1]
                if "..." in spec:
                    bases.append(spec.split("...", 1)[0])
        return bases
