"""Приёмочный тест AC-13 (tasks/01M1RDCEF0JZ4AVQRE43JFH8TN/SPEC.md,
«Критерии приёмки»).

AC-13. `doctor` выдаёт WARN с перечнем отличающихся файлов, если
развёрнутый `.artel/home/.claude/` отличается от референса
`docs/reference/role-home/claude/`; расхождение проверяется на
временном каталоге (не на реальном `.artel/home`), автоправки нет.

Красен до реализации: `orchestrator.doctor` сегодня не содержит такой
проверки вообще — импорт `doctor.check_role_home_reference` падает
`AttributeError` уже на первой строке каждого теста ниже.

Предположение об интерфейсе (решение test_author): проверка — функция
`orchestrator.doctor.check_role_home_reference()` без аргументов,
возвращающая один `Check` (namedtuple `name, status, detail`, тот же
тип, что и у всех остальных проверок doctor) — по образцу
`check_cli_found()`/`check_target_layout()`. Сравнивает
`config.ROLE_CONFIG_DIR` (развёрнутый слой) с `config.ROOT / "docs" /
"reference" / "role-home" / "claude"` (референс) — та же пара путей,
что уже использует `catalog._deploy_role_home_reference` для
РАЗВЁРТЫВАНИЯ (здесь — для СВЕРКИ постфактум).

«Проверяется на временном каталоге, не на реальном `.artel/home`»
(требование AC-13) — обеспечено `TmpRootTest`: `ROLE_HOME`/
`ROLE_CONFIG_DIR` патчатся на временный путь, а `ROOT` НЕ патчится
(`PATCHED_ATTRS` сужен ниже) — референс читается с настоящего дерева
репозитория (он read-only материал, не эфемерное состояние), а
«развёрнутый» слой — тот самый временный каталог, который тест сам
наполняет.
"""
import shutil
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, doctor  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class _RoleHomeReferenceDiffTest(TmpRootTest):
    """Сужение `TmpRootTest`: только `ROLE_HOME`/`ROLE_CONFIG_DIR` во
    временном каталоге — `ROOT` остаётся настоящим деревом репозитория,
    чтобы референс `docs/reference/role-home/claude/` читался реальным,
    без необходимости копировать его в песочницу самим тестом."""

    PATCHED_ATTRS = ("ROLE_HOME", "ROLE_CONFIG_DIR")

    def setUp(self):
        super().setUp()
        self.reference = config.ROOT / "docs" / "reference" / "role-home" / "claude"
        self.assertTrue(self.reference.is_dir(),
                        "референс должен существовать на реальном дереве репозитория")

    def _deploy_reference_copy(self) -> None:
        shutil.copytree(self.reference, config.ROLE_CONFIG_DIR)


class DeployedLayerMatchingReferenceTest(_RoleHomeReferenceDiffTest):

    def test_ac13_matching_deploy_is_not_warn(self):
        """Развёрнутый слой, побайтово совпадающий с референсом, не
        даёт WARN.

        Ловит мутацию: сравнение, которое всегда возвращает `warn`
        (например, по самому факту существования каталога, а не по
        реальному различию) — тест ловит ложное срабатывание.
        """
        self._deploy_reference_copy()

        check = doctor.check_role_home_reference()

        self.assertNotEqual(check.status, "warn",
                            f"ложный WARN на совпадающем слое: {check.detail}")


class DivergedLayerIsFlaggedTest(_RoleHomeReferenceDiffTest):

    def setUp(self):
        super().setUp()
        self._deploy_reference_copy()
        self.diverged_file = config.ROLE_CONFIG_DIR / "CLAUDE.md"
        original = self.diverged_file.read_text(encoding="utf-8")
        self.tampered_content = original + "\nлишняя строка, внесённая руками Оператора\n"
        self.diverged_file.write_text(self.tampered_content, encoding="utf-8")

    def test_ac13_diverged_file_produces_warn_naming_it(self):
        """Отличие одного файла от референса — статус WARN, а причина
        называет ИМЕННО этот файл (не общий текст «что-то не так»).

        Ловит мутацию: сравнение только по составу имён файлов (без
        сверки содержимого) не заметит правку существующего файла —
        `status` остался бы не `warn`.
        """
        check = doctor.check_role_home_reference()

        self.assertEqual(check.status, "warn")
        self.assertIn("CLAUDE.md", check.detail,
                      f"причина не называет отличающийся файл: {check.detail}")

    def test_ac13_no_autofix_leaves_the_divergence_on_disk(self):
        """Проверка не чинит расхождение сама — файл остаётся
        изменённым после вызова.

        Ловит мутацию: проверка, которая заодно перезаписывает
        разошедшийся файл обратно референсом («заботливая» автоправка,
        прямо запрещённая требованием 5 SPEC) — `assertEqual` ниже не
        увидит `tampered_content`.
        """
        doctor.check_role_home_reference()

        self.assertEqual(self.diverged_file.read_text(encoding="utf-8"),
                         self.tampered_content)


if __name__ == "__main__":
    unittest.main()
