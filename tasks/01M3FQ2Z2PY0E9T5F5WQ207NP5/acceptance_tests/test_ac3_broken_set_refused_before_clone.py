"""AC-3 — 01M3FQ2Z2PY0E9T5F5WQ207NP5: битый набор — отказ до клона, по
случаю на каждый.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Битый набор — отказ с названной причиной до клона, по случаю на
каждый: (а) роль вне `roles.yaml`; (б) модель вне каталога `models.yaml`;
(в) две роли одного яруса с разными моделями; (г) провайдер роли не
совпадает с провайдером её модели в каталоге.

Каждый случай — свой тестовый метод, и у каждого оба факта «до клона» (ни
одного `git clone`, ни одной строки `tasks`) сверяет
`_util.CanarySetSandbox.refuse_before_clone`. «Названная причина» —
отказ, называющий ту сущность, из-за которой набор битый (роль, модель,
пару моделей одного яруса): без имени Оператор не знает, какую из строк
набора править.

Модели и ярусы берутся из НАСТОЯЩИХ `models.yaml`/`roles.yaml` (обе роли
набора — `developer`/`reviewer` — сегодня на одном ярусе), поэтому
сценарий (в) не требует подделки карты исполнителей.

Красен до реализации: параметра набора у `canary.cmd_canary` нет, ни
одна из четырёх проверок не существует — вызов падает на отсутствующем
параметре подписи.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import models, roles  # noqa: E402

UNKNOWN_ROLE = "desiner"
UNKNOWN_MODEL = "gpt-9000-mirage"


class BrokenSetRefusedTest(_util.CanarySetSandbox):

    def _refuse(self, entries) -> str:
        self.write_local_layer({_util.SET_NAME: entries}, self.OVERRIDES)
        return self.refuse_before_clone(_util.SET_NAME)

    def test_ac3_role_outside_roles_yaml_is_refused(self):
        """Набор называет роль, которой нет в карте исполнителей целевого
        sha: отказ до клона, имя роли названо.

        Ловит мутацию: неизвестная роль молча пропускается при сборке слоя
        (`for role, entry in set.items(): tiers[roles.model_tier(role)]` в
        обёртке `try/except RolesError: continue`) — набор «один developer
        на Codex» с опечаткой в имени роли ушёл бы в клон как набор по
        умолчанию, и прогон отчитался бы о Codex, идя на Claude.
        """
        with self.assertRaises(roles.RolesError):
            roles.model_tier(UNKNOWN_ROLE)

        message = self._refuse({
            UNKNOWN_ROLE: {"provider": _util.SET_PROVIDER,
                           "model": _util.SET_MODEL}})

        self.assertIn(UNKNOWN_ROLE, message)

    def test_ac3_model_outside_the_catalog_is_refused(self):
        """Набор называет модель, которой нет в каталоге `models.yaml`:
        отказ до клона, идентификатор модели назван.

        Ловит мутацию: модель набора кладётся в `tiers:` слоя клона без
        сверки с каталогом — отказ «модель вне каталога» всплыл бы уже
        ВНУТРИ клона, на первом шаге роли (`models.resolve_role`), то есть
        после `git clone` и заведения задачи, а причина умерла бы вместе с
        клоном.
        """
        catalog = models.load_catalog()
        self.assertNotIn(UNKNOWN_MODEL, catalog.models)

        message = self._refuse({
            "developer": {"provider": _util.SET_PROVIDER,
                          "model": UNKNOWN_MODEL}})

        self.assertIn(UNKNOWN_MODEL, message)

    def test_ac3_two_roles_of_one_tier_with_different_models_are_refused(self):
        """Набор даёт двум ролям ОДНОГО яруса разные модели: отказ до
        клона, названы обе модели.

        Ловит мутацию: сборка `tiers:` идёт присваиванием в словарь
        (`tiers[tier] = model`) — вторая роль молча перебивала бы первую,
        и прогон шёл бы на модели той роли, которая в наборе оказалась
        последней, вопреки записанному набору.
        """
        self.assertEqual(roles.model_tier("developer"),
                         roles.model_tier("reviewer"),
                         "предпосылка сценария: обе роли на одном ярусе")

        message = self._refuse({
            "developer": {"provider": _util.SET_PROVIDER,
                          "model": _util.SET_MODEL},
            "reviewer": {"provider": _util.SET_PROVIDER,
                         "model": _util.THIRD_MODEL}})

        self.assertIn(_util.SET_MODEL, message)
        self.assertIn(_util.THIRD_MODEL, message)

    def test_ac3_role_provider_not_matching_model_provider_is_refused(self):
        """Провайдер роли в наборе не совпадает с провайдером её модели в
        каталоге: отказ до клона, названы роль и модель.

        Ловит мутацию: половины записи набора проверяются по отдельности
        (модель — в каталоге, провайдер — в реестре), но не друг против
        друга — шаг ушёл бы `claude --model gpt-…`: оплаченная попытка
        чужим CLI, ровно та пара, которую `doctor.check_model_provider_cli`
        называет расхождением.
        """
        model = models.catalog_model(_util.SET_MODEL)
        self.assertNotEqual("claude", model.provider,
                            "предпосылка сценария: модель набора не от claude")

        message = self._refuse({
            "developer": {"provider": "claude", "model": _util.SET_MODEL}})

        self.assertIn("developer", message)
        self.assertIn(_util.SET_MODEL, message)


if __name__ == "__main__":
    unittest.main()
