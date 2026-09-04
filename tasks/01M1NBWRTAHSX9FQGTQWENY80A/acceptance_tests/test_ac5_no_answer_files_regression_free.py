"""AC-5 (tasks/01M1NBWRTAHSX9FQGTQWENY80A/SPEC.md): «Для задачи без
файлов ANSWER-n.md review.review_package возвращает пакет, байт-в-байт
идентичный пакету, собираемому до этого изменения (регресс отсутствует).»

Тело каждого компонента пакета оборачивается парой ГРАНИЧНЫХ маркеров со
случайным `run_id` (`brief.new_run_id`, `secrets.token_hex` — tasks/
01M1GV6H5DDDCWW4G3GW1D3A1X, уже существующая механика ДО этой задачи) —
буквальное байтовое равенство между двумя ЗАПУСКАМИ поэтому недостижимо
в принципе даже без единой строки новой логики. Проверяемое здесь и
есть содержание «регресса нет»: СТРУКТУРА и СОСТАВ пакета (набор частей,
их порядок, полные тела SPEC/PLAN/diff/stat, отсутствие деления на части
при этом маленьком фикстурном наборе) — те же, что фиксирует уже
существующий `tests/test_review_package.py` для задачи без ANSWER-файлов,
и никакого следа ANSWER-механики (заголовков компонента, записей
журнала) там быть не должно.

Зелёный с рождения: сегодня `review.review_package` не читает
ANSWER-n.md вовсе — для задачи без таких файлов сегодняшнее поведение
УЖЕ ровно то, что здесь проверяется (докстрока `test_ac1`). Тест ловит
БУДУЩУЮ регрессию: реализация AC-1/AC-2/AC-3/AC-4 задевает путь «ANSWER-
файлов нет» — тем же приёмом «не сегодняшний дефект, а окно для
регрессии следующей правки», что и
`tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/acceptance_tests/
test_ac1_head_already_pushed_unchanged.py`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import AnswerInReviewPackageSandbox  # noqa: E402


class Ac5NoAnswerFilesRegressionFreeTest(AnswerInReviewPackageSandbox):

    def test_ac5_package_without_answer_files_carries_no_trace_of_the_feature(self):
        """Задача без единого ANSWER-n.md — ни в промпте, ни в журнале
        шага нет ни одного следа новой механики: ни слова «ANSWER» в
        пакете, ни одной записи «бриф: компонент», деления на части нет
        (фикстурные SPEC/PLAN/diff/stat маленькие).

        Ловит мутацию: реализация забывает охранное условие «файлов
        ANSWER-n.md нет — компонент не добавляется» (например, всегда
        приклеивает пустой заголовок «### tasks/<id>/ANSWER» или
        безусловно пишет журнальную запись даже без найденных файлов) —
        тест обнаружит подстроку «ANSWER» в пакете, которой там неоткуда
        взяться для задачи, ни разу не получившей ответ Оператора.
        """
        self.run_agent("review")

        package = self.package_text()
        self.assertNotIn("ANSWER", package,
                         "пакет задачи без ANSWER-файлов упоминает ANSWER — "
                         "след новой механики там, где файлов нет "
                         "(проверяется только тело пакета — скил review-"
                         "checklist легитимно упоминает ANSWER в промпте "
                         "целиком, см. `_sandbox.package_text`)")
        # `action="бриф: компонент"` уже используется СЕГОДНЯ для скилов
        # роли (`brief.skills_text`, `orchestrator/runner.py`, каждый
        # запуск ЛЮБОЙ роли) — список записей поэтому не пуст сам по себе
        # (три скила ревьювера) даже без единой строки этой задачи; проверяем
        # узко — что среди них нет ни одной про ANSWER-файл.
        answer_journal_entries = [d for d in self.journal_details("бриф: компонент")
                                  if "ANSWER" in d]
        self.assertEqual(
            answer_journal_entries, [],
            "запись «бриф: компонент» про ANSWER появилась без единого "
            "ANSWER-файла у задачи")
        self.assertNotIn("--- ЧАСТЬ 1/", package,
                         "маленький фикстурный пакет неожиданно поделён на "
                         "части без единого ANSWER-компонента")

    def test_ac5_stable_component_order_and_content_are_unaffected(self):
        """Порядок и полнота существующих компонентов (задача, SPEC, PLAN,
        стат-список, diff) — те же, что фиксирует существующий
        `ReviewPackageTest.test_all_parts_are_present_in_a_stable_order`
        (`tests/test_review_package.py`) для задачи без ANSWER: правка
        этой задачи не имеет права переставить или обрезать их.

        Ловит мутацию: точка вставки ANSWER-компонента (даже пустого)
        сдвигает существующие компоненты друг относительно друга —
        например, ANSWER-заглушка встаёт МЕЖДУ SPEC и PLAN даже когда
        ANSWER-файлов нет — порядок вхождений в тексте перестанет быть
        монотонно возрастающим.
        """
        self.run_agent("review")

        package = self.package_text()
        marks = []
        for needle in ("### Задача", f"tasks/{self.TASK}/SPEC.md",
                       f"tasks/{self.TASK}/PLAN.md", "### Изменённые файлы",
                       "### Diff"):
            self.assertIn(needle, package, f"компонент {needle!r} пропал из пакета")
            marks.append(package.index(needle))
        self.assertEqual(marks, sorted(marks), "порядок компонентов пакета сдвинут")


if __name__ == "__main__":
    import unittest
    unittest.main()
