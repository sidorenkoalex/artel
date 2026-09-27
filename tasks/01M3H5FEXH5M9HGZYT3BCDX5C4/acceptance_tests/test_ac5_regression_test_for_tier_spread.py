"""AC-5: в `tests/` появился регрессионный тест, который сам разводит
agent-роли по ярусам и требует от `orchestrator/stack.py` отсутствия
строк `model-<роль>` со статусом `fail`, — и который краснеет, если
локальный слой называет модель только у одного яруса.

Имени такого теста ни один критерий не называет, поэтому планка ищет его
ПОВЕДЕНИЕМ, среди новых и изменённых тестовых методов `tests/`
относительно главной ветки:

- сегодня, на зелёном слое, кандидат проходит;
- под мутацией «локальный слой называет модель только у одного яруса»
  (плагин прогона `_util.ONE_TIER_PLUGIN_SOURCE` подменяет
  `models.load_local`, через который идут ОБА входа резолва цепочки)
  кандидат краснеет.

Сохраняется ярус ПЕРВОЙ agent-роли карты, которую тест поставил сам, —
и это тот самый разделитель, который отличает искомый тест от любого
другого: тест, у которого все agent-роли на одном ярусе, при такой
мутации остаётся зелёным (его единственный ярус и сохранён), а красным
становится ровно тот, который развёл роли по разным ярусам и потребовал
разрешимости цепочки у всех.

Красен до реализации: регрессионного теста ещё нет — `tests/` не
отличается от главной ветки ни одним тестовым методом, и множество
кандидатов пусто.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class TierSpreadRegressionTestPresenceTest(unittest.TestCase):
    """Поиск регрессионного теста среди новых и изменённых тестов."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def candidates(self, base: str) -> list:
        """Nodeid новых и изменённых тестовых методов файлов `tests/`."""
        found = []
        for rel in _util.changed_tests_files(base):
            head_source = _util.text_on_disk(rel)
            if head_source is None:
                continue
            for name in _util.changed_test_methods(
                    _util.text_at(base, rel), head_source):
                found.append(_util.nodeid(rel, name))
        return found

    def run_or_fail(self, targets, plugins=(), path_extra=()):
        try:
            return _util.run_pytest(_util.REPO_ROOT, targets, plugins=plugins,
                                    path_extra=path_extra, timeout=45)
        except subprocess.TimeoutExpired as exc:
            self.fail(f"прогон кандидатов не уложился в отведённое время: "
                      f"{exc}")

    def test_ac5_a_new_test_goes_red_when_only_one_tier_names_a_model(self):
        """Среди новых и изменённых тестов `tests/` есть хотя бы один,
        который сегодня зелен, а при локальном слое с моделью только у
        одного яруса краснеет.

        Ловит мутацию: регрессионный тест написан так, что все его
        agent-роли стоят на ОДНОМ ярусе (разведения ярусов в нём нет, он
        повторяет уже покрытый сценарий) — под мутацией «модель названа
        только у одного яруса» его единственный ярус остаётся названным,
        тест зеленеет, и ни один кандидат не проходит связку «зелен
        сейчас, красен под мутацией»: регресс 27.09 снова уехал бы в
        главную ветку незамеченным.
        """
        base = _util.main_base_ref()
        self.assertTrue(
            base, "git не ответил на запрос точки расхождения ветки задачи с "
                  "главной веткой — сравнить `tests/` не с чем")

        candidates = self.candidates(base)
        self.assertTrue(
            candidates,
            "в `tests/` нет ни одного нового или изменённого тестового "
            "метода относительно главной ветки — регрессионного теста, "
            "который сам разводит agent-роли по ярусам, не появилось")

        healthy = self.run_or_fail(candidates)
        green_now = [node for node in candidates
                     if node not in set(_util.failed_nodeids(healthy.stdout))]
        self.assertTrue(green_now, _util.run_report(healthy))

        plugin_dir = _util.write_one_tier_plugin(self.tdir)
        mutated = self.run_or_fail(green_now,
                                   plugins=[_util.ONE_TIER_PLUGIN_NAME],
                                   path_extra=[plugin_dir])
        red_under_mutation = [node for node in green_now
                              if node in set(_util.failed_nodeids(mutated.stdout))]

        self.assertTrue(
            red_under_mutation,
            "ни один новый или изменённый тест `tests/` не краснеет при "
            "локальном слое, называющем модель только у одного яруса — "
            "значит, ни один из них не разводит agent-роли по разным ярусам "
            "и не требует от `orchestrator/stack.py` отсутствия строк "
            "`model-<роль>` со статусом fail.\n"
            f"кандидаты: {green_now}\n{_util.run_report(mutated)}")


if __name__ == "__main__":
    unittest.main()