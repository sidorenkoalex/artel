"""AC-4 — 01M3H3JRBD544GQ10SS3DBGEVP: нечитаемая карта исполнителей.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. Нечитаемая карта исполнителей приводит к прежнему именованному
отказу строки `role-providers`, а не к падению doctor.

Критерий стоит здесь не теоретически: до задачи перечень ролей `doctor`
брался из словаря в коде и читать `roles.yaml` не требовал вовсе. Смена
источника делает КАЖДУЮ строку, перебирающую роли, зависимой от файла,
который может не разобраться, — и трейсбек вместо диагностики выбросил бы
все остальные строки `doctor` заодно.

Предмет второго теста — СТРОКИ `doctor`, перебирающие роли, а не
сигнатура помощника `agent_roles` (см. комментарий у списка).
`provider_preflight_checks` в перечень сознательно не включена: она
роняет `RolesError` на нечитаемой карте УЖЕ СЕГОДНЯ, и причина к перечню
ролей отношения не имеет — `doctor.check_token` читает слоты keychain
роли (`roles.token_slots`, orchestrator/doctor/preflight.py:61) вне
обработки отказа, когда токена не нашлось. Это отдельный дефект,
существующий до задачи; требовать его починку этим критерием значило бы
расширить объём задачи.

Зелёный с рождения: оба теста файла сохраняют СУЩЕСТВУЮЩЕЕ поведение —
именованный WARN строки `role-providers` на нечитаемой карте есть до
задачи (`check_role_providers` ловит `roles.RolesError`), а остальные
строки перечня сегодня карту не читают вовсе и упасть на ней не могут.
Краснеют они тогда, когда смена источника потеряет именованный отказ или
уронит трейсбеком строку, которая раньше карту не трогала.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, doctor  # noqa: E402

from _analyst import (DoctorLinesSandbox,  # noqa: E402
                      UNREADABLE_ROLES_TEXT)


class UnreadableRolesMapTest(DoctorLinesSandbox):
    """Строки `doctor`, перебирающие роли, на неразобранной карте."""

    def setUp(self):
        super().setUp()
        self.use_roles(UNREADABLE_ROLES_TEXT)

    def test_ac4_role_providers_keeps_its_named_refusal(self):
        """Строка `role-providers` остаётся жёлтой и называет причину от
        `roles`: файл и то, что он не разобран.

        Ловит мутацию: перечень ролей читается ДО входа в обработку
        `RolesError` (или отказ подменяется деградацией к провайдеру по
        умолчанию) — строка либо зеленеет с перечнем ролей на `claude`,
        утверждая прочитанным файл, которого не читала, либо теряет
        причину, и Оператор видит «провайдеры ролей: —» без имени файла и
        без слова о разборе.
        """
        check = doctor.check_role_providers()

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn("провайдеры ролей:", check.detail)
        self.assertIn("не разобран", check.detail)
        self.assertIn(str(config.ROLES), check.detail)

    def test_ac4_no_role_listing_line_of_doctor_crashes(self):
        """Ни одна зависимая от перечня ролей функция `doctor` не роняет
        исключение на нечитаемой карте — каждая отвечает значением.

        Ловит мутацию: перечень ролей отдаёт `RolesError` наружу, а
        читатели перечня (`models-local`, склейка предполёта провайдеров,
        сверка «провайдер роли ≠ провайдер её модели») зовут его вне
        обработки отказа — одна опечатка в `roles.yaml` роняет прогон
        `doctor` трейсбеком целиком, вместе со всеми строками, которые к
        карте исполнителей отношения не имеют (диск, сироты, lease).
        """
        # Сам перечень (`agent_roles`) в списке сознательно отсутствует:
        # критерий говорит про СТРОКИ `doctor`, а не про сигнатуру
        # помощника. Реализация вправе отдавать из него `RolesError` —
        # `check_role_providers` уже зовёт перечень внутри обработки
        # отказа, и именно так его именованный WARN и сохраняется; ценой
        # служит обязанность остальных строк ниже деградировать самим.
        callables = (
            ("check_models_local", doctor.check_models_local),
            ("check_role_providers", doctor.check_role_providers),
            ("model_provider_mismatches", doctor.model_provider_mismatches),
            ("check_model_provider_cli", doctor.check_model_provider_cli),
        )

        for name, call in callables:
            with self.subTest(line=name):
                try:
                    result = call()
                except Exception as exc:  # noqa: BLE001 — предмет теста
                    self.fail(f"{name} упал на нечитаемой карте: {exc!r}")
                self.assertIsNotNone(result, name)


if __name__ == "__main__":
    unittest.main()
