"""AC-1..AC-4 (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF): разбор приложений PLAN.md
функцией `scripts/guard.py` — пути и текст диффа, обе именованные ошибки,
PLAN без приложений.

Красен до реализации: разбора приложений в `scripts/guard.py` ещё нет — ни одна функция модуля не возвращает список приложений раздела «## Приложение», поэтому `parser_names()` пуст и все четыре критерия падают на его проверке.

Функция ищется по контракту, а не по имени: SPEC имени не называет
(«Функция в `scripts/guard.py` (рядом с `section_body`)») — контракт
описан в докстринге `_parse.py`. Имя одного и того же кандидата AC-1
переиспользуется в AC-2..AC-4: критерии говорят об ОДНОЙ функции разбора,
а не о четырёх независимых.

Провалидировано стабом (решение Оператора 03.09): временная функция
`guard.plan_appendices` (разделы по префиксу заголовка, блоки ```diff,
путь из `diff --git`, сверка с `config.PROTECTED_PATHS`, возврат
«(приложения, ошибки)») зеленит все пять тестов файла; стаб удалён,
репозиторий не тронут.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _parse  # noqa: E402

TASK = "01M2YSHDKWFJN3XSJ618Z74FNF"

# Опорный сценарий AC-1 (одно приложение) — он же отбирает кандидатов для
# AC-2..AC-4.
ONE_MARKER = "правка Оператора номер один"
ONE_APPENDIX = _parse.plan_text(TASK, [
    _parse.appendix_section(
        [_parse.diff_block(_parse.PROTECTED_FILE, ONE_MARKER)],
        suffix=f": правка {_parse.PROTECTED_FILE}")])
ONE_WANTED = [(_parse.PROTECTED_FILE, ONE_MARKER)]


class PlanAppendixParsingTest(unittest.TestCase):

    def parser_names(self) -> list[str]:
        """Кандидаты разбора, удовлетворившие опорному сценарию AC-1 —
        предпосылка всех четырёх критериев этого файла."""
        names = _parse.parsers(ONE_APPENDIX, ONE_WANTED)
        self.assertTrue(
            names,
            f"в scripts/guard.py нет функции от одного текстового "
            f"аргумента, возвращающей одно приложение с путём "
            f"{_parse.PROTECTED_FILE} и текстом его диффа; что вернули "
            f"функции модуля: {_parse.report(ONE_APPENDIX)!r}")
        return names

    def test_ac1_single_diff_block_gives_one_appendix_with_path_and_diff(self):
        """Раздел «## Приложение …» с одним блоком ```diff и корректным
        заголовком `diff --git a/<защищённый путь> b/<защищённый путь>`
        разбирается в одно приложение, несущее и путь из заголовка, и
        текст диффа.

        Ловит мутацию: разбор возвращает только путь (текст диффа
        потерян при склейке строк блока — применять на мерже будет
        нечего) либо только текст (путь берётся не из заголовка `diff
        --git`, а из заголовка раздела) — `_parse.parsers` требует в
        ОДНОМ элементе списка обе части сразу, и кандидатов не останется.
        """
        self.assertTrue(self.parser_names())

    def test_ac1_several_blocks_and_sections_keep_the_order_of_appearance(self):
        """Два блока ```diff в одном разделе и третий блок во втором
        разделе «## Приложение …» дают три приложения в порядке
        появления в тексте PLAN.md.

        Ловит мутацию: разбор берёт из раздела только ПЕРВЫЙ блок
        ```diff (поиск первого совпадения вместо цикла по всем) — список
        выйдет короче ожидаемого; либо разделы собираются множеством/
        словарём по пути, и порядок появления теряется (второй и третий
        маркеры встанут не на свои места).
        """
        markers = ["правка первая", "правка вторая", "правка третья"]
        text = _parse.plan_text(TASK, [
            _parse.appendix_section(
                [_parse.diff_block(_parse.PROTECTED_FILE, markers[0]),
                 _parse.diff_block(_parse.PROTECTED_FILE_2, markers[1])],
                suffix=": два блока"),
            _parse.appendix_section(
                [_parse.diff_block(_parse.PROTECTED_FILE, markers[2])],
                suffix=": второй раздел")])
        wanted = [(_parse.PROTECTED_FILE, markers[0]),
                  (_parse.PROTECTED_FILE_2, markers[1]),
                  (_parse.PROTECTED_FILE, markers[2])]

        names = set(self.parser_names()) & set(_parse.parsers(text, wanted))

        self.assertTrue(
            names,
            f"ни один кандидат разбора не вернул три приложения в порядке "
            f"появления; что вернули функции модуля: "
            f"{_parse.report(text)!r}")

    def test_ac2_block_without_the_diff_git_header_gives_the_named_error(self):
        """Блок ```diff без строки `diff --git` даёт именованную ошибку
        «приложение PLAN: нет заголовка diff --git».

        Ловит мутацию: разбор молча пропускает блок без заголовка
        (`continue` вместо ошибки) — приложение потерялось бы бесследно,
        и Оператор узнал бы об этом только на мерже; именованного текста
        среди возвращённых строк не окажется.
        """
        text = _parse.plan_text(TASK, [
            _parse.appendix_section(
                [_parse.diff_block(_parse.PROTECTED_FILE, "правка без шапки",
                                   header=False)],
                suffix=": блок без заголовка")])

        for name in self.parser_names():
            with self.subTest(parser=name):
                found = _parse.all_strings(name, text)
                self.assertTrue(
                    any(_parse.NO_HEADER_ERROR in s for s in found),
                    f"нет ошибки «{_parse.NO_HEADER_ERROR}»; вернулось: "
                    f"{found!r}")

    def test_ac3_block_with_an_unprotected_path_gives_the_named_error(self):
        """Блок ```diff с путём вне `config.PROTECTED_PATHS` даёт
        именованную ошибку «приложение PLAN: путь <путь> не защищённый —
        правь в ветке задачи» с этим путём.

        Ловит мутацию: проверка защищённости пути снята (или сверяется
        подстрокой «есть ли путь где-то в PROTECTED_PATHS» вместо
        префикса) — правку обычного файла репозитория пульт применил бы
        коммитом Оператора в main мимо ветки задачи, ревью и CI ветки.
        """
        text = _parse.plan_text(TASK, [
            _parse.appendix_section(
                [_parse.diff_block(_parse.UNPROTECTED_FILE, "правка не там")],
                suffix=": путь вне защищённых")])
        expected = _parse.unprotected_error(_parse.UNPROTECTED_FILE)

        for name in self.parser_names():
            with self.subTest(parser=name):
                found = _parse.all_strings(name, text)
                self.assertTrue(
                    any(expected in s for s in found),
                    f"нет ошибки «{expected}»; вернулось: {found!r}")

    def test_ac4_plan_without_appendix_sections_gives_no_appendices_and_no_errors(self):
        """PLAN.md без разделов «## Приложение» — пустой список приложений
        и ни одной ошибки.

        Ловит мутацию: раздел ищется не по префиксу заголовка, а поиском
        любого блока ```diff по всему тексту PLAN (или `section_body`
        заменён на «весь текст, если раздела нет», как уже ловил
        `tests/test_zones_gate.py` для «## Расширение зон») — тогда
        обычный PLAN без приложений начнёт приносить и приложения, и
        ошибки, а гейт применимости AC-7 перестанет пропускать задачи,
        которые приложений не предлагали вовсе.
        """
        text = _parse.plan_text(TASK)

        for name in self.parser_names():
            with self.subTest(parser=name):
                lists = _parse.appendix_lists(name, text)
                self.assertTrue(
                    all(not items for items in lists),
                    f"разбор вернул приложения для PLAN без разделов "
                    f"«## Приложение»: {lists!r}")
                found = _parse.all_strings(name, text)
                self.assertFalse(
                    [s for s in found
                     if "приложение PLAN" in s or "diff --git" in s],
                    f"разбор вернул ошибку или текст диффа для PLAN без "
                    f"приложений: {found!r}")


if __name__ == "__main__":
    unittest.main()
