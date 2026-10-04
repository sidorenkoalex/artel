---
task: 01M443HPZBMJGCHVGV4JQN88RS
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Тесты не подменяют time.sleep на весь процесс

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–7 привязаны к шагам; шаги
  размера MR (помощники песочницы → перевод мест → приложение → юнит-тесты
  помощников → заявки мутаций), не микрооперации.
- Подход (заместитель ссылки модуля на `time`, `patch_sleep`/
  `patch_pult_sleep` в `tests/sandbox.py`) — ровно приём требования 1,
  код пульта не тронут (требование 7), защищённый `tests/test_invariants.py`
  едет приложением с подтверждённым `git apply --check` (требование 5).
- «Влияние на систему» совпадает с diff: 16 файлов `tests/` + новый
  `tests/test_sandbox_time_with_sleep.py` + карта; путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Все 32 места вне `test_invariants.py` переведены на `TimeWithSleep`/`patch_sleep`/`patch_pult_sleep`, включая формы вспомогательных методов (`test_auto_cycle.py`, `test_runner_model_preflight.py`, `test_01m3yxyax…`) и кортежей (`test_01m3ychs4…`, `test_01m3ychvv…`, `test_01m409ykm…`, `test_01m3sf7d…`). Сверено: модуль, которому подменена пауза, — тот, что её зовёт (`grep sleep( orchestrator/`: `_await_main_ci` зовёт `fsm_merge_gate.time.sleep` — fsm_merge_gate.py:581; `wait_for_window` — merge_queue.py:144; `_wait_for_zone` — auto.py:148), т.е. `assert_not_called`/счётчики не стали тривиально зелёными. |
| 2 | OK | `git diff a6d1656d -- tests/` — ни одной удалённой строки с `assert`; имена `sleep`/`self.pauses`/`fake_sleep` указывают на тот же объект; в 4 методах добавлены только докстринги-заявки. |
| 3 | OK | Сторож test_author `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py` зелёный; временная мутация краснит его с файлом и строкой. |
| 4 | OK | `tests/test_merge_gate_clock_isolation.py` в diff отсутствует, сторож его не отвергает (`test_ac3_…` зелёный). |
| 5 | OK | Приложение PLAN: планка `test_ac6_invariants_appendix.py` (apply --check, поиск, прогон добавленного метода) зелёная. |
| 6 | OK | В долгоживущих файлах других задач методы не удалены/не переименованы, пропусков и ранних `return` нет — меняются только строки подмены и импорты. |
| 7 | OK | `orchestrator/` не в diff. |

## Замечания
Нет замечаний уровня blocker/major/minor.

Наблюдения без замечания:
- `_PULT_SLEEP_MODULES` (tests/sandbox.py) — жёсткий перечень для
  принудительного импорта; новый модуль пульта с паузой, не импортированный
  к вызову, останется с настоящей паузой. Риск назван в PLAN («Риски») и
  проявится зависанием до таймаута pytest, а не тихим зелёным — принимаю.
- AC-4 планки помечен «разовый» законно: долгоживущее свойство «под
  `patch_sleep` `time.sleep` модуля `time` настоящий» держат
  `tests/test_sandbox_time_with_sleep.py` и сторож дерева.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider -o timeout=120` по сторожу
  задачи, `test_sandbox_time_with_sleep.py` и всем 16 изменённым файлам
  `tests/` — 366 passed, 19 failed. Все 19 падений — отказ признака роли
  (`artel.py approve|pin-update|pin --to: команда недоступна процессу роли
  reviewer`) и его прямые следствия (`'merge_gate' != 'done'`, пустой журнал
  после отказа approve) в `test_01m3sf7d…_main_ci.py` и
  `test_main_ci_line.py::FixesMainArgTest`; эти методы зовут команды
  Оператора, правка их не касается; CI de3a4c88 (без признака роли) — зелёный,
  16 проверок.
- `artel.py plank-run 01M443HPZBMJGCHVGV4JQN88RS` — 4 passed, код 0
  (AC-4 subprocess, AC-6 приложение, факты diff).
- Временная мутация: `tests/test_main_ci_line.py:361`
  `patch_sleep(fsm_merge_gate, sleep)` → `mock.patch("time.sleep", sleep)` —
  сторож красный: `tests/test_main_ci_line.py:361: глобальная подмена
  time.sleep — строка цели 'time.sleep'`; код возвращён.
- Временная мутация: `tests/sandbox.py::patch_sleep` →
  `mock.patch.object(time, "sleep", sleep)` — `test_sandbox_time_with_sleep.py`
  2 failed (заявки обоих методов подтверждены); после возврата — 2 passed.
  `git status --short` после мутаций — пусто.
- `git diff a6d1656d -- tests/ | grep -E "^-\s+.*(assert|self\.fail)"` — пусто.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без
  `built_at_sha` — 0 расхождений (карта свежая); файл возвращён.

## Предложения системе
- Шаг ревью не может локально прогнать тесты, зовущие `artel.main` с
  командами Оператора (`approve`, `pin-update`) — признак роли даёт
  ложно-красное (тот же класс отметил developer в PLAN). Стоит, чтобы
  песочница тестов снимала `ARTEL_ROLE` из окружения (tests/sandbox.py /
  conftest.py), иначе каждая роль заново разбирает одни и те же 19 падений.
