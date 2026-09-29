"""Раздел `role_models:` локального слоя: модель одной роли мимо яруса —
разрешение цепочки роли, именованные отказы и строки `doctor`.

Группа: долгоживущий

Критерии приёмки, которые покрывает файл:

AC-3. Слой с записью `role_models: {<роль>: <модель каталога>}`:
`models.resolve_role(<роль>)` возвращает модель записи независимо от
модели яруса роли; провайдер — из `role_providers:` для этой роли, если
запись там есть, иначе провайдер модели в каталоге. Роль без записи
разрешается через ярус, как до задачи.

AC-4. Запись `role_models:` с моделью вне каталога — `resolve_role`
поднимает подкласс `models.ResolutionError`, текст которого называет роль
и модель; запись с моделью статуса `experimental` без разрешения в
`allow_experimental:` — такой же именованный отказ; с разрешением —
модель разрешается.

AC-5. `doctor` при слое с записями `role_models:` печатает по строке на
каждую запись, называющую роль и её модель из раздела; без раздела таких
строк нет.

Каталог моделей, карта исполнителей и локальный слой — фикстуры
песочницы (`TmpRootTest.use_catalog_fixture`/`use_role_map`, слой пишется
в `config.MODELS_LOCAL` песочницы), не боевые файлы пульта: их состав —
крутилка Оператора. Роли, модели и их сочетания выбираются случайно из
фикстуры при каждом запуске; зерно печатается и входит в текст провала.

«Строка `doctor` на запись» (AC-5) ищется среди проверок
`doctor.all_checks` по содержанию, а не по имени проверки (имени SPEC не
фиксирует): проверка, чей текст называет роль записи и её модель и не
называет модели другой записи. Второе условие отсекает строки-перечни,
называющие все роли разом (`role-providers`, `models-local`, тариф):
они назвали бы обе записи одной строкой, а не «по строке на запись».

Красен до реализации: раздела `role_models:` `models.resolve_role` не
читает — роль разрешается в модель яруса, отказов по записи нет, строк
`doctor` о разделе нет.
"""
import random
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config, doctor, models, store
from tests.sandbox import TmpRootTest

AGENT_ROLES = ("analyst", "test_author", "developer", "reviewer")

TIER_MODEL = "m-yarus-fikstury"
CLAUDE_MODELS = ("m-alfa-fikstury", "m-beta-fikstury", "m-gamma-fikstury")
CLAUDE_EXPERIMENTAL = "m-eksperiment-fikstury"
CODEX_MODEL = "m-kodeks-fikstury"


def _model_block(model_id: str, status: str, min_cli: str) -> str:
    return (f"      {model_id}:\n"
            f"        min_cli_version: {min_cli}\n"
            f"        status: {status}\n"
            f"        list_price_usd_per_mtok:\n"
            f"          input: 5.0\n"
            f"          output: 25.0\n"
            f"          cache_write: 6.25\n"
            f"          cache_read: 0.50\n"
            f"        price_date: 2026-09-20\n")


CATALOG_TEXT = (
    "providers:\n"
    "  claude:\n"
    "    cli: claude\n"
    "    min_cli_version: 1.0.0\n"
    "    cost_from_cli: true\n"
    "    models:\n"
    + _model_block(TIER_MODEL, "supported", "1.0.0")
    + "".join(_model_block(m, "supported", "1.0.0") for m in CLAUDE_MODELS)
    + _model_block(CLAUDE_EXPERIMENTAL, "experimental", "1.0.0")
    + "  codex:\n"
    "    cli: codex\n"
    "    min_cli_version: 0.155.1\n"
    "    cost_from_cli: false\n"
    "    models:\n"
    + _model_block(CODEX_MODEL, "supported", "0.155.1"))

#: Провайдер модели в каталоге-фикстуре.
PROVIDER_OF = {**{m: "claude" for m in (TIER_MODEL, *CLAUDE_MODELS,
                                         CLAUDE_EXPERIMENTAL)},
               CODEX_MODEL: "codex"}


def layer_text(role_models: dict = None, role_providers: dict = None,
               allow: tuple = (), canary_sets: dict = None) -> str:
    """Локальный слой: все ярусы на `TIER_MODEL` плюс названные разделы."""
    text = "tiers:\n" + "".join(f"  {tier}: {TIER_MODEL}\n"
                                for tier in models.TIERS)
    if allow:
        text += "allow_experimental:\n" + "".join(f"  {m}: true\n" for m in allow)
    if role_providers:
        text += "role_providers:\n" + "".join(
            f"  {role}: {name}\n" for role, name in role_providers.items())
    if role_models:
        text += "role_models:\n" + "".join(
            f"  {role}: {model}\n" for role, model in role_models.items())
    if canary_sets:
        text += "canary_sets:\n"
        for set_name, entries in canary_sets.items():
            text += f"  {set_name}:\n"
            for role, model in entries.items():
                text += (f"    {role}:\n      provider: {PROVIDER_OF[model]}\n"
                         f"      model: {model}\n")
    return text


class _RoleModelsSandbox(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.use_catalog_fixture(CATALOG_TEXT)
        self.use_role_map()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def write_layer(self, **sections) -> None:
        Path(config.MODELS_LOCAL).write_text(layer_text(**sections),
                                             encoding="utf-8")

    def msg(self, text: str = "") -> str:
        return f"зерно {self.seed}: {text}"


class RoleModelsResolutionTest(_RoleModelsSandbox):
    """AC-3: запись раздела ведёт роль мимо яруса, соседи — через ярус."""

    def test_ac3_entry_model_wins_over_the_tier_model(self):
        """Роль с записью `role_models:` без записи `role_providers:`.

        Для случайной роли и случайной модели каталога (разных провайдеров)
        `resolve_role` отдаёт модель записи, а не модель яруса роли, и
        провайдера этой модели по каталогу.

        Ловит мутацию: `resolve_role` не читает `role_models:` и
        разрешает роль через ярус — модель `m-yarus-fikstury` вместо модели
        записи; либо берёт модель записи, но провайдера оставляет от модели
        яруса (`claude` для модели раздела `codex`).
        """
        for role in AGENT_ROLES:
            model = self.rng.choice((*CLAUDE_MODELS, CODEX_MODEL))
            self.write_layer(role_models={role: model})

            resolved = models.resolve_role(role)

            self.assertEqual(resolved.model, model,
                             self.msg(f"роль {role}, запись {model}"))
            self.assertEqual(resolved.provider, PROVIDER_OF[model],
                             self.msg(f"роль {role}, запись {model}"))

    def test_ac3_provider_comes_from_role_providers_when_present(self):
        """Роль несёт запись и в `role_models:`, и в `role_providers:`.

        Провайдер разрешения — значение `role_providers:` этой роли, а не
        провайдер модели записи по каталогу (модель и провайдер берутся из
        разных провайдеров, чтобы источники различались).

        Ловит мутацию: провайдер роли с записью `role_models:` всегда
        берётся из каталога по модели записи — `role_providers:` для неё
        игнорируется, и разрешение называет `claude` там, где слой назвал
        `codex` (и наоборот).
        """
        role = self.rng.choice(AGENT_ROLES)
        claude_model = self.rng.choice(CLAUDE_MODELS)
        for model, provider in ((claude_model, "codex"), (CODEX_MODEL, "claude")):
            self.write_layer(role_models={role: model},
                             role_providers={role: provider})

            resolved = models.resolve_role(role)

            self.assertEqual(resolved.model, model,
                             self.msg(f"роль {role}, запись {model}"))
            self.assertEqual(resolved.provider, provider,
                             self.msg(f"роль {role}, запись {model}, "
                                      f"role_providers {provider}"))

    def test_ac3_role_without_entry_still_resolves_through_its_tier(self):
        """Запись раздела есть у одной случайной роли.

        Каждая из остальных агентских ролей (тот же ярус, что у роли с
        записью) разрешается в модель своего яруса и её провайдера, как до
        задачи.

        Ловит мутацию: запись `role_models:` применяется к ярусу роли
        целиком (все роли того же яруса уходят на модель записи) либо ко
        всем ролям слоя — сосед по ярусу получает чужую модель.
        """
        role = self.rng.choice(AGENT_ROLES)
        model = self.rng.choice((*CLAUDE_MODELS, CODEX_MODEL))
        self.write_layer(role_models={role: model})

        for other in AGENT_ROLES:
            if other == role:
                continue
            resolved = models.resolve_role(other)
            self.assertEqual(resolved.model, TIER_MODEL,
                             self.msg(f"роль {other} без записи; запись у "
                                      f"{role} -> {model}"))
            self.assertEqual(resolved.provider, "claude",
                             self.msg(f"роль {other} без записи"))


class RoleModelsRefusalTest(_RoleModelsSandbox):
    """AC-4: запись с негодной моделью — именованный отказ разрешения."""

    def assert_named_refusal(self, role: str, model: str) -> None:
        with self.assertRaises(models.ResolutionError,
                               msg=self.msg(f"роль {role}, запись {model}")) as ctx:
            models.resolve_role(role)
        self.assertIsNot(type(ctx.exception), models.ResolutionError,
                         self.msg("отказ — сам базовый класс, не подкласс"))
        self.assertIn(role, str(ctx.exception), self.msg("роль не названа"))
        self.assertIn(model, str(ctx.exception), self.msg("модель не названа"))

    def test_ac4_model_outside_the_catalog_is_a_named_refusal(self):
        """Запись раздела называет модель, которой нет в каталоге.

        `resolve_role` поднимает подкласс `ResolutionError`, текст
        называет и роль, и модель записи.

        Ловит мутацию: модель записи вне каталога молча пропускается, и
        роль разрешается через ярус (`m-yarus-fikstury`) — отказа нет;
        либо отказ поднимается без имени роли (как у отказа
        `models.catalog_model`, знающего только модель).
        """
        role = self.rng.choice(AGENT_ROLES)
        model = f"m-net-v-kataloge-{self.rng.randrange(10**6):06d}"
        self.write_layer(role_models={role: model})

        self.assert_named_refusal(role, model)

    def test_ac4_experimental_model_without_allowance_is_a_named_refusal(self):
        """Запись раздела называет модель статуса `experimental`.

        Разрешения в `allow_experimental:` нет — именованный отказ с ролью
        и моделью.

        Ловит мутацию: сверка статуса `experimental` стоит только на пути
        яруса — роль уходит на неразрешённую модель записи без отказа.
        """
        role = self.rng.choice(AGENT_ROLES)
        other = self.rng.choice(CLAUDE_MODELS)
        self.write_layer(role_models={role: CLAUDE_EXPERIMENTAL},
                         allow=(other,))

        self.assert_named_refusal(role, CLAUDE_EXPERIMENTAL)

    def test_ac4_experimental_model_with_allowance_resolves(self):
        """Та же запись `experimental`, но с разрешением в слое.

        `resolve_role` отдаёт модель записи без отказа.

        Ловит мутацию: разрешение `allow_experimental:` сверяется только
        для модели яруса, и запись `role_models:` с моделью
        `experimental` отказывает всегда, даже разрешённая.
        """
        role = self.rng.choice(AGENT_ROLES)
        self.write_layer(role_models={role: CLAUDE_EXPERIMENTAL},
                         allow=(CLAUDE_EXPERIMENTAL,))

        resolved = models.resolve_role(role)

        self.assertEqual(resolved.model, CLAUDE_EXPERIMENTAL,
                         self.msg(f"роль {role}"))


class RoleModelsDoctorLinesTest(_RoleModelsSandbox):
    """AC-5: `doctor` — строка на каждую запись раздела."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        # Пул канарейки `doctor` ищет от домашнего каталога — песочница
        # уводит его во временный каталог, не в дом машины прогона.
        home = self.root / "dom"
        home.mkdir()
        patcher = mock.patch.object(Path, "home", lambda *a, **k: home)
        patcher.start()
        self.addCleanup(patcher.stop)
        roles = self.rng.sample(AGENT_ROLES, 2)
        chosen = self.rng.sample(CLAUDE_MODELS, 2)
        self.records = dict(zip(roles, chosen))

    def checks(self) -> list:
        """Все проверки `doctor`; внешние процессы (CLI, git) не
        исполняются — `subprocess` модуля `doctor` отвечает заглушкой."""
        def fake_run(*args, **kwargs):
            raise FileNotFoundError("песочница: внешний процесс не запускается")
        with mock.patch.object(doctor.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(doctor.subprocess, "Popen", side_effect=fake_run):
            return doctor.all_checks(store.db())

    def record_lines(self, checks) -> dict:
        """{роль записи: [текст проверки]} — проверки, называющие роль и её
        модель и не называющие модели другой записи."""
        found = {}
        for role, model in self.records.items():
            others = [m for r, m in self.records.items() if r != role]
            found[role] = [c.detail for c in checks
                           if role in c.detail and model in c.detail
                           and not any(o in c.detail for o in others)]
        return found

    def test_ac5_doctor_prints_a_line_per_role_models_entry(self):
        """Слой с двумя записями `role_models:` (случайные роли, разные
        модели вне ярусов).

        Среди проверок `doctor` для каждой записи есть своя строка,
        называющая роль и её модель из раздела.

        Ловит мутацию: `doctor` раздел не показывает вовсе либо печатает
        его одной общей строкой на все записи — у записи не находится
        собственной строки (строка-перечень называет модели обеих записей).
        """
        self.write_layer(role_models=self.records)

        found = self.record_lines(self.checks())

        for role, model in self.records.items():
            self.assertTrue(found[role],
                            self.msg(f"нет строки doctor о записи "
                                     f"{role} -> {model}; записи: {self.records}"))

    def test_ac5_no_such_lines_without_the_section(self):
        """Слой без раздела `role_models:`, но с набором `canary_sets:`,
        называющим те же роли с теми же моделями.

        Ни одна проверка `doctor` не называет роль с моделью записи
        отдельной строкой.

        Ловит мутацию: строки «роль → модель» `doctor` собирает не из
        раздела `role_models:`, а из записей наборов канарейки (или из
        любого раздела слоя, где встретилась пара роль/модель) — без
        раздела такие строки появляются.
        """
        self.write_layer(canary_sets={"nabor-fikstury": self.records})

        found = self.record_lines(self.checks())

        for role, lines in found.items():
            self.assertEqual(lines, [],
                             self.msg(f"без раздела role_models: строка о "
                                      f"{role} -> {self.records[role]}"))


if __name__ == "__main__":
    unittest.main()
