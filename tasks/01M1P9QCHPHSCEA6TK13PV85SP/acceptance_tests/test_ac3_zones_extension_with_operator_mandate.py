"""AC-3 (tasks/01M1P9QCHPHSCEA6TK13PV85SP/SPEC.md): исключение из AC-1 —
если PLAN несёт раздел расширения зон с обоснованием, подкреплённым
ANSWER Оператора с явным согласием на расширение, расширение
записывается в БД задачи, и переход `in_dev -> review` проходит.

Конкретика трёх параметров, без которых AC-3 был неисполним тестом
(эскалация test_author, снятый файл `test_ac3_ac7_markers.py`), зафиксирована
tasks/01M1P9QCHPHSCEA6TK13PV85SP/ANSWER-1.md (вариант (b), уточнённый):
1. Формат PLAN.md — раздел `## Расширение зон` со строкой
   `Пути: <путь1>, <путь2>` и обоснованием свободным текстом ниже.
2. Мандат — строка `Расширение зон разрешено: <путь1>, <путь2>` в любом
   ANSWER-n.md задачи; каждый путь раздела PLAN обязан входить в список
   хотя бы одного такого маркера, иначе — отказ с перечнем непокрытых
   путей (та же семантика отказа, что AC-1/AC-2).
3. Колонка БД `tasks.zones_extension TEXT` — список путей через запятую,
   пишется при успешном переходе.

Смешанная краснота — по тестам, не по файлу целиком:
- `test_ac3_plan_extension_backed_by_matching_answer_mandate_passes` —
  Зелёный с рождения: сегодня гейта зон нет вовсе (AC-1 не реализован,
  см. test_ac1_ac2_out_of_zone_diff_refuses.py) — любой дифф проходит
  переход без сверки, значит и этот сценарий проходит уже сейчас, но по
  отсутствию кода, не по намеренной логике исключения AC-3 (тот же
  случай, что AC-6 в test_ac6_common_zones_pass.py). После появления
  гейта тест обязан остаться зелёным ИМЕННО потому, что мандат Оператора
  распознан правильно — см. «Ловит мутацию» метода.
- `test_ac3_successful_extension_is_recorded_in_zones_extension_column` —
  Красен до реализации: колонки `zones_extension` в таблице `tasks` не
  существует до миграции этой задачи — `ZonesGateSandbox.zones_extension()`
  падает `IndexError` (sqlite3.Row без такой колонки) на самом обращении.
- Оба теста класса `Ac3ExtensionWithoutMatchingMandateStillRefusesTest` —
  Красен до реализации: гейта зон нет вовсе (см. выше) — переход проходит
  в `review` для любого диффа независимо от (не)совпадения мандата,
  ожидаемый отказ не наступает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ZonesGateSandbox  # noqa: E402


class Ac3ExtensionWithMatchingMandatePassesTest(ZonesGateSandbox):

    def test_ac3_plan_extension_backed_by_matching_answer_mandate_passes(self):
        """PLAN.md несёт раздел `## Расширение зон` с путём вне `zones`
        задачи, а ANSWER-1.md несёт маркер `Расширение зон разрешено:` с
        ТЕМ ЖЕ путём — переход обязан пройти в `review`, хотя дифф трогает
        файл вне объявленных `zones` и вне COMMON_ZONES.

        Ловит мутацию: гейт зон реализован буквально по AC-1 без ветки
        исключения AC-3 (раздел PLAN и ANSWER-*.md вовсе не читаются на
        этом переходе) — переход отказал бы для `docs/extra_module.md`
        точно так же, как в test_ac1, несмотря на действующий мандат
        Оператора."""
        self.set_zones("orchestrator/store.py")
        self.write_plan_with_zones_extension(
            "docs/extra_module.md",
            "Нужен отдельный модуль документации вне заявленных zones.")
        self.write_answer_mandate(1, "docs/extra_module.md")

        self.advance_with_diff_files(["docs/extra_module.md"], write_plan=False)

        self.assertEqual(
            self.state(), "review",
            "PLAN несёт раздел расширения зон, ANSWER-1.md несёт мандат "
            "на ТОТ ЖЕ путь — исключение AC-3 обязано пропустить переход")

    def test_ac3_successful_extension_is_recorded_in_zones_extension_column(self):
        """После прохождения перехода по исключению AC-3 колонка
        `tasks.zones_extension` обязана нести путь расширения — «расширение
        записывается в БД задачи» дословно из формулировки AC-3.

        Ловит мутацию: гейт признаёт мандат и пропускает переход, но не
        пишет `zones_extension` (условие есть, побочный эффект в БД —
        нет) — колонка осталась бы NULL/отсутствующей, и следующий
        advance (ANSWER-1, п.4: объединение `zones`/`zones_extension`)
        не увидел бы уже одобренный путь как часть зоны."""
        self.set_zones("orchestrator/store.py")
        self.write_plan_with_zones_extension(
            "docs/extra_module.md",
            "Нужен отдельный модуль документации вне заявленных zones.")
        self.write_answer_mandate(1, "docs/extra_module.md")

        self.advance_with_diff_files(["docs/extra_module.md"], write_plan=False)

        self.assertIn(
            "docs/extra_module.md", self.zones_extension() or "",
            "успешное расширение обязано лечь в tasks.zones_extension (AC-3)")


class Ac3ExtensionWithoutMatchingMandateStillRefusesTest(ZonesGateSandbox):

    def test_ac3_plan_extension_section_without_a_matching_answer_mandate_still_refuses(self):
        """PLAN.md несёт раздел `## Расширение зон» с путём, но НИ ОДИН
        ANSWER-n.md задачи не несёт маркер `Расширение зон разрешено:` с
        этим путём (единственный ANSWER-1.md мандата не содержит вовсе) —
        раздел PLAN сам по себе, без «подкреплённого ANSWER Оператора с
        явным согласием», не открывает исключение: переход обязан
        остаться в `in_dev`, как и без раздела расширения вовсе.

        Ловит мутацию: гейт принимает раздел «## Расширение зон» в PLAN.md
        как достаточное основание САМ ПО СЕБЕ, не проверяя ANSWER-*.md на
        маркер мандата вовсе (пропуская п.2 ANSWER-1.md) — переход прошёл
        бы в `review`, хотя Оператор никакого согласия не давал."""
        self.set_zones("orchestrator/store.py")
        self.write_plan_with_zones_extension(
            "docs/extra_module.md", "Обоснование без мандата Оператора.")
        self.write_answer_mandate(1, "нужен ответ на другой вопрос эскалации")

        self.advance_with_diff_files(["docs/extra_module.md"], write_plan=False)

        self.assertEqual(
            self.state(), "in_dev",
            "раздел PLAN без ANSWER-мандата на ТОТ ЖЕ путь не открывает "
            "исключение AC-3 — переход обязан отказать (AC-1)")

    def test_ac3_mismatched_mandate_path_is_not_silently_substituted(self):
        """ANSWER-1.md несёт мандат на другой путь
        (`docs/some_other_path.md`), не на тот, что заявлен в разделе
        PLAN и реально тронут диффом (`docs/extra_module.md`) — частичный/
        неточный мандат не покрывает путь, реально вышедший за зону:
        отказ обязан назвать именно `docs/extra_module.md` (AC-2 для
        AC-3), а переход остаться в `in_dev`.

        Ловит мутацию: сверка мандата смотрит только на факт «хотя бы
        один ANSWER с маркером существует», не сравнивая конкретные пути
        (упрощение до «мандат есть — всё разрешено») — переход прошёл бы
        в `review`, хотя Оператор согласился на СОВСЕМ ДРУГОЙ путь."""
        self.set_zones("orchestrator/store.py")
        self.write_plan_with_zones_extension(
            "docs/extra_module.md", "Обоснование расширения зон.")
        self.write_answer_mandate(1, "docs/some_other_path.md")

        out = self.advance_with_diff_files(
            ["docs/extra_module.md"], write_plan=False)

        self.assertEqual(
            self.state(), "in_dev",
            "мандат на другой путь не покрывает docs/extra_module.md — "
            "переход обязан отказать")
        combined = out + "\n".join(self.journal_details())
        self.assertIn(
            "docs/extra_module.md", combined,
            "отказ обязан назвать конкретный непокрытый мандатом путь")


if __name__ == "__main__":
    unittest.main()
