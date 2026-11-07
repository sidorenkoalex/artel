# Записка analyst

## Выяснено
- Шаг 2 (возврат аудита, fail): 10 отклонений — это решения, которых в ТЗ нет (зона хука, предел/место ожиданий, canceled/auto-cancel, «красное», гейт мержа, источник отправки, входы in_dev, раздел полей). Поэтому QUESTIONS.md (9 вопросов с дефолтами), SPEC.md не тронут.
- Хук `scripts/git-hooks/target-human/pre-push` читает 4 ключа (:38-50), отказ ветке не по шаблону (:96-100) — без зоны хука требование 5 невыполнимо.
- `_ci_base_report` (outcome_integrity.py:1113-1133) отбрасывает `_pending`; `_CI_FIT_STATUSES` (:1045) включает `failed`.
- Мерж: `_Prepare` -> `sys.exit`, задача остаётся на гейте (outcome_integrity.py:1617-1622).
- Поля компонента — `description.components` (targets.py:130); `policy.components` — только LOCAL_POLICY_SCOPES (:436, :579).

## Не сработало
—

## Где остановился
QUESTIONS.md написан, guard: ок. После ANSWER: переписать SPEC по ответам (дефолты: A во всех вопросах), добавить хук в зоны, удалить QUESTIONS.md, status: ready. Бюджет пересчитать (+хук, +AC; сейчас 55).

## Чего не хватило
Механизма «ожидание вне advance» в коде нет — ожидание базы возможно только опросом verifying.
