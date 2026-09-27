"""Регрессия 27.09: строки манифеста стека не зависят от того, на каких
ярусах стоят agent-роли, которых тест не называет (SPEC
01M3H5FEXH5M9HGZYT3BCDX5C4, требование 6, AC-5).

Тесты `tests/`, которым нужна управляемая карта исполнителей, строят её
из НАСТОЯЩЕГО `roles.yaml` (`_roles_yaml_text`): ярус подменяется у ОДНОЙ
названной роли, остальные остаются такими, как в боевом файле. Локальный
слой такая песочница пишет свой — и пока он называл модель только у
яруса роли под тестом, роль на другом ярусе оставалась без модели: её
цепочка «роль -> ярус -> модель» не разрешалась, и `orchestrator/stack.py`
давал строку `model-<роль>` со статусом `fail`. Так перевод роли analyst
на ярус `standard` уронил на главной ветке
`tests/test_stack_optional_tools.py` — покраснело распределение ролей по
ярусам, решение Оператора в защищённом `roles.yaml`, а не предмет
проверки (копилка 27.09, откат d910c523).

Песочница — готовая `_ManifestSandbox` из
`tests/test_stack_optional_tools.py` (каталог с двумя провайдерами,
настоящий `check_stack()` поверх заготовленных ответов `subprocess.run`):
своей копии этой обвязки здесь не заводится.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, models, roles, yamlmini  # noqa: E402
from tests.sandbox import roles_text_on_default_provider  # noqa: E402
from tests.test_runner_role_model import (_REAL_ROLES_TEXT,  # noqa: E402
                                          _roles_yaml_text, _tiers_text)
from tests.test_stack_optional_tools import (CLAUDE_MODEL,  # noqa: E402
                                             _ManifestSandbox)


def _spread_roles_text() -> tuple:
    """(текст карты исполнителей, роль, её ярус): ровно одна agent-роль
    переставлена на ярус перечня `models.TIERS`, которого нет ни у одной
    из остальных agent-ролей.

    Ярус выбирается по факту боевого файла, а не литералом: сегодня все
    agent-роли стоят на `strong`, но распределение — крутилка Оператора,
    и прибитый литерал перестал бы давать разброс ровно в тот день, когда
    Оператор переставит роли. Если разброс в боевом файле уже есть
    (agent-роли заняли все ярусы перечня), карта берётся как есть —
    переставлять нечего.

    Провайдер у ролей — по умолчанию (`roles_text_on_default_provider`):
    предмет сценария — РАЗБРОС ЯРУСОВ, а `provider: codex` у любой роли
    боевого файла делает CLI второго провайдера обязательным и даёт
    песочнице (`codex_found=False`) красную строку мимо предмета. Тот же
    класс, что и ярус выше: и то и другое — крутилка Оператора в
    защищённом файле, которую он правит отдельным MR без прогона этих
    тестов (REVIEW.md 01M3H3JRBD544GQ10SS3DBGEVP итерации 1, R1-F1).
    """
    entries = yamlmini.mapping(_REAL_ROLES_TEXT).get("roles") or {}
    agents = [name for name, entry in entries.items()
              if isinstance(entry, dict) and entry.get("executor") == "agent"]
    role = agents[0]
    taken = {entries[name].get("model_tier")
             for name in agents if name != role}
    free = [tier for tier in models.TIERS if tier not in taken]
    if not free:
        return (roles_text_on_default_provider(_REAL_ROLES_TEXT), role,
                entries[role].get("model_tier"))
    return (roles_text_on_default_provider(_roles_yaml_text(role, free[0])),
            role, free[0])


class RolesTierSpreadTest(_ManifestSandbox):
    """Карта исполнителей с разбросом ярусов — требование 6."""

    def use_spread(self) -> None:
        """Карта исполнителей с разбросом ярусов плюс локальный слой
        песочницы: `self.spread_role` стоит на `self.spread_tier`,
        остальные agent-роли — на своих ярусах боевого файла."""
        text, self.spread_role, self.spread_tier = _spread_roles_text()
        self.roles_path.write_text(text, encoding="utf-8")
        self.patch(config, "ROLES", self.roles_path)
        config.MODELS_LOCAL.write_text(_tiers_text(CLAUDE_MODEL),
                                       encoding="utf-8")

    def agent_tiers(self) -> dict:
        return {name: roles.model_tier(name)
                for name, entry in roles.load().items()
                if isinstance(entry, dict) and entry.get("executor") == "agent"}

    def test_a_role_on_its_own_tier_leaves_no_red_model_line(self):
        """Ловит мутацию: локальный слой песочницы снова называет модель
        у ОДНОГО яруса (`_tiers_text` -> `tiers:\\n  strong: …`) — роль,
        стоящая на другом ярусе, остаётся без модели, её цепочка не
        разрешается, и `check_stack()` даёт `model-<роль>` со статусом
        `fail`. Тест краснеет от решения Оператора в защищённом
        `roles.yaml`, а не от дефекта в предмете проверки — ровно тот
        отказ, которым 27.09 покраснела главная ветка."""
        self.use_spread()
        tiers = self.agent_tiers()

        checks = self.stack_checks(codex_found=False)

        self.assertGreaterEqual(
            len(set(tiers.values())), 2,
            f"предмет сценария — разброс ярусов, а их один: {tiers}")
        self.assertEqual(tiers[self.spread_role], self.spread_tier, tiers)
        self.assertEqual([c.name for c in checks if c.status == "fail"], [],
                         [c.detail for c in checks if c.status == "fail"])

    def test_every_agent_role_of_the_spread_map_gets_a_green_model_line(self):
        """Строки моделей ролей зелёные, а не просто «не красные»
        (требование 6): отсутствие строки — тоже отсутствие `fail`.

        Ловит мутацию: роль, чей ярус не совпал с ярусом роли под тестом,
        выпадает из перебора `stack._model_checks` вовсе — `doctor`
        молчит о ней, и Оператор узнаёт о нерабочей цепочке отказом
        первого же шага этой роли."""
        self.use_spread()
        tiers = self.agent_tiers()

        checks = self.stack_checks(codex_found=False)

        lines = {c.name: c for c in checks if c.name.startswith("model-")}
        self.assertEqual(sorted(lines),
                         sorted(f"model-{name}" for name in tiers))
        for name, check in sorted(lines.items()):
            with self.subTest(line=name):
                self.assertEqual(check.status, "ok", check.detail)

    def test_the_sandbox_layer_names_a_model_for_every_tier_of_the_list(self):
        """Прямая проверка помощника, которым слой пишут все песочницы
        этого класса (требование 1): перечень ярусов растёт правкой
        `models.TIERS`, и слой обязан ехать за ним сам.

        Ловит мутацию: `_tiers_text` называет подмножество перечня (новый
        ярус добавлен в `models.TIERS`, а в помощник — нет) — роль на
        новом ярусе снова остаётся без модели, и класс отказа возвращается
        целиком, молча и на всех песочницах сразу."""
        config.MODELS_LOCAL.write_text(_tiers_text(CLAUDE_MODEL),
                                       encoding="utf-8")

        layer = models.load_local()

        self.assertEqual(sorted(layer.tiers), sorted(models.TIERS))
        self.assertEqual(set(layer.tiers.values()), {CLAUDE_MODEL})


if __name__ == "__main__":
    unittest.main()
