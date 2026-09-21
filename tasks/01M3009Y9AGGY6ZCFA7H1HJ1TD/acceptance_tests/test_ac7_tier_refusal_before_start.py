"""AC-7: agent-роль без `model_tier` и роль с ярусом вне перечня —
именованный отказ `run`/`auto` ДО старта агента и красная строка
`doctor`.

Красен до реализации: цепочки нет целиком — сценарий падает уже на
фикстуре каталога (`models.yaml` в корне ещё нет, эта задача его
создаёт), а за ней нет ни чтения `model_tier`, ни отказа шага, ни строк
`doctor` о ярусах.
"""
import unittest

import _models
from _sandbox import FOREIGN_TIER, ModelsDoctorSandbox, offline_doctor, \
    rendered_checks, TierStepSandbox
from orchestrator import doctor, store

# Слова, которыми отказ обязан назвать предмет: поле яруса или само слово
# «ярус» — формулировку SPEC не фиксирует, предмет фиксирует.
TIER_WORDS = ("model_tier", "ярус")


def names_the_tier(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in TIER_WORDS)


class TierStepRefusalTest(TierStepSandbox):
    """Шаг роли `developer` с полной цепочкой, кроме яруса роли."""

    def setUp(self):
        super().setUp()
        self.set_cli_version("9.9.9")

    def assert_refused_before_start(self, printed: str) -> None:
        text = self.refusal_text(printed)
        self.spawn.assert_not_called()
        self.assertIn(self.ROLE, text, f"отказ не называет роль:\n{text}")
        self.assertTrue(names_the_tier(text),
                        f"отказ не называет ярус роли:\n{text}")

    def test_ac7_run_refuses_a_role_without_model_tier_before_the_agent_starts(self):
        """Роль без поля `model_tier` — `run` отказывает именованно, агент
        не стартует.

        Ловит мутацию: отсутствующий ярус трактуется как дефолт (`strong`
        или «первый ярус локального слоя») — роль, которой Оператор ярус
        не назначил, молча уходит на дорогую модель, и отказ, ради
        которого цепочка сделана fail-closed, не наступает никогда.
        """
        self.seed_chain(tier=None)

        self.assert_refused_before_start(self.run_step())

    def test_ac7_run_refuses_a_tier_outside_the_closed_list(self):
        """Ярус вне перечня `strong | standard | cheap` — `run` отказывает
        именованно, агент не стартует.

        Ловит мутацию: значение яруса ищется в `tiers:` локального слоя
        без сверки с перечнем — самодельный ярус, прописанный в обоих
        файлах, работал бы как законный, и закрытый перечень существовал
        бы только в тексте SPEC.
        """
        self.seed_chain(tier=FOREIGN_TIER)

        self.assert_refused_before_start(self.run_step())

    def test_ac7_auto_refuses_a_role_without_model_tier_with_the_same_line(self):
        """`auto` отказывает тем же текстом и тоже не запускает агента.

        Ловит мутацию: проверка яруса вставлена в путь `cmd_run` мимо
        общего `_refuse_before_start` — `auto` её не видит и крутит шаги
        до потолка, платя за каждую попытку.
        """
        self.seed_chain(tier=None)

        self.assert_refused_before_start(self.run_auto())


class TierDoctorTest(ModelsDoctorSandbox):
    """`doctor` на карте исполнителей без ярусов и с ярусом вне перечня."""

    def checks(self, tier) -> list:
        self.write_catalog()
        self.write_local(_models.local_texts(self.default_tiers())[0])
        self.set_roles_tiers({role: tier for role in _models.agent_roles()})
        self.touch_backup()
        with offline_doctor():
            return doctor.all_checks(store.db())

    def assert_red_about_tier(self, checks: list) -> None:
        red = [c for c in checks
               if c.status == "fail" and names_the_tier(c.detail)]
        self.assertTrue(red, f"нет красной строки про ярус роли:\n"
                             f"{rendered_checks(checks)}")

    def test_ac7_doctor_is_red_for_a_role_without_model_tier(self):
        """Agent-роль без яруса — красная строка `doctor`.

        Ловит мутацию: отсутствие яруса `doctor` показывает жёлтым
        (`warn`) — Оператор видит предупреждение среди прочих, `doctor`
        выходит с нулевым кодом, а шаг роли при этом уже не стартует
        вовсе.
        """
        self.assert_red_about_tier(self.checks(None))

    def test_ac7_doctor_is_red_for_a_tier_outside_the_closed_list(self):
        """Ярус вне перечня — красная строка `doctor`.

        Ловит мутацию: `doctor` сверяет только «поле есть», не сверяя
        значение с перечнем — опечатка в ярусе доживает до первого
        запуска роли и там оборачивается отказом шага, хотя `doctor`
        обязан назвать её раньше.
        """
        self.assert_red_about_tier(self.checks(FOREIGN_TIER))


if __name__ == "__main__":
    unittest.main()
