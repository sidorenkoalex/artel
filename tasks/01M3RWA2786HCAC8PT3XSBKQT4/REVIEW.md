---
task: 01M3RWA2786HCAC8PT3XSBKQT4
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Автогейт приёмки видит долгоживущие файлы планки

## Соответствие SPEC

Фаза A (гейт плана): покрытие требований полное; два шага проверяемы и
соразмерны MR. Подход использует тот же узел чтения перечня, что переход
`in_dev`, сохраняет прежний путь задачи без перечня и описывает откат.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1, AC-1 | OK | `_plank_sources` объединяет разовые файлы артефактной ветки с файлами перечня из кодовой ветки; оба потребителя сканируют этот набор. |
| 2, AC-2 | OK | Непустой перечень учитывается при проверке пустоты, а ошибка чтения долгоживущего файла возвращает отказ с путём. |
| 3, AC-3 | OK | При отсутствии `tests_locked_sha` сохранены прежний набор разовых файлов и текст отказа; существующий модуль автогейта прошёл без изменений. |
| 4, AC-4 | OK | Долгоживущий тест задачи покрывает зелёную планку, `manual` и нечитаемый файл; новый модуль проверяет перечисление `skip`/`escalate` и ошибку чтения в записи. Заявки «Ловит мутацию» конкретны и подтверждены временной мутацией. |

## Замечания

Замечаний нет.

## Реестр замечаний

Замечаний для регистрации нет.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py tests/test_fsm_autogate.py tests/test_fsm_autogate_long_lived.py tests/test_long_lived_manifest.py tests/test_long_lived_transitions.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 52 passed, 20 subtests passed.
- Временная мутация в `_plank_sources`, исключающая файлы перечня долгоживущих, и запуск `python3 -m pytest tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py tests/test_fsm_autogate_long_lived.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 5 ожидаемых падений; мутация отменена.
- `git diff --check 538ad0dec074991805c26941aed0383146613469...HEAD` — без ошибок.

