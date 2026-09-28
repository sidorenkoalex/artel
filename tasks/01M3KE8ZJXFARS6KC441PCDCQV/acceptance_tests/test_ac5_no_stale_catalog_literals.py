"""AC-5 — 01M3KE8ZJXFARS6KC441PCDCQV: в `tests/` не осталось литералов
прежних цен и прежних наименьших версий клиента правленых записей.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. Ни один тест `tests/` не утверждает литералом прежнюю цену или
прежнюю наименьшую версию клиента правленой записи каталога: значения
приведены к таблице требования 1.

«Новое» планка берёт из каталога ВЕТКИ, «прежнее» — из снимка каталога
ДО правки (`_catalog.PREVIOUS_PRICES`/`PREVIOUS_MIN_CLI`). Редакция 2
планки по ANSWER-1, вопрос 1, вариант (а): прежняя редакция брала обе
половины из пары «база сравнения -> результат применения приложения
PLAN», и коммит `ae3370c5` эту пару схлопнул — прежних значений в git
больше нет (докстринг `_catalog.py`). Сравниваемые величины и правило
адресации литерала те же.

Литерал сверяется с записью, о которой он говорит: адресатом считается
модель, ЕДИНСТВЕННО названная в том же тестовом методе —
`models.Tariff(...)` в методе, где рядом стоит `list_price` и ровно один
идентификатор модели каталога, утверждает прейскурант именно этой записи.

Красен до реализации: `tests/test_models.py` сверяет прейскурант
`claude-sonnet-5` прежними 3.00 / 15.00 / 3.75 / 0.30, а каталог ветки
несёт сверенные 2.00 / 10.00 / 2.50 / 0.20 — краснеют оба теста о ценах.
"""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _catalog  # noqa: E402

#: Имя поля прейскуранта каталога: по нему метод-претендент отличается от
#: метода, собирающего собственный тариф фикстуры (`override.tariff`).
LIST_PRICE_FIELD = "list_price"


def _mentions(text: str, model_id: str) -> bool:
    """Идентификатор назван в тексте целиком, а не как начало другого:
    `claude-opus-5` — не упоминание `claude-opus-5-5`."""
    return re.search(rf"(?<![\w.\-]){re.escape(model_id)}(?![\w.\-])",
                     text) is not None


def _numbers(node) -> tuple | None:
    """Кортеж чисел из аргументов вызова/элементов кортежа; `None` —
    среди них есть не-число (имя, выражение): такой литерал ничего не
    утверждает сам по себе."""
    values = []
    for item in node:
        if not isinstance(item, ast.Constant) or isinstance(item.value, bool):
            return None
        if not isinstance(item.value, (int, float)):
            return None
        values.append(float(item.value))
    return tuple(values)


def _func_defs(tree, source: str):
    """(узел функции, её текст) по всем функциям модуля, включая
    вложенные."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node, ast.get_source_segment(source, node) or ""


def _as_prices(was, model_id: str) -> tuple:
    """Прейскурант снимка — кортежем чисел, как его отдаёт разбор
    каталога (`models.Tariff`)."""
    return tuple(float(value) for value in was)


def _as_version(was, model_id: str) -> tuple:
    """Наименьшая версия клиента снимка — кортежем чисел, тем же разбором
    (`models.version_tuple`), которым её читает пульт."""
    return _catalog.models.version_tuple(was, f"снимок каталога, {model_id}")


def _sole_model(text: str, model_ids) -> str | None:
    """Единственный идентификатор модели каталога, названный в тексте;
    `None` — не назван ни один либо названо несколько (адресата литерала
    не определить, и молчать честнее, чем гадать)."""
    named = [model_id for model_id in model_ids if _mentions(text, model_id)]
    return named[0] if len(named) == 1 else None


class StaleCatalogLiteralsTest(unittest.TestCase):

    def setUp(self):
        self.subject = _catalog.catalog()
        self.sources = [(rel, text) for rel, text in _catalog.tests_sources()]
        self.model_ids = sorted(self.subject.catalog.models)

    def changed(self, snapshot: dict, field: str, convert) -> dict:
        """{модель: прежнее значение} по записям, у которых `field`
        каталога ветки разошёлся со снимком ДО правки. `convert` —
        приведение значения снимка к тому виду, в котором поле живёт в
        разобранном каталоге (кортеж цен, кортеж версии).

        Снятая запись (в каталоге ветки её уже нет) пропускается: её
        прежний прейскурант — предмет AC-3, а не AC-5.
        """
        out = {}
        for model_id, was in sorted(snapshot.items()):
            now = self.subject.catalog.models.get(model_id)
            if now is None:
                continue
            want = convert(was, model_id)
            if want != tuple(getattr(now, field)):
                out[model_id] = want
        return out

    def test_ac5_no_test_asserts_a_previous_price_of_a_corrected_record(self):
        """Ни в одном методе `tests/` нет литерала `Tariff(...)` с
        ПРЕЖНИМИ ценами записи, чей прейскурант правится этой задачей.

        Ловит мутацию: цены `claude-sonnet-5` исправлены в каталоге, а
        сверку прежних 3.00 / 15.00 / 3.75 / 0.30 в наборе оставили —
        полный прогон краснеет ровно там, где правленый каталог и набор
        сходятся в одном дереве: на мерже, где чинить его уже некому
        (ровно класс 26.09: main красный с мержа правки каталога).
        """
        stale = self.changed(_catalog.PREVIOUS_PRICES, "list_price",
                             _as_prices)
        self.assertTrue(stale, "прейскурант не правится ни у одной записи — "
                               "проверять нечего, а требование 1 его правит")

        hits = []
        for rel, source in self.sources:
            for func, text in _func_defs(ast.parse(source), source):
                model_id = _sole_model(text, sorted(stale))
                if model_id is None:
                    continue
                for node in ast.walk(func):
                    if not (isinstance(node, ast.Call)
                            and getattr(node.func, "attr", None) == "Tariff"):
                        continue
                    if _numbers(node.args) == tuple(stale[model_id]):
                        hits.append(f"{rel}:{node.lineno} — прежние цены "
                                    f"{model_id}")

        self.assertEqual([], hits, "; ".join(hits))

    def test_ac5_price_literals_agree_with_the_branch_catalog(self):
        """Каждый литерал `Tariff(...)`, утверждающий прейскурант
        названной записи каталога (метод называет `list_price` и ровно
        одну модель), равен цене этой записи в каталоге ветки.

        Ловит мутацию: правя соседние строки прейскуранта, разработчик
        задел и `claude-opus-5` — запись, которую таблица требования 1
        оставляет нетронутой: сверка с калибровкой 20.09
        (5.00 / 25.00 / 6.25 / 0.50) в `tests/test_models.py` разойдётся
        с каталогом, и учёт расхода поехал бы на несверенных числах.
        """
        hits = []
        for rel, source in self.sources:
            for func, text in _func_defs(ast.parse(source), source):
                if LIST_PRICE_FIELD not in text:
                    continue
                model_id = _sole_model(text, self.model_ids)
                if model_id is None:
                    continue
                want = tuple(self.subject.catalog.models[model_id].list_price)
                for node in ast.walk(func):
                    if not (isinstance(node, ast.Call)
                            and getattr(node.func, "attr", None) == "Tariff"):
                        continue
                    got = _numbers(node.args)
                    if got is not None and got != want:
                        hits.append(f"{rel}:{node.lineno} — {model_id}: в "
                                    f"тесте {got}, в каталоге {want}")

        self.assertEqual([], hits, "; ".join(hits))

    def test_ac5_no_test_asserts_a_previous_minimum_cli_version(self):
        """Ни в одном методе `tests/` нет литерала прежней наименьшей
        версии клиента записи, чей минимум правится этой задачей.

        Ловит мутацию: минимум записи каталога сдвинут правкой, а сверка
        прежнего кортежа версии в наборе оставлена — предполётная сверка
        шага и её тест разошлись бы, и набор покраснел бы на мерже.
        (Таблица требования 1 минимумов существующих записей не двигает —
        на ней список пуст, и проверка молчит; она сторожит именно тот
        случай, когда минимум всё-таки поедет.)
        """
        stale = self.changed(_catalog.PREVIOUS_MIN_CLI, "min_cli_version",
                             _as_version)

        hits = []
        for rel, source in self.sources:
            for func, text in _func_defs(ast.parse(source), source):
                model_id = _sole_model(text, sorted(stale))
                if model_id is None:
                    continue
                was = tuple(float(part) for part in stale[model_id])
                for node in ast.walk(func):
                    if isinstance(node, ast.Tuple):
                        if _numbers(node.elts) == was:
                            hits.append(f"{rel}:{node.lineno} — прежний "
                                        f"минимум {model_id}")
                    elif (isinstance(node, ast.Constant)
                          and isinstance(node.value, str)
                          and node.value == ".".join(
                              str(part) for part in stale[model_id])):
                        hits.append(f"{rel}:{node.lineno} — прежний минимум "
                                    f"{model_id} строкой")

        self.assertEqual([], hits, "; ".join(hits))


if __name__ == "__main__":
    unittest.main()
