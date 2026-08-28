"""Тесты канала промпта роли (см. tasks/T017/SPEC.md, требование 4).

Промпт шага уходит агенту файлом на стандартном входе, а не аргументом
командной строки. Проверяется наблюдаемое: в argv текста промпта нет,
процесс получает его на stdin, файл лежит рядом с логом прогона — и всё
это одинаково для обеих ролей, включая ревьювера с его пакетом.

Реального CLI здесь нет: `subprocess.Popen` подменён и запоминает, с чем
его позвали.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, gitcmd, runner, store  # noqa: E402
from tests.sandbox import (capture, fake_git,  # noqa: E402
                           seed_developer_brief_fixtures, sync_spec_from_worktree)

REPO_ROOT = Path(__file__).resolve().parent.parent


class FakeStream:
    """Пайп процесса: отдаёт заготовленные строки, помнит своё закрытие."""

    def __init__(self, lines):
        self.lines = iter(lines)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        self.closed = True


class FakeProc:
    """Процесс агента: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines, returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


class PromptChannelTest(unittest.TestCase):

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        # `ROOT` тоже уводится (SPEC T049: холодный старт сканирует его для
        # посева счётчика — непропатченный ROOT читал бы реальное дерево
        # пульта); `templates/`/`skills/` копируются рядом — `cmd_new`
        # читает `templates/SPEC.md`, `cmd_run` читает промпт роли из
        # `skills/*.md`, оба уже из песочницы.
        shutil.copytree(REPO_ROOT / "templates", root / "templates")
        shutil.copytree(REPO_ROOT / "skills", root / "skills")
        seed_developer_brief_fixtures(root)

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROOT", root),
                            ("PROJECTS", root / ".artel" / "projects"),
                            ("TARGETS", root / "targets.yaml"),
                            # Курируемый слой ролей (T019): каталог заводит
                            # запуск шага — пусть заводит в песочнице, а не
                            # в .artel/ репозитория.
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("BACKUP_MARKER", root / ".artel" / "backup-marker"),
                            # `cmd_new` (SPEC T048) сам заводит ветку и
                            # worktree через `gitcmd` — тому нужен адрес,
                            # не задетый ROOT репозитория пульта.
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        # git не спрашиваем: ревью-пакет собирается на заготовке. Не
        # `lambda *a: FakeGitResult()` (везде rc=0) — с SPEC T048 `cmd_new`
        # сам решает, заводить ли задачу, по ответу `branch_exists`
        # (AC-3): успех на любой вызов означал бы «ветка уже есть» и
        # вечный отказ. `tests.sandbox.fake_git` этот случай уже разбирает.
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Канал промпта")
        sync_spec_from_worktree(self.TASK)

    # ------------------------------------------------------------ утилиты

    capture = staticmethod(capture)

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def run_agent(self, state: str = "in_dev") -> mock.Mock:
        """Прогон шага с подменённым процессом; возвращает мок Popen."""
        self.set_state(state)
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            self.capture(runner.cmd_run, self.TASK)
        return popen

    def argv_of(self, popen: mock.Mock) -> list[str]:
        return popen.call_args.args[0]

    def prompt_path_of(self, popen: mock.Mock) -> Path:
        return Path(popen.call_args.kwargs["stdin"].name)

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    # ----------------------------------------------------------- сценарии

    def test_no_prompt_text_in_the_command_line(self):
        """Критерий приёмки 4: строка запуска не содержит текста промпта."""
        for state in ("in_dev", "review"):
            with self.subTest(состояние=state):
                popen = self.run_agent(state)

                argv = self.argv_of(popen)
                prompt = self.prompt_path_of(popen).read_text(encoding="utf-8")
                self.assertTrue(argv[argv.index("-p") + 1].startswith("--"),
                                f"после -p идёт флаг, а не промпт: {argv}")
                for word in ("Роль:", "СКИЛЫ РОЛИ", prompt[:40]):
                    self.assertFalse(any(word in arg for arg in argv),
                                     f"'{word[:20]}' попал в argv: {argv}")

    def test_the_process_gets_the_prompt_on_stdin(self):
        popen = self.run_agent()

        prompt = self.prompt_path_of(popen).read_text(encoding="utf-8")
        self.assertIn("Роль: разработчик", prompt)
        self.assertIn("--- СКИЛЫ РОЛИ ---", prompt)
        self.assertIn("conventions-core", prompt, "скилы из roles.yaml")

    def test_the_prompt_file_sits_next_to_the_step_log(self):
        """Шаг воспроизводим руками: промпт лежит рядом со своим логом."""
        popen = self.run_agent()

        path = self.prompt_path_of(popen)
        self.assertEqual(path.parent, config.LOGS)
        self.assertEqual(path.name, f"{self.TASK}-developer-1.prompt.txt")
        self.assertTrue((config.LOGS / f"{self.TASK}-developer-1.log").exists(),
                        "лог того же прогона — соседним файлом")

    def test_the_prompt_file_is_named_in_the_journal(self):
        popen = self.run_agent()

        details = self.journal_details("agent run started")
        self.assertEqual(len(details), 1)
        self.assertIn(str(self.prompt_path_of(popen)), details[0])

    def test_the_orchestrator_does_not_hold_the_file_open(self):
        """Дескриптор нужен только процессу: свой оркестратор закрывает."""
        popen = self.run_agent()

        self.assertTrue(popen.call_args.kwargs["stdin"].closed)

    def test_the_prompt_is_not_echoed_to_the_terminal(self):
        """Простыня промпта в терминал не летит — там живой вывод агента.

        Где промпт лежит, Оператор узнаёт из журнала шага
        (`test_the_prompt_file_is_named_in_the_journal`), а не из экрана.
        """
        self.set_state("in_dev")
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out = self.capture(runner.cmd_run, self.TASK)

        self.assertNotIn("--- СКИЛЫ РОЛИ ---", out)
        self.assertNotIn("Роль: разработчик", out)

    def test_unwritable_prompt_skips_the_step_without_a_traceback(self):
        """Промпт не записан — шаг не начат, причина в журнале."""
        self.set_state("in_dev")
        with mock.patch.object(Path, "write_text",
                               side_effect=OSError("диск переполнен")):
            with mock.patch.object(runner, "spawn_agent") as popen:
                self.capture(runner.cmd_run, self.TASK)

        popen.assert_not_called()
        self.assertTrue(any("промпт не записан" in d
                            for d in self.journal_details("agent run SKIPPED")))

    def test_a_vanished_prompt_is_not_blamed_on_the_cli(self):
        """Файл исчез между записью и чтением (уборка `.artel/logs`, tmp-reaper).

        Отчитаться про «claude CLI не найден» значило бы отправить Оператора
        чинить установку CLI вместо диска: обе беды приходят одним
        FileNotFoundError, и различает их только место перехвата.
        """
        self.set_state("in_dev")
        with mock.patch.object(runner, "open",
                               side_effect=FileNotFoundError("нет файла"),
                               create=True):
            with mock.patch.object(runner, "spawn_agent") as popen:
                out = self.capture(runner.cmd_run, self.TASK)

        popen.assert_not_called()
        details = self.journal_details("agent run SKIPPED")
        self.assertTrue(any("промпт не прочитан" in d for d in details), details)
        self.assertNotIn("CLI не найден", out)


if __name__ == "__main__":
    unittest.main()
