"""AC-9: проверки «CLI найден», «версия CLI», «секрет», «дом роли» идут
через `preflight()` провайдера и дают тот же набор, что сегодня, без
дублей.

Красен до реализации: метода `preflight()` нет — реестра провайдеров ещё
не существует; часть файла про отсутствие дублей в выводе `doctor`
проверяет сохранение сегодняшнего набора и зелена уже сегодня.
"""
import unittest

from orchestrator import config, doctor, store
from _providers import provider
from _sandbox import DoctorSandbox, offline_doctor, rendered_checks

# Имена проверок, как их зовут сегодня (`orchestrator/doctor/preflight.py`):
# критерий требует тот же набор, а не новые имена.
PROVIDER_CHECK_NAMES = ("cli-found", "cli-version", "token",
                        "role-home-reference")
# Проверки, не зависящие от роли: сколько бы agent-ролей ни спрашивали
# провайдера, в выводе `doctor` каждая из них остаётся одна.
SINGLE_CHECK_NAMES = ("cli-found", "cli-version", "role-home-reference")
STATUSES = {"ok", "warn", "fail", "skip"}


class ProviderPreflightTest(DoctorSandbox):
    """Предполётные проверки провайдера во временном корне песочницы."""

    ROLE = "developer"

    def test_ac9_preflight_gives_todays_four_checks_without_duplicates(self):
        """`preflight(role)` провайдера отдаёт проверки с сегодняшними
        именами — по одной на каждую из четырёх, со статусом и пояснением.

        Ловит мутацию: в провайдера переехали не все четыре (дом роли
        остался отдельной проверкой мимо интерфейса) либо одна и та же
        проверка попала в список дважды — предполёт шага начинает врать
        Оператору количеством строк, а следующий провайдер не получает
        полного списка того, что обязан проверить до старта.
        """
        with offline_doctor():
            checks = list(provider().preflight(self.ROLE))

        names = [c.name for c in checks]
        self.assertEqual(sorted(names), sorted(set(names)),
                         f"дубли проверок: {names}")
        for expected in PROVIDER_CHECK_NAMES:
            self.assertIn(expected, names)
        for check in checks:
            with self.subTest(check=check.name):
                self.assertIn(check.status, STATUSES)
                self.assertTrue(str(check.detail).strip(),
                                f"{check.name}: пустое пояснение")

    def test_ac9_doctor_does_not_repeat_the_provider_checks(self):
        """Вывод `doctor` несёт проверки, не зависящие от роли, ровно по
        одному разу, а предполёт шага — без повторов имён вовсе.

        Ловит мутацию: `preflight()` провайдера вызван на каждую
        agent-роль поверх прежних вызовов — «CLI найден»/«версия CLI»/
        «дом роли» печатаются по четыре раза, и Оператор ищет настоящий
        провал в четырёхкратном списке.
        """
        self.touch_backup()
        with offline_doctor():
            checks = doctor.all_checks(store.db())
            step_checks = doctor.preflight_checks(self.ROLE,
                                                  config.DEFAULT_TARGET)

        names = [c.name for c in checks]
        for name in SINGLE_CHECK_NAMES:
            with self.subTest(check=name):
                self.assertEqual(names.count(name), 1,
                                 f"{name} в выводе doctor "
                                 f"{names.count(name)} раз(а):\n"
                                 f"{rendered_checks(checks)}")
        step_names = [c.name for c in step_checks]
        self.assertEqual(sorted(step_names), sorted(set(step_names)),
                         f"дубли в предполёте шага: {step_names}")


if __name__ == "__main__":
    unittest.main()
