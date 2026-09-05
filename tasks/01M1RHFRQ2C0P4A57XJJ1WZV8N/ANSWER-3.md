---
task: 01M1RHFRQ2C0P4A57XJJ1WZV8N
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

1. Приёмка ОТКЛОНЕНА (AC-10), правка обязательна — вывод «код менять не
   нужно» неверен. Планка задачи 01M1R8B3ZKXQT0Z0G6QQQDV906 (снапшот
   `refs/artifacts/01M1R8B3ZKXQT0Z0G6QQQDV906`, каталог
   `tasks/01M1R8B3ZKXQT0Z0G6QQQDV906/acceptance_tests/`) на коде этой
   ветки падает: `test_ac7_lock_conflict_skips_developer_and_stops_on_
   the_repeat` — при отказе `advance` из-за конфликта с локом
   `acceptance_tests/` цикл `auto` теперь запускает developer снова и
   снова (`recorder.roles == ['developer'] * N`) вместо того, чтобы
   пропустить developer и остановиться на повторном отказе. На main тот
   же тест зелёный — регрессию вносит эта ветка.
2. Причина: новое правило «после возврата с основанием переделки —
   сначала шаг developer» применено ко ВСЕМ отказам advance в `in_dev`.
   Отказ guard'а по локу планки (и любой другой отказ, не являющийся
   возвратом `review/acceptance/merge_gate/verifying -> in_dev`) —
   не основание переделки; для него сохраняется прежняя логика: без
   шага developer, стоп-кран на повторном одинаковом отказе (SPEC T038).
3. Воспроизведение: `git archive refs/artifacts/01M1R8B3ZKXQT0Z0G6QQQDV906
   tasks/01M1R8B3ZKXQT0Z0G6QQQDV906/acceptance_tests | tar -x -C <worktree>`,
   затем в worktree `python3 -m unittest discover -s
   tasks/01M1R8B3ZKXQT0Z0G6QQQDV906/acceptance_tests`. Приёмка — этот
   прогон зелёный плюс собственная планка задачи и tests/test_auto_cycle.
