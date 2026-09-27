"""Юнит-тесты строки `doctor` о наборах ролей канарейки
(`orchestrator/doctor/canary_sets.py`, SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5,
требование 9).

Каталог моделей, карта исполнителей и локальный слой — временные файлы
под патчами `config` (те же фикстуры, что у `tests/test_canary_sets.py`):
боевые `models.yaml`/`roles.yaml` — защищённые пути и крутилки Оператора,
и тест, опирающийся на их сегодняшнее содержимое, краснел бы от правки, к
его предмету отношения не имеющей.

Строка не заводит ни одного подпроцесса и живой CLI провайдера не
запускает: читает только файлы слоёв и реестр провайдеров.
"""
import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import doctor, models  # noqa: E402
from tests.test_canary_sets import _SetLayersTest, SET_NAME  # noqa: E402


class DoctorCanarySetsTest(_SetLayersTest):

    def test_consistent_sets_are_ok_even_on_an_experimental_model(self):
        """Ловит мутацию: статус `experimental` трактуется как битая ссылка
        — `doctor` пульта с заведённым Codex-набором был бы красным
        постоянно, и красная строка перестала бы значить «набор битый»
        (разрешение на такую модель собирается в слой клона)."""
        self.write_local("canary_sets:\n"
                         f"  {SET_NAME}:\n"
                         "    developer:\n"
                         "      provider: codex\n"
                         "      model: model-codex-a\n")

        check = doctor.check_canary_sets()

        self.assertEqual("ok", check.status, check.detail)
        self.assertIn("model-codex-a", check.detail)

    def test_layer_without_the_section_is_a_warn(self):
        """Ловит мутацию: отсутствие раздела считается согласованностью
        (`ok`) — пульт, где наборы не заведены, отчитывался бы «наборы
        согласованы», и Оператор узнавал бы об отсутствии набора только из
        отказа `--set`."""
        check = doctor.check_canary_sets()

        self.assertEqual("warn", check.status, check.detail)
        self.assertIn(models.CANARY_SETS_KEY, check.detail)

    def test_missing_layer_file_is_a_warn_not_a_fail(self):
        """Ловит мутацию: отсутствие самого слоя красит строку `fail` —
        свежий клон пульта (слоя ещё нет, его кладёт `init`/`doctor --fix`)
        получал бы провал `doctor` по набору, которого никто не заводил, и
        причина тонула бы среди настоящих провалов."""
        self.local_path.unlink()

        check = doctor.check_canary_sets()

        self.assertEqual("warn", check.status, check.detail)

    def test_unparseable_layer_is_a_fail(self):
        """Ловит мутацию: нечитаемый слой уходит в `warn` наравне с
        «наборов нет» — битый файл, из-за которого `--set` отказывает
        всегда, выглядел бы штатным состоянием пульта."""
        self.write_local("canary_sets: не отображение\n")

        check = doctor.check_canary_sets()

        self.assertEqual("fail", check.status, check.detail)

    def test_set_naming_an_unknown_role_fails_and_names_it(self):
        """Ловит мутацию: проверка сверяет только модели и провайдеров
        («роли и так придут из roles.yaml») — опечатка в имени роли жила бы
        в слое до первого прогона с `--set`, когда за неё уже заплачено
        попыткой."""
        self.write_local("canary_sets:\n"
                         f"  {SET_NAME}:\n"
                         "    desiner:\n"
                         "      provider: codex\n"
                         "      model: model-codex-a\n")

        check = doctor.check_canary_sets()

        self.assertEqual("fail", check.status)
        self.assertIn("desiner", check.detail)

    def test_set_naming_a_model_outside_the_catalog_fails_and_names_it(self):
        """Ловит мутацию: модель сверяется с локальным слоем (`tiers:`), а
        не с каталогом — модель, которой в `models.yaml` нет, прошла бы как
        согласованная, а отказ всплыл бы уже внутри клона."""
        self.write_local("canary_sets:\n"
                         f"  {SET_NAME}:\n"
                         "    developer:\n"
                         "      provider: codex\n"
                         "      model: model-net-v-kataloge\n")

        check = doctor.check_canary_sets()

        self.assertEqual("fail", check.status)
        self.assertIn("model-net-v-kataloge", check.detail)

    def test_set_naming_an_unknown_provider_fails_and_names_it(self):
        """Ловит мутацию: имя провайдера не сверяется с реестром
        `orchestrator/providers/` — набор ссылался бы на исполнителя,
        которым пульт запускать шаг не умеет, и `doctor` этого не назвал
        бы."""
        self.write_local("canary_sets:\n"
                         f"  {SET_NAME}:\n"
                         "    developer:\n"
                         "      provider: mistral\n"
                         "      model: model-codex-a\n")

        check = doctor.check_canary_sets()

        self.assertEqual("fail", check.status)
        self.assertIn("mistral", check.detail)

    def test_every_broken_link_of_one_entry_is_named_at_once(self):
        """Ловит мутацию: перебор прерывается на первой найденной битой
        ссылке — Оператор чинил бы одну запись двумя прогонами `doctor`,
        каждый раз узнавая про следующую половину."""
        self.write_local("canary_sets:\n"
                         f"  {SET_NAME}:\n"
                         "    desiner:\n"
                         "      provider: mistral\n"
                         "      model: model-net-v-kataloge\n")

        check = doctor.check_canary_sets()

        self.assertEqual("fail", check.status)
        for broken in ("desiner", "mistral", "model-net-v-kataloge"):
            self.assertIn(broken, check.detail)

    def test_the_check_is_wired_into_all_checks(self):
        """Ловит мутацию: проверка написана, но не подключена к
        `all_checks` — `doctor` молчал бы о наборах, и битая ссылка
        обнаруживалась бы только на самом прогоне канарейки."""
        source = inspect.getsource(doctor.all_checks)

        self.assertIn("check_canary_sets", source)


if __name__ == "__main__":
    unittest.main()
