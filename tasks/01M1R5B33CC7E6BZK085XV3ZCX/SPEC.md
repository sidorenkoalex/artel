---
task: 01M1R5B33CC7E6BZK085XV3ZCX
type: spec
author_role: analyst
status: ready
schema_version: 4
zones: orchestrator/gitcmd.py, orchestrator/ci.py, orchestrator/github_adapter.py, orchestrator/fsm.py, orchestrator/fsm_advance.py, orchestrator/fsm_merge_gate.py, orchestrator/fsm_postmerge.py, orchestrator/review.py, orchestrator/acceptance.py, orchestrator/doctor.py, tests/sandbox.py, tests/
budget_usd: 45
---

# SPEC: B2 ТЗ-1: репозиторный контекст target для git/gh-слоя

## Контекст
Весь git- и forge-слой оркестратора привязан к репозиторию ПУЛЬТА:
`gitcmd.git` и `ci.gh` всегда исполняются с `cwd=config.ROOT`, а `gh api
repos/{owner}/{repo}/…` резолвит владельца/имя репозитория из remote
`config.ROOT`. Для target `self` (артель) это правильно — её код и
живёт в `config.ROOT`. Для любого другого target — нет: ветка задачи,
её CI, её MR и её main живут в ДРУГОМ репозитории
(`.artel/projects/<target>/workspace`, `targets.yaml[target]`), а код
сегодня об этом не знает и молча работает с репозиторием пульта. Итог
(докладная 2026-09-04, `docs/research/2026-09-04-external-target-
readiness.md`, §2.2, §4.3 класс Б): подключить внешний target нельзя —
не по одной причине, а структурно.

## Реестр точек репозиторного контекста
Точки таблицы §4.3 класс Б докладной, актуализированные на голову этой
ветки (сверено чтением кода 05.09; регрессии №5/№6/№8 уже смержены).
Пункт «карта кодовой базы брифа» реестра докладной сюда не входит —
это `brief.py`/генерация карты целевого, явно отнесённые к ТЗ-4 (см.
«Не входит»); «снапшот закрытия» переведён отдельной строкой ниже без
изменения кода — только фиксирует общий адрес клона.

| № | Точка | Файл:функция | Что читает/пишет сегодня | Что должна после этой задачи |
|---|---|---|---|---|
| 1 | Сверка свежести и подтяжка | `orchestrator/fsm.py::_pull_main_or_escalate` (через `_origin_main_source`/`_origin_main_sha`) | sha `origin/<base>` уже берётся из `targets.yaml[target]` (регрессия №5, смержена 05.09) — но `commits_behind(branch, base=sha)` и сам merge/подтяжка (`workspace.ensure` + `gitcmd.in_repo`) идут в worktree ПУЛЬТА, где ветки внешнего target нет: `commits_behind` возвращает `None` → «fresh» молча, без реального сравнения | ветка задачи, `commits_behind` и merge подтяжки — в клоне/worktree репозиторного контекста target'а, не `config.ROOT` |
| 2 | Doctor «отставание ветки» | `orchestrator/doctor.py::check_branch_freshness` | `gitcmd.commits_behind(t["branch"])` без `base` — сравнение с локальным `config.MAIN_BRANCH` в `config.ROOT` для ЛЮБОГО target | сравнение с `origin/<base>` репозиторного контекста target'а (тот же источник, что и точка 1) |
| 3 | Голова ветки для CI | `orchestrator/ci.py::head_sha` | `refs/heads/<branch>` в `config.ROOT` | клон контекста target'а |
| 4 | Опрос check-runs / run list | `orchestrator/ci.py::check_runs_page`, `run_list` | `gh api repos/{owner}/{repo}/…`/`gh run list` без `--repo`, репозиторий резолвится `gh` из remote `config.ROOT` | `--repo <targets.yaml[target].url>` контекста |
| 5 | Push ветки задачи | `orchestrator/github_adapter.py::ensure_draft_mr`, `ensure_head_in_origin`; `orchestrator/fsm_merge_gate.py::_cmd_approve_merge_gate` (push после подтяжки) | `git push -u origin <branch>` в `config.ROOT` | push в origin клона контекста target'а |
| 6 | Draft-MR / undraft / комментарий | `orchestrator/github_adapter.py::ensure_draft_mr`, `undraft_mr` | `gh pr create/ready/comment` без `--repo`, из `config.ROOT` | `gh --repo <url>` контекста |
| 7 | Защищённые пути в MR | `orchestrator/github_adapter.py::_touched_protected_paths` | diff `base...branch` в `config.ROOT` | diff в клоне контекста target'а (источник самого списка путей — `config.PROTECTED_PATHS` vs `targets.yaml.no_paths` — не меняется этой задачей, см. «Не входит») |
| 8 | Diff ревью-пакета | `orchestrator/review.py::git_diff_part` | `gitcmd.git("diff", …)` в `config.ROOT` | клон контекста target'а |
| 9 | Гейт ёмкости diff | `orchestrator/fsm_advance.py::_capacity_gate_refuses` | для target ≠ self гейт не считается вовсе (`return False` сразу) — обоснование «`config.ROOT` не видит код внешнего target» | считается для ЛЮБОГО target через `git_diff_part` в клоне контекста (см. точку 8) — внешний target больше не пропускается |
| 10 | Прогон приёмочных тестов | `orchestrator/acceptance.py::run` | `unittest discover` с `cwd=config.ROOT` ВСЕГДА, даже когда `tdir` — материализованный из ветки временный каталог внешнего target: код target'а из его клона в `sys.path` не попадает | `cwd` = клон контекста target'а (или его временная материализация — решение исполнителя на PLAN), не `config.ROOT`, для target ≠ self |
| 11 | Merge / scratch / push main | `orchestrator/fsm_merge_gate.py::_origin_main_sha` (своя копия, только про main артели), `_scratch_worktree`, финальный `push` | scratch создаётся из `config.ROOT`, merge и push `refs/heads/<MAIN_BRANCH>` — ВСЕГДА в `config.ROOT`/её origin, независимо от target (для внешнего target это сегодня тупик: ветки там нет, merge падает на неизвестной ссылке) | для target ≠ self — scratch, merge и push `refs/heads/<base>` в клоне контекста target'а и его origin; для self — без изменений |
| 12 | RETRO/карта после мержа | `orchestrator/fsm_merge_gate.py::_cmd_approve_merge_gate` (зовёт `fsm_postmerge._regenerate_and_commit_map`/`_generate_and_commit_retro` безусловно, в том же scratch) | для ЛЮБОГО target пытается регенерировать карту и закоммитить RETRO в main | для target ≠ self — оба вызова пропускаются целиком (RETRO задачи внешнего target уже есть в снапшоте `refs/artifacts/<id>`, `snapshot.py`); для self — без изменений |
| 13 | Снапшот закрытия | `orchestrator/snapshot.py::publish_and_cleanup` (не меняется этой задачей) | workspace = `.artel/projects/<target>/workspace`, требует клона с origin (даёт ТЗ-2) | путь клона репозиторного контекста этой задачи обязан совпадать с этим же адресом — не заводить второй/другой путь для того же target |

## Требования
1. Понятие «репозиторный контекст target» в одном месте (модуль/
   функция): путь клона (`config.ROOT` для self; `.artel/projects/
   <target>/workspace` для любого другого — тот же адрес, что уже
   использует `orchestrator/snapshot.py`), адрес форджа
   (`targets.yaml[target]["url"]`), базовая ветка
   (`config.MAIN_BRANCH` для self; `targets.yaml[target]["base"]`
   иначе). Все точки реестра выше (кроме №13, не меняемой этой
   задачей) переводятся на этот контекст — так, что «что должна»
   становится «что делает».
2. `ci.gh` принимает контекст и передаёт `--repo <url>` в `pr create`,
   `pr ready`, `pr comment`, `api repos/<owner>/<repo>/…`, `run list`;
   `ci.head_sha` и опрос check-runs читают клон и форджу контекста
   target'а, не `config.ROOT`, когда target ≠ self.
3. Сверка свежести и подтяжка (`fsm._pull_main_or_escalate`) для
   target ≠ self ведёт сравнение и merge подтяжки в клоне/worktree
   контекста target'а (не в worktree `config.ROOT`), достраивая уже
   смерженную (05.09) параметризацию источника sha по target
   (01M1NBWPKNBXP9ZXXQDJM7AXPJ) до полноценной работы на внешнем
   target; поведение для self не меняется. `doctor.
   check_branch_freshness` сравнивается с тем же источником.
4. Merge для внешнего target с `merge_gate: operator`: scratch-
   worktree и push `refs/heads/<base>` — в клоне контекста target'а и
   его origin, не в `config.ROOT`; после мержа для внешнего target НЕ
   регенерируется карта и НЕ коммитится RETRO в main контекста
   (правило «в пульте — только кухня пульта»; RETRO у внешнего target
   остаётся только в снапшоте). Для self (артель) поведение мержа/
   карты/RETRO не меняется.
5. Гейт ёмкости diff (`fsm_advance._capacity_gate_refuses`) и diff
   ревью-пакета (`review.git_diff_part`) строятся из клона контекста
   target'а; для внешнего target гейт больше не пропускается
   безусловно.
6. Тесты: сквозной (end-to-end) прогон на ДВУХ настоящих
   git-репозиториях в песочнице (пульт + целевой с локальным
   bare-origin, тем же приёмом, что уже опробован для внешнего target
   в задаче M1 — `ExternalTargetGitSandbox`): задача внешнего target
   проходит `new → in_dev → review (diff непустой) → merge_gate →
   done` с merge, зарегистрированным в origin ЦЕЛЕВОГО, и без единого
   нового коммита в `main` пульта; существующие тесты остаются
   зелёными; инвариант «тесты не пишут в настоящий репозиторий»
   (01M1KVGD18P9H5WR7VM8TGPV1T) — предусловие, не ослабляется новыми
   тестами.

## Критерии приёмки
AC-1. Существует единая функция/объект «репозиторный контекст target»:
для self — путь клона `config.ROOT`, remote `origin`, ветка
`config.MAIN_BRANCH`; для любого другого target — путь клона
`.artel/projects/<target>/workspace`, адрес форджа
`targets.yaml[target]["url"]`, базовая ветка
`targets.yaml[target]["base"]`.

AC-2. `ci.gh` принимает контекст target и подставляет `--repo <url>` в
вызовы `pr create`, `pr ready`, `pr comment`, `api repos/<owner>/
<repo>/…`, `run list`; для self поведение (без `--repo`, из
`config.ROOT`) байт-в-байт не меняется.

AC-3. `ci.head_sha` и опрос статуса проверок (`check_runs_page`/
`run_list`) резолвят коммит и статус из клона/форджа контекста
target'а, когда target ≠ self.

AC-4. `fsm._pull_main_or_escalate` для target ≠ self сравнивает
(`commits_behind`) и выполняет merge подтяжки в клоне/worktree
контекста target'а, а не в worktree `config.ROOT`; для self —
поведение прежнее.

AC-5. `doctor.check_branch_freshness` для target ≠ self сравнивает
ветку задачи с `origin/<base>` контекста target'а, не с локальным
`config.MAIN_BRANCH` `config.ROOT`.

AC-6. Push ветки задачи (`github_adapter.ensure_draft_mr`,
`ensure_head_in_origin`, push после подтяжки в `fsm_merge_gate`) для
target ≠ self идёт в origin клона контекста target'а; для self — в
origin `config.ROOT`, как и прежде.

AC-7. Draft-MR, снятие Draft и комментарий защищённых путей
(`github_adapter.ensure_draft_mr`, `undraft_mr`) для target ≠ self
зовут `gh --repo <url>` контекста target'а.

AC-8. Подсветка защищённых путей в MR (`_touched_protected_paths`)
считает diff в клоне контекста target'а, не в `config.ROOT`, когда
target ≠ self.

AC-9. Diff ревью-пакета (`review.git_diff_part`) для target ≠ self
строится в клоне контекста target'а; для self diff по-прежнему из
`config.ROOT`.

AC-10. Гейт ёмкости diff (`fsm_advance._capacity_gate_refuses`)
применяется к ЛЮБОМУ target: для target ≠ self он больше не
пропускается безусловно, а считает diff в клоне контекста target'а
тем же способом, что и AC-9.

AC-11. `acceptance.run` для target ≠ self исполняет прогон приёмочных
тестов с `cwd`, указывающим на клон контекста target'а (или его
временную материализацию), а не на `config.ROOT`; для self поведение
не меняется.

AC-12. `merge_gate` c `merge_gate: operator` для target ≠ self строит
scratch-worktree, выполняет merge и push `refs/heads/<base>` в клоне
контекста target'а и его origin, а не в `config.ROOT`; для self
(артель) плотницкий merge выполняется как прежде, в `config.ROOT`.

AC-13. Для target ≠ self после успешного merge вызовы регенерации
`docs/codebase-map.md` и коммита RETRO в main НЕ выполняются вовсе
(ни одного коммита в кодовую базу целевого этими двумя шагами); для
self оба шага выполняются как прежде.

AC-14. Путь клона репозиторного контекста для target ≠ self
буквально совпадает с адресом, который уже использует
`snapshot.publish_and_cleanup` (`.artel/projects/<target>/workspace`)
— эта задача не вводит для того же target второй/иной путь клона.

AC-15. На песочнице с ДВУМЯ настоящими git-репозиториями (пульт +
целевой с локальным bare-origin) задача внешнего (не self) target
проходит `new → in_dev → review → merge_gate → done`: diff
ревью-пакета на входе в `review` не пуст и построен из клона
целевого; merge-коммит появляется в origin ЦЕЛЕВОГО (bare-репозиторий
песочницы); ни одного нового коммита не появляется в `main` пульта.

AC-16. На той же песочнице (AC-15) гейт ёмкости diff (`_capacity_gate_
refuses`) реально вычисляет размер diff клона целевого на переходе
`in_dev → review` — не пропускает переход безусловно, как до этой
задачи.

AC-17. Существующие тесты `tests/` остаются зелёными после изменений
этой задачи; новые тесты двух-репозиторной песочницы не пишут ни
байта в настоящий репозиторий пульта или произвольное дерево
разработчика (инвариант 01M1KVGD18P9H5WR7VM8TGPV1T соблюдён).

## Оценка объёма и деление
Сработавшие сигналы: число затрагиваемых модулей зоны (10 файлов
`orchestrator/*.py`, порог 5); бюджет (`budget_usd: 45` ≥ порога 30);
число критериев приёмки (17 ≥ порога 10).

Монолит принят Оператором 05.09.2026 (реестр 13 точек при пороге 15 из ТЗ,
сквозной прогон как единственная проверка полноты). Код стартует после
мержа зон частей 2–3 и группы процессов (fsm_advance.py, doctor.py).

Решение — монолит, не нарезка. Обоснование:

1. Само ТЗ («Рамка») задаёт явный порог для решения о вынесении
   отдельного этапа: «делить дальше — если реестр точек в SPEC
   превысит 15 строк, вынести merge/postmerge в отдельный этап».
   Реестр этой SPEC несёт 13 строк (точки 1–13 выше, «карта кодовой
   базы брифа» исключена в ТЗ-4) — меньше порога. Формального повода
   выносить merge/postmerge отдельным этапом нет.
2. Технически все точки реестра — проявления ОДНОГО примитива:
   «откуда читать/куда писать код и статус задачи для данного
   target». Их объединяет общий контекст (требование 1) — это не
   декоративная абстракция, а единственный источник истины, на
   который переключаются все остальные требования. Границы зон точек
   1–13 не разъезжаются по независимым модулям: `fsm.py`,
   `fsm_advance.py`, `fsm_merge_gate.py`, `ci.py`, `github_adapter.py`
   и `review.py` меняются РОВНО ради одного и того же параметра —
   контекста, передаваемого во все их git/gh-вызовы.
3. Частичное внедрение — например, свежесть/CI без merge — не
   мержимо с зелёной планкой: единственная проверка полноты флоу
   (требование 6, AC-15/AC-16) — это ЦЕЛЫЙ прогон `new → in_dev →
   review → merge_gate → done` на двух репозиториях; она структурно
   не проходит, пока в конвейере остаётся ХОТЯ БЫ ОДНА точка, ещё
   читающая/пишущая `config.ROOT` вместо контекста (несовпадение sha,
   несуществующая ветка на очередном шаге, диалог с чужим origin).
   Частичный этап оставил бы систему без единого способа подтвердить
   работоспособность целиком — то самое «промежуточное нерабочее
   состояние», которого нарезка обязана избегать
   (`skills/spec-authoring.md`).

## Не входит
- Клон целевого, его первичное создание (`target-init`) и ветка
  задачи внутри него — ТЗ-2. Эта задача готовит код читать/писать по
  адресу `.artel/projects/<target>/workspace`, но не создаёт клон;
  в тестах песочницы репозиторий-имитацию заводит тестовая фикстура,
  не механика `target-init`.
- `target-human`/`awaiting_human` (C1).
- Карта кодовой базы целевого при подключении и генерация карты в
  бриф из клона target'а (строка «Карта кодовой базы брифа» реестра
  докладной) — ТЗ-4; `brief.py` в зонах этой задачи нет.
- Контейнерный запуск роли (ТЗ-6, B3).
- Содержательные исполнители `no_paths`/`token_slot`/`project_skills`
  (замена источника списка защищённых путей с `config.PROTECTED_PATHS`
  на `targets.yaml.no_paths`, токен форджа роли, курируемые скилы) —
  ТЗ-4. Эта задача меняет только ГДЕ считается diff для подсветки
  (AC-8), не ПО КАКОМУ списку путей.
- Doctor-проверки клона/форджа целевого (наличие клона с origin, право
  push `refs/artifacts`, CI на `pull_request`, защита базовой ветки,
  напоминание триггера №24, токен в слоте) — ТЗ-5. Единственная точка
  doctor в зоне этой задачи — `check_branch_freshness` (AC-5).
- `new --target` в CLI — ТЗ-2/ТЗ-3.
- Заведение записи внешнего target (например, `sled`) в
  `targets.yaml` — защищённый путь, правит только Оператор отдельным
  MR.

## Материалы
- `docs/research/2026-09-04-external-target-readiness.md` — §2.2
  (механика), §4.3 класс Б (реестр точек), §5 ТЗ-1 (черновик), §6
  (порядок).
- `docs/adr/0003-target-projects.md` — п.4, п.6 (workspace — эфемерный
  клон целевого; merge в целевой — только оркестратор через адаптер).
- `docs/roadmap.md` §3 (блок B1b, Draft-MR-флоу), §4 п.2г (реестр
  регрессий, класс «локальная копия вместо источника истины»).
- `tasks/T094/acceptance_tests/_sandbox.py::ExternalTargetGitSandbox` —
  существующий приём двух настоящих git-репозиториев (пульт + bare-
  origin целевого) в песочнице; требование 6 ожидает его обобщение в
  `tests/sandbox.py`, не копирование заново.
- `orchestrator/fsm.py::_origin_main_source`/`_origin_main_sha` —
  уже смерженная (05.09) параметризация источника sha по target
  (01M1NBWPKNBXP9ZXXQDJM7AXPJ), на которую опирается требование 3.
