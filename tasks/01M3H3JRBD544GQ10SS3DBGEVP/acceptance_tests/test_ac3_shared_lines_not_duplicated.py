"""AC-3 — 01M3H3JRBD544GQ10SS3DBGEVP: общие строки не дублируются, а
вывод пульта на Claude меняется только добавлением строк analyst.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Проверки, не зависящие от роли, остаются склеенными в одну строку
на провайдера; в пульте, где все роли используют Claude, вывод doctor
отличается от прежнего только добавлением строк роли analyst.

«Прежний вывод» воспроизводится не памятью и не снимком текста, а картой
исполнителей, в которой analyst не agent-роль: перечень ролей `doctor` на
такой карте равен `sorted(set(config.STATE_ROLE.values()))` — ровно тому
перечню, из которого вывод собирался до задачи (тест это и утверждает
прежде сравнения, иначе сравнивались бы два произвольных прогона).

Красен до реализации: на карте с analyst перечень ролей `doctor` не
меняется, и второй прогон отдаёт то же самое, что первый — добавленных
строк роли analyst нет ни одной.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, doctor, providers  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402

from _analyst import (ANALYST, DoctorLinesSandbox, chain_items,  # noqa: E402
                      roles_with)

#: Строки, не зависящие от роли: их предмет — сам провайдер (найденный
#: CLI, его версия, развёрнутый дом роли), и в выводе `doctor` каждая
#: обязана остаться одна на провайдера, сколько бы ролей на нём ни шло.
CLAUDE_SHARED_LINES = ("cli-found", "cli-version", "role-home-reference")
CODEX_SHARED_LINES = ("codex-cli-found", "codex-cli-version",
                      "codex-role-home")


class SharedLinesTest(DoctorLinesSandbox):
    """Склейка провайдерских строк и разница вывода с прежним."""

    def test_ac3_role_independent_lines_stay_one_per_provider(self):
        """На карте, где analyst идёт на Codex, а остальные роли — на
        Claude, каждая не зависящая от роли строка ОБОИХ провайдеров
        печатается один раз, а строка авторизации — по одной на роль
        своего провайдера.

        Ловит мутацию: расширяя перечень ролей, снимают дедупликацию
        склейки (или склеивают по роли, а не по имени строки) — «CLI
        найден», «версия CLI» и «дом роли» печатаются по разу на роль, и
        Оператор ищет настоящий провал в учетверённом списке. Обратная
        мутация: схлопнуты и зависимые от роли строки — отсутствие токена
        у одной роли исчезает за зелёной строкой другой.
        """
        self.use_roles(roles_with(ANALYST, provider=codex_provider.CLI_NAME))
        claude_roles = [role for role in doctor.agent_roles()
                        if providers.name_for_role(role)
                        == providers.DEFAULT_PROVIDER]
        self.assertTrue(claude_roles, "сценарию нужны роли на Claude")

        grouped = self.grouped_provider_lines()

        for name in CLAUDE_SHARED_LINES + CODEX_SHARED_LINES:
            with self.subTest(line=name):
                self.assertEqual(len(grouped.get(name, [])), 1,
                                 f"{name}: {grouped.get(name)}")
        self.assertEqual(len(grouped.get("token", [])), len(claude_roles),
                         grouped.get("token"))
        self.assertEqual(len(grouped.get(doctor.CODEX_AUTH_CHECK, [])), 1,
                         grouped.get(doctor.CODEX_AUTH_CHECK))

    def test_ac3_claude_only_pult_output_differs_only_by_analyst_lines(self):
        """Два прогона одного и того же набора строк `doctor` на пульте,
        где все роли на Claude: карта без analyst как agent-роли (прежний
        вывод) и карта с ним. Ни одна строка не исчезла и не изменилась —
        добавились только строки, называющие analyst; цепочки прежних
        ролей в `role-providers` и `models-local` сохранены слово в слово.

        Ловит мутацию: перечень ролей стал источником и для строк, которые
        ролью не параметризованы, — прежние строки размножились или
        поменяли текст, и `doctor` привычного пульта перестал читаться
        (Оператор сверяет вывод глазами и от прогона к прогону ждёт
        прежних строк). Вторая мутация: analyst попал в перечень, но
        вытеснил роль из строки цепочек (перебор по одной роли вместо
        всех) — исчезнувшая цепочка будет названа.
        """
        self.use_roles(roles_with(ANALYST, executor="none"))
        self.assertEqual(doctor.agent_roles(),
                         sorted(set(config.STATE_ROLE.values())),
                         "карта без analyst обязана дать ПРЕЖНИЙ перечень "
                         "ролей — иначе сравнивать не с чем")
        before_lines = self.flat_provider_lines()
        before_chains = chain_items(doctor.check_role_providers().detail)
        before_models = chain_items(doctor.check_models_local().detail)

        self.use_roles(roles_with(ANALYST,
                                  provider=providers.DEFAULT_PROVIDER))
        after_lines = self.flat_provider_lines()
        after_chains = chain_items(doctor.check_role_providers().detail)
        after_models = chain_items(doctor.check_models_local().detail)

        self.assertEqual(before_lines - after_lines, set(),
                         "строки прежнего вывода исчезли или изменились")
        added = after_lines - before_lines
        self.assertTrue(added, "ни одной строки роли analyst не добавилось")
        self.assertEqual([entry for entry in sorted(added)
                          if ANALYST not in entry[1]], [],
                         f"добавились строки, не называющие analyst: {added}")
        self.assertEqual(before_chains - after_chains, set())
        self.assertEqual([item for item in sorted(after_chains - before_chains)
                          if ANALYST not in item], [])
        self.assertEqual(before_models - after_models, set())
        self.assertEqual([item for item in sorted(after_models - before_models)
                          if ANALYST not in item], [])


if __name__ == "__main__":
    unittest.main()
