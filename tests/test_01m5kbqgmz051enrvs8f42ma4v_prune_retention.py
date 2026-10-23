"""Команда `prune`: промпты `*.prompt.txt` и каталоги `suite-run/<id>/` по
двойному правилу хранения логов, удаление брошенного каталога
упразднённого механизма `.artel/notes-work` только при сохранённой работе.

Группа: долгоживущий

Красен до реализации: `prune.cmd_prune` отбирает из `.artel/logs/` только `*.log` верхнего уровня — промпты, каталоги `suite-run` и `.artel/notes-work` в план и отчёт не попадают, строк «каталог suite-run …»/«каталог упразднённого механизма …» нет, старые промпты и каталоги переживают `--execute`.

Планка провалидирована временным стабом реализации `orchestrator/prune.py` (все методы зелёные, стаб удалён, не закоммичен).

Предмет — только публичная команда `prune.cmd_prune` (вывод отчёта и
состояние файловой системы после неё). Окружение — песочница корня пульта:
`tests.sandbox.InitializedTmpRootTest` для логов и `suite-run` (git не
нужен), `tests.sandbox.RealGitSandbox` для `.artel/notes-work` — связка
«команда — настоящий git каталога — файловая система»: корень песочницы сам
git-репозиторий пульта, `.artel/notes-work` — вложенный собственный
репозиторий с bare `origin` во временном каталоге. Давность ставится
`os.utime` от `config.LOG_RETENTION_DAYS`, «последние N закрытых» — от
`config.LOG_RETENTION_KEEP_TASKS`: закрытие задачи — запись журнала
`state -> done` с подставленным моментом.

Идентификаторы задач, возраст файлов, состав и число файлов каталогов
порождаются при каждом запуске от зерна; зерно печатается и входит в текст
провала.
"""
import json
import os
import random
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from orchestrator import config, prune, store, suite_lock
from tests.sandbox import (InitializedTmpRootTest, RealGitSandbox, _dead_pid,
                           capture, init_bare_origin)

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
NOTES_REL = ".artel/notes-work"
NOTES_LINE = f"  каталог упразднённого механизма {NOTES_REL}"
ABOLISHED = "каталог упразднённого механизма"
NOTHING = "нечего убирать"
ROLES = ("analyst", "test_author", "developer", "reviewer")


def suite_line(name: str) -> str:
    return f"  каталог suite-run {name}"


def file_count(path: Path) -> int:
    return sum(1 for p in path.rglob("*") if p.is_file() and not p.is_symlink())


def tree_snapshot(path: Path) -> set:
    """Все пути под `path` (файлы и каталоги) — для «ничего не удалено»."""
    return {str(p.relative_to(path)) for p in path.rglob("*")}


def worktree_files(path: Path) -> dict:
    """Содержимое файлов каталога вне `.git` (индекс git обновляет сам)."""
    out = {}
    for p in path.rglob("*"):
        rel = p.relative_to(path)
        if rel.parts and rel.parts[0] == ".git":
            continue
        if p.is_file():
            out[str(rel)] = p.read_bytes()
    return out


class _Seeded:
    """Зерно сценария, генераторы входов и общие шаги посева."""

    def seed_rng(self) -> None:
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.msg = f"зерно: {self.seed}"

    def new_id(self) -> str:
        return "".join(self.rng.choice(ULID_ALPHABET) for _ in range(26))

    def old_days(self) -> float:
        return config.LOG_RETENTION_DAYS + self.rng.uniform(1, 300)

    def fresh_days(self) -> float:
        return self.rng.uniform(0, config.LOG_RETENTION_DAYS - 1)

    def age(self, path: Path, days: float, follow: bool = True) -> None:
        stamp = time.time() - days * 86400
        os.utime(path, (stamp, stamp), follow_symlinks=follow)

    def close_task(self, task_id: str, days_ago: float) -> str:
        """Задача закрыта (`state -> done`) `days_ago` дней назад."""
        conn = store.db()
        store.insert_task(conn, task_id, "Задача", "done",
                          f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                          25.0)
        store.journal(conn, task_id, "test", "state -> done")
        when = datetime.now(timezone.utc) - timedelta(days=days_ago)
        conn.execute("UPDATE steps SET ts=? WHERE task_id=? AND action=?",
                     (when.strftime("%Y-%m-%d %H:%M:%SZ"), task_id,
                      "state -> done"))
        conn.commit()
        return task_id

    def open_task(self, task_id: str) -> str:
        store.insert_task(store.db(), task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                          25.0)
        return task_id

    def seed_closed(self, outside: int, kept: int = 0) -> tuple:
        """`kept` задач среди последних `LOG_RETENTION_KEEP_TASKS` закрытых
        и `outside` задач, закрытых раньше всех последних N."""
        recent = [self.close_task(self.new_id(), self.rng.uniform(0.1, 0.9))
                  for _ in range(config.LOG_RETENTION_KEEP_TASKS)]
        kept_ids = recent[:kept]
        outside_ids = [self.close_task(self.new_id(), self.rng.uniform(2, 60))
                       for _ in range(outside)]
        return outside_ids, kept_ids

    def old_log(self, task_id: str, suffix: str) -> Path:
        role = self.rng.choice(ROLES)
        path = config.LOGS / f"{task_id}-{role}-{self.rng.randint(1, 9)}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("лог\n", encoding="utf-8")
        self.age(path, self.old_days())
        return path

    def suite_dir(self, name: str, *, fresh_nested: bool = False,
                  run_pid: int | None = None) -> Path:
        """Каталог `suite-run/<name>/` со старыми файлами (в том числе во
        вложенном подкаталоге); `fresh_nested` — один свежий файл глубже
        всех; `run_pid` — `run.json` с этим pid."""
        root = suite_lock.directory() / name
        nested = root / "nested" / "deep"
        nested.mkdir(parents=True, exist_ok=True)
        files = [root / f"out-{i}.txt" for i in range(self.rng.randint(1, 4))]
        files += [nested / f"part-{i}.txt" for i in range(self.rng.randint(1, 3))]
        for path in files:
            path.write_text("вывод\n", encoding="utf-8")
            self.age(path, self.old_days())
        if run_pid is not None:
            run = root / "run.json"
            run.write_text(json.dumps({"task_id": name, "pid": run_pid,
                                       "run": 1}), encoding="utf-8")
            self.age(run, self.old_days())
        if fresh_nested:
            fresh = nested / "fresh.txt"
            fresh.write_text("свежий\n", encoding="utf-8")
            self.age(fresh, self.fresh_days())
        for d in (nested, nested.parent, root):
            self.age(d, self.old_days())
        return root


class PromptLogRetentionTest(_Seeded, InitializedTmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed_rng()
        config.LOGS.mkdir(parents=True, exist_ok=True)

    def test_ac1_old_prompt_outside_kept_tasks_is_pruned(self):
        """Старый промпт задачи вне последних N закрытых — в плане и удалён.

        Свежий промпт той же задачи и старый промпт задачи из последних N
        закрытых не упоминаются ни в плане, ни в отчёте исполнения и целы.

        Ловит мутацию: отбор по-прежнему `glob("*.log")` — старого промпта нет
        в плане, он переживает `--execute`; либо промпт отбирается без
        условия давности или без `_kept_task_ids` — в отчёте появляется
        свежий промпт или промпт сохраняемой задачи и он удаляется.
        """
        (out_id,), (kept_id,) = self.seed_closed(outside=1, kept=1)
        old = self.old_log(out_id, ".prompt.txt")
        fresh = config.LOGS / f"{out_id}-reviewer-{self.rng.randint(10, 99)}.prompt.txt"
        fresh.write_text("промпт\n", encoding="utf-8")
        self.age(fresh, self.fresh_days())
        kept = self.old_log(kept_id, ".prompt.txt")

        plan = capture(prune.cmd_prune)

        self.assertIn(f"  лог {old.name} будет удалён", plan.splitlines(), self.msg)
        for path in (fresh, kept):
            self.assertNotIn(path.name, plan, self.msg)
        self.assertTrue(old.exists(), self.msg)

        done = capture(prune.cmd_prune, True)

        self.assertIn(f"  лог {old.name} удалён", done.splitlines(), self.msg)
        self.assertFalse(old.exists(), self.msg)
        for path in (fresh, kept):
            self.assertNotIn(path.name, done, self.msg)
            self.assertTrue(path.exists(), f"{path.name}; {self.msg}")

    def test_ac1_other_top_level_files_are_not_pruned(self):
        """Старые файлы верхнего уровня не `.log`/`.prompt.txt` не отбираются.

        `x-state.db` и `<id>-state.db` задачи вне последних N закрытых
        старше порога; рядом — старый промпт той же задачи, который
        удаляется (контроль, что `--execute` действительно исполнялся).

        Ловит мутацию: отбор расширен до любого файла верхнего уровня
        (`glob("*")`) или до окончания `.txt`/`.db` — файл `*-state.db`
        попадает в план «лог … будет удалён» и пропадает после `--execute`.
        """
        (out_id,), _ = self.seed_closed(outside=1)
        control = self.old_log(out_id, ".prompt.txt")
        others = [config.LOGS / "x-state.db", config.LOGS / f"{out_id}-state.db",
                  config.LOGS / f"{out_id}-developer-1.prompt.txt.bak"]
        for path in others:
            path.write_text("данные\n", encoding="utf-8")
            self.age(path, self.old_days())

        plan = capture(prune.cmd_prune)
        done = capture(prune.cmd_prune, True)

        self.assertFalse(control.exists(), self.msg)
        for path in others:
            with self.subTest(name=path.name):
                self.assertNotIn(path.name, plan, self.msg)
                self.assertNotIn(path.name, done, self.msg)
                self.assertTrue(path.exists(), self.msg)


class SuiteRunRetentionTest(_Seeded, InitializedTmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed_rng()
        suite_lock.directory().mkdir(parents=True, exist_ok=True)

    def test_ac2_old_suite_run_dir_planned_then_removed_whole(self):
        """Старый каталог `suite-run/<id>/` закрытой задачи вне последних N.

        Сухой прогон печатает строку с числом файлов и не удаляет ничего;
        `--execute` удаляет каталог целиком. Каталог той же категории, где
        один файл во вложенном подкаталоге свежий, не отбирается.

        Ловит мутацию: давность каталога берётся по mtime самого каталога или
        только по файлам верхнего уровня — каталог со свежим вложенным файлом
        удаляется; число файлов считается без вложенных подкаталогов —
        «(<N> файлов)» расходится; сухой прогон удаляет — снимок дерева
        после плана меньше исходного; отбора `suite-run` нет — строки нет.
        """
        (old_id, fresh_id), _ = self.seed_closed(outside=2)
        old = self.suite_dir(old_id, run_pid=_dead_pid())
        fresh = self.suite_dir(fresh_id, fresh_nested=True)
        count = file_count(old)
        fresh_count = file_count(fresh)
        before = tree_snapshot(config.LOGS)

        plan = capture(prune.cmd_prune)

        self.assertIn(f"{suite_line(old_id)} ({count} файлов) будет удалён",
                      plan.splitlines(), self.msg)
        self.assertNotIn(fresh_id, plan, self.msg)
        self.assertEqual(tree_snapshot(config.LOGS), before, self.msg)

        done = capture(prune.cmd_prune, True)

        self.assertIn(f"{suite_line(old_id)} ({count} файлов) удалён",
                      done.splitlines(), self.msg)
        self.assertFalse(old.exists(), self.msg)
        self.assertNotIn(fresh_id, done, self.msg)
        self.assertTrue((fresh / "nested" / "deep" / "fresh.txt").exists(), self.msg)
        self.assertEqual(file_count(fresh), fresh_count, self.msg)

    def test_ac3_empty_suite_run_dir_judged_by_own_mtime(self):
        """Пустой каталог `suite-run/<id>/`: давность — mtime самого каталога.

        Старый пустой каталог удаляется `--execute`, свежий пустой каталог
        другой такой же задачи не упоминается и цел.

        Ловит мутацию: у каталога без файлов давность не определена и он
        пропускается — старый пустой каталог переживает `--execute`; либо
        пустой каталог считается старым при любом mtime — свежий удалён.
        """
        (old_id, fresh_id), _ = self.seed_closed(outside=2)
        old = suite_lock.directory() / old_id
        fresh = suite_lock.directory() / fresh_id
        old.mkdir()
        fresh.mkdir()
        self.age(old, self.old_days())
        self.age(fresh, self.fresh_days())

        plan = capture(prune.cmd_prune)
        done = capture(prune.cmd_prune, True)

        self.assertFalse(old.exists(), self.msg)
        self.assertTrue(fresh.is_dir(), self.msg)
        self.assertNotIn(fresh_id, plan + done, self.msg)

    def test_ac4_open_and_recently_closed_task_dirs_kept(self):
        """Старые каталоги открытой задачи и задачи из последних N закрытых.

        Оба не упоминаются в плане и отчёте и целы после `--execute`; рядом
        старый каталог задачи вне последних N удаляется (контроль исполнения).

        Ловит мутацию: в отборе `suite-run` нет условия `_kept_task_ids` или
        в него попадают только закрытые задачи — каталог открытой задачи
        либо недавно закрытой удаляется `--execute`.
        """
        (out_id,), (kept_id,) = self.seed_closed(outside=1, kept=1)
        open_id = self.open_task(self.new_id())
        control = self.suite_dir(out_id)
        keep = [self.suite_dir(open_id), self.suite_dir(kept_id)]
        counts = [file_count(d) for d in keep]

        plan = capture(prune.cmd_prune)
        done = capture(prune.cmd_prune, True)

        self.assertFalse(control.exists(), self.msg)
        for d, count in zip(keep, counts):
            with self.subTest(task=d.name):
                self.assertNotIn(d.name, plan + done, self.msg)
                self.assertTrue(d.is_dir(), self.msg)
                self.assertEqual(file_count(d), count, self.msg)

    def test_ac5_protected_entries_of_suite_run_survive(self):
        """Не отбираются: каталог держателя замка, живой `run.json`,
        `pending-journal/`, `lock.json`, имя не формы id, ссылка.

        Все — старые и задачи вне последних N закрытых; замок пишется
        публичным `suite_lock.hand` за задачей (её процесс мёртв); `run.json`
        несёт pid текущего процесса; ссылка формы id ведёт на старый каталог
        вне `suite-run`. Рядом старый обычный каталог удаляется (контроль).

        Ловит мутацию: пропущена одна из проверок отбора — замок
        `suite_lock.holder()`, живость pid из `run.json`, форма имени
        `idgen.is_task_id_form`, отказ от символических ссылок — и
        соответствующий каталог (или цель ссылки) пропадает после
        `--execute`; `lock.json`/`pending-journal/` попадают под отбор
        как обычные записи каталога и удаляются.
        """
        (lock_id, live_id, link_id, out_id), _ = self.seed_closed(outside=4)
        control = self.suite_dir(out_id)
        held = self.suite_dir(lock_id)
        live = self.suite_dir(live_id, run_pid=os.getpid())
        tmp_x = self.suite_dir("tmp-x")
        pending = suite_lock.directory() / "pending-journal"
        pending.mkdir()
        (pending / "entry.json").write_text("{}", encoding="utf-8")
        self.age(pending / "entry.json", self.old_days())
        self.age(pending, self.old_days())
        suite_lock.hand(lock_id, 1, _dead_pid())
        lock = suite_lock.path()
        self.age(lock, self.old_days())
        target = self.root / "elsewhere" / link_id
        target.mkdir(parents=True)
        (target / "kept.txt").write_text("цель\n", encoding="utf-8")
        self.age(target / "kept.txt", self.old_days())
        self.age(target, self.old_days())
        link = suite_lock.directory() / link_id
        link.symlink_to(target, target_is_directory=True)
        self.age(link, self.old_days(), follow=False)
        survivors = {held: file_count(held), live: file_count(live),
                     tmp_x: file_count(tmp_x)}

        plan = capture(prune.cmd_prune)
        done = capture(prune.cmd_prune, True)

        self.assertFalse(control.exists(), self.msg)
        for name in (lock_id, live_id, link_id, "tmp-x", "pending-journal",
                     "lock.json"):
            with self.subTest(name=name):
                self.assertNotIn(name, plan + done, self.msg)
        for d, count in survivors.items():
            with self.subTest(dir=d.name):
                self.assertTrue(d.is_dir(), self.msg)
                self.assertEqual(file_count(d), count, self.msg)
        self.assertTrue((pending / "entry.json").exists(), self.msg)
        self.assertTrue(lock.exists(), self.msg)
        self.assertEqual(suite_lock.holder()["task_id"], lock_id, self.msg)
        self.assertTrue(link.is_symlink(), self.msg)
        self.assertTrue((target / "kept.txt").exists(), self.msg)

    def test_ac6_suite_run_removal_failure_reported_logs_still_removed(self):
        """Сбой удаления отобранного каталога `suite-run` — строка «не удалён».

        Внутри старого каталога подкаталог без права записи — удаление
        каталога целиком отказывает; старые `*.log` и `*.prompt.txt` того же
        прогона всё равно удалены со строками «… удалён».

        Ловит мутацию: исключение удаления каталога не перехвачено — команда
        падает и отчёта с логами нет; либо сбой глотается молча — строки
        «каталог suite-run <id> не удалён: <ошибка>» нет; либо после сбоя
        удаление прочих видов прекращается — старый лог остаётся на диске.
        """
        if os.geteuid() == 0:
            self.skipTest("от root право записи каталога не ограничивает удаление")
        (out_id, log_id), _ = self.seed_closed(outside=2)
        broken = self.suite_dir(out_id)
        locked = broken / "ro"
        locked.mkdir()
        (locked / "pinned.txt").write_text("x\n", encoding="utf-8")
        self.age(locked / "pinned.txt", self.old_days())
        self.age(locked, self.old_days())
        self.age(broken, self.old_days())
        locked.chmod(0o500)
        self.addCleanup(locked.chmod, 0o700)
        logs = [self.old_log(log_id, ".log"), self.old_log(log_id, ".prompt.txt")]

        done = capture(prune.cmd_prune, True)

        prefix = f"{suite_line(out_id)} не удалён: "
        self.assertTrue(any(line.startswith(prefix) for line in done.splitlines()),
                        f"{done}\n{self.msg}")
        for path in logs:
            with self.subTest(log=path.name):
                self.assertIn(f"  лог {path.name} удалён", done.splitlines(), self.msg)
                self.assertFalse(path.exists(), self.msg)


class NotesWorkSandbox(_Seeded, RealGitSandbox):
    """Корень пульта — настоящий git-репозиторий; `.artel/notes-work` —
    вложенный каталог, собранный сценарием."""

    def setUp(self):
        super().setUp()
        self.seed_rng()
        self.notes = self.root / NOTES_REL

    def ngit(self, repo: Path, *args: str) -> str:
        return self.git("-C", str(repo), "-c", "user.name=t",
                        "-c", "user.email=t@example.invalid",
                        "-c", "commit.gpgsign=false", *args)

    def bare(self) -> Path:
        path = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        init_bare_origin(path, self.git)
        return path

    def clean_repo(self, path: Path) -> Path:
        """Собственный репозиторий: всё закоммичено и отправлено в
        `origin`, чистое дерево, пустой stash, HEAD на ветке."""
        self.git("init", "-q", "-b", config.MAIN_BRANCH, str(path))
        (path / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
        (path / "README.md").write_text("заметки\n", encoding="utf-8")
        sub = path / "notes"
        sub.mkdir()
        for i in range(self.rng.randint(1, 4)):
            (sub / f"n{i}.md").write_text(f"заметка {i}\n", encoding="utf-8")
        self.ngit(path, "add", "-A")
        self.ngit(path, "commit", "-q", "-m", "заметки")
        self.ngit(path, "remote", "add", "origin", str(self.bare()))
        self.ngit(path, "push", "-q", "origin", config.MAIN_BRANCH)
        return path

    def reset_notes(self) -> None:
        if self.notes.is_symlink():
            self.notes.unlink()
        elif self.notes.exists():
            shutil.rmtree(self.notes)

    def assert_left(self, reason: str) -> None:
        """Обе команды печатают строку «оставлено: <reason>», каталог и
        содержимое его рабочего дерева целы, «нечего убирать» нет."""
        files = worktree_files(self.notes)
        plan = capture(prune.cmd_prune)
        done = capture(prune.cmd_prune, True)
        line = f"{NOTES_LINE} оставлено: {reason}"
        for name, out in (("план", plan), ("исполнение", done)):
            self.assertIn(line, out.splitlines(), f"{name}: {out}\n{self.msg}")
            self.assertNotIn(NOTHING, out, f"{name}; {self.msg}")
        self.assertTrue(self.notes.is_dir(), self.msg)
        self.assertTrue((self.notes / ".git").exists(), self.msg)
        self.assertEqual(worktree_files(self.notes), files, self.msg)


class NotesWorkRemovalTest(NotesWorkSandbox):

    def test_ac7_clean_own_repo_planned_then_removed(self):
        """Чистый собственный репозиторий `.artel/notes-work` удаляется.

        Сухой прогон печатает строку с числом файлов (рекурсивно, `.git`
        включительно) и каталог не трогает; `--execute` удаляет каталог;
        повторный `--execute` без прочих видов печатает «нечего убирать».

        Ловит мутацию: `ABOLISHED_DIRS` не подключены к `cmd_prune` — строки
        нет и каталог цел; сухой прогон исполняет удаление — каталога нет
        после плана; признак «нечего убирать» не учитывает новый вид —
        печатается при каталоге в плане.
        """
        self.clean_repo(self.notes)
        count = file_count(self.notes)

        plan = capture(prune.cmd_prune)

        self.assertIn(f"{NOTES_LINE} ({count} файлов) будет удалён",
                      plan.splitlines(), f"{plan}\n{self.msg}")
        self.assertNotIn(NOTHING, plan, self.msg)
        self.assertTrue((self.notes / "README.md").exists(), self.msg)
        count = file_count(self.notes)

        done = capture(prune.cmd_prune, True)

        self.assertIn(f"{NOTES_LINE} ({count} файлов) удалён",
                      done.splitlines(), f"{done}\n{self.msg}")
        self.assertFalse(os.path.lexists(self.notes), self.msg)

        again = capture(prune.cmd_prune, True)

        self.assertIn(NOTHING, again, self.msg)

    def test_ac8_symlinked_notes_work_is_never_touched(self):
        """`.artel/notes-work` — символическая ссылка на каталог.

        Цель — чистый репозиторий из AC-7 либо обычный каталог: ни в плане,
        ни в отчёте каталога упразднённого механизма нет, печатается
        «нечего убирать», ссылка и всё содержимое цели целы.

        Ловит мутацию: проверка `is_symlink()` пропущена и `is_dir()`
        следует по ссылке — чистый репозиторий-цель попадает в план и
        удаляется (или удаляется ссылка) при `--execute`.
        """
        for kind in ("чистый репозиторий", "обычный каталог"):
            with self.subTest(kind=kind):
                self.reset_notes()
                target = Path(tempfile.mkdtemp()) / "target"
                self.addCleanup(shutil.rmtree, target.parent, ignore_errors=True)
                if kind == "чистый репозиторий":
                    self.clean_repo(target)
                else:
                    target.mkdir()
                    (target / "a.txt").write_text("a\n", encoding="utf-8")
                before = tree_snapshot(target)
                self.notes.parent.mkdir(parents=True, exist_ok=True)
                self.notes.symlink_to(target, target_is_directory=True)

                plan = capture(prune.cmd_prune)
                done = capture(prune.cmd_prune, True)

                for out in (plan, done):
                    self.assertNotIn(ABOLISHED, out, f"{out}\n{self.msg}")
                    self.assertIn(NOTHING, out, self.msg)
                self.assertTrue(self.notes.is_symlink(), self.msg)
                self.assertEqual(tree_snapshot(target), before, self.msg)

    def test_ac9_dir_without_own_git_is_left(self):
        """Каталог без своего `.git` внутри репозитория пульта песочницы.

        `git -C` в нём отвечает о репозитории пульта выше по дереву —
        каталог оставлен с причиной «не собственный репозиторий».

        Ловит мутацию: сверка `--show-toplevel` с самим каталогом пропущена
        и проверка чистоты идёт по репозиторию пульта — каталог попадает в
        план и удаляется вместе с содержимым.
        """
        sub = self.notes / "notes"
        sub.mkdir(parents=True)
        for i in range(self.rng.randint(1, 4)):
            (sub / f"n{i}.md").write_text(f"заметка {i}\n", encoding="utf-8")
        files = worktree_files(self.notes)

        plan = capture(prune.cmd_prune)
        done = capture(prune.cmd_prune, True)

        line = f"{NOTES_LINE} оставлено: не собственный репозиторий"
        for out in (plan, done):
            self.assertIn(line, out.splitlines(), f"{out}\n{self.msg}")
            self.assertNotIn(NOTHING, out, self.msg)
        self.assertEqual(worktree_files(self.notes), files, self.msg)

    def test_ac10_git_failure_leaves_dir(self):
        """Повреждённый индекс собственного репозитория — git отвечает ошибкой.

        Строка «оставлено: git не ответил: …», каталог и его содержимое
        целы после `--execute`.

        Ловит мутацию: код возврата git не проверяется и пустой вывод
        `status --porcelain` считается чистым деревом — каталог удаляется;
        либо ошибка git разбирается как «не собственный репозиторий».
        """
        self.clean_repo(self.notes)
        (self.notes / ".git" / "index").write_bytes(b"not an index")
        files = worktree_files(self.notes)

        plan = capture(prune.cmd_prune)
        done = capture(prune.cmd_prune, True)

        prefix = f"{NOTES_LINE} оставлено: git не ответил: "
        for out in (plan, done):
            self.assertTrue(any(line.startswith(prefix) for line in out.splitlines()),
                            f"{out}\n{self.msg}")
        self.assertTrue((self.notes / ".git").is_dir(), self.msg)
        self.assertEqual(worktree_files(self.notes), files, self.msg)

    def test_ac11_uncommitted_untracked_or_ignored_files_leave_dir(self):
        """Изменённый отслеживаемый, неотслеживаемый, игнорируемый файл.

        Изменение в рабочем дереве и в индексе — «незакоммиченные правки»;
        неотслеживаемый и игнорируемый по `.gitignore` файл при прочих
        условиях AC-7 — «неотслеживаемые или игнорируемые файлы».

        Ловит мутацию: проверка дерева без `--ignored` (или без
        неотслеживаемых) — каталог с `*.tmp` либо новым файлом удаляется;
        проверка только индекса или только рабочего дерева — правка в
        другом месте не видна и каталог удаляется; причины перепутаны.
        """
        cases = (
            ("правка в рабочем дереве", "незакоммиченные правки", False),
            ("правка в индексе", "незакоммиченные правки", True),
            ("неотслеживаемый файл", "неотслеживаемые или игнорируемые файлы", None),
            ("игнорируемый файл", "неотслеживаемые или игнорируемые файлы", None),
        )
        for kind, reason, staged in cases:
            with self.subTest(kind=kind):
                self.reset_notes()
                self.clean_repo(self.notes)
                if kind == "неотслеживаемый файл":
                    (self.notes / "notes" / "new.md").write_text("н\n", encoding="utf-8")
                elif kind == "игнорируемый файл":
                    (self.notes / "draft.tmp").write_text("ч\n", encoding="utf-8")
                else:
                    (self.notes / "README.md").write_text("правка\n", encoding="utf-8")
                    if staged:
                        self.ngit(self.notes, "add", "README.md")
                self.assert_left(reason)

    def test_ac12_commits_outside_origin_leave_dir(self):
        """Коммит локальной ветки не достижим ни из одной `refs/remotes/origin/*`.

        Отдельно — коммит только локальный и коммит, отправленный в другой
        удалённый (`backup`): оба раза «оставлено: коммиты вне origin».

        Ловит мутацию: сверка идёт по всем `refs/remotes/*` (`--remotes`)
        вместо `refs/remotes/origin/*` — коммит, лежащий только в `backup`,
        считается сохранённым и каталог удаляется; либо сверки нет вовсе —
        удаляется и каталог с чисто локальным коммитом.
        """
        for kind in ("только локально", "только в другом удалённом"):
            with self.subTest(kind=kind):
                self.reset_notes()
                self.clean_repo(self.notes)
                (self.notes / "notes" / "late.md").write_text("п\n", encoding="utf-8")
                self.ngit(self.notes, "add", "-A")
                self.ngit(self.notes, "commit", "-q", "-m", "поздняя")
                if kind == "только в другом удалённом":
                    self.ngit(self.notes, "remote", "add", "backup", str(self.bare()))
                    self.ngit(self.notes, "push", "-q", "backup", config.MAIN_BRANCH)
                    self.ngit(self.notes, "rev-parse", "--verify",
                              f"refs/remotes/backup/{config.MAIN_BRANCH}")
                self.assert_left("коммиты вне origin")

    def test_ac13_nonempty_stash_leaves_dir(self):
        """Чистое дерево, всё в `origin`, HEAD на ветке, но stash не пуст.

        Ловит мутацию: проверки `stash list` нет — каталог со спрятанной
        правкой удаляется вместе с ней.
        """
        self.clean_repo(self.notes)
        (self.notes / "README.md").write_text("спрятано\n", encoding="utf-8")
        self.ngit(self.notes, "stash", "-q")
        self.assertEqual(self.ngit(self.notes, "status", "--porcelain",
                                   "--ignored"), "", self.msg)

        self.assert_left("непустой stash")

    def test_ac14_detached_head_leaves_dir(self):
        """HEAD на коммите, а не на ветке, при прочих условиях AC-7.

        Ловит мутацию: проверки отделённого HEAD нет (`symbolic-ref`) —
        каталог с HEAD на коммите удаляется при `--execute`.
        """
        self.clean_repo(self.notes)
        self.ngit(self.notes, "checkout", "-q", "--detach")

        self.assert_left("отделённый HEAD")

    def test_ac6_notes_removal_failure_reported_logs_still_removed(self):
        """Сбой удаления отобранного `.artel/notes-work` — строка «не удалён».

        Чистый репозиторий, в нём закоммиченный подкаталог без права
        записи — удаление целиком отказывает; старые `*.log` и
        `*.prompt.txt` того же прогона всё равно удалены со строками.

        Ловит мутацию: исключение удаления каталога не перехвачено — команда
        падает до отчёта; либо сбой глотается молча — строки «каталог
        упразднённого механизма .artel/notes-work не удалён: <ошибка>» нет;
        либо удаление логов идёт после каталогов и прерывается сбоем.
        """
        if os.geteuid() == 0:
            self.skipTest("от root право записи каталога не ограничивает удаление")
        self.clean_repo(self.notes)
        locked = self.notes / "notes"
        locked.chmod(0o500)
        self.addCleanup(locked.chmod, 0o700)
        log_id = self.new_id()
        logs = [self.old_log(log_id, ".log"), self.old_log(log_id, ".prompt.txt")]

        done = capture(prune.cmd_prune, True)

        prefix = f"{NOTES_LINE} не удалён: "
        self.assertTrue(any(line.startswith(prefix) for line in done.splitlines()),
                        f"{done}\n{self.msg}")
        for path in logs:
            with self.subTest(log=path.name):
                self.assertIn(f"  лог {path.name} удалён", done.splitlines(), self.msg)
                self.assertFalse(path.exists(), self.msg)


if __name__ == "__main__":
    unittest.main()
