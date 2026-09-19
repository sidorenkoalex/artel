"""Приёмочные тесты AC-1/AC-2 задачи 01M2XFSNVGWA2VX5XFEYR93Y4Z:
гейт зон различает «мандат есть, раздел PLAN не оформлен» и обычный
отказ «вне заявленных zones».

Красен до реализации: `orchestrator/advance_gates/zones.py::_zones_gate`
сегодня применяет мандат ТОЛЬКО внутри ветки `if extension_paths is not
None` (zones.py:250-263) — при отсутствующем либо несовпадающем разделе
«## Расширение зон» он вовсе не читает `_answer_zones_mandate` и
журналирует обычное действие «переход отклонён: гейт зон»; оба теста
AC-1 падают на `assertNotEqual(action, "переход отклонён: гейт зон")`.
Тесты AC-2 зелёные с рождения — они фиксируют сегодняшний текст отказа
БЕЗ мандата байт-в-байт (критерий требует именно неизменности), и это
контроль против мутации «новая ветка перехватила и случай без мандата»,
а не молчаливый пропуск.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import gitcmd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (DECLARED_ZONE, OLD_ZONES_REFUSAL_ACTION,  # noqa: E402
                      OLD_ZONES_REFUSAL_HINT, OUT_OF_ZONE_PATH,
                      ZonesMandateSandbox)


class Ac1MandateWithoutPlanSectionTest(ZonesMandateSandbox):
    """AC-1: все пути вне зон покрыты мандатом Оператора, раздела
    «## Расширение зон» PLAN.md нет либо он не совпадает с мандатом."""

    def setUp(self):
        super().setUp()
        self.commit_mandate(OUT_OF_ZONE_PATH)
        self.commit_out_of_zone_file()

    def _assert_mandate_refusal(self, action: str, detail: str,
                                out: str) -> None:
        self.assertNotEqual(
            action, OLD_ZONES_REFUSAL_ACTION,
            "отказ обязан отличаться ПО ТЕКСТУ действия от обычного "
            "отказа гейта зон — иначе auto не отличит его класс")
        self.assertTrue(
            action.startswith("переход отклонён"),
            f"действие {action!r} не опознаётся ни `auto._advance_refusal`, "
            f"ни `store.refusal_history` — они отбирают записи по этому "
            f"префиксу")
        self.assertIn(
            OUT_OF_ZONE_PATH, detail,
            f"в тексте отказа не перечислены пути мандата: {detail!r}")
        hint = "".join(line[len("  дальше: "):] for line in out.splitlines()
                       if line.startswith("  дальше: "))
        self.assertIn("Расширение зон", hint,
                      f"подсказка не называет раздел PLAN.md: {hint!r}")
        self.assertIn("PLAN", hint,
                      f"подсказка не называет PLAN.md: {hint!r}")

    def test_ac1_missing_plan_section_refuses_with_its_own_action(self):
        """Мандат Оператора покрывает единственный путь диффа вне зон, а
        раздела «## Расширение зон» в PLAN.md нет вовсе — гейт отказывает
        переходу `in_dev -> review` действием, отличным по тексту от
        «переход отклонён: гейт зон»; путь мандата назван в тексте
        отказа, подсказка предписывает оформить раздел в PLAN.md.

        Ловит мутацию: чтение мандата (`_answer_zones_mandate`) осталось
        внутри ветки `if extension_paths is not None` — случай
        «раздела нет» по-прежнему падает в общий отказ «переход отклонён:
        гейт зон», неотличимый для `auto` от причины, требующей рук
        Оператора (ровно инцидент 13.09).
        """
        self.commit_plan(extension_paths=None)

        refuses, out = self.run_zones_gate()

        self.assertTrue(refuses, "гейт обязан отказать: раздел PLAN не оформлен")
        action, detail = self.refusals()[-1]
        self._assert_mandate_refusal(action, detail, out)

    def test_ac1_plan_section_mismatching_the_mandate_refuses_the_same_way(self):
        """Раздел «## Расширение зон» в PLAN.md ЕСТЬ, но его строка
        `Пути:` называет другой путь, не совпадающий с мандатом — тот же
        именованный отказ, что и при отсутствующем разделе (критерий
        называет оба случая одной формулировкой «отсутствует или не
        совпадает с мандатом»).

        Ловит мутацию: различение причины прикручено только к ветке
        «раздела нет вовсе» (`extension_paths is None`), а несовпадение
        путей раздела с мандатом по-прежнему уходит в общий отказ —
        разработчик, опечатавшийся в строке `Пути:`, снова получал бы
        отказ класса «нужны руки Оператора».
        """
        self.commit_plan(extension_paths="docs/another_module.md")

        refuses, out = self.run_zones_gate()

        self.assertTrue(refuses, "гейт обязан отказать: раздел PLAN не "
                                 "совпадает с мандатом")
        action, detail = self.refusals()[-1]
        self._assert_mandate_refusal(action, detail, out)


class Ac2ZonesRefusalWithoutMandateIsUnchangedTest(ZonesMandateSandbox):
    """AC-2: мандата нет вовсе либо он покрывает не все пути вне зон —
    прежнее действие, прежние текст отказа и подсказка байт-в-байт."""

    def setUp(self):
        super().setUp()
        self.commit_plan(extension_paths=None)

    def _expected_detail_prefix(self) -> str:
        base = gitcmd.diff_base(self.code_branch)
        source = gitcmd.diff_base_source(self.code_branch)
        self.assertIsNotNone(base, "merge-base ветки задачи не посчитан")
        return (f"дифф трогает файлы вне заявленных zones и COMMON_ZONES "
                f"(база сравнения {base} от {source}): ")

    def _assert_old_refusal(self, action: str, detail: str, out: str,
                            expected_paths: list) -> None:
        self.assertEqual(action, OLD_ZONES_REFUSAL_ACTION)
        self.assertEqual(
            detail,
            self._expected_detail_prefix() + ", ".join(expected_paths),
            "текст отказа гейта зон без мандата изменился — критерий "
            "требует байт-в-байт прежний")
        self.assertIn(f"  дальше: {OLD_ZONES_REFUSAL_HINT.format(task=self.TASK)}",
                      out)

    def test_ac2_no_mandate_at_all_keeps_the_previous_refusal_byte_for_byte(self):
        """Мандата в `ANSWER-*.md` нет вовсе — гейт отказывает прежним
        действием «переход отклонён: гейт зон», с прежними текстом
        (перечень путей вне зон и база сравнения) и подсказкой.

        Ловит мутацию: новая ветка различения причины поставлена ДО
        проверки покрытия мандатом (например, срабатывает на одном лишь
        факте «раздела PLAN нет») — задача вовсе без мандата Оператора
        получала бы отказ класса «роль ещё не закончила» и крутила бы
        developer на пути, который никто не разрешал.
        """
        self.commit_out_of_zone_file()

        refuses, out = self.run_zones_gate()

        self.assertTrue(refuses)
        action, detail = self.refusals()[-1]
        self._assert_old_refusal(action, detail, out, [OUT_OF_ZONE_PATH])

    def test_ac2_mandate_covering_only_part_of_the_paths_keeps_the_previous_refusal(self):
        """Мандат есть, но покрывает лишь ОДИН из двух путей диффа вне
        заявленных zones — отказ остаётся прежним, байт-в-байт: критерий
        разводит «все пути покрыты» и «покрыты не все».

        Ловит мутацию: покрытие мандатом сверяется «есть хоть одно
        пересечение» (`any`) вместо «покрыты ВСЕ» (`all`) — непокрытый
        путь `docs/uncovered_module.md` молча получал бы мягкий отказ
        класса «роль ещё не закончила», и роль гоняла бы круги по пути,
        на который мандата не выдавали.
        """
        uncovered = "docs/uncovered_module.md"
        self.commit_mandate(OUT_OF_ZONE_PATH)
        self.commit_out_of_zone_file(OUT_OF_ZONE_PATH)
        self.commit_out_of_zone_file(uncovered)

        refuses, out = self.run_zones_gate()

        self.assertTrue(refuses)
        action, detail = self.refusals()[-1]
        self.assertEqual(action, OLD_ZONES_REFUSAL_ACTION)
        self.assertIn(uncovered, detail)
        self.assertIn(
            f"  дальше: {OLD_ZONES_REFUSAL_HINT.format(task=self.TASK)}", out)

    def test_ac2_declared_zone_alone_never_reaches_the_refusal(self):
        """Контроль предпосылки обоих тестов выше: дифф строго внутри
        заявленной зоны `DECLARED_ZONE` гейт пропускает — значит отказ в
        них вызван именно путём ВНЕ зон, а не самой песочницей.

        Ловит мутацию: сверка зон сломана так, что отказывает на любом
        диффе (например `declared` собирается из пустого значения) —
        тогда «байт-в-байт прежний отказ» выше проходил бы по ложной
        причине и не подтверждал бы ничего.
        """
        self.commit_out_of_zone_file(DECLARED_ZONE)

        refuses, _out = self.run_zones_gate()

        self.assertFalse(refuses,
                         f"дифф строго в заявленной зоне {DECLARED_ZONE} "
                         f"не должен отказывать")


if __name__ == "__main__":
    unittest.main()
