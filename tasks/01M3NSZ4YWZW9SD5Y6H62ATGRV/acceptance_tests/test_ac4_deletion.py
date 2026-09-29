"""AC-4: удаление файла перечня в worktree — перенос без ослабления
проходит (путь выпадает из нового перечня), потеря метода — отказ без
записей с именем файла и метода.

Планка вложенной задачи покрывает AC-1 и AC-2 сама, так что удаление
долгоживущего файла трассируемость не ломает — отказ, если он есть,
принадлежит только правилу удаления.

Группа: разовый
Красен до реализации: `amend.cmd_amend_tests` считает удаление пути в tests/ изменением «за пределами» каталога приёмочных тестов и отказывает переносу, а отказ не называет потерянный метод.

Почему разовый: сценарий строит ветку документов через `artifact_branch`
и адресует `tasks/<id>/acceptance_tests/` — признаки, запрещённые
долгоживущему файлу; долгоживущие тесты — требование 9 SPEC.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AmendSandbox, failed, plank_source  # noqa: E402

MOVED_PLANK = plank_source(("test_ac2_long_fixture",))


class DeletionTest(AmendSandbox):

    PLANK_COVERS_AC2 = True

    def test_ac4_moved_to_plank_drops_from_manifest(self):
        """Оператор удаляет долгоживущий файл из worktree и переносит его
        метод `test_ac2_long_fixture` в `acceptance_tests/` разовым файлом.

        Команда проходит: на голове кодовой ветки пути больше нет, новый
        перечень лока его не несёт, лок — на голове ветки документов, в
        ней — перенесённый файл; сверка сумм не отказывает.

        Ловит мутацию: новый перечень строится как старый плюс изменённые
        пути (удалённый путь в нём остаётся) — сверка сумм на следующем
        переходе отказывает «удалён».
        """
        self.materialize_plank()
        (self.wt / self.own).unlink()
        self.write_wt(f"tasks/{self.TASK}/acceptance_tests/test_moved.py",
                      MOVED_PLANK)

        code, out = self.amend("перенос долгоживущего теста в разовую группу")

        self.assertFalse(failed(code), out)
        code_head, docs_head, lock = self.heads()
        self.assertNotIn(self.own, self.long_lived_paths_at(code_head),
                         "удаление обязано быть закоммичено в кодовую ветку")
        self.assertEqual(lock, docs_head)
        self.assertNotIn(self.own, self.manifest_at(lock) or "",
                         "удалённый путь не имеет права остаться в перечне лока")
        self.assertEqual(self.manifest_at(lock), self.expected_manifest(code_head))
        self.assertEqual(self.plank_file_at(docs_head, "test_moved.py"),
                         MOVED_PLANK)
        refused, text = self.manifest_check_refuses()
        self.assertFalse(refused, text)

    def test_ac4_lost_method_refused_without_writes(self):
        """Оператор удаляет долгоживущий файл, не перенося его метод никуда
        — отказ, называющий файл и метод `test_ac2_long_fixture`; головы
        обеих веток и лок прежние.

        Ловит мутацию: правило удаления не сверяет методы удаляемого файла
        с итоговой планкой (или сверяет только трассируемость AC) —
        удаление коммитится, и тест тихо снят правкой планки.
        """
        before = self.heads()
        (self.wt / self.own).unlink()

        code, out = self.amend("снятие долгоживущего теста")

        self.assertTrue(failed(code), f"отказа нет: {out}")
        self.assertIn(self.own.rsplit("/", 1)[-1], out)
        self.assertIn("test_ac2_long_fixture", out)
        self.assertEqual(self.heads(), before)


if __name__ == "__main__":
    unittest.main()
