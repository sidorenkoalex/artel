---
task: 01M5K9M5DGPDRXG2M5B4KKGQ54
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: pin-update --wait-ci — ожидание CI головы main командой пульта

## Подход
Ожидание — новая закрытая функция `orchestrator/pin.py::_wait_for_main_ci_green(sha)`,
которая встаёт в `cmd_pin_update` на место `_refuse_unless_main_ci_green` только
при `wait_ci=True` (после `fetch` и гейта канарейки). Цикл повторяет порядок
`fsm_merge_gate._wait_for_branch_ci_green`: опрос `ci.main_line_status(sha,
repo=config.ROOT)` → зелёный — выход; красный — прежний текст отказа; иначе
строка `[pin-update] <note> (ожидание N сек)`, затем потолок
(`time.monotonic() - start >= MERGE_GATE_CI_WAIT_CEILING_SEC`, в тексте —
значение константы), затем `time.sleep(MERGE_GATE_CI_WAIT_POLL_SEC)`.
`start` берётся перед первым опросом. Часы и пауза — через `import time`
модуля `pin`.

Разбор формы команды — `orchestrator/artel.py::_cmd_pin_update(rest)` рядом с
`_cmd_pin`: `--wait-ci` пропускается, прочий `--…` и второй sha — отказ
«неизвестный аргумент», отсутствие sha — отказ с формой команды; оба отказа
до вызова `pin.cmd_pin_update`, т.е. без `fetch` и журнала.

Свои тесты не добавлялись: все свойства AC-1..AC-9 держит долгоживущий файл
`tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py`, прежнее
поведение без флага — `tests/test_pin.py` и
`tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`.

## Шаги
1. `orchestrator/pin.py`: `import time`, `_wait_for_main_ci_green`, параметр
   `wait_ci: bool = False` у `cmd_pin_update`.
2. `orchestrator/artel.py`: `_cmd_pin_update` (разбор аргументов, два отказа
   формы), запись таблицы диспетчера, строка перечня команд и абзац справки
   `pin-update`; регенерация `docs/codebase-map.md`.
3. Прогон: долгоживущий файл задачи + `tests/test_pin.py`,
   `test_01m3xtf5506gf43hd51ece230t_role_refusal.py`,
   `test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`,
   `test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`,
   `test_01m3yqb4kmady0bet5n8279n6b_start_precision.py` — 62 passed, 2 skipped.
   Контрольная мутация `>=` → `>` в потолке — AC-5 красный, код возвращён.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 2 |
| 3 | 2 |
| 4 | 1 (ветка `else` вызывает прежнюю `_refuse_unless_main_ci_green`) |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 (merge только после возврата из ожидания на `MAIN_GREEN`; `cmd_pin_to` не тронут) |
| 8 | 2 |
| 9 | 1 |
| 10 | 3 (долгоживущий файл задачи) |

## Влияние на систему
Гейт CI пина не ослабляется: без флага код пути прежний побайтно; с флагом
пин сдвигается только при `MAIN_GREEN`, `MAIN_UNKNOWN` не считается зелёным
(инвариант 19), красный отказывает тем же текстом. Порядок «канарейка до CI»
сохранён. Константы гейта мержа только читаются, `config.py`/`ci.py`/
`fsm_merge_gate.py` не меняются. `pin` теперь имеет ссылку `time` — его
захватывает `tests/sandbox.patch_pult_sleep`, это ожидаемо и безвредно (пауза
зовётся только с `--wait-ci`). Откат — revert коммита задачи.

## Риски
- Отказ «неизвестный аргумент» теперь срабатывает на форме, которую раньше
  диспетчер молча игнорировал (`pin-update <sha> <лишнее>`) — это требование 3.

## Предложения системе
- Прочие команды диспетчера `artel.py` с `rest[0]` (`amend-tests`, `ci-rerun`,
  `pull-main`, `zone-release`) без аргументов падают `IndexError` — класс тот
  же, что закрыт здесь для `pin-update`; SPEC выносит его в отдельную задачу.
