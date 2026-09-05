"""AC-9, AC-10, AC-11 (SPEC.md, требование 4) — манифест
`canary/guids.txt`: список canary-GUID шаблонов пула, лежит в
репозитории открыто, обновляется `pool-seal`, набор GUID совпадает с
набором шаблонов на момент последнего seal, значения — случайные
строки, не содержимое шаблонов.

О значениях GUID (AC-10) этот файл проверяет ровно то, что формулировка
критерия утверждает буквально — «не несущие содержимого шаблонов»,
то есть отсутствие УТЕЧКИ тела шаблона в открытый манифест. Саму
«случайность» строк (энтропию) единственным прогоном юнит-теста
проверить нельзя в принципе (это свойство генератора, не одного
значения) — SPEC не просит статистической проверки, только отсутствия
содержимого; читать это шире значило бы придумывать не написанный в
AC-10 тест.

Красен до реализации: `pool-seal` не существует (см. `test_pool_seal.py`)
— `canary/guids.txt` не появляется, все три теста падают на
`assertTrue(self.guids_path.exists())`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PoolBaseSandbox  # noqa: E402


def _manifest_lines(path: Path) -> list:
    if not path.exists():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").splitlines()
           if ln.strip()]


class PoolGuidManifestTest(PoolBaseSandbox):

    def test_ac9_pool_seal_writes_guid_manifest_open_in_the_repo(self):
        """После `pool-seal` `canary/guids.txt` существует в репозитории
        пульта (не в зашифрованном виде — читается как обычный текстовый
        файл) и несёт по одной записи на каждый шаблон пула.

        Ловит мутацию: разработчик обновляет только `pool.sealed`, забыв
        завести манифест (требование 4 явно требует ОБА артефакта) —
        `assertTrue` по существованию файла падает.
        """
        self.write_pool_templates({
            "a.md": "тело А\n", "b.md": "тело Б\n", "c.md": "тело В\n"})
        output = self.seal()

        self.assertTrue(
            self.guids_path.exists(),
            f"canary/guids.txt не создан после pool-seal: {output!r}")
        lines = _manifest_lines(self.guids_path)
        self.assertEqual(
            len(lines), 3,
            f"canary/guids.txt несёт {len(lines)} записей вместо 3 "
            f"(по числу шаблонов пула): {lines}")

    def test_ac10_guid_values_do_not_leak_template_body_content(self):
        """Ни одна строка манифеста не содержит подстроку тела ни
        одного шаблона пула — значения манифеста не несут содержимого
        шаблонов (требование 4, AC-10 буквально), а не, например, сам
        текст шаблона или его имя файла.

        Ловит мутацию: разработчик кладёт в манифест сам текст шаблона
        (или его имя файла) вместо отдельного GUID-значения — один из
        `assertNotIn` ниже находит утечку.
        """
        secret_bodies = {
            "a.md": "секрет-тела-шаблона-А-9f81c2\n",
            "b.md": "секрет-тела-шаблона-Б-3e7d40\n",
        }
        self.write_pool_templates(secret_bodies)
        self.seal()

        self.assertTrue(
            self.guids_path.exists(),
            "canary/guids.txt не создан после pool-seal — нечего "
            "проверять на утечку содержимого")
        manifest_text = self.guids_path.read_text(encoding="utf-8")
        for name, body in secret_bodies.items():
            secret = body.strip()
            self.assertNotIn(
                secret, manifest_text,
                f"canary/guids.txt несёт содержимое тела шаблона {name}: "
                f"{secret!r}")
            self.assertNotIn(
                name, manifest_text,
                f"canary/guids.txt несёт имя файла шаблона {name} вместо "
                f"GUID-значения")

    def test_ac11_manifest_guid_set_tracks_current_pool_after_reseal(self):
        """Число записей манифеста меняется вместе с составом пула на
        каждом `pool-seal`: добавили шаблон — записей на одну больше,
        убрали — на одну меньше; манифест не накапливает записи ушедших
        шаблонов и не остаётся от предыдущего прогона.

        Ловит мутацию: `pool-seal` ДОПИСЫВАЕТ манифест вместо того,
        чтобы перезаписать его набором ТЕКУЩИХ шаблонов, — после
        удаления шаблона число записей осталось бы прежним вместо
        уменьшения.
        """
        self.write_pool_templates({"a.md": "тело А\n", "b.md": "тело Б\n"})
        self.seal()
        baseline = len(_manifest_lines(self.guids_path))
        self.assertEqual(baseline, 2)

        self.write_pool_templates({"c.md": "тело В\n"})
        self.seal()
        after_add = len(_manifest_lines(self.guids_path))
        self.assertEqual(
            after_add, 3,
            f"после добавления шаблона в манифесте {after_add} записей, "
            f"ожидалось 3 (2 старых + 1 новый)")

        (self.pool_dir / "a.md").unlink()
        self.seal()
        after_remove = len(_manifest_lines(self.guids_path))
        self.assertEqual(
            after_remove, 2,
            f"после удаления шаблона в манифесте {after_remove} записей, "
            f"ожидалось 2 (набор не совпадает с текущим пулом — AC-11)")


if __name__ == "__main__":
    unittest.main()
