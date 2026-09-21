"""AC-3, AC-4, AC-5 — 01M31ZHWJWRSACYMRWTCPBC0DM: блок стоимости RETRO
показывает по каждой роли доллары, суммарные токены, разбивку по четырём
видам, провайдера и модель — а роль без записей токенов показывает
прочерк вместо нуля.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. RETRO печатает по каждой роли доллары, суммарное число токенов и
разбивку по четырём видам: `input`, `output`, `cache_write`, `cache_read`.

AC-4. RETRO печатает по каждой роли провайдера и модель шагов этой роли.

AC-5. Роль, по шагам которой записей токенов нет, показана в RETRO
прочерком вместо нуля (и в суммарном числе, и в разбивке по видам).

Красен до реализации: `retro._cost_block` печатает по роли ровно
«`  <actor>: $X.XX[, N токенов]`» (`orchestrator/retro.py:218-220`) —
разбивки по видам, провайдера и модели в строке нет вовсе, а роль без
токенов (`_actor_costs` отдаёт `None`) получает пустой хвост, а не
прочерк.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tokens  # noqa: E402
from orchestrator import retro  # noqa: E402

MERGE_SHA = "abcdef01" * 5


class RetroCostBlockTest(_tokens.TokensSandbox):

    def setUp(self):
        super().setUp()
        self.charge_two_roles()
        self.charge_without_tokens(self.TASK, _tokens.MUTE_ROLE,
                                   _tokens.MUTE_USD)
        self.text = retro.build_done(self.conn, self.TASK, MERGE_SHA)

    def role_block(self, role: str) -> str:
        """Строки RETRO, называющие роль, — одной строкой или несколькими
        подряд: сколько строк отвести роли, критерий не диктует (только
        AC-6 ограничивает файл целиком)."""
        block = "\n".join(ln for ln in self.text.splitlines() if role in ln)
        self.assertTrue(block, f"роль {role} не названа в RETRO:\n{self.text}")
        return block

    def test_ac3_role_shows_dollars_total_tokens_and_all_four_kinds(self):
        """`developer` (60 токенов, $1.25) и `reviewer` (120 токенов,
        $2.50) показаны каждый со своими деньгами, своей суммой токенов и
        своей разбивкой по всем четырём видам цены.

        Ловит мутацию: разбивка печатается общая по задаче, а не по роли
        (складываются строки «agent cost KNOWN» всех актёров) — у
        `developer` в разбивке окажется `input=34` вместо `input=11`, и
        `missing_kinds` назовёт все четыре вида непоказанными.
        """
        cases = ((_tokens.DEV_ROLE, _tokens.DEV_USD, _tokens.DEV_TOTAL,
                  _tokens.DEV_TOKENS),
                 (_tokens.REV_ROLE, _tokens.REV_USD, _tokens.REV_TOTAL,
                  _tokens.REV_TOKENS))
        for role, usd, total, tokens in cases:
            with self.subTest(role=role):
                block = self.role_block(role)
                self.assertIn(f"${usd:.2f}", block)
                self.assertIn(str(total), block,
                              f"суммарного числа токенов {total} роли {role} "
                              f"нет в RETRO:\n{block}")
                self.assertEqual(
                    [], _tokens.missing_kinds(block, tokens),
                    f"виды разбивки роли {role} не показаны своими "
                    f"числами:\n{block}")

    def test_ac4_role_shows_its_provider_and_model(self):
        """У каждой роли назван провайдер и модель ЕЁ шагов: `developer`
        шёл на `alfa-cli`/`alfa-model-x`, `reviewer` — на
        `beta-cli`/`beta-model-y`.

        Ловит мутацию: провайдер и модель берутся из первой попавшейся
        строки журнала задачи (или из сегодняшней цепочки роли), а не из
        строк ЭТОЙ роли — обе роли получат одну и ту же пару, и проверка
        «чужой провайдер в блоке роли не назван» покраснеет.
        """
        cases = ((_tokens.DEV_ROLE, _tokens.DEV_PROVIDER, _tokens.DEV_MODEL,
                  _tokens.REV_PROVIDER, _tokens.REV_MODEL),
                 (_tokens.REV_ROLE, _tokens.REV_PROVIDER, _tokens.REV_MODEL,
                  _tokens.DEV_PROVIDER, _tokens.DEV_MODEL))
        for role, provider, model, alien_provider, alien_model in cases:
            with self.subTest(role=role):
                block = self.role_block(role)
                self.assertIn(provider, block,
                              f"провайдер шагов роли {role} не назван:\n{block}")
                self.assertIn(model, block,
                              f"модель шагов роли {role} не названа:\n{block}")
                self.assertNotIn(alien_provider, block)
                self.assertNotIn(alien_model, block)

    def test_ac5_role_without_token_records_shows_a_dash_not_zero(self):
        """`analyst`, чей шаг завершился без разбивки usage, показан
        прочерком — и вместо суммарного числа, и вместо каждого вида; ни
        одного голого нуля в его строках нет.

        Ловит мутацию: отсутствие разбивки трактуется как пустой словарь и
        печатается через `.get(kind, 0)` — в строке роли появятся
        `input=0, output=0, cache_write=0, cache_read=0` (и «0 токенов»),
        то есть «роль отработала бесплатно» вместо честного «данных нет».
        """
        block = self.role_block(_tokens.MUTE_ROLE)

        self.assertIn(f"${_tokens.MUTE_USD:.2f}", block)
        self.assertTrue(
            _tokens.has_dash(block),
            f"роль без записей токенов показана без прочерка:\n{block}")
        self.assertEqual(
            [], _tokens.zeroed_kinds(block),
            f"виды разбивки показаны нулём вместо прочерка:\n{block}")
        self.assertEqual(
            [], _tokens.bare_zeros(block),
            f"голый ноль вместо прочерка в строках роли:\n{block}")


if __name__ == "__main__":
    unittest.main()
