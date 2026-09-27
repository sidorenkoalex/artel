"""AC-13 — 01M3FQ2Z2PY0E9T5F5WQ207NP5: строка `doctor` по наборам.

Источник — SPEC.md, «Критерии приёмки»:

AC-13. Строка `doctor` по наборам: `fail` с названием битой ссылки, если
набор называет несуществующую роль, модель вне каталога или неизвестного
провайдера; `warn`, если наборов в локальном слое нет; `ok` при
согласованных наборах; набор с `experimental`-моделью каталога `fail` не
даёт.

Имя новой строки планка не угадывает: строки `doctor` — функции
`def check_*` пакета `orchestrator/doctor/`, и новая ищется как разница с
деревом main (`_util.new_check_names`). Критерий говорит об ОДНОЙ строке
по наборам, поэтому и разница обязана быть одной функцией; её участие
именно в строке `doctor` подтверждается ссылкой из
`orchestrator/doctor/cli.py` — там собирается перечень строк команды.

Аргумент вызова определяется подписью: проверке может понадобиться
соединение БД (как `check_canary_trigger`), а может и нет (как
`check_model_provider_cli`).

Красен до реализации: новой строки `doctor` нет — разница с main пуста, и
`_util.new_check_names` отдаёт пустое множество.
"""
import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import doctor, models  # noqa: E402

UNKNOWN_ROLE = "desiner"
UNKNOWN_MODEL = "gpt-9000-mirage"
UNKNOWN_PROVIDER = "mistral"


class DoctorLineForSetsTest(_util.LocalLayerOnlyTest):

    def _check_name(self) -> str:
        names = sorted(_util.new_check_names())
        self.assertEqual(
            1, len(names),
            "строка doctor по наборам — ровно одна новая функция "
            f"`check_*` пакета doctor относительно {_util.MAIN_SHA}, "
            f"найдено: {names or 'ни одной'}")
        return names[0]

    def _check(self):
        name = self._check_name()
        cli_source = (_util.DOCTOR_DIR / "cli.py").read_text(encoding="utf-8")
        self.assertIn(name, cli_source,
                      "новая проверка не собрана в перечень строк команды "
                      "`doctor` (orchestrator/doctor/cli.py)")
        function = getattr(doctor, name, None)
        self.assertTrue(callable(function),
                       f"{name} не выставлена фасадом пакета doctor")
        required = [parameter for parameter
                    in inspect.signature(function).parameters.values()
                    if parameter.default is inspect.Parameter.empty]
        return function(self.conn) if required else function()

    def test_ac13_consistent_sets_are_ok_even_with_an_experimental_model(self):
        """Согласованные наборы дают `ok`, хотя обе их модели имеют в
        каталоге статус `experimental`.

        Ловит мутацию: статус `experimental` трактуется как битая ссылка
        (`fail`) — `doctor` пульта, у которого заведён Codex-набор, был бы
        красным постоянно, и красная строка перестала бы значить «набор
        битый»; разрешение на такую модель собирается в слой клона, а не
        запрещает набор.
        """
        for model_id in (_util.SET_MODEL, _util.OTHER_SET_MODEL):
            self.assertEqual(models.STATUS_EXPERIMENTAL,
                             models.catalog_model(model_id).status,
                             "предпосылка сценария: модели наборов "
                             "experimental")

        check = self._check()

        self.assertEqual("ok", check.status, check.detail)

    def test_ac13_no_sets_in_the_local_layer_is_a_warn(self):
        """Локальный слой без раздела наборов вовсе — `warn`, не `fail` и
        не `ok`.

        Ловит мутацию: отсутствие раздела считается согласованностью
        (`ok`) — пульт, где наборы не заведены, отчитывался бы «наборы
        согласованы», и Оператор узнавал бы об отсутствии набора только из
        отказа `--set`.
        """
        self.write_local_layer(None)

        check = self._check()

        self.assertEqual("warn", check.status, check.detail)

    def test_ac13_set_naming_an_unknown_role_fails_and_names_it(self):
        """Набор с несуществующей ролью — `fail`, и битая ссылка названа.

        Ловит мутацию: проверка сверяет только модели и провайдеров (роли
        «и так придут из roles.yaml») — опечатка в имени роли жила бы в
        слое пульта до первого прогона с `--set`, когда за неё уже
        заплачено попыткой.
        """
        self.write_local_layer({
            _util.SET_NAME: {UNKNOWN_ROLE: {"provider": _util.SET_PROVIDER,
                                            "model": _util.SET_MODEL}}})

        check = self._check()

        self.assertEqual("fail", check.status)
        self.assertIn(UNKNOWN_ROLE, check.detail)

    def test_ac13_set_naming_a_model_outside_the_catalog_fails_and_names_it(self):
        """Набор с моделью вне каталога — `fail`, и модель названа.

        Ловит мутацию: модель сверяется с локальным слоем (`tiers:`), а не
        с каталогом — модель, которой в `models.yaml` нет, прошла бы как
        согласованная, а отказ всплыл бы уже внутри клона.
        """
        self.write_local_layer({
            _util.SET_NAME: {"developer": {"provider": _util.SET_PROVIDER,
                                           "model": UNKNOWN_MODEL}}})

        check = self._check()

        self.assertEqual("fail", check.status)
        self.assertIn(UNKNOWN_MODEL, check.detail)

    def test_ac13_set_naming_an_unknown_provider_fails_and_names_it(self):
        """Набор с провайдером вне реестра — `fail`, и провайдер назван.

        Ловит мутацию: имя провайдера набора не сверяется с реестром
        (`orchestrator/providers/`) — набор ссылался бы на исполнителя,
        которым пульт запускать шаг не умеет, и `doctor` этого не назвал бы.
        """
        self.write_local_layer({
            _util.SET_NAME: {"developer": {"provider": UNKNOWN_PROVIDER,
                                           "model": _util.SET_MODEL}}})

        check = self._check()

        self.assertEqual("fail", check.status)
        self.assertIn(UNKNOWN_PROVIDER, check.detail)


if __name__ == "__main__":
    unittest.main()
