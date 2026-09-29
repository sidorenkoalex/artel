"""AC-1, AC-2, AC-3: `amend-tests <id> --reason …` из worktree правит
долгоживущие файлы задачи в `tests/` — успех с записью в обе ветки и
сдвигом лока, отказ проверок и отказ границ правки без единой записи.

Группа: разовый
Красен до реализации: `amend.cmd_amend_tests` знает только каталог acceptance_tests/ — правка одного долгоживущего файла получает отказ «нет изменений», а отказы не называют файл долгоживущей правки.

Почему разовый, а не долгоживущий: сценарий строит ветку документов через
`artifact_branch` и адресует `tasks/<id>/acceptance_tests/` — признаки,
запрещённые долгоживущему файлу; долгоживущие тесты этих свойств в
`tests/` — требование 9 SPEC, их пишет разработчик.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AmendSandbox, MANIFEST_NAME, failed,  # noqa: E402
                      long_lived_source)


class WorktreeAmendSuccessTest(AmendSandbox):

    def assert_relocked(self, before: tuple, paths: set[str]) -> None:
        code_old, docs_old, lock_old = before
        code_new, docs_new, lock_new = self.heads()
        self.assertNotEqual(code_new, code_old, "кодовая ветка без нового коммита")
        self.assertEqual(self.changed_paths(code_old, code_new), paths,
                         "новый коммит кодовой ветки обязан менять ровно правленые пути")
        self.assertNotEqual(docs_new, docs_old, "ветка документов без нового коммита")
        self.assertEqual(lock_new, docs_new,
                         "tests_locked_sha обязан указывать на новую голову ветки документов")
        self.assertEqual(self.manifest_at(docs_new),
                         self.expected_manifest(code_new),
                         "перечень ветки документов обязан нести суммы новой головы кодовой ветки")
        refused, text = self.manifest_check_refuses()
        self.assertFalse(refused, f"сверка сумм после правки отказывает: {text}")

    def test_ac1_modified_long_lived_file_relocked(self):
        """Оператор правит в worktree долгоживущий файл перечня (без
        коммита) и зовёт `amend-tests --reason`.

        Итог: коммит кодовой ветки ровно с этим путём, перечень в ветке
        документов с суммой нового файла, лок — на голове ветки документов,
        сверка сумм проходит.

        Ловит мутацию: перечень пересчитан по байтам worktree/старой
        головы, а не по новой голове кодовой ветки (или лок сдвинут на
        голову до коммита перечня) — перечень в дереве лока расходится с
        суммой файла, и сверка сумм отказывает.
        """
        before = self.heads()
        self.write_wt(self.own, long_lived_source(tail="# правка Оператора\n"))

        code, out = self.amend()

        self.assertFalse(failed(code), out)
        self.assert_relocked(before, {self.own})

    def test_ac1_added_long_lived_file_enters_manifest(self):
        """Вместе с правкой файла перечня Оператор добавляет новый
        `tests/test_<id>_beta.py`, проходящий проверки.

        Коммит кодовой ветки меняет ровно оба пути; новый файл — в
        перечне лока.

        Ловит мутацию: новый перечень строится только из путей старого
        перечня — добавленный файл не попадает в перечень лока и
        закоммичен в ветку без суммы.
        """
        before = self.heads()
        self.write_wt(self.own, long_lived_source(tail="# правка Оператора\n"))
        self.write_wt(self.new_path, long_lived_source("test_ac2_second_fixture"))

        code, out = self.amend()

        self.assertFalse(failed(code), out)
        self.assert_relocked(before, {self.own, self.new_path})
        self.assertIn(self.new_path, self.manifest_at(self.heads()[2]) or "")


class WorktreeAmendCheckRefusalTest(AmendSandbox):

    SCENARIOS = {
        "нет строки группы": (lambda: long_lived_source(group=None), "own"),
        "чтение tasks/": (lambda: long_lived_source(
            tail='\nDATA_DIR = "tasks/"\n'), "own"),
        "метод без «Ловит мутацию»": (lambda: long_lived_source(claim=False),
                                      "own"),
        "файл не собирается": (lambda: long_lived_source(
            tail="\ndef broken(:\n    pass\n"), "own"),
        "непромаркированное падение": (lambda: long_lived_source(rhs="3"),
                                       "own"),
        "трассируемость AC": (lambda: long_lived_source(
            "test_other_long_fixture"), "AC-2"),
    }

    def test_ac2_failed_check_refused_without_writes(self):
        """Каждая правка долгоживущего файла, нарушающая одну проверку
        (строка группы, статический признак `tasks/`, заявка мутации,
        сухой сбор, прогон, трассируемость AC — метод AC-2 переименован),
        получает отказ с именем файла (для трассируемости — с именем
        критерия); три головы — те же, что до вызова.

        Ловит мутацию: проверка перед записью снята — запись в кодовую
        ветку идёт раньше проверки либо без неё, и голова кодовой ветки
        (или ветки документов, или лок) сдвигается при отказе.
        """
        for label, (make, needle) in self.SCENARIOS.items():
            with self.subTest(scenario=label):
                self.restore_wt()
                before = self.heads()
                self.write_wt(self.own, make())

                code, out = self.amend()

                self.assertTrue(failed(code), f"{label}: отказа нет: {out}")
                expected = self.own.rsplit("/", 1)[-1] if needle == "own" else needle
                self.assertIn(expected, out, f"{label}: отказ не называет {expected}")
                self.assertEqual(self.heads(), before,
                                 f"{label}: отказ обязан оставить головы и лок на месте")


class WorktreeAmendBoundaryRefusalTest(AmendSandbox):

    def test_ac3_out_of_bounds_change_refused_without_writes(self):
        """Рядом с годной правкой долгоживущего файла в worktree лежит
        недопустимое изменение: правленый `tests/test_existing.py` (без
        префикса задачи), новый `tests/test_noprefix.py`, новый
        `docs/extra.md` — отказ с путём нарушителя, головы и лок прежние.

        Ловит мутацию: граница правки расширена на весь `tests/` (или
        посторонние пути отбрасываются молча) — чужой файл уезжает в
        коммит кодовой ветки вместе с правкой.
        """
        existing_text = (self.wt / self.EXISTING).read_text(encoding="utf-8")
        scenarios = {
            "правка файла tests/ без префикса": (
                self.EXISTING, existing_text + "# правка\n"),
            "новый файл tests/ без префикса": (
                "tests/test_noprefix.py", long_lived_source()),
            "изменение вне tests/": ("docs/extra.md", "постороннее\n"),
        }
        for label, (rel, text) in scenarios.items():
            with self.subTest(scenario=label):
                self.restore_wt()
                before = self.heads()
                self.write_wt(self.own, long_lived_source(tail="# годная правка\n"))
                self.write_wt(rel, text)

                code, out = self.amend()

                self.assertTrue(failed(code), f"{label}: отказа нет: {out}")
                self.assertIn(rel, out, f"{label}: отказ не называет {rel}")
                self.assertEqual(self.heads(), before, label)

    def test_ac3_hand_edited_manifest_refused_without_writes(self):
        """Оператор правит долгоживущий файл и сам вписывает в
        `long_lived.sha256.txt` worktree его новую (верную) сумму — отказ
        с именем файла перечня, головы и лок прежние.

        Ловит мутацию: перечень worktree принимается, если его суммы
        сходятся с файлами (или правка перечня не отличается от правки
        тестов) — ручной перечень уходит в ветку документов и лок.
        """
        self.materialize_plank()
        before = self.heads()
        self.write_wt(self.own, long_lived_source(tail="# годная правка\n"))
        manifest_rel = f"tasks/{self.TASK}/acceptance_tests/{MANIFEST_NAME}"
        self.write_wt(manifest_rel,
                      f"{self.sha256_of_wt(self.own)}  {self.own}\n")

        code, out = self.amend()

        self.assertTrue(failed(code), f"отказа нет: {out}")
        self.assertIn(MANIFEST_NAME, out)
        self.assertEqual(self.heads(), before)


if __name__ == "__main__":
    unittest.main()
