"""AC-5: сбой записи в ветку документов после коммита в кодовую ветку и
путь восстановления `amend-tests <id> --from-branch --reason …`.

Сбой — подмена плотницкой записи `artifact_branch.write_commit` отказом
для путей под `tasks/<id>/` (запись в ветку документов); коммит кодовой
ветки идёт настоящим git.

Группа: разовый
Красен до реализации: `amend.cmd_amend_tests` не пишет в кодовую ветку, а `--from-branch` видит только расхождение acceptance_tests/ ветки документов — расхождение долгоживущих путей кодовой ветки с перечнем лока для него «нет расхождения».

Почему разовый: сценарий строит ветку документов через `artifact_branch`
и адресует `tasks/<id>/acceptance_tests/` — признаки, запрещённые
долгоживущему файлу; долгоживущие тесты — требование 9 SPEC.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AmendSandbox, MANIFEST_NAME, failed,  # noqa: E402
                      long_lived_source)
from scripts import guard  # noqa: E402


class FromBranchRecoveryTest(AmendSandbox):

    def assert_relocked_to_code_head(self) -> None:
        code_head, docs_head, lock = self.heads()
        self.assertEqual(lock, docs_head,
                         "лок обязан указывать на голову ветки документов")
        self.assertEqual(self.manifest_at(lock), self.expected_manifest(code_head),
                         "перечень нового лока обязан совпасть с суммами головы "
                         "кодовой ветки")
        refused, text = self.manifest_check_refuses()
        self.assertFalse(refused, f"сверка сумм после восстановления: {text}")

    def test_ac5_docs_write_failure_then_from_branch_recovers(self):
        """Правка долгоживущего файла в worktree; запись в ветку документов
        не удаётся после коммита в кодовую ветку.

        Команда — ненулевой код, сообщение называет `amend-tests <id>
        --from-branch`; лок прежний; сверка сумм отказывает. Затем
        `--from-branch` проходит: перечень лока — суммы головы кодовой
        ветки, лок сдвинут, сверка сумм проходит.

        Ловит мутацию: `--from-branch` сравнивает только каталог
        acceptance_tests/ лока и головы ветки документов — после сбоя
        расхождения там нет, восстановление отказывает «нет расхождения»,
        и задача застревает на отказе сверки сумм.
        """
        code_before, _docs_before, lock_before = self.heads()
        self.write_wt(self.own, long_lived_source(tail="# правка Оператора\n"))

        with self.docs_branch_write_fails():
            code, out = self.amend()

        self.assertTrue(failed(code), f"сбой записи обязан дать ненулевой код: {out}")
        self.assertIn(f"amend-tests {self.TASK} --from-branch", out)
        code_head, _docs_head, lock = self.heads()
        self.assertNotEqual(code_head, code_before,
                            "предпосылка: запись в кодовую ветку прошла")
        self.assertEqual(lock, lock_before, "лок не имеет права сдвинуться")
        refused, _text = self.manifest_check_refuses()
        self.assertTrue(refused, "сверка сумм обязана отказать честно")

        code, out = self.amend_from_branch()

        self.assertFalse(failed(code), out)
        self.assertNotEqual(self.heads()[2], lock_before)
        self.assert_relocked_to_code_head()

    def test_ac5_from_branch_violating_divergence_refused_without_writes(self):
        """На голове кодовой ветки — закоммиченный долгоживущий файл без
        строки группы; `--from-branch` — отказ, головы и лок прежние.

        Ловит мутацию: `--from-branch` при расхождении долгоживущих путей
        пересчитывает перечень и сдвигает лок, не применив проверки
        требования 1.
        """
        self.wt_commit({self.own: long_lived_source(group=None)})
        before = self.heads()

        code, out = self.amend_from_branch()

        self.assertTrue(failed(code), f"отказа нет: {out}")
        self.assertEqual(self.heads(), before)

    def test_ac5_bypass_manifest_replaced_by_recomputed(self):
        """Кодовая ветка несёт годную правку долгоживущего файла, а в ветку
        документов в обход команды закоммичен перечень с чужой суммой;
        `--from-branch` проходит, и в дерево нового лока попадает
        пересчитанный перечень, а не закоммиченный в обход.

        Ловит мутацию: `--from-branch` сдвигает лок на голову ветки
        документов как есть (прежнее поведение) — в лок уезжает перечень
        с чужой суммой, и сверка сумм отказывает.
        """
        self.wt_commit({self.own: long_lived_source(tail="# годная правка\n")})
        bypass = guard.render_long_lived_manifest({self.own: "0" * 64})
        self.artifact_commit({f"acceptance_tests/{MANIFEST_NAME}": bypass},
                             "перечень в обход команды")

        code, out = self.amend_from_branch()

        self.assertFalse(failed(code), out)
        self.assertNotEqual(self.manifest_at(self.heads()[2]), bypass)
        self.assert_relocked_to_code_head()


if __name__ == "__main__":
    unittest.main()
