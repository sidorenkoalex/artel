"""Приёмочные тесты AC-6, AC-7, AC-8 (tasks/01M1RDCEF0JZ4AVQRE43JFH8TN/
SPEC.md, «Критерии приёмки»).

AC-6: Отсутствие любого объявленного инструмента (`shutil.which` не
находит путь) — попытка агента не запускается.

AC-7: В этом случае в журнал шага пишется запись `agent run SKIPPED` с
именованной причиной по образцу «окружение роли не подготовлено».

AC-8: Отсутствие инструмента не приводит к тихому откату окружения роли
на PATH/переменные Оператора — шаг не подменяет источник окружения
запасным путём.

Красен до реализации: сегодня `role_env` не проверяет присутствие
инструментов вообще (нет резолвинга через манифест).
- `test_ac6_*` — `shutil.which`, вернувший `None` для объявленного
  инструмента, ни на что не влияет — `role_env` не поднимет исключение,
  `assertRaises` ниже не сработает (тест краснеет).
- `test_ac7_ac8_*` — воспроизводят интеграционный сценарий ПО ОБРАЗЦУ
  уже существующего теста `tests/test_multitarget.py::RoleEnvTest::
  test_step_does_not_start_without_the_layer` (тот же приём: `role_env`
  подменяется исключением, `cmd_run` должен пропустить шаг). Этот
  сценарий уже работает на сегодняшнем `runner.py` — он «зелёный с
  рождения» как ПРОВЕРКА СУЩЕСТВУЮЩЕГО контракта `run_agent_once`
  (перехват `OSError` из `role_env`, журнал SKIPPED, `popen` не
  вызывается); AC-7/AC-8 требуют, чтобы `role_env` реализации ЭТОЙ
  задачи заводил такой же `OSError` при отсутствующем инструменте —
  само по себе новое поведение красное (см. `test_ac6_*`), а этот файл
  проверяет, что `cmd_run` обработает его так же, как любой другой сбой
  подготовки окружения.

Предположение о реализации: отсутствие инструмента поднимает `OSError`
(тот же класс исключения, что уже ловит `run_agent_once` вокруг вызова
`role_env` — «по образцу уже существующей записи», требование 3 SPEC) —
решение test_author по аналогии с существующим кодом, не факт из кода
части 3 (которого ещё нет).
"""
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import catalog, runner, store  # noqa: E402
from tests.sandbox import (TmpRootTest, capture,  # noqa: E402
                           capture_new_task_id, fake_git,
                           seed_developer_brief_fixtures,
                           sync_spec_from_worktree)

FAKE_TOOL_PATHS = {
    "python3": "/opt/fake-pyenv/shims/python3",
    "git": "/usr/bin/git",
    "gh": "/usr/local/bin/gh",
    "claude": "/usr/local/bin/claude",
}


def _which_missing(missing_tool):
    def fn(name, *args, **kwargs):
        if name == missing_tool:
            return None
        return FAKE_TOOL_PATHS.get(name)
    return fn


def _stub_git(*args):
    import subprocess
    return subprocess.CompletedProcess(list(args), 1, "", "")


class RoleEnvRaisesOnMissingToolTest(TmpRootTest):

    def test_ac6_missing_declared_tool_raises_instead_of_building_env(self):
        """`role_env` поднимает исключение, если `which` не находит один
        из объявленных инструментов (`gh` в этом сценарии), вместо того
        чтобы построить окружение без него.

        Ловит мутацию: замена отсутствующего пути на `None`/пустую
        строку с продолжением сборки PATH — `assertRaises` не увидит
        исключения, тест покраснеет.
        """
        with mock.patch("shutil.which", side_effect=_which_missing("gh")), \
                mock.patch.object(runner.gitcmd, "git", _stub_git):
            with self.assertRaises(OSError) as ctx:
                runner.role_env()

        self.assertIn("gh", str(ctx.exception),
                     "причина исключения обязана называть отсутствующий инструмент")


class MissingToolSkipsStepWithoutFallbackTest(TmpRootTest):
    """Интеграционный сценарий на уровне `cmd_run` — по образцу
    `RoleEnvTest.test_step_does_not_start_without_the_layer` и
    `_MultitargetTmpRootTest` (`tests/test_multitarget.py`): pre-flight
    (токен/CLI/диск/layout), сборка брифа и worktree-механика — не
    предмет ЭТИХ тестов, поэтому обходятся тем же набором подмен, чтобы
    выполнение реально дошло до `run_agent_once`/`role_env`, а не
    отвалилось раньше по не связанной с AC-7/AC-8 причине (иначе
    `popen.assert_not_called()` был бы истинным ВСЕГДА, независимо от
    того, есть ли в `role_env` тихий откат — ложноположительный тест)."""

    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "PROJECTS",
                     "ROLE_HOME", "ROLE_CONFIG_DIR", "TARGETS", "ROOT")

    def setUp(self):
        super().setUp()
        shutil.copytree(_REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(_REPO_ROOT / "skills", self.root / "skills")
        seed_developer_brief_fixtures(self.root)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch("orchestrator.doctor.preflight_checks",
                                lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)
        wt_patcher = mock.patch.object(runner.workspace, "ensure",
                                       lambda task_id, branch: (self.root, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)
        git_patcher = mock.patch.object(runner.gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)

    def _run_with_missing_tool(self, reason_text: str) -> tuple:
        capture(catalog.cmd_init)
        _, task_id = capture_new_task_id(catalog.cmd_new, "Окружение роли: инструмент отсутствует")
        store.update_task(store.db(), task_id, state="in_dev")
        sync_spec_from_worktree(task_id)

        with mock.patch.object(runner, "role_env",
                               side_effect=OSError(reason_text)), \
                mock.patch.object(runner, "spawn_agent") as popen:
            out = capture(runner.cmd_run, task_id)

        return task_id, out, popen

    def test_ac7_skip_is_journalled_with_the_missing_tool_named(self):
        """Отсутствие инструмента журналируется `agent run SKIPPED` с
        причиной, называющей конкретный инструмент — не общим текстом.

        Ловит мутацию: причина, не долетевшая до журнала (проглоченное
        исключение) или общий текст без имени инструмента — тест не
        найдёт `"gh"` в записи журнала.
        """
        reason_text = "объявленный инструмент не найден: gh"
        task_id, out, popen = self._run_with_missing_tool(reason_text)

        self.assertIn("окружение роли не подготовлено", out)
        details = [r["detail"] for r in store.task_steps(store.db(), task_id)
                  if r["action"] == "agent run SKIPPED"]
        self.assertTrue(details and "gh" in details[0],
                        f"причина SKIPPED не называет отсутствующий инструмент: {details}")

    def test_ac8_step_never_spawns_the_agent_process(self):
        """Отсутствие инструмента не откатывается тихо на PATH/переменные
        Оператора — шаг не запускает процесс агента вообще, ни с каким
        окружением.

        Ловит мутацию: запасной путь, подставляющий `os.environ`
        Оператора, когда `role_env` падает — `spawn_agent` в этом случае
        был бы вызван; `popen.assert_not_called()` поймает это.
        """
        _, _, popen = self._run_with_missing_tool("объявленный инструмент не найден: git")

        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
