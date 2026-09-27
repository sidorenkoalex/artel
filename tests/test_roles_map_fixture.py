"""Карта исполнителей и локальный слой моделей тестов — фикстура, а не
боевые файлы пульта (SPEC 01M3HP7RQEY0SBYNKQ902QD2CZ, требования 2-5).

Класс дефекта: штатная правка `roles.yaml` Оператором красит тесты,
предмет которых — не карта. 27.09 смена яруса роли analyst (a6da0abe)
уронила `tests/test_stack_optional_tools.py` (откат d910c523); перевод той
же роли на провайдер Codex ронял `tests/test_analyst_role.py` отказом
«модель роли не поддерживается CLI», а на карте, где ярус analyst
разрешается в модель Codex, краснели `tests/test_doctor.py::
DoctorCommandTest` и `tests/test_stack.py::CheckStackTest` — их подмена
процессов знает один CLI.

Здесь — регрессия на сам механизм: `tests/sandbox.py::role_map_fixture`
собирает карту и слой из литералов песочницы, а не из файлов пульта, и
адресует ими `config.ROLES`/`config.MODELS_LOCAL` на весь процесс
прогона. Последний класс (`LiveRolesMapConsistencyTest`) — обратная
сторона того же: боевой `roles.yaml` остаётся предметом СВОЕГО теста и
обязан краснеть от несогласованной правки (требование 4).

Песочница — готовая `_ManifestSandbox` из
`tests/test_stack_optional_tools.py` (каталог с двумя провайдерами,
настоящий `check_stack()` поверх заготовленных ответов `subprocess.run`):
своей копии этой обвязки здесь не заводится, ни один настоящий CLI не
запускается.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (config, doctor, models, providers,  # noqa: E402
                          roles, yamlmini)
from tests.sandbox import (FIXTURE_ROLES, FIXTURE_TIER,  # noqa: E402
                           FIXTURE_TIER_MODEL, SANDBOX_ROLES_TEXT,
                           role_map_fixture)
from tests.test_stack_optional_tools import (CODEX_MODEL,  # noqa: E402
                                             _ManifestSandbox)

REPO_ROOT = Path(__file__).resolve().parent.parent
LIVE_ROLES_PATH = REPO_ROOT / "roles.yaml"

#: Роль, которую сценарии этого файла НЕ называют: её поля крутит
#: Оператор, и ни один исход от них зависеть не должен.
FOREIGN_ROLE = "analyst"
#: Роль, о которой сценарии и говорят.
OWN_ROLE = "developer"
#: Ярус, отличный от яруса остальных agent-ролей фикстуры (требование 5).
OTHER_TIER = next(tier for tier in models.TIERS if tier != FIXTURE_TIER)
CODEX_PROVIDER = "codex"


class _FixtureMapSandbox(_ManifestSandbox):
    """Карта сценария ставится `use_role_map` (общая фикстура), а каталог
    моделей и `check_stack()` берутся у `_ManifestSandbox`."""

    def ac7_map(self):
        """Карта требования 5: `FOREIGN_ROLE` на провайдере Codex и на
        ярусе, отличном от остальных agent-ролей, а локальный слой
        называет этому ярусу модель Codex."""
        return self.use_role_map(
            roles={FOREIGN_ROLE: {"provider": CODEX_PROVIDER,
                                  "model_tier": OTHER_TIER}},
            tiers={OTHER_TIER: CODEX_MODEL},
            allow_experimental=[CODEX_MODEL])

    def own_role_outcome(self) -> tuple:
        """Исход представительного сценария О РОЛИ `OWN_ROLE`: всё, что
        читает о ней шаг пульта, плюс вердикт строки её модели в
        манифесте. Роль-сосед в этот кортеж не входит по построению —
        предмет такого сценария не она."""
        resolved = models.resolve_role(OWN_ROLE)
        own_line = [c for c in self.stack_checks(codex_found=True)
                    if c.name == f"model-{OWN_ROLE}"]
        return (resolved.tier, resolved.model, resolved.provider,
                tuple(roles.skills(OWN_ROLE)),
                tuple(roles.token_slots(OWN_ROLE)),
                providers.name_for_role(OWN_ROLE),
                tuple(c.status for c in own_line))

    def fail_lines(self) -> tuple:
        """Имена красных строк манифеста при установленных CLI обоих
        провайдеров — мера «карта в целом согласована»."""
        return tuple(sorted(c.name for c in self.stack_checks(codex_found=True)
                            if c.status == "fail"))


class RoleMapFixtureSourceTest(unittest.TestCase):
    """Требования 2-3: источник карты — литерал песочницы, не файл."""

    def test_config_roles_of_the_test_process_is_the_fixture_not_the_live_file(self):
        """`config.ROLES` прогона адресует файл фикстуры песочницы, а не
        `roles.yaml` репозитория, и его содержимое равно
        `SANDBOX_ROLES_TEXT`.

        Ловит мутацию: песочница снова уводит карту условно (прежнее `if
        SANDBOX_ROLES_TEXT != _REAL_ROLES_TEXT`) либо не уводит вовсе —
        каждый тест, доходящий до шага роли, снова читает решение
        Оператора в защищённом файле, и правка провайдера роли красит
        набор целиком (`tests/test_analyst_role.py`, 27.09).
        """
        self.assertNotEqual(Path(config.ROLES), LIVE_ROLES_PATH)
        self.assertEqual(Path(config.ROLES).read_text(encoding="utf-8"),
                         SANDBOX_ROLES_TEXT)

    def test_the_fixture_does_not_read_the_map_it_is_pointed_at(self):
        """Текст фикстуры не меняется, когда `config.ROLES` указывает на
        карту требования 5 (analyst на Codex и на чужом ярусе), а
        `config.MODELS_LOCAL` — на слой с моделью Codex у этого яруса.

        Ловит мутацию: сборщик снова ВЫВОДИТ карту из файла, на который
        смотрит `config.ROLES` (`Path(config.ROLES).read_text()` + правка
        поля) — состав ролей и их ярусы опять приезжают из чужого файла, и
        требование «исход не меняется при добавлении agent-роли» перестаёт
        выполняться в принципе.
        """
        before = role_map_fixture()
        foreign = role_map_fixture(
            roles={FOREIGN_ROLE: {"provider": CODEX_PROVIDER,
                                  "model_tier": OTHER_TIER}},
            tiers={OTHER_TIER: CODEX_MODEL})
        with mock.patch.object(config, "ROLES", LIVE_ROLES_PATH):
            self.assertEqual(role_map_fixture(), before)

        self.assertNotIn(f"provider: {CODEX_PROVIDER}", before.roles_text)
        self.assertIn(f"provider: {CODEX_PROVIDER}", foreign.roles_text)
        entries = yamlmini.mapping(before.roles_text).get("roles") or {}
        self.assertEqual(
            {name for name, entry in entries.items()
             if isinstance(entry, dict) and entry.get("executor") == "agent"},
            {name for name, fields in FIXTURE_ROLES.items()
             if fields.get("executor") == "agent"})
        self.assertEqual(
            {entry.get("model_tier") for name, entry in entries.items()
             if isinstance(entry, dict) and entry.get("executor") == "agent"},
            {FIXTURE_TIER})


class ForeignRoleFieldsTest(_FixtureMapSandbox):
    """Требование 2 (AC-3, AC-4): поля и состав ролей, которых сценарий не
    называет, его исход не двигают."""

    def test_any_allowed_field_of_a_role_the_scenario_does_not_name(self):
        """Исход сценария о роли `OWN_ROLE` один и тот же при любом
        допустимом значении `provider:`/`model_tier:`/`skills:`/
        `token_slot:` у роли-соседа, и ни один вариант не даёт красных
        строк манифеста.

        Ловит мутацию: карта сценария снова собирается из боевого файла
        (или помощник карты перестаёт покрывать моделью все ярусы
        перечня) — сосед на чужом ярусе остаётся без модели, строка
        `model-<роль>` краснеет, и тест краснеет от крутилки Оператора, а
        не от дефекта в своём предмете.
        """
        self.use_role_map()
        baseline = self.own_role_outcome()
        self.assertEqual(self.fail_lines(), ())
        variants = (
            ("провайдер и ярус", {"provider": CODEX_PROVIDER,
                                  "model_tier": OTHER_TIER},
             {OTHER_TIER: CODEX_MODEL}, [CODEX_MODEL]),
            ("ярус", {"model_tier": OTHER_TIER}, None, ()),
            ("скилы", {"skills": ["conventions-core"]}, None, ()),
            ("слот токена", {"token_slot": "artel-drugoy-slot"}, None, ()),
        )

        for name, fields, tiers, allowed in variants:
            with self.subTest(поле=name):
                self.use_role_map(roles={FOREIGN_ROLE: fields}, tiers=tiers,
                                  allow_experimental=allowed)

                self.assertEqual(self.own_role_outcome(), baseline)
                self.assertEqual(self.fail_lines(), ())

    def test_one_more_agent_role_in_the_map_moves_nothing(self):
        """Исход того же сценария не меняется, когда в карту добавлена
        ещё одна agent-роль (AC-4) — и роль эта действительно попадает в
        перечень пульта, иначе сценарий был бы вырожден.

        Ловит мутацию: карта выводится из боевого файла — состав ролей
        приходит из него, добавить роль сценарием нельзя вовсе, и
        требование проверить нечем; либо перебор ролей манифеста молча
        пропускает роль, которой нет в его собственном списке.
        """
        self.use_role_map()
        baseline = self.own_role_outcome()

        self.use_role_map(roles={"sigma": {
            "executor": "agent", "token_slot": "artel-sigma",
            "skills": ["conventions-core"], "model_tier": FIXTURE_TIER}})

        self.assertIn("sigma", doctor.agent_roles())
        self.assertEqual(self.own_role_outcome(), baseline)
        self.assertEqual(self.fail_lines(), ())


class Ac7MapAcceptedTest(_FixtureMapSandbox):
    """Требование 5: карта с analyst на Codex, подменённая самим тестом."""

    def test_the_map_with_a_role_on_codex_is_a_working_configuration(self):
        """Роль-сосед идёт на Codex и разрешается в модель Codex, роль
        сценария остаётся на провайдере по умолчанию, предполёт зелёный, и
        ни одна строка манифеста не красная — карта, которую Оператор
        вправе применить, набор не красит.

        Ловит мутацию: локальный слой фикстуры перестаёт называть модель
        названному ярусу (или разрешение `experimental` теряется) —
        цепочка роли не разрешается, `check_stack()` даёт `model-<роль>`
        со статусом `fail`, и возврат роли analyst на Codex снова стоит
        красной главной ветки.
        """
        self.ac7_map()

        resolved = models.resolve_role(FOREIGN_ROLE)

        self.assertEqual(roles.provider(FOREIGN_ROLE), CODEX_PROVIDER)
        self.assertEqual((resolved.tier, resolved.model, resolved.provider),
                         (OTHER_TIER, CODEX_MODEL, CODEX_PROVIDER))
        own = models.resolve_role(OWN_ROLE)
        self.assertEqual((own.tier, own.model, own.provider),
                         (FIXTURE_TIER, FIXTURE_TIER_MODEL,
                          providers.DEFAULT_PROVIDER))
        self.assertEqual(self.fail_lines(), ())

        with mock.patch.object(doctor.shutil, "which",
                               lambda name, *a, **kw: f"/stub-bin/{name}"):
            check = doctor.check_model_provider_cli()

        self.assertEqual(check.status, "ok", check.detail)


class LiveRolesMapConsistencyTest(unittest.TestCase):
    """Требование 4: боевой `roles.yaml` — предмет своего теста.

    Пока карта песочницы выводилась из боевого файла, его согласованность
    проверялась СЛУЧАЙНО: несогласованная правка красила чужие тесты. С
    фикстурой это покрытие исчезает, и его нужно вернуть явно — иначе
    задача сделала бы систему слабее (принцип целостности): ярус вне
    перечня или незарегистрированный провайдер в карте не заметил бы ни
    один тест до первого отказа шага.

    Файл адресуется путём репозитория, а не `config.ROLES`: последний
    песочница уводит на фикстуру на весь процесс.
    """

    def live_agent_roles(self) -> dict:
        entries = yamlmini.mapping(
            LIVE_ROLES_PATH.read_text(encoding="utf-8")).get("roles") or {}
        return {name: entry for name, entry in entries.items()
                if isinstance(entry, dict) and entry.get("executor") == "agent"}

    def test_every_agent_role_of_the_live_map_is_runnable_as_written(self):
        """У каждой agent-роли боевой карты ярус из перечня
        `models.TIERS`, провайдер из реестра `orchestrator/providers/` и
        скилы, которым есть файлы в `skills/`.

        Ловит мутацию: сверка сведена к «файл разобран» (или к одной
        роли) — опечатка в ярусе, имя провайдера, которого нет в реестре,
        и скил без файла проходят в главную ветку молча, а Оператор
        узнаёт о них отказом первого же шага роли. До фикстуры это ловили
        чужие тесты, доходившие до шага роли на боевой карте.
        """
        agents = self.live_agent_roles()

        self.assertTrue(agents, f"{LIVE_ROLES_PATH}: agent-ролей нет вовсе")
        for role, entry in sorted(agents.items()):
            with self.subTest(роль=role):
                self.assertIn(entry.get("model_tier"), models.TIERS)
                self.assertIn(entry.get("provider")
                              or providers.DEFAULT_PROVIDER,
                              providers.PROVIDERS)
                names = entry.get("skills")
                self.assertIsInstance(names, list)
                for name in names:
                    self.assertTrue((REPO_ROOT / "skills" / f"{name}.md").exists(),
                                    f"скил {name} назван в roles.yaml, но файла нет")


if __name__ == "__main__":
    unittest.main()
