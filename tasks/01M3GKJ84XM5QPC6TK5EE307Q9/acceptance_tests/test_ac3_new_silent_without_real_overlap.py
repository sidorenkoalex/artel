"""AC-3 — 01M3GKJ84XM5QPC6TK5EE307Q9: без настоящего пересечения `new`
молчит — ни предупреждения, ни записи журнала.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Пересечения нет — `new` не печатает предупреждения и не пишет
записи журнала «пересечение зон при заведении». Пересечение только по
путям, покрытым `config.COMMON_ZONES` (например `tests/` или
`orchestrator/config.py`), пересечением не считается: вывод и журнал те
же, что без пересечения. Задача в `done`/`killed` с пересекающейся зоной
предупреждения не даёт.

Общие зоны берутся из `config.COMMON_ZONES` динамически (`_sandbox.
COMMON_FILE_ZONE`/`COMMON_DIR_ZONE`), не литералами: состав общих зон —
крутилка Оператора.

Зелёный с рождения: сегодня `catalog.cmd_new` не печатает и не
журналирует пересечений вовсе, поэтому все три сценария этого файла
проходят и до правки — это тесты НЕГАТИВНОГО условия, они краснеют
ровно тогда, когда новая сверка начнёт срабатывать шире, чем велит
критерий (общие зоны, закрытые задачи, отсутствие пересечения).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402


class NewSilentWithoutRealOverlapTest(_sandbox.ZoneOverlapSandbox):

    def assert_silent(self, out: str, new_id: str, holder_ids) -> None:
        for holder in holder_ids:
            self.assertEqual(
                [], _sandbox.lines_mentioning(out, holder),
                f"`new` назвал задачу {holder}, хотя настоящего "
                f"пересечения зон нет:\n{out}")
        self.assertNotIn(
            _sandbox.OVERLAP_ACTION, self.journal_actions(new_id),
            f"в журнале {new_id} появилась запись "
            f"«{_sandbox.OVERLAP_ACTION}» без настоящего пересечения")

    def test_ac3_disjoint_zones_produce_no_warning(self):
        """Задача в `in_dev` держит `orchestrator/aaa.py`, ТЗ заявляет
        `orchestrator/bbb.py` — вывод и журнал чисты.

        Ловит мутацию: сверка сравнивает не пути, а сам факт наличия
        непустых зон у кандидата (или сводит пересечение к «оба пути
        начинаются с orchestrator/») — задача T830 попала бы в вывод.
        """
        self.seed_task("T830", "in_dev", "orchestrator/aaa.py")

        out, new_id = self.new_with_zones("orchestrator/bbb.py")

        self.assert_silent(out, new_id, ["T830"])

    def test_ac3_overlap_only_through_common_zones_is_not_an_overlap(self):
        """Единственные общие пути — покрытые `config.COMMON_ZONES`
        (общая зона-файл и путь внутри общей зоны-каталога): ни
        предупреждения, ни записи журнала.

        Ловит мутацию: пути сверяются напрямую `zone_lock._paths_overlap`
        по сырым строкам, без предварительного отсева общих зон
        (`_own_paths`) — обе задачи «пересеклись» бы по
        `orchestrator/config.py`, и каждая волна задач тонула бы в
        ложных предупреждениях.
        """
        inner = f"{_sandbox.COMMON_DIR_ZONE}test_fixture_planki.py"
        self.seed_task("T831", "in_dev",
                       f"{_sandbox.COMMON_FILE_ZONE}, {inner}")

        out, new_id = self.new_with_zones(
            f"{_sandbox.COMMON_FILE_ZONE}, {inner}")

        self.assert_silent(out, new_id, ["T831"])

    def test_ac3_done_and_killed_tasks_never_warn(self):
        """Две закрытые задачи (`done` и `killed`) держат ту же зону,
        что заявляет ТЗ, — предупреждения нет.

        Ловит мутацию: набор состояний сверки описан как «всё, кроме
        задач в полёте» или собран через отрицание, и закрытые задачи в
        него попали — Оператор получал бы предупреждение о зоне, которую
        никто не держит.
        """
        zone = "orchestrator/zakrytaya_zona.py"
        self.seed_task("T832", "done", zone)
        self.seed_task("T833", "killed", zone)

        out, new_id = self.new_with_zones(zone)

        self.assert_silent(out, new_id, ["T832", "T833"])


if __name__ == "__main__":
    unittest.main()
