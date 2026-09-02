"""AC-3 (tasks/01M1GV6H5DDDCWW4G3GW1D3A1X/SPEC.md): идентификатор границ
генерируется заново на каждый запуск шага — идентификаторы, использованные
в двух разных запусках (в том числе повторных для одной и той же задачи
и роли), не совпадают.

Красен до реализации: без маркеров `marker_id_for` бросает
`AssertionError` — нечему быть равным или неравным.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (BriefSandbox, FakeGitDiff, MAP_FRESH,  # noqa: E402
                      build_review_package, marker_id_for, standard_files)


class Ac3DeveloperBriefFreshIdTest(BriefSandbox):

    def test_ac3_two_runs_for_the_same_task_and_role_get_different_ids(self):
        """Два последовательных вызова `developer_brief` для ОДНОЙ и той
        же задачи (тот же сценарий, что «повторные [запуски] для одной и
        той же задачи и роли» из AC-3) — идентификаторы границ не
        совпадают.

        Ловит мутацию: идентификатор границы вычислен детерминированно от
        входа (например `sha256(task_id)` или `sha256(spec_text)`) вместо
        свежей случайной генерации — тест краснеет, так как вход
        идентичен между вызовами, а id обязан отличаться.
        """
        text_run1 = self.build_developer_brief()
        text_run2 = self.build_developer_brief()

        id_run1 = marker_id_for(text_run1, MAP_FRESH.strip())
        id_run2 = marker_id_for(text_run2, MAP_FRESH.strip())

        self.assertNotEqual(
            id_run1, id_run2,
            "идентификатор границы обязан генерироваться заново на "
            "каждый запуск шага, даже при идентичном содержимом задачи")


class Ac3ReviewPackageFreshIdTest(unittest.TestCase):

    def test_ac3_two_runs_of_review_package_get_different_ids(self):
        """То же свойство — для ревью-пакета: два вызова `review_package`
        с одинаковым содержимым ветки не должны разделять идентификатор.

        Ловит мутацию: id границы ревью-пакета вычислен от sha ветки/
        диффа вместо свежей случайной генерации — при идентичном diff'е
        id совпал бы между запусками.
        """
        files = standard_files()

        def build():
            git = FakeGitDiff(files=files)
            return build_review_package(git)["text"]

        text_run1 = build()
        text_run2 = build()

        id_run1 = marker_id_for(text_run1, "Маркер-тела-SPEC-ревью-пакета.")
        id_run2 = marker_id_for(text_run2, "Маркер-тела-SPEC-ревью-пакета.")

        self.assertNotEqual(id_run1, id_run2)


if __name__ == "__main__":
    unittest.main()
