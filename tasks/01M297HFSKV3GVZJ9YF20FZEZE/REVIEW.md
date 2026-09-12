---
task: 01M297HFSKV3GVZJ9YF20FZEZE
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: база ветки задачи — origin/main, а не локальный пин; doctor и new видят непушенные коммиты главной копии

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`workspace.ensure` от `origin/<MAIN_BRANCH>`, AC-1..AC-3) | OK | Self-сценарий работал уже в итерации 1. Блокер итерации 1 (канареечный путь `canary._ephemeral_clone` ломался обязательным `git fetch origin`) закрыт: `orchestrator/canary.py::_ephemeral_clone` теперь заводит рядом с эфемерным клоном одноразовый bare-mirror `origin_dir` (`git clone --bare --shared dest origin_dir`) и переставляет `origin` клона на него вместо недостижимой схемы `ORIGIN_STUB_URL` (константа убрана). Fetch внутри клона проходит локально, push по-прежнему не покидает пару временных каталогов (требование 3 SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ не нарушено — прочитан код, `origin_dir` не более достижим извне, чем прежний `dest`). |
| 2 (`doctor` `pin-unpushed`, AC-4..AC-6) | OK | Без изменений с итерации 1, диф этой итерации файл не трогает. |
| 3 (`cmd_new` предупреждение + журнал, AC-7/AC-8) | OK | Без изменений с итерации 1, диф этой итерации файл не трогает. |
| 4 (тесты) | OK | Ранее падавший `tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/test_ac2_ac4_ephemeral_clone_lifecycle.py` перепрогнан лично мной — зелёный (см. «Проверено исполнением»). `tests/test_workspace.py::RealGitWorkspaceTest` поправлен (`git init --bare -b <MAIN_BRANCH>`, чтобы голый origin нёс ветку под ожидаемым именем) — не ослабление, чисто техническая правка под новую реальность (bare-репозиторий без `-b` заводит ветку с дефолтным именем окружения, не обязательно `main`). |

## Замечания

(нет — R1-F1 закрыт, новых дефектов не найдено)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/canary.py:478-543 (было workspace.py:73-82 + canary.py:1018-1034, 496-502 до рефакторинга) | Обязательный `git fetch origin` в `workspace.ensure` был несовместим с намеренно нерабочим `origin` `canary._ephemeral_clone` | `artel.py canary --k N` падал `RuntimeError` на каждом прогоне | Подтверждаю закрытие: `_ephemeral_clone` заводит одноразовый bare-mirror `origin_dir` (`--shared`, без удвоения копии объектов пульта — переживает `dest` при удалении вместе с ним), `origin` клона указывает на него. Лично перепрогнал ранее падавшие `test_ac2_ac4_ephemeral_clone_lifecycle.py` + `test_ac3_no_traces_in_main_pult.py` — зелёные (3 passed, 8 subtests, 248с). Расширение зоны на `orchestrator/canary.py` покрыто мандатом Оператора (`ANSWER-3.md`). |

## Вердикт

approved — единственный блокер итерации 1 (R1-F1) закрыт и лично перепроверен прогоном ранее падавшего сценария, требования 1-4 реализованы корректно, побочных затрагиваний вне заявленных зон не найдено.

## Проверено исполнением

- Инкрементальный diff пакета (сгенерированный от sha `1045a9e961ce2dbdaf12a1f1d3998bb06cbd4277`) оказался пустым, потому что этот sha совпадает с текущим HEAD ветки (тот же класс, что T087 — sha предыдущего вердикта из отдельной артефактной ветки указывает мимо кода). Нашёл реальный коммит вердикта итерации 1 через `git log --oneline --all -- tasks/01M297HFSKV3GVZJ9YF20FZEZE/REVIEW.md` (8e995b40, не предок HEAD — артефактная ветка) и восстановил границы диапазона фикса через `git log --oneline 65ce91e4..HEAD` / `git diff f6bc6b3d..HEAD --stat`: реальный диф итерации 2 — `orchestrator/canary.py` (+41/-6), `tests/test_workspace.py` (+2/-1), `docs/codebase-map.md` (только `built_at_sha`). Дальше ревьюировал именно этот диапазон.
- `python3 -m pytest tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/test_ac2_ac4_ephemeral_clone_lifecycle.py tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/test_ac3_no_traces_in_main_pult.py -q` — 3 passed, 8 subtests passed (248.41с). Ровно тот сценарий, что падал `RuntimeError` в итерации 1 — теперь зелёный.
- `python3 -m pytest tests/test_workspace.py tests/test_canary.py -q` — 96 passed, 4 subtests passed (10.79с).
- `python3 -m pytest tasks/01M297HFSKV3GVZJ9YF20FZEZE/acceptance_tests/ -q` (AC-1..AC-8 этой задачи) — 10 passed (3.79с).
- `git diff origin/main -- orchestrator/fsm_advance.py` — пусто; подтверждает заявленный в PLAN откат правки комментариев (коммит `fefc89a4`) байт-в-байт до состояния main, комментарии вне мандата ANSWER-3 действительно не задеты финальным диффом.
- Проверка боковой находки PLAN («предсуществующая флакующая планка `test_ac8`/`test_ac9`/`test_ac11` с потолком 30с»): временно откатил `orchestrator/workspace.py`, `orchestrator/canary.py`, `orchestrator/catalog.py` к `cd9a477b` (`git checkout cd9a477b -- ...`, чистое дерево до и после подтверждено `git status --short`/`git diff --quiet`) и прогнал `test_ac9_per_task_baseline.py` — падает тем же `pytest-timeout (>120.0s)`, что и на HEAD с фиксом; `test_ac8_escalation_marker_discrepancy.py` на baseline и на HEAD (с фиксом) падает ОДНОЙ И ТОЙ ЖЕ логической ассерцией («отчёт не отметил расхождение маркер/факт»), не таймаутом — то есть класс дефекта идентичен на обеих версиях кода, к диффу этой задачи не относится. После проверки файлы восстановлены (`git checkout HEAD -- ...`, `git diff --quiet HEAD -- ...` подтвердил чистое совпадение).
- Полный набор `tests/` не прогонял (решение Оператора 05.09 — гоняет CI на каждый пуш); статус CI коммита `1045a9e9` — зелёный, 14 проверок (дано в пакете).

## Предложения системе

- Инкрементальный diff ревью-пакета второй раз подряд (после T087) указал на sha, совпадающий с текущим HEAD, хотя реальный коммит предыдущего вердикта лежит в отдельной артефактной ветке и не является предком кода — стоит чинить построение diff-пакета так, чтобы для артефактных веток брался коммит, где REVIEW.md получил предыдущий `status`, а не эвристика «последний известный код-sha», которая здесь тривиально совпала с HEAD и дала пустой (обманчивый) diff.
- Подтверждаю независимо находку PLAN этой задачи (раздел «Предложения системе»): `test_ac8_escalation_marker_discrepancy.py`/`test_ac9_per_task_baseline.py`/`test_ac11_verifying_gate_bypassed.py` (`tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/`) флакуют на HEAD ДО этой задачи так же, как и после — не регрессия этой задачи, а старение планки под рост пульта; стоит завести отдельную задачу на пересмотр порогов (30с/120с), пока эта планка не начала маскировать реальные регрессии таким же классом ложных сигналов.
