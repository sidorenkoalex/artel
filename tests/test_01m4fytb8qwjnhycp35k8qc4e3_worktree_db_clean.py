"""Команда `worktree-db-clean` и сигнал `doctor` о файлах БД пульта в рабочей копии.

Группа: долгоживущий
Красен до реализации: команды `worktree-db-clean` в таблице `artel.py` нет (вызов падает на неизвестной команде), и ни одна проверка `doctor.all_checks` не смотрит в рабочие копии задач на `.artel/state.db*`.

Рабочая копия задачи — каталог `workspace.path(<id>)` в области проекта
(`.artel/projects/<проект>/worktrees/<id>/`) песочницы `TmpRootTest`;
команда зовётся публичным входом `artel.main` с подменённым `sys.argv`.
"""

import contextlib
import io
import os
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artel, config, doctor, store, workspace
from tests.sandbox import TmpRootTest

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
DB_FILES = (".artel/state.db", ".artel/state.db-wal", ".artel/state.db-shm",
            ".artel/state.db-journal")
ROLE_REFUSAL = "команда недоступна процессу роли"


class WorktreeDbSandbox(TmpRootTest):
    """БД пульта со схемой, задача артели и её рабочая копия на диске."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2**32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        store.create_schema(store.db())
        self.conn = store.db()
        self.task = "01M" + "".join(self.rng.choice(ALPHABET)
                                    for _ in range(23))
        store.insert_task(self.conn, self.task, "Задача", "in_dev",
                          f"task/{self.task.lower()}-x",
                          config.DEFAULT_TARGET, 25.0)
        self.wt = workspace.path(self.task)
        self.wt.mkdir(parents=True)
        (self.wt / "marker.txt").write_text("код задачи\n", encoding="utf-8")

    def note(self, text: str) -> str:
        return f"{text}\nзерно: {self.seed}"

    def put_db_files(self, rels) -> dict:
        """Файлы БД пульта в рабочей копии; содержимое у каждого своё."""
        placed = {}
        for rel in rels:
            path = self.wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            data = (f"{rel}:{self.seed}:".encode()
                    + self.rng.randbytes(self.rng.randrange(1, 5000)))
            path.write_bytes(data)
            placed[rel] = data
        return placed

    def logs_snapshot(self) -> dict:
        logs = Path(config.LOGS)
        if not logs.is_dir():
            return {}
        return {p: p.read_bytes() for p in logs.rglob("*") if p.is_file()}

    def clean(self, env: dict | None = None) -> tuple:
        """(код выхода, вывод) `artel.py worktree-db-clean <id>`; код `None`
        либо 0 — успех."""
        env = {config.ARTEL_ROLE_ENV: "", **(env or {})}
        buf = io.StringIO()
        code = None
        with mock.patch.object(sys, "argv", ["artel.py", "worktree-db-clean",
                                             self.task]), \
                mock.patch.dict(os.environ, env), \
                contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(buf):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
                if code not in (None, 0):
                    buf.write(f"\n{code}")
        return code, buf.getvalue()


class WorktreeDbCleanTest(WorktreeDbSandbox):

    def test_ac8_clean_moves_db_files_to_logs_unchanged(self):
        """Команда переносит файлы БД из рабочей копии в каталог логов без изменений; повтор ничего не меняет.

        Сценарий: в рабочей копии задачи лежит случайный непустой набор из
        `.artel/state.db`, `-wal`, `-shm`, `-journal` со случайным
        содержимым. `worktree-db-clean <id>` завершается успешно; в рабочей
        копии этих файлов больше нет, в `config.LOGS` для каждого есть файл
        с тем же содержимым байт в байт; прочие файлы рабочей копии на
        месте. Повторный вызов успешен и не меняет ни каталог логов, ни
        рабочую копию.

        Ловит мутацию: команда переносит только `state.db` и оставляет
        спутники SQLite в рабочей копии (`-wal` остаётся на месте), либо
        повторный вызов без файлов завершается ненулевым кодом.
        """
        rels = self.rng.sample(DB_FILES, self.rng.randint(1, len(DB_FILES)))
        placed = self.put_db_files(rels)
        before_logs = self.logs_snapshot()
        code, out = self.clean()
        context = self.note(f"файлы {rels}; вывод:\n{out}")
        self.assertIn(code, (None, 0), context)
        moved = {p: data for p, data in self.logs_snapshot().items()
                 if before_logs.get(p) != data}
        for rel, data in placed.items():
            self.assertFalse((self.wt / rel).exists(), context)
            self.assertIn(data, moved.values(), self.note(
                f"{rel}: в {config.LOGS} нет файла с тем же содержимым\n"
                f"{out}"))
        self.assertTrue((self.wt / "marker.txt").is_file(), context)

        logs_after = self.logs_snapshot()
        code, out = self.clean()
        context = self.note(f"повторный вызов; вывод:\n{out}")
        self.assertIn(code, (None, 0), context)
        self.assertEqual(self.logs_snapshot(), logs_after, context)
        for rel in DB_FILES:
            self.assertFalse((self.wt / rel).exists(), context)

    def test_ac12_role_environment_refuses_clean(self):
        """В окружении роли команда отказывает и файлы не трогает; вне роли — переносит.

        Сценарий: в рабочей копии лежат файлы БД пульта. Окружение роли
        распознаётся маркером `ARTEL_ROLE` (случайная роль) либо `HOME`,
        равным дому роли `config.ROLE_HOME`: вызов завершается отказом с
        текстом «команда недоступна процессу роли», файлы на месте байт в
        байт, каталог логов не изменился. Затем тот же вызов вне окружения
        роли переносит файлы.

        Ловит мутацию: команда добавлена в белый список читающих команд роли
        в `artel.py` — под ролью она исполняется и уносит файлы из рабочей
        копии.
        """
        rels = self.rng.sample(DB_FILES, self.rng.randint(1, len(DB_FILES)))
        placed = self.put_db_files(rels)
        role = self.rng.choice(["developer", "reviewer", "analyst",
                                "test_author"])
        variants = (("маркер ARTEL_ROLE", {config.ARTEL_ROLE_ENV: role}),
                    ("HOME роли", {"HOME": str(config.ROLE_HOME)}))
        for name, env in variants:
            with self.subTest(variant=name, seed=self.seed):
                before_logs = self.logs_snapshot()
                code, out = self.clean(env)
                context = self.note(f"{name}; вывод:\n{out}")
                self.assertNotIn(code, (None, 0), context)
                self.assertIn(ROLE_REFUSAL, out, context)
                for rel, data in placed.items():
                    self.assertEqual((self.wt / rel).read_bytes(), data,
                                     context)
                self.assertEqual(self.logs_snapshot(), before_logs, context)

        code, out = self.clean()
        context = self.note(f"вне роли; вывод:\n{out}")
        self.assertIn(code, (None, 0), context)
        self.assertNotIn(ROLE_REFUSAL, out, context)
        for rel in placed:
            self.assertFalse((self.wt / rel).exists(), context)


class DoctorWorktreeDbTest(WorktreeDbSandbox):

    def test_ac7_doctor_warns_on_db_file_and_is_ok_without(self):
        """`doctor` предупреждает о файле БД в рабочей копии и даёт ok, когда его нет.

        Сценарий: в рабочей копии задачи лежит один из файлов БД пульта
        (случайный из четырёх). Среди строк `doctor.all_checks` есть `warn`,
        в которой назван путь этого файла и
        `artel.py worktree-db-clean <id>`. Файл убран — та же проверка (по
        имени строки) даёт `ok`, и ни одна строка не предупреждает об
        уборке.

        Ловит мутацию: проверка смотрит только на `.artel/state.db` главной
        копии (`config.DB`), а не в рабочие копии области проектов — строки
        `warn` с путём файла рабочей копии и командой уборки нет.
        """
        rel = self.rng.choice(DB_FILES)
        path = self.wt / rel
        self.put_db_files([rel])
        command = f"artel.py worktree-db-clean {self.task}"
        spellings = {str(path), str(path.resolve())}
        with contextlib.suppress(ValueError):
            spellings.add(str(path.relative_to(config.ROOT)))
        with contextlib.suppress(ValueError):
            spellings.add(str(path.resolve().relative_to(
                Path(config.ROOT).resolve())))

        dirty = doctor.all_checks(self.conn)
        warned = [c for c in dirty if c.status == "warn" and command in c.detail
                  and any(s in c.detail for s in spellings)]
        self.assertTrue(warned, self.note(
            f"{rel}: нет строки warn с путём и командой уборки:\n"
            + "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in dirty)))

        path.unlink()
        names = {c.name for c in warned}
        clean = doctor.all_checks(self.conn)
        context = self.note("\n".join(f"[{c.status}] {c.name}: {c.detail}"
                                      for c in clean))
        self.assertTrue([c for c in clean
                         if c.name in names and c.status == "ok"], context)
        self.assertFalse([c for c in clean if c.status in ("warn", "fail")
                          and "worktree-db-clean" in c.detail], context)


if __name__ == "__main__":
    unittest.main()
