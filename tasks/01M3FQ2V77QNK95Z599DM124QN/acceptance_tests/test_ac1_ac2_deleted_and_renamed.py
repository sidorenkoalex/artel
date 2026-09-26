"""AC-1 и AC-2 (tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md): удалённый файл
тестов и переименованный файл тестов отказывают переходу
in_dev -> verifying, и переименование распознаётся ответом git
(`git diff -M --name-status`), а не совпадением имён тестовых методов.

Красен до реализации: обёртки `_test_integrity_gate_refuses` в
`orchestrator/fsm_advance.py` (требование 6) ещё нет — вызов падает
`AttributeError` на первом же сценарии.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (MOVABLE_WITHOUT_THIRD_METHOD, REFUSAL_ACTION,  # noqa: E402
                      TestIntegritySandbox)


class DeletedTestFileTest(TestIntegritySandbox):

    def test_ac1_deleted_test_file_refuses_and_detail_names_the_path(self):
        """Ветка удаляет `tests/test_doomed.py`, у которого в base два
        тестовых метода: гейт обязан отказать именованным действием и
        назвать в detail путь удалённого файла и сам факт удаления.

        Ловит мутацию: класс находки (а) — «в base есть, в head нет» —
        собирается из пересечения путей base и head вместо разности
        (перепутанное условие принадлежности), и удаление файла
        проходит гейт молча ровно так же, как оно проходит сегодня
        гейт заявки мутации (`test_file_deleted_in_head_is_skipped`).
        """
        self.remove("tests/test_doomed.py")
        self.commit()

        outcome = self.run_gate()

        self.assertTrue(outcome.refused,
                        f"гейт обязан отказать; журнал: {outcome.journal}")
        self.assertIn(
            REFUSAL_ACTION, [action for action, _ in outcome.steps],
            f"действие отказа названо не так, как требует AC-1; "
            f"журнал: {outcome.journal}")
        self.assertIn("tests/test_doomed.py", outcome.detail)
        self.assertIn("удалён", outcome.detail)


class RenamedTestFileTest(TestIntegritySandbox):

    def test_ac2_renamed_test_file_refuses_naming_both_paths(self):
        """Ветка переименовывает `tests/test_movable.py` в
        `tests/test_renamed.py` без правки содержимого: гейт отказывает,
        detail несёт оба пути в форме «<старый>: переименован в <новый>».

        Ловит мутацию: пара удалён/добавлен не сворачивается в одну
        находку — переименование докладывается как удаление старого пути
        (и молчание о новом), из-за чего Оператор на гейте читает отказ,
        не отличимый от настоящей потери тестов, и текст AC-2 в detail
        не появляется вовсе.
        """
        self.move("tests/test_movable.py", "tests/test_renamed.py")
        self.commit()

        outcome = self.run_gate()

        self.assertTrue(outcome.refused,
                        f"гейт обязан отказать; журнал: {outcome.journal}")
        self.assertIn(
            "tests/test_movable.py: переименован в tests/test_renamed.py",
            outcome.detail,
            f"detail обязан назвать оба пути формой AC-2; detail: "
            f"{outcome.detail}")

    def test_ac2_rename_with_dropped_method_gives_both_findings(self):
        """Переименование, ОДНОВРЕМЕННОЕ с удалением одного тестового
        метода: находок две — переименование (пара распознана git'ом) и
        исчезнувший метод (сравнение СТАРОГО пути в base против НОВОГО в
        head, требование 3).

        Это же — разделитель между `git diff -M --name-status` и
        эвристикой «пара удалён/добавлен с совпадающим набором имён
        тестовых методов»: наборы имён здесь РАЗНЫЕ (`test_movable_three`
        удалён), поэтому эвристика показала бы удаление старого файла
        плюс новый файл и обеих находок AC-2/AC-3 не дала бы.

        Ловит мутацию: распознавание переименования реализовано
        эвристикой совпадения имён методов вместо нового примитива
        чтения `git diff -M --name-status` — на этом диффе фраза
        «переименован в» из detail пропадает.
        """
        self.move("tests/test_movable.py", "tests/test_renamed.py")
        self.write("tests/test_renamed.py", MOVABLE_WITHOUT_THIRD_METHOD)
        self.commit()

        outcome = self.run_gate()

        self.assertTrue(outcome.refused,
                        f"гейт обязан отказать; журнал: {outcome.journal}")
        self.assertIn(
            "tests/test_movable.py: переименован в tests/test_renamed.py",
            outcome.detail,
            f"переименование с правкой тела обязано остаться "
            f"переименованием (git -M, требование 3); detail: "
            f"{outcome.detail}")
        self.assertIn(
            "test_movable_three", outcome.detail,
            f"исчезнувший при переименовании метод — вторая находка "
            f"(требование 3, последняя фраза); detail: {outcome.detail}")


if __name__ == "__main__":
    unittest.main()
