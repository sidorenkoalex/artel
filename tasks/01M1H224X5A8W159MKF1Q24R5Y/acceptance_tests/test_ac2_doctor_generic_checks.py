"""AC-2: `doctor.check_target_layout`, `check_target_wrapper`,
`check_remote_empty`, `check_base_branch` для `target == "artel"` проверяют
`.artel/projects/artel/` и возвращают тот же класс результата (ok/warn/fail
по тому же основанию), что и для любого другого объявленного в
`targets.yaml` target — без ветки вида `if target == config.DEFAULT_TARGET:
return Check(..., "skip"/"ok", "догфуд...")`.

Красен до реализации: сегодня все четыре функции несут буквально такую
ветку (`orchestrator/doctor.py`, строки ~178, ~205, ~827, ~843) — каждый
тест ниже сравнивает результат для `target="artel"` с результатом для
`target="sled"` при ИДЕНТИЧНОМ состоянии диска (оба каталога заведены/не
заведены одинаково через `projects.cmd_target_init`) и падает именно
потому, что сегодня 'artel' получает особый (ok/skip с текстом «догфуд»),
а 'sled' — общий путь.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, doctor, projects  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

OTHER_TARGET = "sled"


class DoctorTargetParityTest(TmpRootTest):
    """`target="artel"` и `target="sled"` — под ОДНИМ и тем же кодом
    doctor-проверок, при одинаковом состоянии диска дают одинаковый класс
    результата."""

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(
            "targets:\n"
            "  artel:\n"
            "    forge: github\n"
            "    url: https://example.invalid/artel\n"
            "    base: main\n"
            "    token_slot: artel-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n"
            f"  {OTHER_TARGET}:\n"
            "    forge: github\n"
            f"    url: https://example.invalid/{OTHER_TARGET}\n"
            "    base: main\n"
            f"    token_slot: {OTHER_TARGET}-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n",
            encoding="utf-8")

    def entry(self, url: str) -> dict:
        return {"forge": "github", "url": url, "base": "main",
               "token_slot": "x-token", "no_paths": [], "project_skills": [],
               "merge_gate": "operator"}

    def test_ac2_target_layout_no_special_case_when_repo_missing(self):
        """Ни `artel`, ни `sled` не подключены (`target-init` не вызван) —
        `check_target_layout` обязана вернуть ОДИНАКОВЫЙ статус для обоих
        (сегодня: warn у 'sled' про неинициализированный репо, ok у
        'artel' с текстом «догфуд»), и текст не должен содержать «догфуд».

        Ловит мутацию: строку `if target == config.DEFAULT_TARGET: return
        Check(..., "ok", "догфуд...")` в начале `check_target_layout`.
        """
        artel_check = doctor.check_target_layout(config.DEFAULT_TARGET)
        other_check = doctor.check_target_layout(OTHER_TARGET)

        self.assertEqual(artel_check.status, other_check.status)
        self.assertNotIn("догфуд", artel_check.detail.lower())

    def test_ac2_target_layout_no_special_case_when_repo_present(self):
        """Оба каталога заведены (`projects.cmd_target_init`) — оба
        `target-layout` обязаны вернуть "ok" по ОДНОМУ основанию
        («артефактный репо на месте»), не разными текстами."""
        projects.cmd_target_init(config.DEFAULT_TARGET)
        projects.cmd_target_init(OTHER_TARGET)

        artel_check = doctor.check_target_layout(config.DEFAULT_TARGET)
        other_check = doctor.check_target_layout(OTHER_TARGET)

        self.assertEqual(artel_check.status, "ok")
        self.assertEqual(other_check.status, "ok")
        self.assertEqual(artel_check.detail, other_check.detail)

    def test_ac2_target_wrapper_no_special_case(self):
        """`check_target_wrapper` для 'artel' сканирует
        `.artel/projects/artel/workspace` (тем же кодом, что 'sled'), а не
        возвращает безусловный `skip` «догфуд — не внешний target».

        Ловит мутацию: строку `if target == config.DEFAULT_TARGET: return
        Check(..., "skip", "догфуд...")` в начале `check_target_wrapper`.
        """
        for target in (config.DEFAULT_TARGET, OTHER_TARGET):
            ws = config.PROJECTS / target / "workspace"
            ws.mkdir(parents=True)
            (ws / "CLAUDE.md").write_text("маркер обвязки\n", encoding="utf-8")

        artel_check = doctor.check_target_wrapper(config.DEFAULT_TARGET)
        other_check = doctor.check_target_wrapper(OTHER_TARGET)

        self.assertEqual(artel_check.status, other_check.status)
        self.assertEqual(artel_check.status, "warn",
                         "обвязка (CLAUDE.md) обнаружена — обе проверки "
                         "обязаны предупредить")
        self.assertNotIn("догфуд", artel_check.detail.lower())

    def test_ac2_remote_empty_no_special_case(self):
        """`check_remote_empty` для 'artel' реально сверяет `git remote`
        артефактного репо (тем же кодом, что 'sled'), а не возвращает
        безусловный `skip` «догфуд — remote есть, это GitHub пульта».

        Ловит мутацию: строку `if target == config.DEFAULT_TARGET: return
        Check(..., "skip", "догфуд...")` в начале `check_remote_empty`.
        """
        projects.cmd_target_init(config.DEFAULT_TARGET)
        projects.cmd_target_init(OTHER_TARGET)

        artel_check = doctor.check_remote_empty(config.DEFAULT_TARGET)
        other_check = doctor.check_remote_empty(OTHER_TARGET)

        self.assertEqual(artel_check.status, "ok")
        self.assertEqual(other_check.status, "ok")
        self.assertEqual(artel_check.detail, other_check.detail)
        self.assertNotIn("догфуд", artel_check.detail.lower())

    def test_ac2_base_branch_no_special_case(self):
        """`check_base_branch("artel", entry)` без доступного `gh` в PATH
        деградирует к тому же честному `skip` «gh CLI не найден», что и
        для 'sled' — не к безусловному `skip` «догфуд — особый случай».

        Ловит мутацию: строку `if name == config.DEFAULT_TARGET: return
        Check(..., "skip", "догфуд...")` в начале `check_base_branch`.
        """
        with mock.patch.object(shutil, "which", lambda cmd: None):
            artel_check = doctor.check_base_branch(
                config.DEFAULT_TARGET, self.entry("https://example.invalid/artel"))
            other_check = doctor.check_base_branch(
                OTHER_TARGET, self.entry("https://example.invalid/sled"))

        self.assertEqual(artel_check.status, other_check.status)
        self.assertEqual(artel_check.status, "skip")
        self.assertIn("gh", artel_check.detail.lower())
        self.assertNotIn("догфуд", artel_check.detail.lower())


if __name__ == "__main__":
    unittest.main()
