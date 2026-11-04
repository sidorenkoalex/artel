# NOTE reviewer, итерация 1

## Выяснено
- Условия пути в `_spec_gate_note_path_refusal` совпадают с ветвями `_approve_spec_gate` (fsm.py ~1561-1580); `artifact_source.resolve` всегда foreign=True.
- `store.task_steps` упорядочен по id — `brief.spec_gate_note` корректен.
- Часть пакета ревьювера — сразу после цикла ANSWER-n (review.py ~996).
- Тесты задачи 27 passed, планка 1 passed, соседние 72 passed; приложения PLAN проходят `git apply --check`; карта свежа; мутации теста формы вызова ловятся.

## Не сработало
Ничего.

## Где остановился
REVIEW.md итерации 1 — approved, реестр пуст.

## Чего не хватило
Ничего существенного.
