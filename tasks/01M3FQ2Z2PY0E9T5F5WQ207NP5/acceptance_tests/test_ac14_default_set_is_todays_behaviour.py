"""AC-14 — 01M3FQ2Z2PY0E9T5F5WQ207NP5: прогон без `--set` воспроизводит
сегодняшнее поведение байт-в-байт.

Источник — SPEC.md, «Критерии приёмки»:

AC-14. Прогон без `--set` воспроизводит сегодняшнее поведение
байт-в-байт: текст локального слоя клона совпадает с
`models.LOCAL_TEMPLATE`, провайдер ролей берётся из `roles.yaml` клона,
argv команды шага роли не изменился.

Три наблюдения снимаются в одной точке — внутри собранного эфемерного
клона (`_util.CanarySetSandbox.clone_probe` без имени набора).

«Argv не изменился» сверяется ЗНАЧЕНИЕМ: argv шага роли, собранное внутри
клона, сравнивается с argv того же шага в главной копии (снято до входа в
клон). Именно эту величину задача и могла бы задеть — собранный слой и
переопределение провайдера меняют то, кем и с какой моделью стартует шаг;
код самой сборки команды (`orchestrator/providers/`, `runner`) в зонах
задачи не значится.

«Провайдер из `roles.yaml`» сверяется с тем, что об этом говорит сам файл
карты исполнителей (поле `provider:` роли, иначе
`providers.DEFAULT_PROVIDER`) — а не литералом `claude`: поле в файле
появится переводом роли, и планка не должна этому мешать.

Красен до реализации: последний тест файла зовёт прогон ИМЕНЕМ набора по
умолчанию, а `_util.default_set_name` падает на отсутствующем параметре
подписи `canary.cmd_canary` — остальные три теста файла зелены с рождения
намеренно (это тесты сохранения существующего поведения: они краснеют
ровно тогда, когда ветка набора задевает прогон без `--set`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import (config, models, providers, roles,  # noqa: E402
                          yamlmini)

PROBED_ROLES = ("developer", "reviewer", "analyst", "test_author")


def _role_step_argv(role: str) -> list:
    """Argv шага роли: команда провайдера роли с моделью, в которую
    разрешается её ярус — та же пара, которой стартует шаг."""
    return providers.for_role(role).command(models.resolve_role(role).model)


class DefaultSetIsTodaysBehaviourTest(_util.CanarySetSandbox):

    def _probe(self, set_name=_util.OMIT):
        outer_argv = {role: _role_step_argv(role) for role in PROBED_ROLES}

        def probe():
            return {
                "text": config.MODELS_LOCAL.read_text(encoding="utf-8"),
                "providers": {role: roles.provider(role)
                              for role in PROBED_ROLES},
                "argv": {role: _role_step_argv(role) for role in PROBED_ROLES},
            }
        got = self.clone_probe(probe, set_name=set_name)
        got["outer_argv"] = outer_argv
        return got

    def test_ac14_clone_layer_text_equals_the_template(self):
        """Без `--set` текст локального слоя клона — ровно
        `models.LOCAL_TEMPLATE`.

        Ловит мутацию: слой клона всегда собирается кодом набора (набор по
        умолчанию — «тот же шаблон, только через сборку») — текст разошёлся
        бы с шаблоном хотя бы порядком ключей, и живой прогон перестал бы
        быть тем же прогоном, которым снят действующий бейзлайн.
        """
        got = self._probe()

        self.assertEqual(models.local_template_text(), got["text"])

    def test_ac14_role_provider_comes_from_roles_yaml(self):
        """Без `--set` провайдер каждой роли в клоне — тот, который
        называет `roles.yaml` (поле роли, иначе провайдер по умолчанию).

        Ловит мутацию: переопределение провайдера пишется в слой клона
        всегда (набор по умолчанию — «все роли на claude» литералом) —
        перевод роли пульта на другого исполнителя правкой `roles.yaml`
        перестал бы действовать внутри канарейки, и канарейка проверяла бы
        не тот конвейер, который у пульта настроен.
        """
        entries = yamlmini.mapping(self.roles_yaml_text).get("roles") or {}

        got = self._probe()

        for role in PROBED_ROLES:
            declared = (entries.get(role) or {}).get("provider")
            expected = declared or providers.DEFAULT_PROVIDER
            self.assertEqual(expected, got["providers"][role],
                             f"провайдер роли {role} в клоне")

    def test_ac14_role_step_argv_in_the_clone_is_the_argv_of_the_main_copy(self):
        """Без `--set` argv шага роли в клоне совпадает с argv того же шага
        в главной копии — включая модель, с которой шаг стартует.

        Ловит мутацию: сборка слоя (или переопределение провайдера)
        затрагивает и ветку без набора — шаг канареечной задачи стартовал
        бы с другой моделью или другим CLI, чем шаг живой задачи, и метрика
        прогона перестала бы быть метрикой сегодняшнего конвейера.
        """
        got = self._probe()

        self.assertEqual(got["outer_argv"], got["argv"])

    def test_ac14_default_set_name_behaves_as_no_flag_at_all(self):
        """`--set <набор по умолчанию>` даёт то же самое, что прогон без
        флага: слой клона — шаблон, провайдеры — из `roles.yaml`.

        Ловит мутацию: имя набора по умолчанию проверяется на наличие в
        `canary_sets:` наравне с остальными — прогон по нему отказывал бы
        на любом пульте, чей локальный слой наборов не несёт (то есть на
        сегодняшнем), а сам набор по умолчанию перестал бы быть
        «как пульт».
        """
        got = self._probe(set_name=_util.default_set_name())

        self.assertEqual(models.local_template_text(), got["text"])
        self.assertEqual(got["outer_argv"], got["argv"])


if __name__ == "__main__":
    unittest.main()
