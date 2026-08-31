# ADR-0009: Маршрут review → verifying → acceptance

Дата: 2026-08-31. Статус: принят (решение Оператора).

## Контекст
T079 (B1b) вводит состояние `verifying` — ожидание CI между review
и acceptance (ADR-0003 §10, docs/design.md «запланированные
расширения маршрута»; решение Оператора по QUESTIONS T079, вопрос 2,
вариант B). Требование 4 SPEC T079 и локед-тест
`test_ac4_review_to_verifying.py` осознанно убирают прямой переход
«review → acceptance за один advance» — даже при уже-зелёном CI
остановка в `verifying` обязательна, иначе возвращается
«протаскивание» проверки внутрь одного шага.

Три теста неослабляемого `tests/test_invariants.py` кодируют старый
маршрут (один `advance` из review при approved-вердикте →
`acceptance`):
- `FreshVerdictGuardsAcceptanceTest.test_every_return_to_dev_requires_a_new_verdict`
- `FreshVerdictGuardsAcceptanceTest.test_escalation_and_return_do_not_make_the_verdict_fresh`
- `CountersNeverResetTest.test_no_transition_of_the_full_cycle_resets_a_counter`

Оба утверждения одновременно истинными быть не могут ни при какой
реализации. Разработчик T079 корректно эскалировал, файл не тронул
(ADR-0002), подготовил минимальный патч.

## Решение
1. Маршрут FSM: `review -(advance, свежий approved)-> verifying
   -(advance, CI ветки зелёный)-> acceptance`. Прямой переход
   review → acceptance упразднён.
2. Охраняемая семантика инвариантов НЕ ослабляется: свежий вердикт
   ревью по-прежнему обязателен для достижения приёмки (инвариант 13),
   счётчики не сбрасываются ни на одном переходе. Меняется только
   число шагов маршрута.
3. Три названных теста обновляются механически (правка Оператора,
   коммит в ветку T079): после `advance` из review добавляется
   `assertEqual(state, "verifying")` и второй `advance` перед
   существующим `assertEqual(state, "acceptance")`. Покрытие растёт:
   тесты теперь кодируют и обязательность промежуточной остановки.

## Последствия
- `verifying` при красном CI задачу сам не возвращает: только ручной
  `reject` (симметрия с инвариантом 19; QUESTIONS T079 вопрос 2,
  вариант B); исчерпание потолка ожидания — эскалация.
- Автогейт acceptance (ADR-0007) не затронут: он срабатывает на
  переходе в acceptance, который теперь наступает из verifying.
