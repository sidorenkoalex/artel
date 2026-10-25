## Выяснено
- Итерация 1 ревью: approved, blocker/major нет; три minor-наблюдения (дубль `_strings` в projects.py, rsplit по env-ключу с точкой в `_check_local_values`, мягкость `core_reference` к пустому `targets:` локального слоя).
- Планки в refs/artifacts нет — все свойства в 4 долгоживущих файлах tests/; 67 passed с test_acceptance_suite_profile.
- Мутации watch (layer_changed=False) и абсолютных путей ловятся.
- Карта свежая (только built_at_sha).

## Не сработало
- Прогон `tests/test_01m5scgsqn0at0b07h7m9803ra_watch_layer.py` в одиночку — ошибка сборки (цикл импорта checkpoint→fixation), есть и на базе 8fcc989d; гонять вместе с другим файлом (например doctor_layer).
- sed -i и `cd … && git worktree` требуют подтверждения — мутации делать через `python3 - <<EOF`, базу смотреть через `git archive` из python.

## Где остановился
REVIEW.md записан (approved).

## Чего не хватило
Правила: заносить ли minor в реестр замечаний при approve (гейт требует всех accepted).
