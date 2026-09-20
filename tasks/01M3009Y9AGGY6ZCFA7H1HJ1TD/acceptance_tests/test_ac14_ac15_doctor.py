"""AC-14/AC-15: `doctor` несёт проверку «каталог моделей» и проверку
«локальный слой» (у каждой свой ok и свой fail) и печатает цепочку
«роль → ярус → модель → провайдер» для каждой agent-роли.

Красен до реализации: сценарий падает на отсутствующем `models.yaml`
(каталог создаёт эта задача), а `doctor` всё равно не знает о каталоге и
локальном слое ни одной строкой, и строка провайдеров ролей печатает
только «роль → провайдер».

Проверки узнаются по предмету в их имени/тексте («каталог … моделей»,
«локальный слой»): имена строк `doctor` SPEC не фиксирует, предмет
фиксирует.
"""
import unittest

import _models
from _sandbox import ModelsDoctorSandbox, offline_doctor, rendered_checks
from orchestrator import doctor, store


def _text(check) -> str:
    return f"{check.name} {check.detail}".lower()


def catalog_checks(checks: list) -> list:
    return [c for c in checks
            if ("каталог" in _text(c) and "модел" in _text(c))
            or ("catalog" in c.name and "model" in c.name)]


def local_checks(checks: list) -> list:
    return [c for c in checks
            if "локальн" in _text(c) or ".artel/models.yaml" in c.detail
            or "local" in c.name]


class ModelsDoctorChecksTest(ModelsDoctorSandbox):
    """`doctor` на временном пульте с управляемыми каталогом, локальным
    слоем и ярусами ролей."""

    def setUp(self):
        super().setUp()
        self.strong_model, self.second_model = _models.two_supported_models()
        self.tiers = {"strong": self.strong_model,
                      "standard": self.second_model,
                      "cheap": self.second_model}
        self.role_tiers = self.distinct_role_tiers()

    def distinct_role_tiers(self) -> dict:
        """Ярусы agent-ролям — по кругу перечня, чтобы строка цепочки
        (AC-15) различала роли, а не повторяла одну и ту же модель."""
        roles = list(dict.fromkeys(_models.agent_roles()
                                   + list(doctor.agent_roles())))
        order = ("strong", "standard", "cheap")
        return {role: order[i % len(order)] for i, role in enumerate(roles)}

    def checks(self, catalog_text=None, local_text=-1, role_tiers=None) -> list:
        """Прогон всех проверок `doctor` на заданном сценарии.
        `local_text=None` — локального слоя нет вовсе."""
        self.write_catalog(catalog_text)
        if local_text == -1:
            local_text = _models.local_texts(self.tiers)[0]
        if local_text is None:
            self.local_path.unlink(missing_ok=True)
        else:
            self.write_local(local_text)
        self.set_roles_tiers(self.role_tiers if role_tiers is None else role_tiers)
        self.touch_backup()
        with offline_doctor():
            return doctor.all_checks(store.db())

    def assert_present(self, selected: list, checks: list, what: str) -> None:
        self.assertTrue(selected, f"в выводе doctor нет проверки «{what}»:\n"
                                  f"{rendered_checks(checks)}")

    def test_ac14_both_checks_are_green_on_a_healthy_pult(self):
        """Разобранный каталог, положенный локальный слой и разрешимые
        ярусы всех agent-ролей — обе проверки зелёные.

        Ловит мутацию: проверка сделана всегда красной (или всегда
        зелёной — статус не зависит от факта) — `doctor` на здоровом
        пульте перестаёт быть сигналом, а красная строка «каталог
        моделей» становится фоном, который Оператор приучается не читать.
        """
        checks = self.checks()

        catalog = catalog_checks(checks)
        local = local_checks(checks)
        self.assert_present(catalog, checks, "каталог моделей")
        self.assert_present(local, checks, "локальный слой")
        for check in catalog + local:
            with self.subTest(check=check.name):
                self.assertEqual(check.status, "ok", check.detail)

    def test_ac14_catalog_check_is_red_when_a_price_is_incomplete(self):
        """У модели, на которую указывает ярус, прейскурант неполон —
        проверка «каталог моделей» краснеет.

        Ловит мутацию: проверка ограничена фактом «файл разобран» —
        каталог, прошедший YAML-разбор, но потерявший цену чтения кэша у
        рабочей модели, `doctor` объявляет здоровым, и неполнота всплывает
        только у потребителя тарифа.
        """
        broken = _models.with_partial_price(self.strong_model, "cache_read")

        checks = self.checks(catalog_text=broken)

        catalog = catalog_checks(checks)
        self.assert_present(catalog, checks, "каталог моделей")
        self.assertTrue([c for c in catalog if c.status == "fail"],
                        f"проверка каталога не покраснела:\n"
                        f"{rendered_checks(checks)}")

    def test_ac14_local_check_is_red_when_the_local_layer_is_missing(self):
        """Локального слоя нет — краснеет проверка «локальный слой», а
        проверка «каталог моделей» остаётся зелёной.

        Ловит мутацию: обе проверки свёрнуты в одну строку «модели» —
        Оператор не видит, что чинить: файл вне git, который кладёт
        `doctor --fix`, или каталог в репозитории, который правит
        приложением к PLAN.
        """
        checks = self.checks(local_text=None)

        local = local_checks(checks)
        catalog = catalog_checks(checks)
        self.assert_present(local, checks, "локальный слой")
        self.assertTrue([c for c in local if c.status == "fail"],
                        f"проверка локального слоя не покраснела:\n"
                        f"{rendered_checks(checks)}")
        self.assertNotIn("fail", [c.status for c in catalog],
                         f"каталог разобран, но его проверка красная (AC-14 "
                         f"не называет отсутствие локального слоя провалом "
                         f"проверки каталога):\n{rendered_checks(checks)}")

    def test_ac14_local_check_is_red_when_a_role_tier_does_not_resolve(self):
        """Ярус agent-роли не назван в `tiers:` — краснеет проверка
        «локальный слой».

        Ловит мутацию: проверка ограничена существованием файла — пульт с
        локальным слоем, где забыт один из ярусов, зеленеет в `doctor` и
        падает на первом же шаге роли, которой этот ярус назначен.
        """
        partial = {"strong": self.strong_model}

        checks = self.checks(local_text=_models.local_texts(partial)[0])

        local = local_checks(checks)
        self.assert_present(local, checks, "локальный слой")
        self.assertTrue([c for c in local if c.status == "fail"],
                        f"проверка локального слоя не покраснела:\n"
                        f"{rendered_checks(checks)}")

    def test_ac14_local_check_is_red_when_experimental_is_not_allowed(self):
        """Ярус указывает на модель со статусом `experimental`, явного
        разрешения в локальном слое нет — краснеет проверка «локальный
        слой».

        Ловит мутацию: статус модели `doctor` не смотрит — пульт, чей
        ярус указывает на экспериментальную модель, выглядит здоровым, а
        шаги всех ролей этого яруса отказывают до старта.
        """
        experimental = _models.with_experimental(self.strong_model)

        checks = self.checks(catalog_text=experimental)

        local = local_checks(checks)
        self.assert_present(local, checks, "локальный слой")
        self.assertTrue([c for c in local if c.status == "fail"],
                        f"проверка локального слоя не покраснела:\n"
                        f"{rendered_checks(checks)}")

    def test_ac15_role_providers_line_prints_the_whole_chain(self):
        """Строка о провайдерах ролей несёт для КАЖДОЙ agent-роли её ярус,
        модель этого яруса и провайдера модели.

        Состав agent-ролей строки — `doctor.agent_roles()`, сегодняшний
        состав той самой строки, которую требование 11 РАСШИРЯЕТ (а не
        пересобирает): критерий про формат цепочки, не про то, чьи имена
        в строке.

        Ловит мутацию: строка дополнена ярусом, но модель в ней берётся
        одна на всех (например, дефолт локального слоя) — Оператор видит
        «роль → ярус → claude-opus-5 → claude» у всех ролей и не
        замечает, что дешёвый ярус на самом деле указывает на другую
        модель.
        """
        checks = self.checks()
        expected = doctor.agent_roles()

        lines = [c.detail for c in checks
                 if all(role in c.detail for role in expected)]
        self.assertTrue(lines, f"нет строки, называющей agent-роли "
                               f"{expected}:\n{rendered_checks(checks)}")
        line = lines[0]
        for role in expected:
            tier = self.role_tiers[role]
            with self.subTest(role=role):
                self.assertIn(tier, line)
                self.assertIn(self.tiers[tier], line)
        self.assertIn("claude", line)


if __name__ == "__main__":
    unittest.main()
