"""AC-11: вывод `doctor` несёт строку «провайдеры ролей: <роль →
провайдер>».

Красен до реализации: `doctor` сегодня ничего не знает о провайдерах
ролей — такой строки в его выводе нет.
"""
import io
import unittest
from contextlib import redirect_stdout

from orchestrator import doctor
from _sandbox import DoctorSandbox, offline_doctor

LINE_PREFIX = "провайдеры ролей:"


class DoctorProvidersLineTest(DoctorSandbox):
    """`doctor` на реальной карте исполнителей репозитория: поля
    `provider:` в ней нет, значит все роли — на `claude`."""

    def doctor_output(self) -> str:
        buf = io.StringIO()
        with offline_doctor(), redirect_stdout(buf):
            try:
                doctor.cmd_doctor()
            except SystemExit:
                # Провалы прочих проверок в песочнице (пин, хуки) — не
                # предмет этого критерия: важен сам факт строки в выводе.
                pass
        return buf.getvalue()

    def test_ac11_output_names_every_role_with_its_provider(self):
        """В выводе есть строка «провайдеры ролей: …», и роль `developer`
        названа в ней вместе со своим провайдером `claude`.

        Ловит мутацию: строка печатается пустой (реестр опрошен, а карта
        исполнителей — нет) либо перечисляет провайдеров без ролей —
        Оператор видит «claude, claude, claude» и не может сказать,
        какая роль на каком CLI пойдёт.
        """
        out = self.doctor_output()

        lines = [line for line in out.splitlines() if LINE_PREFIX in line]
        self.assertTrue(lines, f"строки «{LINE_PREFIX}» нет в выводе "
                               f"doctor:\n{out}")
        line = lines[0]
        self.assertIn("developer", line)
        self.assertIn("claude", line.split(LINE_PREFIX, 1)[1])


if __name__ == "__main__":
    unittest.main()
