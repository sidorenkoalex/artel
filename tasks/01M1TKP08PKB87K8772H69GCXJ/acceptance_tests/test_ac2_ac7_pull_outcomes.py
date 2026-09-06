"""AC-2 / AC-7 задачи 01M1TKP08PKB87K8772H69GCXJ.

AC-2: `orchestrator.fsm._pull_main_or_escalate` сохраняет сигнатуру
`(conn, task_id, t, state) -> str` и прежний контракт возврата
(`"escalated"`/`"refused"`/`"fresh"`/`"pulled"`), делегируя вычисление
исхода `pull.py`. AC-7: новые юнит-тесты на `pull.py` в лёгкой
песочнице покрывают все четыре исхода — здесь тем же приёмом лёгкой
песочницы, что и `tests/test_branch_freshness_gate.py`/`tests/test_fsm_
map_conflict_autoresolve.py` (SPEC требование 5), плюс структурная
проверка, что `pull.py` реально КОНСТРУИРУЕТ все четыре типа исхода
(не только их объявляет).

Красен до реализации: тесты AC-7 (`test_ac7_*`, класс
`Ac7OutcomesConstructedTest`) падают уже сегодня — `orchestrator/pull.py`
ещё не существует, конструировать четыре исхода негде.

Зелёный с рождения: остальные тесты файла (`Ac2SignatureTest`,
`Ac2Ac7OutcomeTest`) — не по этой причине. Контракт сигнатуры/возврата
`_pull_main_or_escalate` не меняется этой задачей (правило фазы R,
требование 4) — сегодняшний код уже удовлетворяет им, они написаны и
провалидированы ПРОТИВ него (задача только переносит реализацию внутрь
`pull.py`, не имеет права изменить наблюдаемое поведение).
"""
import ast
import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import MAP_REL, PullNodeSandbox  # noqa: E402
from orchestrator import acceptance, config, fsm, gitcmd  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
PULL_PY = REPO_ROOT / "orchestrator" / "pull.py"

OUTCOME_NAMES = ("Fresh", "Pulled", "Conflict", "Refused")


class Ac2SignatureTest(unittest.TestCase):

    def test_ac2_signature_unchanged(self):
        """`_pull_main_or_escalate` принимает ровно `(conn, task_id, t,
        state)`, в этом порядке — тот же контракт, что и до переноса
        логики в `pull.py`.

        Ловит мутацию: сигнатура правится под новую делегацию (например,
        добавляется параметр самого модуля `pull` или убирается `state`)
        — `assertEqual` по списку имён параметров это поймает.
        """
        sig = inspect.signature(fsm._pull_main_or_escalate)
        self.assertEqual(list(sig.parameters), ["conn", "task_id", "t", "state"])


class Ac2Ac7OutcomeTest(PullNodeSandbox):

    def test_ac2_fresh_outcome_returned_when_branch_not_behind(self):
        """Ветка не отстала от origin (`commits_behind` -> 0) — узел
        обязан вернуть строковый литерал `"fresh"`, не трогая merge/git
        вовсе.

        Ловит мутацию: делегация `pull.py` меняет контракт возврата на
        сам объект исхода (`pull.Fresh()`) вместо строки `"fresh"` —
        `assertEqual`/`assertIsInstance` на `str` это поймает.
        """
        with mock.patch.object(gitcmd, "commits_behind", return_value=0):
            outcome = self.pull()

        self.assertIsInstance(outcome, str)
        self.assertEqual(outcome, "fresh")

    def test_ac2_ac7_pulled_outcome_after_clean_merge_and_green_acceptance(self):
        """Ветка отстала, merge проходит без конфликта, приёмочные тесты
        планки зелёные — узел обязан вернуть `"pulled"`.

        Ловит мутацию: делегация `pull.py` теряет случай успешной
        подтяжки (например, всегда возвращает `Conflict`/`Refused` по
        ошибке маршрутизации исходов) — `assertEqual` по возврату это
        поймает.
        """
        self.write_acceptance_plank()
        side_effect = self.in_repo_side_effect()
        with mock.patch.object(gitcmd, "commits_behind", return_value=3), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            outcome = self.pull()

        self.assertEqual(outcome, "pulled")
        self.assertEqual(len(self.merge_calls), 1)
        self.assertEqual(self.abort_calls, [])

    def test_ac2_ac7_escalated_outcome_on_two_file_conflict(self):
        """Конфликт merge по двум файлам (карта + посторонний файл) —
        неразрешаемый: узел обязан откатить merge и вернуть `"escalated"`.

        Ловит мутацию: делегация `pull.py` теряет ветвление
        «авторазрешаемо только когда единственный конфликт — карта» и
        трактует ЛЮБОЙ конфликт как авторазрешённый (или наоборот, теряет
        сам исход `Conflict` и падает трейсбеком) — `assertEqual`
        по возврату и по числу `abort_calls` это поймает.
        """
        side_effect = self.in_repo_side_effect(
            conflict_files=[MAP_REL, "shared.txt"],
            merge_stderr="CONFLICT (content): Merge conflict in "
            "docs/codebase-map.md")
        with mock.patch.object(gitcmd, "commits_behind", return_value=5), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run") as acc_run:
            outcome = self.pull()

        self.assertEqual(outcome, "escalated")
        self.assertEqual(self.state(), "escalated")
        self.assertEqual(len(self.merge_calls), 1)
        self.assertEqual(len(self.abort_calls), 1)
        acc_run.assert_not_called()

    def test_ac2_ac7_refused_outcome_when_plank_missing_and_ac_required(self):
        """SPEC несёт AC-разметку (`requires_ac_markup` — `True`), но
        артефактная ветка не несёт `acceptance_tests/` — узел обязан
        отказать именованно (`"refused"`), не эскалировать и не пройти
        молчаливо `"pulled"`.

        Ловит мутацию: делегация `pull.py` схлопывает «планка не
        найдена, AC-разметка обязательна» в тот же исход, что и
        легитимный вырожденный случай (`skip_tests`) — `assertEqual` по
        возврату и неизменности состояния это поймает.
        """
        self.write_spec_requiring_ac_without_plank()
        side_effect = self.in_repo_side_effect()
        with mock.patch.object(gitcmd, "commits_behind", return_value=2), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run") as acc_run:
            outcome = self.pull()

        self.assertEqual(outcome, "refused")
        self.assertEqual(self.state(), "in_dev",
                         "refused не имеет права менять состояние задачи")
        acc_run.assert_not_called()


class Ac7OutcomesConstructedTest(unittest.TestCase):

    def test_ac7_pull_module_constructs_all_four_outcome_variants(self):
        """`orchestrator/pull.py` не просто ОБЪЯВЛЯЕТ `Fresh`/`Pulled`/
        `Conflict`/`Refused` (AC-1), но и реально СОЗДАЁТ экземпляр
        каждого из них хотя бы в одном месте исходного текста — иначе
        один из четырёх исходов объявлен, но никогда не производится ни
        одной веткой кода.

        Ловит мутацию: `pull.py` заводит все четыре типа, но одна из
        веток (например, именованный отказ `Refused`) на деле
        возвращает `None`/строку вместо `Refused(...)` — `assertTrue` по
        числу `ast.Call`-конструкций каждого имени это поймает.
        """
        self.assertTrue(PULL_PY.is_file(),
                        f"{PULL_PY} не существует — модуль pull.py не заведён")
        source = PULL_PY.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(PULL_PY))

        constructed = {name: 0 for name in OUTCOME_NAMES}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None)
            if name in constructed:
                constructed[name] += 1

        for name, count in constructed.items():
            self.assertGreaterEqual(
                count, 1, f"pull.py объявляет {name}, но нигде не создаёт "
                f"его экземпляр ({name}(...) ни разу не встречается)")


if __name__ == "__main__":
    unittest.main()
