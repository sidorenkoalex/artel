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

from orchestrator import (catalog, config, gitcmd, models, runner,  # noqa: E402
                          stack, store)
from tests.sandbox import (FakeProc, SANDBOX_ROLES_TEXT, SpyRun,  # noqa: E402
                           _stub_check_stack, capture,
                           capture_new_task_id, disk_backed_ls_tree_files,
                           disk_backed_show, fake_git,
                           seed_developer_brief_fixtures, sync_spec_from_worktree)

REPO_ROOT = Path(__file__).resolve().parent.parent


class PromptChannelTest(unittest.TestCase):

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
                            ("WORKTREES", root / ".artel" / "worktrees"),
                            # Локальный слой моделей и карта исполнителей с
                            # ярусами (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD,
                            # требования 5-6): модель шага — результат
                            # разрешения цепочки, и без обоих файлов шаг
                            # отказывает «ярус роли не разрешён» ещё до
                            # предмета этого файла (тот же приём, что
                            # `tests.sandbox.TmpRootTest.setUp`).
                            ("MODELS_LOCAL", root / ".artel" / "models.yaml"),
                            ("ROLES", root / "roles-sandbox.yaml")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        config.ROLES.write_text(SANDBOX_ROLES_TEXT, encoding="utf-8")
        models.ensure_local_template()
        # git не спрашиваем: ревью-пакет собирается на заготовке. Не
        # `lambda *a: FakeGitResult()` (везде rc=0) — с SPEC T048 `cmd_new`
        # сам решает, заводить ли задачу, по ответу `branch_exists`
        # (AC-3): успех на любой вызов означал бы «ветка уже есть» и
        # вечный отказ. `tests.sandbox.fake_git` этот случай уже разбирает.
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)
        # A7 (generic-путь заведения, AC-5): `cmd_new` коммитит артефакты
        # плотницки (`artifact_branch.write_commit`) — та функция зовёт
        # `subprocess.run` НАПРЯМУЮ, минуя `gitcmd.git`/фейк выше; `root`
        # здесь не настоящий git-репозиторий — без этого патча `cmd_new`
        # падает `sys.exit` («git не ответил») ещё до сценария, который
        # тест проверяет (тот же приём, что `tests.sandbox.TmpRootTest.
        # setUp`).
        spy_patcher = mock.patch.object(gitcmd.subprocess, "run", SpyRun())
        spy_patcher.start()
        self.addCleanup(spy_patcher.stop)
        # `artifact_source.resolve` теперь ВСЕГДА возвращает `foreign=True`
        # — брифу/FSM читают SPEC через `gitcmd.show`/`ls_tree_files`, не
        # с диска напрямую; эта песочница без настоящего git ведёт один
        # источник истины — диск `config.TASKS` (`sync_spec_from_worktree`
        # ниже), тот же приём, что `tests.test_invariants.FsmTest`.
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)
        # `runner.role_env` сверяет `.artel/venv` через `stack.check_stack()`
        # (SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8, требование 4) — `root` этой
        # песочницы не несёт согласованного venv (тот же приём, что
        # `tests.sandbox.TmpRootTest.setUp`).
        stack_patcher = mock.patch.object(stack, "check_stack",
                                          _stub_check_stack)
        stack_patcher.start()
        self.addCleanup(stack_patcher.stop)

        self.capture(catalog.cmd_init)
        # `cmd_new` возвращает id ULID (SPEC T094, требование 2), больше не
        # предсказуемый "T001" — забираем реальный через
        # `capture_new_task_id`, а не `self.capture` (та отбрасывает возврат).
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Канал промпта")
        sync_spec_from_worktree(self.TASK)

    # ------------------------------------------------------------ утилиты

    capture = staticmethod(capture)

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    # Имя обязательного артефакта роли этого состояния (SPEC
    # 01M1RQ12JVHE3PQYDFV1XPSTQ3, требование 3) — без него на диске
    # рабочего каталога роли `runner.run_agent_once` честно ретраит шаг
    # вместо одного тихого успеха, которого ждут остальные тесты этого
    # файла (они проверяют канал промпта, не отказ без артефакта).
    _STEP_ARTIFACT = {"in_dev": "PLAN.md", "review": "REVIEW.md"}

    def run_agent(self, state: str = "in_dev") -> mock.Mock:
        """Прогон шага с подменённым процессом; возвращает мок Popen."""
        self.set_state(state)
        marker = self._STEP_ARTIFACT.get(state)
        if marker is not None:
            tdir = config.WORKTREES / self.TASK / "tasks" / self.TASK
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / marker).write_text("маркер\n", encoding="utf-8")
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

    def test_setting_sources_excludes_project_and_local_layer(self):
        """SPEC T058, требование 1: агентный шаг не читает project-/local-
        слой клиентских настроек репозитория (инцидент T046) — `claude`
        запускается с `--setting-sources`, исключающим оба источника."""
        for state in ("in_dev", "review"):
            with self.subTest(состояние=state):
                argv = self.argv_of(self.run_agent(state))

                self.assertIn("--setting-sources", argv)
                value = argv[argv.index("--setting-sources") + 1]
                sources = {s.strip() for s in value.split(",")}
                self.assertFalse(
                    sources & {"project", "local"},
                    f"--setting-sources {value!r} не исключает project/local")

    def test_strict_mcp_config_and_no_curated_mcp_servers(self):
        """SPEC T069, требование 1: шаг роли не резолвит MCP-серверы из
        `.mcp.json` рабочего каталога — `--strict-mcp-config` без
        `--mcp-config` (курируемого списка MCP-серверов у пульта пока
        нет) резолвит шагу ноль MCP-серверов."""
        for state in ("in_dev", "review"):
            with self.subTest(состояние=state):
                argv = self.argv_of(self.run_agent(state))

                self.assertIn("--strict-mcp-config", argv)
                self.assertNotIn("--mcp-config", argv)

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
