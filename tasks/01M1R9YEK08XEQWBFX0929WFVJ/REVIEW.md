---
task: 01M1R9YEK08XEQWBFX0929WFVJ
type: review
author_role: reviewer
status: changes_requested
iteration: 4
schema_version: 4
---

# REVIEW: Приёмка и мерж читают артефакты из артефактной ветки (регрессия №12)

## О пакете этой итерации

Ревью-пакет, полученный на входе, оказался построен от неверной точки:
инкрементальный diff `<sha>...HEAD` использовал в качестве базы
`6a2209331d61106b826cf9ae63adf9df3f283659` — это коммит R1-F1
(`orchestrator/fsm.py: R1-F1 — сбой чтения SPEC.md отказывает
именованно...`) САМОЙ этой ветки, а не sha предыдущего вердикта. Двух-
точечный diff от него до HEAD зацепил и следующий коммит ветки
(«подтяжка main»), который принёс в дерево целиком чужие,
уже смерженные в main изменения других задач (`orchestrator/stack.py` —
RETRO 01M1RDCAFENSW2VVAPECHCVGMM, `orchestrator/zone_lock.py` — RETRO
01M1REVJ8AJDKAMK5VTKES5J6D) — предмета ЭТОЙ задачи (fsm.py/
fsm_advance.py/fsm_merge_gate.py/canary.py) в показанном diff не было
вовсе. Одновременно пакет не нашёл SPEC.md/PLAN.md задачи ни в кодовой
ветке, ни в рабочем дереве — хотя оба лежат на артефактной ветке
(`artifact/01m1r9yek08xeqwbfx0929wfvj`) и материализованы в
`tasks/01M1R9YEK08XEQWBFX0929WFVJ/` рабочего дерева.

Проверка по инструкции пакета («Инкрементальный diff — пустой не значит
без изменений») привела к прямому обходу репозитория: реальный diff —
`git diff main...HEAD` (трёхточечный, от merge-base `a94caf61`), реальные
SPEC.md/PLAN.md — прочитаны с диска рабочего дерева. Вердикт ниже вынесен
по НИМ, не по содержимому присланного пакета. См. «Предложения системе».

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (планка approve `acceptance` — из артефактной ветки) | OK | `orchestrator/fsm.py:322-329` — `acceptance.materialize_from_branch(task_id, artifact_branch_name)` вместо `acceptance.run(wt_path/"tasks"/task_id)`; временный каталог чистится в `finally` (fsm.py:365-366). AC-1/AC-10 подтверждены прогоном приёмочной планки задачи и приёмочными тестами (см. «Проверено исполнением»). |
| 2 (тот же источник в общем узле сверки свежести) | OK | Один узел `_pull_main_or_escalate` покрывает `in_dev` (`fsm_advance.py:763-764`), `acceptance` (`fsm.py:830-831`) и окно `merge_gate` (`fsm_merge_gate.py:326-327`) — AC-2 подтверждён `test_ac1_ac2_pull_reads_plank_from_artifact_branch.py` (оба сценария зелёные). |
| 3 (merge_gate->done несёт снимок артефактной ветки) | OK | `orchestrator/fsm_merge_gate.py::_overlay_artifact_snapshot` (строки 203-266), вызван из `_cmd_approve_merge_gate` сразу после успешного merge, до `merge_sha` (строка ~393). AC-6/AC-7/AC-8/AC-11 подтверждены приёмочными тестами `test_ac6_ac7_ac8_ac11_merge_overlays_artifact_snapshot.py` (все 4 сценария зелёные). |
| 4 (CI guard не валидирует tasks/<id>/ на task/**) | OK | Дифф `.github/workflows/ci.yml`, приложенный к PLAN.md, не коммитится веткой (защищённый путь) — `git apply --check` этого диффа против текущего содержимого файла (совпадает с `main`, файл не тронут этой веткой) прошёл чисто, перепроверено этой итерацией заново (см. «Проверено исполнением»). AC-9 — легитимный `manual` (внешний runtime GitHub Actions вне песочницы, обоснование в `test_ac9_ac12_ci_guard_and_regression_markers.py` отвечает «почему детерминированный тест невозможен» — правило review-checklist). |
| 5 (существующее поведение не ослаблено) | OK | Полный целевой прогон (73 теста: `test_branch_freshness_gate`, `test_fsm_autogate`, `test_artifact_materialization`, `test_merge_gate_ci_wait`, `test_fsm_merge_gate_done_snapshot`, `test_canary`, `test_fsm_map_conflict_autoresolve`) — зелёный. Diff `tests/` не содержит удалённых/ослабленных assert — только новые фикстуры (`write_acceptance_plank()`) и уточнённые проверки источника планки (`assertNotEqual`/`assertIn` вместо жёсткого пути worktree, что и должно было измениться по требованию 1). AC-12 (`skip`, класс `ci-covered`) легитимен — тот же набор гоняет CI-джоб `python` на каждый пуш. |

Реальный код ветки (трёхточечный diff `main...HEAD`, merge-base
`a94caf61d2c5a59470e346b98bcacbd70c88177c`) затрагивает ровно
заявленную зону: `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`
(расширение зоны, ANSWER-1), `orchestrator/fsm_merge_gate.py`,
`orchestrator/canary.py` (расширение зоны, ANSWER-1),
`docs/codebase-map.md`, `tests/test_branch_freshness_gate.py`,
`tests/test_fsm_map_conflict_autoresolve.py`. Расширение зон по
ANSWER-1 (`canary.py`, `fsm_advance.py`) — по одной строке условия в
каждом файле (`in ("escalated", "refused")` вместо `== "escalated"`),
поведение прочего кода не затронуто — соответствует мандату.

## Замечания

- major — `orchestrator/fsm.py:342-360` (чтение SPEC.md через
  `_read_branch_text_or_refuse` для различения AC-3/AC-5) — R1-F1
  (итерации 1-3) исправлен корректно ПО КОДУ (проверено эмпирически,
  см. «Проверено исполнением»), но исправление НЕ закреплено ни одним
  тестом: ни `tests/test_branch_freshness_gate.py`, ни приёмочная
  планка задачи (`test_ac3_ac4_ac5_missing_plank_named_refusal.py`) не
  воспроизводят сценарий «SPEC.md на артефактной ветке НЕ прочитан
  из-за сбоя git (не легитимно отсутствует)» — все существующие тесты
  этой ветки логики покрывают только случай «`acceptance_tests/` не
  найдены, а SPEC.md читается нормально». Ровно этот непокрытый сценарий
  и был предметом блокера три итерации подряд — единственная защита от
  его повторения сегодня — ручная эмпирическая проверка ревьювера
  (итерации 1-4), не воспроизводимая автоматически при следующей правке
  `_pull_main_or_escalate`/`_read_branch_text_or_refuse`. Следующий
  рефакторинг этого узла может тихо вернуть дефолт `meta={}` — и ничего
  в наборе тестов не покраснеет.

  Предложение: добавить в `tests/test_branch_freshness_gate.py` тест,
  мокающий `gitcmd.show`/`gitcmd.ls_tree_files` на сбой (не на
  легитимное «файла/ветки нет») именно для `SPEC.md`, и проверяющий, что
  `fsm._pull_main_or_escalate` возвращает `"refused"` с записью в журнале
  (не `"pulled"`). Ровно такой тест использован для проверки этой
  итерации — воспроизводится:

  ```python
  def fake_show(branch, path):
      if path.endswith("SPEC.md"):
          return None, "git не ответил"
      return None, "нет файла"

  with mock.patch.object(gitcmd, "commits_behind", return_value=3), \
       mock.patch.object(gitcmd, "in_repo", side_effect=self._recording_ok), \
       mock.patch.object(gitcmd, "show", side_effect=fake_show), \
       mock.patch.object(gitcmd, "ls_tree_files", return_value=None):
      outcome = fsm._pull_main_or_escalate(conn, self.TASK, t, "acceptance")
  # outcome обязан быть "refused", журнал — нести "не прочитан"
  ```

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm.py:344-360 (+ fsm.py:830, fsm_advance.py:763, fsm_merge_gate.py:326, canary.py:191) | сбой чтения SPEC.md с артефактной ветки схлопывался в дефолтный `meta={}` → `"pulled"` вместо именованного отказа | молчаливый зелёный проход при транзиентном сбое git | Подтверждено этой итерацией: прямой `gitcmd.show(...) or {}` заменён на `_read_branch_text_or_refuse(conn, task_id, artifact_branch_name, "SPEC.md")` (fsm.py:353-357) — эмпирическая проверка (mock `gitcmd.show`/`ls_tree_files` на сбой чтения SPEC.md) подтвердила: `_pull_main_or_escalate` вернула `"refused"`, журнал получил запись «дерево не на ветке задачи ... — SPEC.md ветки не прочитан (git не ответил)». Дефект устранён по существу — принято. Отдельно от принятия: тест на этот сценарий так и не закреплён (см. новое замечание, major, выше). |
| R1-F2 | accepted | tests/test_branch_freshness_gate.py:340,484,516 | три изменённых теста не несли докстринг «Ловит мутацию» | сложнее восстановить намерение теста при следующей правке файла | Докстринг добавлен всем трём тестовым методам (`test_approve_pulls_main_and_advances_when_acceptance_green`, `test_advance_escalates_on_red_acceptance_after_pull_keeps_merge`, `test_approve_escalates_on_red_acceptance_after_pull_keeps_merge`) — каждый описывает конкретную мутацию (подмена ветки AC-3/AC-4, откат к источнику worktree), заявка соответствует телу теста. Принято. |

## Вердикт

changes_requested — оба замечания реестра прошлых итераций (R1-F1,
R1-F2) закрыты по существу и переведены в `accepted`; новое замечание
(major, выше) требует одного точечного добавления — теста, закрепляющего
сценарий сбоя чтения SPEC.md, который был предметом R1-F1. Сама
реализация SPEC полностью соответствует требованиям 1-5, все AC
подтверждены прогонами; блокеров нет. Добавить предложенный (или
эквивалентный) тест в `tests/test_branch_freshness_gate.py` — после
этого задача готова к approve.

## Проверено исполнением

- `git diff main...HEAD` (трёхточечный, реальный diff ветки от
  merge-base `a94caf61d2c5a59470e346b98bcacbd70c88177c`) — прочитан
  целиком вместо присланного (некорректного) diff пакета; список
  файлов подтверждён `git diff --stat main...HEAD`.
- `python3 -m unittest tests.test_branch_freshness_gate tests.test_fsm_autogate tests.test_artifact_materialization tests.test_merge_gate_ci_wait tests.test_fsm_merge_gate_done_snapshot tests.test_canary tests.test_fsm_map_conflict_autoresolve` — 73 теста, все зелёные.
- `python3 -m unittest discover -s tasks/01M1R9YEK08XEQWBFX0929WFVJ/acceptance_tests` — 10 тестов (AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-10, AC-11), все зелёные; AC-9 manual, AC-12 skip — оба обоснования проверены и легитимны (внешний runtime вне песочницы; класс ci-covered).
- `git apply --check` диффа `.github/workflows/ci.yml`, приложенного к PLAN.md, против текущего содержимого файла (не тронутого этой веткой, совпадает с `main`) — применяется чисто.
- `python3 scripts/codebase_map.py --check` — карта свежая (расхождение только в `built_at_sha`, что не является дефектом по правилу review-checklist); подтверждено, что новый импорт `fsm_merge_gate.py -> artifact_branch.py` отражён в карте с обеих сторон.
- Эмпирическая проверка R1-F1 (см. «Реестр замечаний»): собран изолированный тест на базе `tests.test_branch_freshness_gate.BranchFreshnessGateTest` с моком `gitcmd.show`/`gitcmd.ls_tree_files`, отвечающим сбоем (не легитимным отсутствием) на чтение `SPEC.md` — `fsm._pull_main_or_escalate(conn, task_id, t, "acceptance")` вернула `"refused"`, журнал получил запись «дерево не на ветке задачи ... — SPEC.md ветки не прочитан (git не ответил)». Подтверждает, что блокер R1-F1 действительно устранён по коду (см. новое замечание про отсутствие закреплённого теста).
- Полный набор `tests/` не прогонялся (штатно гоняет CI на каждый пуш, решение Оператора 05.09) — сверка «набор не ослаблен» сделана по diff `tests/` (только два файла изменены, без удаления/ослабления assert).

## Предложения системе

- Сборка ревью-пакета для этой итерации взяла в качестве базы
  инкрементального diff коммит самой этой ветки (`6a220933`, R1-F1),
  а не sha предыдущего вердикта — последующая «подтяжка main» этой
  ветки принесла в двухточечный diff чужие изменения других
  уже смерженных задач (`orchestrator/stack.py`,
  `orchestrator/zone_lock.py`) и скрыла реальный (маленький) diff этой
  задачи целиком; SPEC.md/PLAN.md пакет не нашёл вовсе, хотя оба лежат
  на артефактной ветке и материализованы в рабочем дереве. Тот же класс
  дефекта, что бэклог называет «Гейт зон сравнивает деревья, не точку
  расхождения» (сравнение по двум точкам вместо трёх/явного merge-base) —
  похоже, сборщик пакета ревью страдает тем же классом проблемы с
  выбором базы diff, не только `fsm_advance.py`.
