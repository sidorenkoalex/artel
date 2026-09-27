"""Юнит-тесты перечня ролей предполёта `doctor` (SPEC
01M3H3JRBD544GQ10SS3DBGEVP, требования 1-4): источник перечня — карта
исполнителей, а не словарь состояний FSM, и зависимые от роли строки
печатаются для КАЖДОЙ agent-роли карты, включая analyst.

Постоянная регрессия поверх приёмочной планки задачи
(`tasks/01M3H3JRBD544GQ10SS3DBGEVP/acceptance_tests/`): планка уходит
вместе с каталогом задачи, а свойство «роль, добавленная в карту или
переведённая на другой провайдер, получает строки предполёта» обязано её
пережить — именно его отсутствие увело analyst из `doctor` молча, и вход
роли на Codex проверялся руками.

Песочница — общая (`tests/sandbox.py::TmpRootTest`), подмена
`subprocess.run` обоих CLI — готовая из `tests/test_providers_codex.py`
(`_LoginStatusRuns`): ни `claude`, ни `codex` на машине прогона не нужны и
ни разу не запускаются. Своих копий этой обвязки здесь не заводится
(skills/test-authoring.md, «Лёгкая песочница — не копия, импорт»).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (config, doctor, keychain, models,  # noqa: E402
                          providers, roles, runner, store)
from orchestrator.providers import codex as codex_provider  # noqa: E402
from tests.sandbox import TmpDirTest, TmpRootTest  # noqa: E402
from tests.test_providers_codex import (CLAUDE_SECRETS,  # noqa: E402
                                        FORBIDDEN_KEY_NAMES, STUB_BIN,
                                        _drop_ambient, _LoginStatusRuns)

ANALYST = "analyst"
#: Строка секрета провайдера по умолчанию.
CLAUDE_TOKEN_LINE = "token"
#: Строки, предмет которых — сам провайдер, а не роль: в выводе `doctor`
#: каждая обязана остаться одна, сколько бы ролей на провайдере ни шло.
#: Имена — литералами, не ссылками на константы кода: переименование
#: строки `doctor` обязано краснеть здесь, а не сверяться с собой.
CLAUDE_SHARED_LINES = ("cli-found", "cli-version", "role-home-reference")
CODEX_SHARED_LINES = ("codex-cli-found", "codex-cli-version",
                      "codex-role-home")

#: Карта исполнителей сценариев: analyst плюс одна роль на провайдере по
#: умолчанию (нужна, чтобы склейка строк была не вырожденной) плюс роли,
#: которые agent-ролями НЕ являются, — перечень обязан отобрать первые две.
ROLES_TEMPLATE = """\
roles:
  orchestrator:
    executor: system
    token_slot: artel-orchestrator
  analyst:
    executor: {analyst_executor}
    token_slot: artel-analyst
    skills: [conventions-core]
    model_tier: standard
{analyst_provider}  developer:
    executor: {developer_executor}
    token_slot: artel-developer
    skills: [conventions-core]
    model_tier: strong
  verifier:
    executor: none
    token_slot: artel-verifier
token_fallback: artel-token
"""

#: Карта, которую `yamlmini` не разбирает (раздел `roles:` — блочный
#: список, а не отображение): сценарий «карта нечитаема».
UNREADABLE_ROLES_TEXT = "roles:\n  - developer\n"


def roles_yaml(analyst_provider: str = None, analyst_executor: str = "agent",
               developer_executor: str = "agent") -> str:
    """Текст карты исполнителей сценария: провайдер роли analyst и поле
    `executor:` каждой из двух ролей — параметры, остальное неизменно."""
    line = f"    provider: {analyst_provider}\n" if analyst_provider else ""
    return ROLES_TEMPLATE.format(analyst_executor=analyst_executor,
                                 analyst_provider=line,
                                 developer_executor=developer_executor)


def map_agent_roles() -> list:
    """Отсортированные роли карты с `executor: agent`, прочитанные тем же
    файлом, что читает `doctor`, — без предположений о его содержимом."""
    return sorted(name for name, entry in roles.load().items()
                  if isinstance(entry, dict)
                  and entry.get("executor") == "agent")


class AgentRolesListTest(TmpDirTest):
    """Требование 1: источник перечня — карта исполнителей, не FSM."""

    def use_roles(self, text: str) -> None:
        path = self.tdir / "roles-under-test.yaml"
        path.write_text(text, encoding="utf-8")
        patcher = mock.patch.object(config, "ROLES", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_list_covers_every_executor_agent_role_of_the_map(self):
        """Перечень `doctor.agent_roles()` на карте пульта совпадает с
        составом её agent-ролей, и analyst в нём есть.

        Ловит мутацию: источник перечня оставлен словарём состояний
        (`config.STATE_ROLE.values()`) — analyst, у которого нет своего
        состояния в этом словаре, не получает ни одной зависимой от роли
        строки предполёта, и вход его провайдера проверяется руками.
        """
        expected = map_agent_roles()

        self.assertIn(ANALYST, expected, f"{config.ROLES}: analyst обязан "
                                         f"быть agent-ролью — иначе сверять "
                                         f"нечего")
        self.assertEqual(doctor.agent_roles(), expected)
        self.assertNotEqual(doctor.agent_roles(),
                            sorted(set(config.STATE_ROLE.values())))

    def test_the_list_follows_the_map_not_the_fsm_state_dictionary(self):
        """На карте, где единственная agent-роль — analyst, перечень равен
        `['analyst']`: карта говорит одно, `config.STATE_ROLE` — другое.

        Ловит мутацию: перечень собран объединением карты и
        `config.STATE_ROLE` («так надёжнее, ничего не потеряется») — роли,
        снятой с агента в карте, продолжают считать токен и вход, и
        `doctor` печатает строки предполёта для роли, которая шагов больше
        не делает.
        """
        self.use_roles(roles_yaml(developer_executor="none"))

        self.assertEqual(doctor.agent_roles(), [ANALYST])

    def test_state_role_dictionary_is_not_the_place_analyst_was_added_to(self):
        """`config.STATE_ROLE` не получил ни роли analyst, ни её состояния.

        Ловит мутацию: analyst «добавлен в перечень» дописыванием
        `spec_writing: analyst` в `config.STATE_ROLE` вместо смены
        источника — тогда каждый читатель словаря (`runner.step_role`,
        `auto`, `pause`, `doctor.leases`) начинает считать `spec_writing`
        обычным рабочим состоянием роли, и FSM меняет поведение там, где
        задача обещала не трогать ничего.
        """
        self.assertNotIn(ANALYST, set(config.STATE_ROLE.values()))
        self.assertNotIn("spec_writing", config.STATE_ROLE)

    def test_the_strict_list_raises_while_the_degrading_one_empties(self):
        """На нечитаемой карте `agent_roles()` отдаёт `RolesError` с
        причиной, а `agent_roles_or_empty()` — пустой перечень.

        Ловит мутацию: строгий перечень деградирует сам («чтобы `doctor` не
        падал») — строка `role-providers` зеленеет с ролями на провайдере
        по умолчанию, утверждая прочитанным файл, которого не читала.
        Обратная мутация: деградирующего перечня нет вовсе, и каждая строка
        `doctor`, перебирающая роли, роняет прогон трейсбеком.
        """
        self.use_roles(UNREADABLE_ROLES_TEXT)

        with self.assertRaises(roles.RolesError) as raised:
            doctor.agent_roles()

        self.assertIn("не разобран", str(raised.exception))
        self.assertEqual(doctor.agent_roles_or_empty(), [])


class DoctorLinesSandbox(TmpRootTest):
    """Песочница строк `doctor`, зависящих от перечня ролей: токен роли из
    подменённого keychain, погашенный ambient-канал секретов, найденный
    любой CLI, резолв объявленных инструментов манифеста в подменённый
    путь и подменённый `subprocess.run` пакета `doctor`."""

    def setUp(self):
        super().setUp()
        # Ambient-канал токена Claude сильнее слота keychain, а внутри шага
        # роли пульт кладёт его в окружение по построению: не погасив, строка
        # `token` вышла бы безымянной («токен уже в окружении»), склейка
        # схлопнула бы её в ОДНУ на все роли, и тест про строку роли analyst
        # краснел бы на машине Оператора без единого дефекта в коде.
        _drop_ambient(self, *CLAUDE_SECRETS, *FORBIDDEN_KEY_NAMES)
        self.patch(keychain, "token", lambda slot: "tok-test")
        self.patch(doctor.shutil, "which", lambda name, *a, **kw:
                   f"{STUB_BIN}/{name}")
        self.patch(runner, "declared_tool_path",
                   lambda name: f"{STUB_BIN}/{name}")
        self.runs = _LoginStatusRuns()
        self.patch(doctor.subprocess, "run", self.runs)

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def use_roles(self, text: str) -> None:
        path = self.root / "roles-under-test.yaml"
        path.write_text(text, encoding="utf-8")
        self.patch(config, "ROLES", path)

    def role_named(self, checks: list) -> list:
        """Проверки, чей текст называет роль analyst."""
        return [check for check in checks if ANALYST in check.detail]


class AnalystPreflightLinesTest(DoctorLinesSandbox):
    """Требования 2-3: строки предполёта analyst на обоих провайдерах."""

    def test_analyst_on_codex_gets_the_subscription_login_and_codex_home(self):
        """Карта держит analyst на `codex`: склейка предполёта несёт строку
        подписочного входа, названную ролью, и строку дома роли Codex, а
        цепочка роли стоит и в `role-providers`, и в `models-local`.

        Ловит мутацию: перечень ролей расширен, а склейка по-прежнему
        спрашивает провайдера ОДНОЙ роли (или провайдера по умолчанию
        вместо провайдера роли) — analyst на Codex получает зелёные строки
        Claude, невыполненный вход ChatGPT не всплывает нигде, и шаг уходит
        платной попыткой в неавторизованный CLI.
        """
        self.use_roles(roles_yaml(analyst_provider=codex_provider.CLI_NAME))

        grouped = doctor.provider_preflight_checks()

        auth = self.role_named(grouped.get(doctor.CODEX_AUTH_CHECK, []))
        self.assertEqual(len(auth), 1, sorted(grouped))
        self.assertEqual(auth[0].status, "ok", auth[0].detail)
        self.assertIn("codex-role-home", grouped, sorted(grouped))

        resolved = models.resolve_role(ANALYST)
        chain = f"{ANALYST} → {resolved.tier} → {resolved.model}"
        role_providers = doctor.check_role_providers()
        models_local = doctor.check_models_local()
        self.assertEqual(role_providers.status, "ok", role_providers.detail)
        self.assertIn(f"{chain} → {codex_provider.CLI_NAME}",
                      role_providers.detail)
        self.assertEqual(models_local.status, "ok", models_local.detail)
        self.assertIn(chain, models_local.detail)

    def test_a_claude_only_pult_gets_no_codex_lines_at_all(self):
        """Карта держит analyst на провайдере по умолчанию: строка секрета
        Claude названа ролью, дом роли Claude на месте, а ни одной строки
        Codex не появляется — и `codex` ни разу не запускается.

        Ловит мутацию: строки провайдера подставлены жёстко под Codex
        («analyst же пробная роль на Codex») — пульт, где analyst остался на
        Claude, начинает платить подпроцессом `codex login status` и
        краснеть на инструменте, которого у него нет; либо строка секрета
        перестала называть роль, и склейка схлопывает её в одну на все
        роли, прячя отсутствие токена у analyst.
        """
        self.use_roles(roles_yaml(analyst_provider=providers.DEFAULT_PROVIDER))

        grouped = doctor.provider_preflight_checks()

        token = self.role_named(grouped.get(CLAUDE_TOKEN_LINE, []))
        self.assertEqual(len(token), 1, sorted(grouped))
        self.assertEqual(token[0].status, "ok", token[0].detail)
        self.assertIn("role-home-reference", grouped, sorted(grouped))
        self.assertNotIn(doctor.CODEX_AUTH_CHECK, grouped, sorted(grouped))
        self.assertNotIn("codex-role-home", grouped, sorted(grouped))
        self.assertEqual(self.runs.login_calls, [], self.runs.login_calls)

    def test_role_independent_lines_stay_one_per_provider(self):
        """На карте, где analyst идёт на Codex, а вторая роль — на Claude,
        каждая не зависящая от роли строка ОБОИХ провайдеров печатается
        один раз, а строка авторизации — по одной на роль своего
        провайдера.

        Ловит мутацию: расширяя перечень ролей, снимают дедупликацию
        склейки (или склеивают по роли, а не по имени строки) — «CLI
        найден», «версия CLI» и «дом роли» печатаются по разу на роль, и
        Оператор ищет настоящий провал в учетверённом списке. Обратная
        мутация: схлопнуты и зависимые от роли строки — отсутствие токена у
        одной роли исчезает за зелёной строкой другой.
        """
        self.use_roles(roles_yaml(analyst_provider=codex_provider.CLI_NAME))
        claude_roles = [role for role in doctor.agent_roles()
                        if providers.name_for_role(role)
                        == providers.DEFAULT_PROVIDER]
        self.assertTrue(claude_roles, "сценарию нужны роли на Claude")

        grouped = doctor.provider_preflight_checks()

        for name in CLAUDE_SHARED_LINES + CODEX_SHARED_LINES:
            with self.subTest(line=name):
                self.assertEqual(len(grouped.get(name, [])), 1,
                                 f"{name}: {grouped.get(name)}")
        self.assertEqual(len(grouped.get(CLAUDE_TOKEN_LINE, [])),
                         len(claude_roles), grouped.get(CLAUDE_TOKEN_LINE))
        self.assertEqual(len(grouped.get(doctor.CODEX_AUTH_CHECK, [])), 1,
                         grouped.get(doctor.CODEX_AUTH_CHECK))

    def test_promoting_a_role_in_the_map_only_adds_lines_naming_it(self):
        """Два прогона склейки на карте, где все роли на Claude: без
        analyst как agent-роли и с ним. Ни одна строка не исчезла и не
        изменилась — добавились только строки, называющие analyst.

        Ловит мутацию: перечень ролей стал источником и для строк, которые
        ролью не параметризованы, — прежние строки размножились или
        поменяли текст, и `doctor` привычного пульта перестал читаться
        (Оператор сверяет вывод глазами и от прогона к прогону ждёт прежних
        строк).
        """
        self.use_roles(roles_yaml(analyst_executor="none"))
        before = self.flat_lines()

        self.use_roles(roles_yaml(analyst_provider=providers.DEFAULT_PROVIDER))
        after = self.flat_lines()

        self.assertEqual(before - after, set(),
                         "строки прежнего вывода исчезли или изменились")
        added = after - before
        self.assertTrue(added, "ни одной строки роли analyst не добавилось")
        self.assertEqual([entry for entry in sorted(added)
                          if ANALYST not in entry[1]], [],
                         f"добавились строки, не называющие analyst: {added}")

    def flat_lines(self) -> set:
        """`{(имя строки, текст)}` склейки предполёта — вывод как множество
        строк, годное для сравнения двух прогонов."""
        return {(name, check.detail)
                for name, checks in doctor.provider_preflight_checks().items()
                for check in checks}


class UnreadableRolesMapTest(DoctorLinesSandbox):
    """Требование 4: нечитаемая карта — именованный отказ, не падение."""

    def setUp(self):
        super().setUp()
        self.use_roles(UNREADABLE_ROLES_TEXT)

    def test_role_providers_keeps_its_named_refusal(self):
        """Строка `role-providers` остаётся жёлтой и называет причину от
        `roles`: файл и то, что он не разобран.

        Ловит мутацию: перечень ролей читается ДО входа в обработку
        `RolesError` — строка теряет причину, и Оператор видит «провайдеры
        ролей: —» без имени файла и без слова о разборе.
        """
        check = doctor.check_role_providers()

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn("провайдеры ролей:", check.detail)
        self.assertIn("не разобран", check.detail)
        self.assertIn(str(config.ROLES), check.detail)

    def test_no_line_that_walks_the_roles_crashes(self):
        """Ни одна перебирающая роли функция `doctor` не роняет исключение
        на нечитаемой карте — каждая отвечает значением.

        Ловит мутацию: читатели перечня (`models-local`, склейка предполёта
        провайдеров, тариф моделей, сверка «провайдер роли ≠ провайдер её
        модели», секреты чужих провайдеров) зовут строгий перечень вне
        обработки отказа — одна опечатка в `roles.yaml` роняет прогон
        `doctor` трейсбеком целиком, вместе со строками, которые к карте
        отношения не имеют (диск, сироты, lease).
        """
        conn = store.db()
        self.addCleanup(conn.close)
        callables = (
            ("check_models_local", doctor.check_models_local),
            ("check_role_providers", doctor.check_role_providers),
            ("model_provider_mismatches", doctor.model_provider_mismatches),
            ("check_model_provider_cli", doctor.check_model_provider_cli),
            ("provider_preflight_checks", doctor.provider_preflight_checks),
            ("check_model_tariff_freshness",
             doctor.check_model_tariff_freshness),
            ("check_model_tariff_vs_model_change",
             lambda: doctor.check_model_tariff_vs_model_change(conn)),
            ("check_foreign_provider_secrets",
             doctor.check_foreign_provider_secrets),
        )

        for name, call in callables:
            with self.subTest(line=name):
                try:
                    result = call()
                except Exception as exc:  # noqa: BLE001 — предмет теста
                    self.fail(f"{name} упал на нечитаемой карте: {exc!r}")
                self.assertIsNotNone(result, name)


if __name__ == "__main__":
    unittest.main()
