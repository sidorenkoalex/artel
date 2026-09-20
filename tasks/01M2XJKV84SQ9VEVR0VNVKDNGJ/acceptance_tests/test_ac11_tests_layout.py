"""Приёмочные тесты AC-11 (tasks/01M2XJKV84SQ9VEVR0VNVKDNGJ/SPEC.md):
тесты сценариев AC-1..AC-10 лежат в `tests/`, названные SPEC файлы не
ослаблены, защищённый `tests/test_invariants.py` правкой не затронут.

«Остаются зелёными» и «полный прогон `tests/` — зелёный» исполняются
штатным CI-гейтом ветки задачи и автогейтом приёмки (`orchestrator/
acceptance.py::run_full_suite`) — повторный прогон всего набора отсюда
новой гарантии не даёт, только удлиняет приёмку (тот же довод, что в
`tasks/01M1SAA01YRRTWAVADT2F81RRQ/acceptance_tests/
test_existing_zone_tests_not_weakened.py`). Здесь — то, чего полный
прогон НЕ ловит: тихое удаление существующего тестового метода (ему
нечему падать), правка защищённого файла и отсутствие новых тестов в
`tests/` вовсе.

Сравнение идёт «база ветки задачи -> рабочее дерево»: на приёмке в
рабочем дереве лежит код разработчика, и диск — то же, что голова
ветки.

Красен до реализации: ни один файл `tests/` не упоминает ни
`MODEL_MIN_CLI_VERSION`, ни сигнатуру «does not support this model»
(проверено grep'ом по репозиторию на момент написания планки) — тестов
сценариев задачи в постоянном наборе ещё нет. Две остальные проверки —
сохранение (не удалять существующие методы, не трогать защищённый
файл) — зелёные с рождения и обязаны остаться зелёными.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (REPO_ROOT, merge_base_or_skip,  # noqa: E402
                      text_at, text_on_disk)
from scripts import guard  # noqa: E402

PROTECTED = "tests/test_invariants.py"
NAMED_BY_SPEC = ("tests/test_runner_role_model.py", "tests/test_stack.py",
                 "tests/test_stack_ci.py")


def method_names(text) -> set:
    return set(guard.TEST_METHOD.findall(text or ""))


def disk_test_files() -> list:
    return sorted(str(p.relative_to(REPO_ROOT))
                  for p in (REPO_ROOT / "tests").rglob("*.py"))


class TestsLayoutTest(unittest.TestCase):
    """Две проверки из трёх сверяются с базой ветки задачи (на самом
    `main` они скипаются — диффить не с чем); проверка содержимого
    `tests/` от базы не зависит и идёт всегда."""

    def test_ac11_scenarios_of_the_task_live_in_the_permanent_suite(self):
        """Сценарии задачи покрыты в `tests/`, а не только планкой,
        которая уедет вместе с каталогом задачи: набор ссылается на обе
        поверхности, заведённые задачей и названные SPEC дословно, —
        таблицу совместимости (AC-5/AC-6/AC-8/AC-10) и сигнатуру вывода
        попытки из инцидента 19.09 (AC-9).

        Проверка идёт по СОДЕРЖИМОМУ `tests/`, а не по диффу с базой
        ветки: ветка задачи штатно несёт коммиты предыдущих задач,
        которые ещё не доехали до `main`, и «в диффе есть новые тестовые
        методы» было бы зелёным без единой строки этой задачи.

        Ловит мутацию: разработчик чинит код под приёмочную планку и не
        заводит ни одного регрессионного теста в `tests/` — после уборки
        `tasks/<id>/` механика остаётся без покрытия вовсе.
        """
        suite_text = "\n".join(text_on_disk(path) or ""
                               for path in disk_test_files())

        for marker in ("MODEL_MIN_CLI_VERSION", "does not support this model"):
            with self.subTest(маркер=marker):
                # `assertTrue`, а не `assertIn`: второй печатает в отчёт
                # весь набор tests/ целиком (мегабайты) — отказ планки
                # должен читаться, а не тонуть.
                self.assertTrue(marker in suite_text,
                                f"ни один файл tests/ не ссылается на {marker}")

    def test_ac11_no_existing_test_method_of_the_named_files_is_deleted(self):
        """Ни один существующий тестовый метод файлов, названных SPEC
        («остаются зелёными»), не исчез.

        Ловит мутацию: тест, покрасневший от нового argv[0] или от новой
        строки стека (например
        `tests/test_runner_role_model.py::test_command_carries_the_model_
        flag_once_in_prior_flag_order`), удаляется вместо починки под
        новое поведение — полному прогону падать нечему.
        """
        base = merge_base_or_skip(self)
        for path in NAMED_BY_SPEC:
            with self.subTest(файл=path):
                removed = sorted(method_names(text_at(base, path))
                                 - method_names(text_on_disk(path)))
                self.assertEqual(removed, [],
                                 f"{path}: удалены тестовые методы {removed}")

    def test_ac11_protected_invariants_file_is_untouched(self):
        """`tests/test_invariants.py` на диске байт-в-байт совпадает с
        базой ветки.

        Ловит мутацию: инвариантный тест «правится» под новое поведение
        (новый класс провала без повторов задевает инвариант 3) — а это
        право Оператора через ADR, не разработчика задачи.
        """
        base = merge_base_or_skip(self)

        # Сравнение через `assertTrue`: `assertEqual` на двух версиях
        # файла печатает в отчёт их построчный дифф целиком.
        self.assertTrue(text_on_disk(PROTECTED) == text_at(base, PROTECTED),
                        f"{PROTECTED} отличается от базы ветки — защищённый "
                        f"путь, правка только Оператором через ADR")


if __name__ == "__main__":
    unittest.main()
