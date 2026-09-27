"""AC-5, AC-6 — 01M3FQ2Z2PY0E9T5F5WQ207NP5: провайдер роли в клоне — из
набора, без правки `roles.yaml`, и без расхождения с провайдером модели.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. В клоне при `--set <имя>` `roles.provider(<роль набора>)` отдаёт
провайдера набора, а `roles.yaml` ни в клоне, ни в главной копии не
изменён (содержимое файла совпадает с содержимым целевого sha).

AC-6. Для набора, прошедшего проверки AC-3, проверка
`doctor.check_model_provider_cli(<роль набора>)` в клоне не отдаёт `fail`
по причине «провайдер роли ≠ провайдер её модели».

Оба критерия наблюдаются в ОДНОЙ точке — внутри собранного эфемерного
клона (`_util.CanarySetSandbox.clone_probe`), поэтому живут в одном файле:
второй прогон того же клона ради второго критерия ничего бы не добавил.

AC-6 сверяется на найденных CLI обоих провайдеров (`shutil.which`
подменён): вторая половина той же строки `doctor` — «объявленный
инструмент не найден в PATH» — от набора не зависит и на машине без
`codex` красила бы строку по причине, которой критерий не касается.
Живой CLI при этом не запускается: `check_model_provider_cli` читает
только PATH и файлы слоёв.

Красен до реализации: `canary.cmd_canary` не знает параметра набора, а
`roles.provider` не читает переопределения из локального слоя — в клоне
роль осталась бы на `providers.DEFAULT_PROVIDER`.
"""
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import config, doctor, roles  # noqa: E402

STUB_BIN = "/artel-plank-stub-bin"

#: Резолв PATH снимается ДО подмены: подменяется тот же атрибут
#: `shutil.which`, и обращение к нему по имени внутри подменяющей функции
#: было бы вызовом самой себя.
_WHICH = shutil.which


def _which_finds_everything(name, *args, **kwargs):
    found = _WHICH(name, *args, **kwargs)
    return found if found is not None else f"{STUB_BIN}/{name}"


class CloneRoleProviderTest(_util.CanarySetSandbox):

    def _probe(self):
        def probe():
            with mock.patch.object(doctor.shutil, "which",
                                  _which_finds_everything):
                checks = {role: doctor.check_model_provider_cli(role)
                          for role in _util.SET_ROLES}
                mismatches = {role: doctor.model_provider_mismatches(role)
                              for role in _util.SET_ROLES}
            return {
                "providers": {role: roles.provider(role)
                              for role in _util.SET_ROLES},
                "roles_yaml": (config.ROOT / "roles.yaml").read_text(
                    encoding="utf-8"),
                "checks": checks,
                "mismatches": mismatches,
            }
        return self.clone_probe(probe, set_name=_util.SET_NAME)

    def test_ac5_role_provider_in_the_clone_comes_from_the_set(self):
        """`roles.provider` каждой роли набора внутри клона отдаёт
        провайдера набора, а не `providers.DEFAULT_PROVIDER`.

        Ловит мутацию: карта «роль → провайдер» в слой клона пишется, но
        `roles.provider` её не читает (поле `provider:` роли осталось
        единственным источником) — шаг ушёл бы Claude'ом с идентификатором
        модели Codex, то есть оплаченной попыткой чужого CLI.
        """
        got = self._probe()

        self.assertEqual({role: _util.SET_PROVIDER for role in _util.SET_ROLES},
                         got["providers"])

    def test_ac5_roles_yaml_is_untouched_in_the_clone_and_in_the_main_copy(self):
        """`roles.yaml` в клоне совпадает с содержимым целевого sha, а
        файл главной копии не изменён.

        Ловит мутацию: провайдер набора проводится в клон правкой
        `roles.yaml` (записью поля `provider:` в файл клона или, хуже,
        главной копии) — защищённый путь оказался бы переписанным прогоном
        канарейки, то есть боевым переводом роли вместо пробного прогона.
        """
        got = self._probe()

        self.assertEqual(self.roles_yaml_text, got["roles_yaml"],
                         "roles.yaml в клоне разошёлся с целевым sha")
        self.assertEqual(self.roles_yaml_text,
                         (self.root / "roles.yaml").read_text(encoding="utf-8"),
                         "roles.yaml главной копии изменён прогоном")

    def test_ac6_model_provider_check_of_the_set_role_is_not_a_mismatch_fail(self):
        """Для исправного набора строка `doctor` о провайдере модели в
        клоне не отдаёт `fail`: ни одного расхождения «провайдер роли ≠
        провайдер её модели» по ролям набора.

        Ловит мутацию: в слой клона попадает модель набора, но
        переопределение провайдера собирается не по тем ролям (например,
        по ярусу вместо роли) — предполёт шага в клоне отказал бы
        расхождением, и прогон набора не начался бы ни разу.
        """
        got = self._probe()

        for role in _util.SET_ROLES:
            self.assertEqual([], got["mismatches"][role])
            self.assertEqual("ok", got["checks"][role].status,
                             got["checks"][role].detail)


if __name__ == "__main__":
    unittest.main()
