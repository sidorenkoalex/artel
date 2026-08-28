"""AC-5 (tasks/T049/SPEC.md): `init` разворачивает `.artel/home` из
референса пульта.

«При отсутствии `.artel/home` команда `init` разворачивает слой ролей из
референса, сохранённого в репозитории пульта.»

Требование 8 SPEC сознательно оставляет КОНКРЕТНОЕ место референса на
усмотрение PLAN разработчика («предлагает разработчик в PLAN») — тест не
имеет права угадывать путь, которого сам SPEC не называет. Поэтому
песочница (`_sandbox.FullRepoCopyRootTest`) копирует не один
предполагаемый путь, а всё дерево пульта: какое бы место ни выбрал
разработчик, оно попадёт в песочницу вместе с остальным кодом, и тест
остаётся написанным ТОЛЬКО из формулировки критерия, а не из
предположения о реализации.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config  # noqa: E402
from _sandbox import FullRepoCopyRootTest, capture  # noqa: E402


class RoleHomeSeedTest(FullRepoCopyRootTest):

    def test_ac5_init_deploys_role_home_layer_from_repo_reference_when_missing(self):
        self.assertFalse(
            config.ROLE_HOME.exists(),
            "предпосылка теста нарушена: .artel/home уже существует до init")

        capture(catalog.cmd_init)

        self.assertTrue(
            config.ROLE_HOME.is_dir(),
            "init не развернул .artel/home при его отсутствии (AC-5)")
        deployed_files = [p for p in config.ROLE_HOME.rglob("*") if p.is_file()]
        self.assertTrue(
            deployed_files,
            ".artel/home создан пустым каталогом — критерий требует "
            "развёрнутый слой ролей (структура + содержимое), не просто "
            "mkdir")


if __name__ == "__main__":
    unittest.main()
