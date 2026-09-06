---
operator: Alexander Sidorenko
model: unknown
artel_sha: f0ac767db971451ee2a947f8611d4a19e73b2492
---

# RETRO: 01M1VBEDGMEXHVGWAH42FTDZ4X — budget под живым шагом и возврат из эскалации без холостого шага роли

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: budget под живым шагом и возврат из эскалации без холостого шага роли

Стоимость итого: $42.89
  analyst: $3.76, 6077745 токенов
  test_author: $11.99, 27843529 токенов
  developer: $23.30, 51584289 токенов
  reviewer: $3.83, 6568647 токенов

Ревью: 1 итераций; приёмка: 0 отказ(ов)

Эскалации: 3 (последняя): эскалация от разработчика: **Вопросы**

1. (блокирует) Планка `tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_
   tests/test_ac8_ac9_ac14_ac15_review_verdict_sha.py` зафиксирована
   (лок `a77a7e0f`, T023) — правка не в зоне разработчика. Применить
   через `amend-tests` (ADR-0012) патч ниже, закрывающий R1-F1 (major)
   и остаток R1-F2 (minor) сразу, тем же приёмом, что и в ANSWER-2?
   - Вариант (а) — применить патч дословно, как в ANSWER-2. **Дефолт**
     при молчании: не применять, задача останется в `escalated`.
   - Вариант (б) — применить с правками (указать, с какими).
   - Вариант (в) — отклонить: R1-F1 не требует правки планки (тогда
     нужно назвать альтернативный путь закрытия, не трогающий
     зафиксированный файл).

   Патч (заменить целиком тело двух классов и поправить упомянутые
   докстринги — единственное СМЫСЛОВОЕ изменение — assertion в
   `test_ac9_...`, остальное — только слово `verifying` → `acceptance`
   в комментариях, поведение тестов не меняет):

   ```
   Строка 23 (докстринг модуля):
   - `verifying` даже при сменившемся sha (проверено прогоном на
   + `acceptance` даже при сменившемся sha (проверено прогоном на

   Строки 66-68 (докстринг класса UnchangedShaSkipsANewReviewerRunTest):
   - переходит в `verifying` без нового прогона ревьювера."""
   + переходит в `acceptance` без нового прогона ревьювера."""

   Строки 70-73 (докстринг test_ac8_...):
   -         вердикта — ручной `advance` после `budget` обязан довести задачу
   -         до `verifying`.
   +         вердикта — ручной `advance` после `budget` обязан довести задачу
   +         до `acceptance`.

   Строки 89-112 (класс ChangedShaBlocksTheTransitionTest целиком):
   - class ChangedShaBlocksTheTransitionTest(_ReviewSandbox):
   -     """AC-9: код сменился ПОСЛЕ вердикта — возврат в `review` не переходит
   -     в `verifying` без нового вердикта ревьювера."""
   -
   -     def test_ac9_manual_advance_does_not_reach_verifying_on_changed_sha(self):
   -         """sha кодовой ветки на момент возврата ОТЛИЧАЕТСЯ от sha на
   -         момент вердикта — ручной `advance` обязан отказать переходу в
   -         `verifying`, несмотря на статус `approved` в REVIEW.md.
   -
   -         Ловит мутацию: требование 3 не реализовано вовсе (сегодняшнее
   -         поведение) — advance доведёт задачу до `verifying` по старому
   -         вердикту, написанному для уже неактуального кода.
   -         """
   -         sha_box = self.escalate_with_approved_verdict("a" * 40)
   -         sha_box["sha"] = "b" * 40  # посторонний коммит, пока задача стояла escalated
   -
   -         self.capture(budget.cmd_budget, self.TASK, "50")
   -         self.assertEqual(self.state(), "review")
   -
   -         self.capture(fsm.cmd_advance, self.TASK)
   -
   -         self.assertNotEqual(
   -             self.state(), "verifying",
   -             "переход в verifying случился несмотря на сменившийся sha кода")
   + class ChangedShaBlocksTheTransitionTest(_ReviewSandbox):
   +     """AC-9: код сменился ПОСЛЕ вердикта — возврат в `review` не переходит
   +     в `acceptance` без нового вердикта ревьювера и остаётся в `review`."""
   +
   +     def test_ac9_manual_advance_does_not_reach_verifying_on_changed_sha(self):
   +         """sha кодовой ветки на момент возврата ОТЛИЧАЕТСЯ от sha на
   +         момент вердикта — ручной `advance` обязан отказать переходу в
   +         `acceptance`, несмотря на статус `approved` в REVIEW.md, и
   +         оставить задачу в `review`.
   +
   +         Ловит мутацию: требование 3 не реализовано вовсе (сегодняшнее
   +         поведение) — advance доведёт задачу до `acceptance` по старому
   +         вердикту, написанному для уже неактуального кода; в отличие от
   +         `assertNotEqual(state(), "verifying")` эта проверка не проходит
   +         тривиально после ADR-0015 (approved review больше не ведёт в
   +         `verifying` вовсе, независимо от гейта).
   +         """
   +         sha_box = self.escalate_with_approved_verdict("a" * 40)
   +         sha_box["sha"] = "b" * 40  # посторонний коммит, пока задача стояла escalated
   +
   +         self.capture(budget.cmd_budget, self.TASK, "50")
   +         self.assertEqual(self.state(), "review")
   +
   +         self.capture(fsm.cmd_advance, self.TASK)
   +
   +         self.assertEqual(
   +             self.state(), "review",
   +             "переход в acceptance случился несмотря на сменившийся sha "
   +             "кода — гейт обязан был отказать и оставить задачу в review")

   Строки 119-121 (докстринг test_ac14_...):
   -         `verifying`, не потратив ни одного нового шага ревьювера.
   +         `acceptance`, не потратив ни одного нового шага ревьювера.

   Строка 153 (докстринг test_ac15_...):
   -         задачу прямиком до `verifying` (проверено прогоном на
   +         задачу прямиком до `acceptance` (проверено прогоном на
   ```

   Имя метода `test_ac9_manual_advance_does_not_reach_verifying_on_
   changed_sha` не переименовано (не влияет на поведение, лишний риск
   расхождения с traceability guard) — по желанию Оператора можно
   переименовать отдельно.

**Контекст**

- Итерация 1 REVIEW.md (changes_requested) нашла R1-F1 (major) и
  R1-F2 (minor) — оба про планку `test_ac8_ac9_ac14_ac15_review_
  verdict_sha.py`. R1-F2 в части кода (`fsm_advance.py:220`) исправлен
  в этом шаге. Юнит-тесты `test_budget_live_lease_and_escalation`,
  `test_auto_escalated_return_rework_gate`, `test_fsm_review_rework_
  sha_gate` прогнаны после правки — зелёные (docstring-only правка не
  меняет поведение).
- Планка задачи зафиксирована (`tests_locked_sha` = `a77a7e0f`,
  ADR-0012, T023) — правка файлов под `acceptance_tests/` не входит в
  права роли developer («их правка — эскалация, не правка», см. бриф
  роли); прецедент — ANSWER-2.md этой же задачи, тем же механизмом
  (`amend-tests`).

**Блокирует**

Без амендмента AC-9 остаётся тестом, не ловящим мутацию (major
замечание REVIEW.md) — задача не может дойти до `status: accepted`
записи R1-F1 в реестре замечаний REVIEW.md, а без этого approved-
вердикт следующей итерации не пройдёт `_registry_gate`
(`orchestrator/fsm_advance.py::_registry_gate`).

Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
