"""AC-3 (tasks/T069/SPEC.md): `doctor` при осмотре target'а фиксирует
наличие `.claude/`, `.mcp.json`, `CLAUDE.md`/`AGENTS.md` в целевом репо —
информационно (`warn`, если обвязка обнаружена, `ok` — если нет),
ничего не блокирует (ADR-0003 п.14).

«Целевое репо» — не артефактный репо оркестратора (`config.PROJECTS/
<target>` сам по себе, куда `git-первичка` A2b коммитит SPEC/PLAN/REVIEW),
а РЕАЛЬНОЕ содержимое target'а: `config.PROJECTS/<target>/workspace/`
(`runner.role_cwd`, docstring прямо называет этот вектор: «внешний
target ... обязан видеть только свой workspace ... не дерево пульта с
его CLAUDE.md, `.claude/`, `.mcp.json` — та же конфиг-инъекция ... здесь
другой вектор, cwd» — дословно то же трио путей, что в этом AC).
`workspace/` создаётся пустым при `target-init` (SPEC T021,
`projects.init_project`, `config.PROJECT_DIRS`) — планировать маркеры
туда безопасно и не требует настоящего клона внешнего репо.

SPEC, требование 3 и «Материалы» называют `check_target_layout`/
`all_checks` образцом МЕСТА для новой проверки (цикл по `targets.load()`
внутри `all_checks`), а не имени новой функции — оно решение PLAN.
Тест поэтому не вызывает функцию по угаданному имени (тот же довод, что
в `test_ac2_isolation_smoke_mcp_marker.py`): он прогоняет
`doctor.all_checks(conn)` целиком (уже существующая, стабильная точка
входа, дословно названная в «Материалах») и ищет среди её результата
любую `warn`-проверку, чей `detail` называет хотя бы один из трёх путей
критерия. Единственный внешний (не-DEFAULT_TARGET) target в фикстуре —
`sled`: методом исключения (все прочие проверки `all_checks` для
единственного внешнего target'а — `check_target_layout`/`check_remote_
empty`/`check_base_branch`/`recovery_check` — используют свои
собственные `name`, не пересекающиеся с текстом ниже) найденная
`warn`-проверка с этим текстом обязана быть новым маркером обвязки,
кем бы разработчик её ни назвал.

Живой запуск настоящего `claude` (версия, live-smoke) в этом сценарии
не нужен и небезопасен по деньгам — `subprocess.run`/`subprocess.Popen`
подменены тем же приёмом, что `tests/test_doctor.py::
DoctorCommandTest.healthy_mocks` (`claude_only_run`/`claude_only_popen`
пропускают настоящий git нетронутым, отвечают только на `claude ...`).

Сегодня (до реализации T069) `check_target_layout`/`check_remote_empty`/
`check_base_branch` не сообщают ничего про `.claude/`/`.mcp.json`/
`CLAUDE.md`/`AGENTS.md` — тест закономерно красный по этой причине
(маркер обвязки ещё не существует), не по посторонней.

Красен до реализации: `test_ac3_wrapper_present_is_flagged_as_warn` —
среди сегодняшних проверок `all_checks` нет ни одной `warn` с текстом
про обвязку (проверено прогоном перед написанием этого докстринга).
Зелёный с рождения: `test_ac3_no_wrapper_is_ok_and_nothing_is_blocked`
— на чистом target'е (без обвязки) уже сегодня нет ложных warn/fail с
этим текстом просто потому, что такой проверки ещё нет; тест обязан
остаться зелёным и после реализации — регресс здесь означает ложный
warn на чистом target'е или блокирующий `fail` вместо информационного
`warn` (SPEC, требование 3).
"""
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, doctor, projects, runner, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture, claude_only_popen, claude_only_run  # noqa: E402

TARGETS_YAML_WITH_SLED = """targets:
  artel:
    forge: github
    url: https://example.invalid/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
  sled:
    forge: github
    url: https://example.invalid/sled
    base: main
    token_slot: sled-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

WRAPPER_MARKERS = (".claude", ".mcp.json", "CLAUDE.md", "AGENTS.md")


def result_event(usd: float) -> str:
    return f'{{"type":"result","total_cost_usd":{usd},"usage":{{}}}}\n'


class FakeLiveSmokeProc:
    def __init__(self, output, returncode: int = 0):
        self.output = output
        self.returncode = returncode

    def communicate(self, timeout=None):
        return self.output, None

    def kill(self) -> None:
        pass

    def wait(self, timeout=None) -> int:
        return self.returncode


class TargetWrapperInventoryTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        # Бриф роли (isolation_smoke собирает промпт) и live-smoke — тот же
        # минимум, что и `tests/test_doctor.py::_DoctorTmpRootTest.setUp`.
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")

        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        env_patcher = mock.patch.dict(
            "os.environ",
            {"CLAUDE_CODE_OAUTH_TOKEN": "", "ANTHROPIC_API_KEY": ""})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

        config.TARGETS.write_text(TARGETS_YAML_WITH_SLED, encoding="utf-8")
        capture(catalog.cmd_init)
        capture(projects.cmd_target_init, "sled")

    def workspace(self) -> Path:
        return config.PROJECTS / "sled" / "workspace"

    def which(self, name):
        return "/usr/bin/claude" if name == "claude" else None

    def run_all_checks(self) -> list:
        conn = store.db()
        with mock.patch.object(doctor.shutil, "which", side_effect=self.which), \
                mock.patch.object(doctor.subprocess, "run", side_effect=claude_only_run(
                    f"{config.CLI_VERSION_PIN} (Claude Code)\n")), \
                mock.patch.object(doctor.subprocess, "Popen",
                                  side_effect=claude_only_popen(
                                      FakeLiveSmokeProc(result_event(0.01)))):
            return doctor.all_checks(conn)

    def _wrapper_warnings(self, checks) -> list:
        return [c for c in checks if c.status == "warn"
                and any(marker in c.detail for marker in WRAPPER_MARKERS)]

    def test_ac3_wrapper_present_is_flagged_as_warn(self):
        (self.workspace() / ".claude").mkdir(parents=True, exist_ok=True)
        (self.workspace() / ".claude" / "settings.json").write_text(
            "{}", encoding="utf-8")
        (self.workspace() / ".mcp.json").write_text("{}", encoding="utf-8")
        (self.workspace() / "CLAUDE.md").write_text(
            "# обвязка target'а\n", encoding="utf-8")

        checks = self.run_all_checks()

        matches = self._wrapper_warnings(checks)
        self.assertTrue(
            matches,
            "doctor не сообщил про обнаруженную агентскую обвязку "
            "(.claude/.mcp.json/CLAUDE.md) target'а sled — SPEC T069 "
            "AC-3; полученные проверки: " +
            "; ".join(f"{c.name}={c.status}:{c.detail}" for c in checks))

    def test_ac3_no_wrapper_is_ok_and_nothing_is_blocked(self):
        checks = self.run_all_checks()

        matches = self._wrapper_warnings(checks)
        self.assertEqual(
            matches, [],
            "doctor сообщил про обвязку target'а sled, которой в его "
            "workspace нет — SPEC T069 AC-3 (ложный warn на чистом "
            f"target'е): {matches}")
        self.assertFalse(
            any(c.status == "fail" for c in checks
                if any(marker in c.detail for marker in WRAPPER_MARKERS)),
            "новая проверка обвязки target'а блокирует ('fail') — SPEC "
            "T069 требование 3 явно требует информационный warn/ok, "
            "'ничего не блокирует'")


if __name__ == "__main__":
    unittest.main()
