"""AC-16 (SPEC.md) — полный цикл «seal → удаление `~/.artel-canary` →
restore» восстанавливает тот же набор файлов пула, что и до seal, по
отпечатку содержимого.

Единственный тест этого файла объединяет то, что `test_pool_seal.py` и
`test_pool_restore.py` проверяют по отдельности (сама сериализация,
сама расшифровка) — здесь же под контролем ДВА independent-от-реализации
отпечатка (`_sandbox.dir_fingerprint`, повторно считается тестом с
нуля до и после цикла, не читает отпечаток, который мог бы напечатать
сам `pool-seal`), и оба входа восстановления (`init`, `doctor
--restore`) по очереди на одном и том же запечатанном пуле.

Красен до реализации: ни `pool-seal`, ни восстановление не существуют
(см. докстринги `test_pool_seal.py`/`test_pool_restore.py`) — цикл
падает уже на первом шаге (`self.seal()` не создаёт `pool.sealed`,
дальнейшее сравнение отпечатков беспредметно, тест падает на
`assertTrue(self.pool_dir.exists())` после первого восстановления).
"""
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PoolDoctorSandbox, dir_fingerprint  # noqa: E402


class PoolSealRoundtripTest(PoolDoctorSandbox):

    def test_ac16_seal_delete_restore_cycle_recovers_the_same_pool_by_fingerprint(self):
        """Цикл прогоняется ДВАЖДЫ подряд на одном и том же
        запечатанном пуле — один раз через `init`, один раз через
        `doctor --restore` — оба обязаны восстановить БАЙТ-В-БАЙТ тот
        же набор файлов, что был запечатан.

        Ловит мутацию: расшифровка теряет файл, меняет байт содержимого
        (например, неверно отделяет тег HMAC от шифртекста или путает
        IV) или путает кодировку — `dir_fingerprint` до и после
        разойдётся на любом из двух входов.
        """
        self.write_pool_templates({
            "a.md": "# А\n\nтело шаблона А, юникод: сёмга, üñïçødé.\n",
            "b.md": "# Б\n\nтело шаблона Б.\n",
            "c.md": "# В\n\nтело шаблона В.\n",
        })
        original = dir_fingerprint(self.pool_dir)
        self.seal()

        shutil.rmtree(self.pool_dir)
        self.restore_via_init()
        self.assertTrue(
            self.pool_dir.exists(),
            "`init` не восстановил ~/.artel-canary из pool.sealed")
        self.assertEqual(
            dir_fingerprint(self.pool_dir), original,
            "цикл seal -> restore (init) не восстановил тот же набор "
            "файлов пула по отпечатку содержимого (AC-16)")

        shutil.rmtree(self.pool_dir)
        self.restore_via_doctor()
        self.assertTrue(
            self.pool_dir.exists(),
            "`doctor --restore` не восстановил ~/.artel-canary из "
            "pool.sealed")
        self.assertEqual(
            dir_fingerprint(self.pool_dir), original,
            "цикл seal -> restore (doctor --restore) не восстановил тот "
            "же набор файлов пула по отпечатку содержимого (AC-16)")


if __name__ == "__main__":
    unittest.main()
