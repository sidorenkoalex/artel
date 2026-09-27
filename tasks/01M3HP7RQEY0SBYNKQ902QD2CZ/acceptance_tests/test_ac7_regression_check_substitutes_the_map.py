"""AC-7: в `tests/` появилась проверка, которая САМА подменяет карту (роль
analyst на провайдере Codex и на ярусе, отличном от остальных agent-ролей;
локальный слой называет этому ярусу модель Codex) и проходит.

Имени такой проверки критерий не называет, поэтому планка ищет её
ПОВЕДЕНИЕМ — среди новых и изменённых тестовых методов `tests/`
относительно базы сравнения ветки:

- сегодня, на здоровом коде, кандидат проходит;
- под мутацией он краснеет.

Мутации две, и достаточно одной: проверка может опереться на любой конец
той же цепочки.

1. «Поле `provider:` карты не читается» (`roles.provider` всегда отдаёт
   `providers.DEFAULT_PROVIDER`) — проверка, поставившая роль analyst на
   Codex, наблюдает вместо Codex провайдер по умолчанию.
2. «Локальный слой называет всем ярусам модель провайдера по умолчанию»
   (`models.load_local` подменяет все ярусы моделью шаблона) — проверка,
   назвавшая своему ярусу модель Codex, теряет её и упирается в отказ
   «модель роли не поддерживается CLI», то есть ровно в тот отказ, которым
   раздел «Контекст» SPEC описывает сегодняшнее состояние.

Обе мутации не трогают тесты, которые карту не подменяют: у роли на
провайдере по умолчанию и без того провайдер по умолчанию, а модель
шаблона и без того стоит у каждого яруса. Поэтому связка «зелен сейчас,
красен под мутацией» отличает искомую проверку от любого другого нового
теста.

Красен до реализации: регрессионной проверки ещё нет — `tests/` не
отличается от базы сравнения ветки ни одним тестовым методом, и множество
кандидатов пусто.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class RegressionCheckPresenceTest(unittest.TestCase):
    """Поиск регрессионной проверки среди новых и изменённых тестов."""

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
                                    path_extra=path_extra, timeout=60)
        except subprocess.TimeoutExpired as exc:  # pragma: no cover
            self.fail(f"прогон кандидатов не уложился в отведённое время: "
                      f"{exc}")

    def test_ac7_a_new_check_substitutes_the_map_and_passes(self):
        """Среди новых и изменённых тестов `tests/` есть хотя бы один,
        который сегодня зелен, а под мутацией «поле `provider:` не
        читается» либо «локальный слой называет всем ярусам модель
        провайдера по умолчанию» краснеет.

        Ловит мутацию: регрессионная проверка написана так, что карту она
        подменяет, но исхода на неё не завязывает (ставит `provider: codex`
        и проверяет лишь то, что карта разобралась) — под обеими мутациями
        она остаётся зелёной, ни один кандидат связку «зелен сейчас,
        красен под мутацией» не проходит, и класс 27.09 снова уедет в
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
            "метода относительно базы сравнения ветки — регрессионной "
            "проверки, которая сама подменяет карту, не появилось")

        healthy = self.run_or_fail(candidates)
        green_now = [node for node in candidates
                     if node not in set(_util.failed_nodeids(healthy.stdout))]
        self.assertTrue(
            green_now,
            f"ни один новый или изменённый тест `tests/` не проходит на "
            f"здоровом коде — AC-7 требует проверки, которая ПРОХОДИТ\n"
            f"{_util.run_report(healthy)}")

        reports = []
        red = set()
        for name, source in ((_util.PROVIDER_BLIND_PLUGIN,
                              _util.PROVIDER_BLIND_SOURCE),
                             (_util.DEFAULT_LAYER_PLUGIN,
                              _util.DEFAULT_LAYER_SOURCE)):
            plugin_dir = _util.write_plugin(self.tdir, name, source)
            mutated = self.run_or_fail(green_now, plugins=[name],
                                       path_extra=[plugin_dir])
            reports.append(f"=== мутация {name} ===\n"
                           f"{_util.run_report(mutated)}")
            red |= {node for node in green_now
                    if node in set(_util.failed_nodeids(mutated.stdout))}

        self.assertTrue(
            red,
            "ни один новый или изменённый тест `tests/` не краснеет ни от "
            "того, что поле `provider:` карты перестало читаться, ни от "
            "того, что локальный слой назвал всем ярусам модель провайдера "
            "по умолчанию — значит, ни один из них не ставит роль "
            f"{_util.ANALYST} на провайдер {_util.CODEX} и на отдельный ярус "
            f"с моделью {_util.CODEX}\nкандидаты: {green_now}\n"
            + "\n".join(reports))


if __name__ == "__main__":
    unittest.main()
