"""Команда `artel.py artifact-branches-cleanup [--execute]` — уборка веток
`artifact/**` в `origin` артели и локальных `artifact/*` главной копии
(ADR-0021 п.13, этап 1; решение Оператора 02.10.2026).

Без флага — предпросмотр: перечень веток, ничего не удаляется. С
`--execute` — сверка: у каждой задачи перечня (id из имени ветки) есть
`refs/artifacts/<id>` в `origin`; нехватка — отказ, называющий задачи, и ни
одна ветка не удалена; сверка прошла — удаляются ветки и в `origin`, и
локально, ссылки `refs/artifacts/*` не трогаются. Процессу роли команда
недоступна.

Сценарий на настоящем git: главная копия (`self.root`) с bare-`origin`
(`self.bare`). Ветки — по форме живых: `artifact/<id в нижнем регистре>`,
ссылки — `refs/artifacts/<id>`. Число веток, доля общих для `origin` и
главной копии и задачи без ссылки — из `random`, зерно печатается и входит
в текст провала.

Группа: долгоживущий
Красен до реализации: команды artifact-branches-cleanup в диспетчере artel.py нет («Неизвестная команда») — методы AC-12…AC-14 красные; метод AC-9 (отказ роли закрытым по умолчанию белым списком) держит существующее поведение и зелёный с рождения.
"""
import contextlib
import io
import os
import random
import sys
import unittest
from unittest import mock

from orchestrator import artel, config
from tests.sandbox import AutoOriginSandbox

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
BRANCH_PREFIX = "artifact/"
REF_PREFIX = "refs/artifacts/"


def new_seed() -> int:
    seed = random.SystemRandom().randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed


class CleanupSandbox(AutoOriginSandbox):
    """Главная копия с `origin`; ветки `artifact/*` по обе стороны и ссылки
    документов в `origin`."""

    def setUp(self):
        super().setUp()
        self.seed = new_seed()
        self.rng = random.Random(self.seed)
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.head = self.git("rev-parse", "HEAD").strip()

    def why(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def task_id(self) -> str:
        return "01M" + "".join(self.rng.choice(ULID_ALPHABET) for _ in range(23))

    def seed_branches(self) -> tuple[list, list, list]:
        """(id только в origin, id только локально, id с обеих сторон)."""
        only_origin = [self.task_id() for _ in range(self.rng.randrange(1, 4))]
        only_local = [self.task_id() for _ in range(self.rng.randrange(1, 3))]
        both = [self.task_id() for _ in range(self.rng.randrange(0, 3))]
        for tid in only_origin + both:
            self.git("push", "-q", "origin",
                     f"{self.head}:refs/heads/{BRANCH_PREFIX}{tid.lower()}")
        for tid in only_local + both:
            self.git("branch", f"{BRANCH_PREFIX}{tid.lower()}", self.head)
        return only_origin, only_local, both

    def put_origin_ref(self, tid: str) -> None:
        self.git("push", "-q", "origin", f"{self.head}:{REF_PREFIX}{tid}")

    def put_local_ref(self, tid: str) -> None:
        self.git("update-ref", f"{REF_PREFIX}{tid}", self.head)

    def origin_refs(self, prefix: str) -> dict:
        out = self.git("ls-remote", self.bare, f"{prefix}*")
        refs = {}
        for line in out.splitlines():
            sha, _, ref = line.partition("\t")
            refs[ref.strip()] = sha.strip()
        return refs

    def origin_branches(self) -> set:
        return {r[len("refs/heads/"):] for r in self.origin_refs("refs/heads/")}

    def local_branches(self) -> set:
        out = self.git("for-each-ref", "--format=%(refname:short)", "refs/heads/")
        return {line for line in out.splitlines() if line}

    def local_refs(self) -> dict:
        out = self.git("for-each-ref", "--format=%(refname) %(objectname)",
                       REF_PREFIX)
        return dict(line.split(" ", 1) for line in out.splitlines() if line)

    def run_cli(self, *argv: str, role: str | None = None) -> tuple[int, str]:
        """(код выхода, stdout+stderr+текст SystemExit) вызова `artel.main`."""
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with mock.patch.dict(os.environ), \
                mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            os.environ.pop(config.ARTEL_ROLE_ENV, None)
            if role is not None:
                os.environ[config.ARTEL_ROLE_ENV] = role
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code is None:
                    code = 0
                elif isinstance(exc.code, int):
                    code = exc.code
                else:
                    code = 1
                    err.write(str(exc.code))
        return code, out.getvalue() + err.getvalue()


class CleanupPreviewTest(CleanupSandbox):

    def test_ac12_preview_lists_and_deletes_nothing(self):
        """Предпросмотр перечисляет ветки обеих сторон и ничего не удаляет.

        В `origin` и в главной копии — ветки `artifact/<id>` (часть только с
        одной стороны, часть с обеих), ссылки есть у всех. Команда без
        флага печатает каждую ветку; множества веток в `origin` и локально
        до и после совпадают.

        Ловит мутацию: разбор флага перевёрнут (`"--execute" not in rest`)
        или предпросмотр смотрит только в `origin` — ветки удалены либо
        локальных веток в выводе нет.
        """
        only_origin, only_local, both = self.seed_branches()
        for tid in only_origin + only_local + both:
            self.put_origin_ref(tid)
        origin_before, local_before = self.origin_branches(), self.local_branches()

        code, out = self.run_cli("artifact-branches-cleanup")

        self.assertEqual(code, 0, self.why(f"предпросмотр: код {code}: {out}"))
        for tid in only_origin + only_local + both:
            self.assertIn(f"{BRANCH_PREFIX}{tid.lower()}", out,
                          self.why(f"в перечне нет ветки задачи {tid}"))
        self.assertEqual(self.origin_branches(), origin_before,
                         self.why("предпросмотр изменил ветки origin"))
        self.assertEqual(self.local_branches(), local_before,
                         self.why("предпросмотр изменил локальные ветки"))


class CleanupExecuteTest(CleanupSandbox):

    def test_ac13_execute_refuses_on_missing_origin_ref(self):
        """Задача перечня без ссылки в origin: отказ с её id, ни одна ветка не удалена.

        У части задач (≥1, из `random`, с любой стороны перечня) нет
        `refs/artifacts/<id>` в `origin`; у одной из них ссылка есть только
        локально. `--execute` завершается ненулевым кодом, текст называет
        каждую такую задачу, ветки в `origin` и локально не тронуты.

        Ловит мутацию: сверка смотрит на локальные ссылки вместо `origin`,
        или удаление начинается до сверки / по задачам, прошедшим её, —
        ветки удалены, отказа нет либо он не называет задачу.
        """
        only_origin, only_local, both = self.seed_branches()
        listed = only_origin + only_local + both
        missing = self.rng.sample(listed, self.rng.randrange(1, len(listed) + 1))
        for tid in listed:
            if tid not in missing:
                self.put_origin_ref(tid)
        self.put_local_ref(missing[0])
        origin_before, local_before = self.origin_branches(), self.local_branches()

        code, out = self.run_cli("artifact-branches-cleanup", "--execute")

        self.assertNotEqual(code, 0, self.why(f"отказа нет: {out!r}"))
        for tid in missing:
            self.assertIn(tid.lower(), out.lower(),
                          self.why(f"отказ не называет задачу {tid}"))
        self.assertEqual(self.origin_branches(), origin_before,
                         self.why("при отказе удалены ветки origin"))
        self.assertEqual(self.local_branches(), local_before,
                         self.why("при отказе удалены локальные ветки"))

    def test_ac14_execute_deletes_branches_keeps_refs(self):
        """Сверка прошла: удалены все ветки `artifact/**` с обеих сторон, ссылки целы.

        У каждой задачи перечня есть ссылка в `origin` (у части — и
        локально). `--execute` удаляет все ветки `artifact/*` в `origin` и
        в главной копии; ветка `main` и ссылки `refs/artifacts/*` в
        `origin` и локально — те же, что до команды.

        Ловит мутацию: удаление только в `origin` (или только локально), либо
        удаление по шаблону `refs/artifacts/*` вместо веток — в одной из
        сторон остаются ветки `artifact/*` или пропадают ссылки документов.
        """
        only_origin, only_local, both = self.seed_branches()
        for tid in only_origin + only_local + both:
            self.put_origin_ref(tid)
            if self.rng.random() < 0.5:
                self.put_local_ref(tid)
        refs_origin_before = self.origin_refs(REF_PREFIX)
        refs_local_before = self.local_refs()

        code, out = self.run_cli("artifact-branches-cleanup", "--execute")

        self.assertEqual(code, 0, self.why(f"--execute: код {code}: {out}"))
        left_origin = {b for b in self.origin_branches()
                       if b.startswith(BRANCH_PREFIX)}
        left_local = {b for b in self.local_branches()
                      if b.startswith(BRANCH_PREFIX)}
        self.assertEqual(left_origin, set(), self.why("в origin остались ветки"))
        self.assertEqual(left_local, set(), self.why("локально остались ветки"))
        self.assertIn(config.MAIN_BRANCH, self.origin_branches(),
                      self.why("удалена основная ветка origin"))
        self.assertIn(config.MAIN_BRANCH, self.local_branches(),
                      self.why("удалена основная ветка главной копии"))
        self.assertEqual(self.origin_refs(REF_PREFIX), refs_origin_before,
                         self.why("тронуты ссылки документов в origin"))
        self.assertEqual(self.local_refs(), refs_local_before,
                         self.why("тронуты локальные ссылки документов"))


class CleanupRoleRefusalTest(CleanupSandbox):

    def test_ac9_role_process_refused_cleanup(self):
        """Под окружением роли уборка отказывает диспетчером в обеих формах.

        Ветки и ссылки у всех задач на месте (сверка прошла бы). Под
        маркером `ARTEL_ROLE` и без флага, и с `--execute` команда
        завершается отказом, называющим роль; ветки обеих сторон целы.

        Ловит мутацию: `artifact-branches-cleanup` внесён в белый список
        команд роли (или его форма без флага — в «читающие») — под ролью
        команда исполняется, отказа нет, с `--execute` ветки удалены.
        """
        only_origin, only_local, both = self.seed_branches()
        for tid in only_origin + only_local + both:
            self.put_origin_ref(tid)
        origin_before, local_before = self.origin_branches(), self.local_branches()
        role = f"role_{self.rng.randrange(1 << 30):x}"
        for argv in (("artifact-branches-cleanup",),
                     ("artifact-branches-cleanup", "--execute")):
            code, out = self.run_cli(*argv, role=role)
            self.assertNotEqual(code, 0, self.why(f"{argv}: под ролью код 0"))
            self.assertIn(role, out, self.why(f"{argv}: отказ не называет роль"))
            self.assertIn("artifact-branches-cleanup", out,
                          self.why(f"{argv}: отказ не называет команду"))
        self.assertEqual(self.origin_branches(), origin_before,
                         self.why("под ролью удалены ветки origin"))
        self.assertEqual(self.local_branches(), local_before,
                         self.why("под ролью удалены локальные ветки"))


if __name__ == "__main__":
    unittest.main()
