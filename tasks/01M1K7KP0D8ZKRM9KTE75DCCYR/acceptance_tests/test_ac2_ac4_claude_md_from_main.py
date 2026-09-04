"""AC-2, AC-4 (tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/SPEC.md): `CLAUDE.md`,
включаемый в бриф роли developer, читается ветко-корректным чтением через
git с головы ветки `main` пульта, а не с диска рабочей копии `config.
ROOT`; журнал шага несёт sha256-fingerprint этого компонента ТОЙ ЖЕ
механикой, что и до этой задачи (`brief._manifest_component`, действие
журнала «бриф: компонент»), и значение fingerprint соответствует
фактически прочитанному содержимому (main-версии), а не диску.

Красен до реализации: `orchestrator/brief.py::developer_brief` (на момент
написания) читает `CLAUDE.md` буквальным `(config.ROOT / CONVENTIONS_REL
).read_text(...)` — содержимым ДИСКА текущего чекаута, не через
`gitcmd.show(config.MAIN_BRANCH, ...)`; журналируемый sha256 поэтому
совпадает с диском, а не с main, когда они расходятся (проверено прогоном
стаб-сценария AC-2/AC-4 против сегодняшнего кода).

`brief.developer_brief` вызывается напрямую (не через `runner.cmd_run`
целиком) — она уже сама решает вопрос «своя/чужая ветка» через
`gitcmd.on_foreign_branch` (см. `orchestrator/artifact_source.py`), и
для CLAUDE.md не нужен полный прогон агента с подменённым `spawn_agent`.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import TaskSandbox, claude_md_marker  # noqa: E402
from orchestrator import brief, context_package, store  # noqa: E402

UNCOMMITTED_CLAUDE_MD = "# Конвенции\n\nМАРКЕР-КОНВЕНЦИЙ-НЕЗАКОММИЧЕНО\n"


class ClaudeMdReadFromMainTest(TaskSandbox):

    def _apply_uncommitted_edit(self) -> None:
        (self.root / "CLAUDE.md").write_text(UNCOMMITTED_CLAUDE_MD,
                                             encoding="utf-8")

    def test_ac2_claude_md_uncommitted_disk_edit_is_ignored(self):
        """`CLAUDE.md` на диске `config.ROOT` правится БЕЗ коммита — бриф
        разработчика обязан нести последнюю ЗАКОММИЧЕННУЮ в main версию,
        не незакоммиченную правку диска.

        Ловит мутацию: если `developer_brief` читает `config.ROOT /
        CONVENTIONS_REL` через `.read_text()` вместо `gitcmd.show(config.
        MAIN_BRANCH, "CLAUDE.md")`, бриф унесёт незакоммиченную правку —
        тест увидит «НЕЗАКОММИЧЕНО» вместо «V1» и покраснеет.
        """
        self._apply_uncommitted_edit()

        text = brief.developer_brief(store.db(), self.TASK)

        self.assertIn(
            "МАРКЕР-КОНВЕНЦИЙ-V1", text,
            "бриф обязан нести последнюю ЗАКОММИЧЕННУЮ в main версию "
            "CLAUDE.md (SPEC AC-2)")
        self.assertNotIn(
            "НЕЗАКОММИЧЕНО", text,
            "бриф не должен нести незакоммиченную правку диска — CLAUDE."
            "md читается через git, а не через диск текущего чекаута "
            "(SPEC AC-2)")

    def test_ac4_claude_md_journal_fingerprint_matches_main_content_not_disk(self):
        """Тот же незакоммиченный сценарий, что AC-2 — журнал бриф-шага
        обязан нести sha256 фактически прочитанной ЗАКОММИЧЕННОЙ версии
        CLAUDE.md, той же механикой, что и до этой задачи (действие
        журнала «бриф: компонент», формат «<label>: sha256=<hex>» —
        `brief._journal_component`/`_manifest_component`).

        Ловит мутацию: если fingerprint считается по содержимому диска
        (незакоммиченная правка), ожидаемый sha256 main-версии не
        встретится в записи журнала про CLAUDE.md — механика останется
        прежней (запись есть), но значение будет неверным.
        """
        self._apply_uncommitted_edit()
        expected_sha = context_package.sha256_of(claude_md_marker("V1"))

        brief.developer_brief(store.db(), self.TASK)
        details = self.journal_details("бриф: компонент")
        claude_entries = [d for d in details if "CLAUDE.md" in d]

        self.assertTrue(
            claude_entries,
            f"журнал обязан нести запись «бриф: компонент» про CLAUDE.md "
            f"(SPEC AC-4, та же механика, что и до задачи); журнал: "
            f"{details}")
        self.assertTrue(
            any(f"sha256={expected_sha}" in d for d in claude_entries),
            "sha256 в журнале обязан соответствовать фактически "
            "прочитанной main-версии CLAUDE.md, не диску (SPEC AC-4); "
            f"записи: {claude_entries}")


if __name__ == "__main__":
    unittest.main()
