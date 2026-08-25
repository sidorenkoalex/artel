---
task: T032
type: spec
author_role: analyst
status: ready        # draft | ready | approved
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
budget_usd: 15
---

# SPEC: doctor: check_base_branch — догфуд-skip и тесты

## Контекст
Minor-замечание ревью T022 (docs/roadmap.md, беклог P3 «doctor:
check_base_branch»): `check_base_branch` в `orchestrator/doctor.py` —
единственная из проверок требования 9 задачи T022, предназначенных
только для внешнего target, которая не исключает догфуд
(`config.DEFAULT_TARGET`). Соседние `check_remote_empty` и
`recovery_check` для догфуда честно возвращают `skip` с причиной, а
`check_base_branch` вместо этого каждый раз делает боевой `gh repo
view` для репозитория пульта. Практических последствий нет (`fail`
или `alert` эта проверка на догфуде не заводит), но это лишний сетевой
вызов вне заявленного объёма требования и расхождение с образцом двух
соседних проверок. Дополнительно сама функция не покрыта тестами в
`tests/test_doctor.py`.

## Требования

1. `check_base_branch` для догфуд-target (`name == config.DEFAULT_TARGET`)
   возвращает `skip` с причиной, объясняющей, что догфуд — особый
   случай, а не попытка сверки базовой ветки с форджем, — по образцу
   раннего выхода в `check_remote_empty` и `recovery_check`.
2. Функция покрыта тестами в `tests/test_doctor.py` по образцу
   соседних проверок: обязателен тест skip-ветки на догфуде; состав
   остальных веток (сверка совпадает/расходится с `targets.yaml`,
   `gh` недоступен — для внешнего target) определяется тем, что
   реально воспроизводимо в песочнице теста.
3. Поведение `check_base_branch` для внешних target (не догфуд) не
   меняется.

## Критерии приёмки

AC-1. Вызов `check_base_branch(config.DEFAULT_TARGET, entry)` возвращает
`Check` со статусом `skip` и причиной, указывающей, что догфуд —
особый случай (не сверка базовой ветки).

AC-2. `tests/test_doctor.py` содержит тест, проверяющий AC-1
(skip-ветка на догфуде).

AC-3. Для target, отличного от `config.DEFAULT_TARGET`, поведение
`check_base_branch` не изменилось: ветки `forge != "github"` (skip),
`gh` не найден (skip), сверка через `gh repo view` (ok при совпадении
базовой ветки, warn при расхождении) работают как до изменения.

## Не входит

- Расширение тестового покрытия на все ветки внешнего target (успешное
  совпадение базовой ветки, расхождение с `targets.yaml`, таймаут или
  ошибка `gh`) сверх минимально необходимого по требованию 2 — состав
  этих тестов вне skip-ветки на догфуде на усмотрение исполнителя,
  по возможностям песочницы.
- Изменения в `check_remote_empty` и `recovery_check` — уже
  соответствуют образцу, не предмет задачи.
- Изменение сигнатуры `check_base_branch(name, entry)` или порядка
  вызова проверок в `all_checks()` за пределами добавляемого
  early-return.

## Материалы

- tasks/T022/REVIEW.md — замечание про `check_base_branch`
  (строки 37–58, 64–79).
- docs/roadmap.md:216 — строка беклога P3.
- `orchestrator/doctor.py:473–484` (`check_remote_empty`),
  `orchestrator/doctor.py:339–348` (`recovery_check`) — образец
  раннего skip для догфуда.
- `orchestrator/doctor.py:487–513` — текущая реализация
  `check_base_branch`.
