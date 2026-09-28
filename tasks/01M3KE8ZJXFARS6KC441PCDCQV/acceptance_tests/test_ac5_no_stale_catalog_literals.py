"""AC-5 — 01M3KE8ZJXFARS6KC441PCDCQV: в `tests/` не осталось литералов
прежних цен и прежних наименьших версий клиента правленых записей.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. Ни один тест `tests/` не утверждает литералом прежнюю цену или
прежнюю наименьшую версию клиента правленой записи каталога: значения
приведены к таблице требования 1.

«Прежнее» и «новое» планка не зашивает числами, а берёт из двух
каталогов: базы сравнения ветки (до правки) и результата применения
приложения PLAN (после). Литерал сверяется с записью, о которой он
говорит: адресатом считается модель, ЕДИНСТВЕННО названная в том же
тестовом методе — `models.Tariff(...)` в методе, где рядом стоит
`list_price` и ровно один идентификатор модели каталога, утверждает
прейскурант именно этой записи.

Красен до реализации: PLAN.md с приложением `models.yaml` ещё нет,
«новых» значений взять неоткуда — `_catalog.applied()` отказывает.
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


def _sole_model(text: str, model_ids) -> str | None:
    """Единственный идентификатор модели каталога, названный в тексте;
    `None` — не назван ни один либо названо несколько (адресата литерала
    не определить, и молчать честнее, чем гадать)."""
    named = [model_id for model_id in model_ids if _mentions(text, model_id)]
    return named[0] if len(named) == 1 else None


class StaleCatalogLiteralsTest(unittest.TestCase):

    def setUp(self):
        self.applied = _catalog.applied()
        self.sources = [(rel, text) for rel, text in _catalog.tests_sources()]
        self.model_ids = sorted(self.applied.catalog.models)

    def changed(self, field: str) -> dict:
        """{модель: прежнее значение} по записям, у которых `field`
        разошёлся между базой сравнения и каталогом после приложения."""
        out = {}
        for model_id, was in sorted(self.applied.base_catalog.models.items()):
            now = self.applied.catalog.models.get(model_id)
            if now is None:
                continue
            if getattr(was, field) != getattr(now, field):
                out[model_id] = getattr(was, field)
        return out

    def test_ac5_no_test_asserts_a_previous_price_of_a_corrected_record(self):
        """Ни в одном методе `tests/` нет литерала `Tariff(...)` с
        ПРЕЖНИМИ ценами записи, чей прейскурант правится этой задачей.

        Ловит мутацию: цены `claude-sonnet-5` исправлены в каталоге, а
        сверку прежних 3.00 / 15.00 / 3.75 / 0.30 в наборе оставили —
        полный прогон покраснеет ровно в тот момент, когда приложение
        каталога ляжет в main, то есть уже на мерже, где чинить его
        некому (ровно класс 26.09: main красный с мержа приложения).
        """
        stale = self.changed("list_price")
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

    def test_ac5_price_literals_agree_with_the_catalog_after_the_appendix(self):
        """Каждый литерал `Tariff(...)`, утверждающий прейскурант
        названной записи каталога (метод называет `list_price` и ровно
        одну модель), равен цене этой записи в каталоге после приложения.

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
                want = tuple(self.applied.catalog.models[model_id].list_price)
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

        Ловит мутацию: минимум записи каталога сдвинут приложением, а
        сверка прежнего кортежа версии в наборе оставлена — предполётная
        сверка шага и её тест разошлись бы, и набор покраснел бы на
        мерже. (Таблица требования 1 минимумов существующих записей не
        двигает — на ней список пуст, и проверка молчит; она сторожит
        именно тот случай, когда минимум всё-таки поедет.)
        """
        stale = self.changed("min_cli_version")

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
