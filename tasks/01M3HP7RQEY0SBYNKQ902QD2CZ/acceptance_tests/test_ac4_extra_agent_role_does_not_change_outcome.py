"""AC-4: те же тесты `tests/`, что у AC-3, дают тот же исход, когда в карту
исполнителей добавлена ещё одна agent-роль.

Перечень — тот же `_util.ac3_targets()`, что у AC-3 («тот же тест» в
формулировке критерия). Добавляемая роль описана ПОЛНОСТЬЮ и допустимо:
`executor: agent`, ярус — тот же, что у agent-ролей боевой карты (значит,
локальный слой песочницы называет ему модель), скил и слот токена — уже
названные картой. Имя роли планка проверяет на отсутствие в тексте каждого
прогоняемого файла: роль, которую тест называет, критерий из сценария
исключает.

Одна копия дерева и один прогон: добавленная роль одинакова для всех
файлов перечня, группировать по названным ролям здесь нечего.

«Тот же исход», а не «зелено»: сравнение с исходом тех же файлов на
НАСТОЯЩЕЙ карте (`_util.baseline_failures`, общий с AC-3 прогон).

Красен до реализации: состав ролей боевой карты сегодня приезжает в
песочницу `tests/` из боевого файла, и появление ещё одной agent-роли
меняет и перечень ролей предполёта `doctor`, и набор строк `model-<роль>`
манифеста стека — у файлов, которые про состав ролей ничего не утверждают.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402

#: Имя добавляемой роли: нарочно не похоже на роль пульта, чтобы не
#: встретиться в тексте ни одного файла `tests/` случайно.
EXTRA_ROLE = "acceptance_extra_agent"


class ExtraAgentRoleTest(unittest.TestCase):
    """Добавление agent-роли в карту исполнителей."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def test_ac4_one_more_agent_role_does_not_change_the_outcome(self):
        """Карта исполнителей с ещё одной полностью описанной agent-ролью:
        каждый тест, чей предмет не карта ролей, даёт тот же исход, что на
        настоящей карте.

        Ловит мутацию: фикстура песочницы собрана как текст боевого файла
        с подменёнными полями — поля закрыты, а СОСТАВ ролей по-прежнему
        боевой. Появление роли в `roles.yaml` снова меняет перечень ролей
        предполёта и набор строк манифеста стека, и решение Оператора
        завести роль опять красит главную ветку тестами, предмет которых не
        карта (требование 2 SPEC называет добавление agent-роли отдельно
        именно поэтому).
        """
        targets = [rel for rel in _util.ac3_targets()
                   if (_util.REPO_ROOT / rel).is_file()]
        self.assertTrue(
            targets,
            "среди читателей боевой карты не осталось ни одного файла, чей "
            "предмет не карта ролей, — проверять нечего")

        text = _util.real_roles_text()
        agents = _util.agent_roles(text)
        self.assertTrue(agents, f"в {_util.ROLES_REL} нет agent-ролей — яруса "
                                f"для добавляемой роли взять неоткуда")
        self.assertNotIn(EXTRA_ROLE, _util.role_entries(text),
                         f"роль {EXTRA_ROLE} уже есть в карте — планка "
                         f"добавляет роль, которой в карте нет")
        for rel in targets:
            self.assertNotIn(
                EXTRA_ROLE, _util.text_on_disk(rel) or "",
                f"{rel} называет роль {EXTRA_ROLE} — критерий говорит о "
                f"РОЛИ, которую тест не называет")

        mutated = _util.add_agent_role(text, EXTRA_ROLE, {
            "executor": "agent",
            "token_slot": _util.fallback_slot(text),
            "skills": f"[{_util.known_skill(text)}]",
            "model_tier": _util.role_entries(text)[agents[0]].get("model_tier"),
        })
        entries = _util.role_entries(mutated)
        self.assertIn(EXTRA_ROLE, entries, mutated)
        self.assertIn(EXTRA_ROLE, _util.agent_roles(mutated), mutated)
        self.assertEqual(
            {role: entry for role, entry in entries.items()
             if role != EXTRA_ROLE},
            _util.role_entries(text),
            "добавление роли изменило записи остальных ролей — сценарий AC-4 "
            "требует ровно одной новой роли")

        base_failures, base_broken, base_report = \
            _util.baseline_failures(targets)
        self.assertEqual(
            base_broken, [],
            f"прогон перечня на НАСТОЯЩЕЙ карте сломался целиком — сравнивать "
            f"исходы не с чем\n{base_report}")

        code = _util.repo_copy(self.tdir, mutated, name="extra-role")
        try:
            results = _util.run_pytest_many([(code, targets)], timeout=110)
        except subprocess.TimeoutExpired as exc:  # pragma: no cover
            self.fail(f"прогон на карте с добавленной ролью не уложился в "
                      f"отведённое время: {exc}")

        self.assertEqual(
            _util.many_broken(results), [],
            f"прогон на карте с добавленной ролью сломался целиком, ни одного "
            f"названного теста\n{_util.many_report(results)}")
        self.assertEqual(
            _util.many_failures(results), base_failures,
            f"исход изменился от появления в карте роли {EXTRA_ROLE}\n"
            f"на настоящей карте:\n{base_report}\n"
            f"на карте с добавленной ролью:\n{_util.many_report(results)}")


if __name__ == "__main__":
    unittest.main()
