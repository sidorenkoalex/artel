---
task: 01M1NEEWH5K1XPFRDGRMPYSBXJ
type: plan
author_role: developer
status: draft
schema_version: 3
---

# PLAN: Канарейка v2 (часть 1): пул вне корня, эфемерный клон, метрики, изоляция пула от ролей

## Подход

Переработка `orchestrator/canary.py` (v1, tasks/T065) под v2: вместо
прогона фиксированного каталога ТЗ прямо в `config.ROOT` пульта — пул
шаблонов вне корня (`~/.artel-canary`), случайная выборка `k` из `N`,
и полный цикл КАЖДОЙ выбранной задачи в отдельном эфемерном клоне
пульта (`git clone` во временный каталог + origin-заглушка), а не в
главном рабочем дереве. Это закрывает дыру v1 (RETRO/ветки/алерты
убитых канареек текли в main) структурно: пока код внутри клона, весь
FSM-конвейер (`catalog`/`store`/`fsm`/`auto`/`cleanup`/`artifact_branch`)
читает пути через модульные атрибуты `orchestrator/config.py`
(`ROOT`/`DB`/`TASKS`/`LOGS`/...) — тот же приём, которым уже пользуется
вся существующая тестовая песочница пульта (`mock.patch.object(config,
attr, value)`, `tests/sandbox.py::TmpRootTest`), только не через
`unittest.mock` (это исполняемый код, не тест), а вручную:
`_ephemeral_clone()` — контекстный менеджер, который перед входом
сохраняет текущие атрибуты `config`, переставляет их на пути под
свежесозданным `tempfile.mkdtemp()`-клоном, а по выходу (включая
исключение) восстанавливает их и удаляет каталог клона `shutil.rmtree`.
Пересчёт путей — универсальный (`dest / saved[attr].relative_to(outer_root)`),
потому что каждый из этих атрибутов в `config.py` определён буквально
как `ROOT / <подпуть>` — не нужно перечислять подпути дважды.

Origin эфемерного клона — явная заглушка (`git remote set-url origin
canary-stub://ephemeral-clone-no-real-remote`), не то, что `git clone`
подставил бы сам (локальный путь к `config.ROOT`, который был бы
формально «не http(s)», но остаётся РЕАЛЬНО дотягивающимся до главного
пульта): `artifact_branch.push()` (best-effort, требование 7 T094)
иначе смог бы реально запушить `refs/heads/artifact/<id>` канареечной
задачи в главный пульт — ровно то, что запрещает AC-3. Заглушка гарантирует,
что push молча проваливается (`git` не резолвит фейковую схему), как и
задумано best-effort кодом.

Метрики прогона — БД пульта СНАРУЖИ клона, отдельными таблицами
(`canary_runs`, `canary_baseline`), а не `.artel/canary/*.json` (v1):
per-task бейзлайн (требование 9), а не сумма по набору — таблица
`canary_baseline` ключуется `title` (стабильное имя шаблона между
прогонами, не одноразовый ULID задачи). SQL — только в `store.py`
(ADR-0003 3ж), новые функции `insert_canary_run`/`canary_baseline`/
`set_canary_baseline` рядом с остальными по тому же идиому (SCHEMA +
блок в `migrate()`), не отдельная функция создания схемы в `canary.py`.

Стдаут-«отчёт прогона» (AC-8/AC-9/AC-12 — «расхождение отражается в
отчёте», «отклонение... поднимает алерт») печатается ПОСЛЕ вывода
создания/вождения задачи ПОДАВЛЕННЫМ (`contextlib.redirect_stdout`
вокруг `catalog.cmd_new`+`_drive_task`, сброс в никуда): без подавления
между строкой создания задачи (`catalog.cmd_new` печатает её первой) и
итоговой сводкой с меткой расхождения/отклонения ложится десяток строк
`store.set_state`/`cleanup.cmd_kill` — сотни символов шума, а планка
(`test_ac8_.../test_ac9_...`) ищет слово расхождения/отклонения строго
в окне ±200 символов вокруг ПЕРВОГО вхождения `task_id` в вывод. Двумя
короткими строками на задачу («заведена» + одна сводная с метриками и,
если есть, меткой) это окно гарантированно закрывает обе строки.

Эскалация (AC-6) — тем же приёмом, что и `spec_gate`/`acceptance` в
самой canary (module docstring v1: «эта команда проходит гейт САМА,
отдельным кодовым путём, не через `fsm.cmd_approve`»): синтетический
ответ коммитится `answer.cmd_answer` (не требует sha/фиксации), а сам
возврат из `escalated` — прямая копия ветки `elif state == "escalated"`
`fsm._cmd_approve` (читает `answer_baseline`/`escalated_from`, пишет
`store.set_state` на `back`), а не вызов `fsm.cmd_approve` — тот на
`escalated` требует sha (`APPROVE_NEEDS_SHA`), которого при первом
вызове ещё нет, и печатает «повтори с sha» вместо перехода.

Изоляция пула от ролей (требование 13) — новый check `doctor.
check_role_log_pool_leak` (13б/AC-15, читает `config.LOGS/*.log` на
упоминание `config.CANARY_POOL_DIRNAME`, поднимает `kind=incident`),
новый `docs/reference/role-home/claude/settings.json` (13а/AC-14,
`permissions.deny` — Read под каталогом пула + Bash `git clone`/
`gh repo clone`/`git remote add`, развёрнутый `_deploy_role_home_reference`
как есть) и best-effort `doctor.check_token_repo_scope` (13в/AC-16, `gh
api user/repos` по токену каждой agent-роли, warn при >1 репозитории —
без сети/`gh` тихо `skip`, не блокирует doctor). Текстовое напоминание
13г («CLAUDE.md курируемого слоя») — правка `docs/reference/role-home/
claude/CLAUDE.md` (не защищённый путь). Вторая половина 13г
(`skills/conventions-core.md`) и CI-джоб утечки GUID (требование 7/AC-7,
`.github/workflows/ci.yml`) — оба пути защищены (`skills/`/`.github/`,
`skills/conventions-core.md`: «эти пути меняет только Оператор отдельным
MR») — готовятся unified-диффами приложением к этому PLAN (см. «Влияние
на систему»), не правятся в этой ветке напрямую.

## Шаги

1. `orchestrator/store.py` — таблицы `canary_runs`/`canary_baseline`
   (SCHEMA + `migrate()`), функции `insert_canary_run`/`canary_baseline`/
   `set_canary_baseline`.
2. `orchestrator/config.py` — константа `CANARY_POOL_DIRNAME`.
3. `orchestrator/canary.py` — полная переработка v1 → v2: пул/`--k`,
   `_ephemeral_clone`, эскалация синтетическим ответом, per-task
   метрики/бейзлайн/отклонение, маркер «ожидается эскалация» (AC-8).
4. `orchestrator/artel.py` — CLI `canary --k <N>` вместо `canary
   <каталог> [--rewrite-baseline]`; обновление докстринга команд.
5. `orchestrator/doctor.py` — `check_role_log_pool_leak` (AC-15),
   `check_token_repo_scope` (AC-16, best-effort), включение в
   `all_checks`.
6. `docs/reference/role-home/claude/settings.json` (новый) — правила
   `permissions.deny` (AC-14).
7. `docs/reference/role-home/claude/CLAUDE.md` — текстовое напоминание
   13г (половина 1).
8. Юнит-тесты: переработка `tests/test_canary.py` под v2 (сигнатура
   `cmd_canary(k=...)` вместо `cmd_canary(tz_dir, rewrite_baseline=...)`,
   новые чистые функции); новые тесты `doctor.check_role_log_pool_leak`/
   `check_token_repo_scope`.
9. Защищённые пути (приложение к этому PLAN, Оператору): unified-дифф
   `skills/conventions-core.md` (13г половина 2) и unified-дифф
   `.github/workflows/ci.yml` (новый джоб `canary-guid-leak`, AC-7) —
   оба провалидированы `git apply --check` на чистом дереве.
10. `python3 scripts/codebase_map.py` (правка `.py` в orchestrator/) +
    `scripts/guard.py` по артефактам задачи + полный `tests/` прогон
    (AC-13).

## Покрытие требований

| Требование (SPEC) | Шаг |
|---|---|
| 1 (пул вне корня, k из N) | 2, 3 |
| 2 (эфемерный клон: каталог/БД/origin-заглушка) | 3 |
| 3 (ноль следов в main) | 3 |
| 4 (клон удаляется по завершении) | 3 |
| 5 (метрики — БД пульта, отдельная таблица) | 1, 3 |
| 6 (эскалация — синтетический ANSWER) | 3 |
| 7 (canary-GUID + CI-джоб утечки) | 9 |
| 8 (маркер «ожидается эскалация» vs факт) | 3 |
| 9 (per-task бейзлайн) | 1, 3 |
| 10 (первый прогон = бейзлайн К3) | — (ручная фиксация Оператором после реального прогона реального пула, «Не входит»/AC-10 manual) |
| 11 (verifying не дожидается CI) | 3 (не тронуто — сохранено из v1) |
| 12 (отклонение — только алерт) | 1, 3 |
| 13а (запрещающие правила CLI на пул) | 6 |
| 13б (аудит логов ролей → incident) | 5 |
| 13в (doctor: токен виден в >1 репо) | 5 |
| 13г (текстовое напоминание) | 7, 9 |

## Влияние на систему

Затронуты: `orchestrator/canary.py` (полная переработка сигнатуры и
поведения — только сама команда `canary`, других вызывателей модуля в
кодовой базе нет), `orchestrator/store.py` (новые таблицы — добавление,
существующие не меняются), `orchestrator/artel.py` (CLI-контракт
`canary` меняется: `<каталог-ТЗ> [--rewrite-baseline]` → `--k <N>`,
breaking change для v1-вызова — оправдан требованием 1 SPEC v2, других
мест кодовой базы, зовущих `cmd_canary` со старой сигнатурой, нет,
проверено `grep -rn "cmd_canary" --include=*.py .`), `orchestrator/
doctor.py` (два новых best-effort check'а, добавлены в `all_checks`
аддитивно — существующие checks не тронуты).

Инварианты/гейты рядом: инвариант 18 («`auto` не проходит гейты») не
затронут — `_pass_spec_gate`/`_pass_acceptance_gate`/эскалационный
обход по-прежнему отдельный кодовый путь только для задач, заведённых
самой `canary`, как и в v1. `verifying`/`merge_gate` обход (требование
11, AC-11) — код `_kill_at_verifying`/`_kill_at_merge_gate` перенесён
из v1 без изменений. Принцип целостности: НИ один существующий тест/
гейт/лимит не ослабляется — `permissions.deny` в новом `settings.json`
только ДОБАВЛЯЕТ ограничения роли, `doctor.check_role_log_pool_leak`/
`check_token_repo_scope` — новые аддитивные check'и (существующие не
правятся).

CI-джоб утечки GUID (шаг 9) устроен тем же приёмом, что и существующий
`id-format-greplint`: смотрит только НОВЫЕ строки дифа PR (`git diff
$BASE...HEAD -- 'skills/*' 'templates/*' 'docs/*' | grep '^\+' | grep
-i 'canary-guid:'`) — сама метка `canary-guid:` не существует нигде в
затронутых этой задачей файлах (документируется только в модульном
докстринге `orchestrator/canary.py`, вне сканируемых джобом путей), так
что джоб не самосрабатывает на собственном добавлении. Правка `skills/
conventions-core.md` — одна строка «Никогда: ...» в уже существующем
формате секции `## Git` (см. диф ниже), без удаления/ослабления
существующих правил.

Откат: `git revert` коммита(ов) этой задачи в её ветке — новые таблицы
БД (`canary_runs`/`canary_baseline`) остаются в схеме как неиспользуемые
(тот же прецедент, что и остальные таблицы `store.py` — миграции этой
кодовой базы никогда не удаляют колонки/таблицы, только добавляют).
Оба защищённых диффа (шаг 9) откатывает Оператор тем же MR, если решит
не применять.

### Защищённые пути — дифф-приложения (для Оператора, `git apply --check` пройден)

**`skills/conventions-core.md`** (13г половина 2 — одна строка в
существующем формате секции `## Git`, между уже существующей строкой
«Никогда: ослабление...» и следующим абзацем «## Стиль коммуникации»):

```diff
--- a/skills/conventions-core.md
+++ b/skills/conventions-core.md
@@ -46,6 +46,10 @@
   `gates.yaml` / `roles.yaml` / `.github/` / `templates/` / `skills/`
   (эти пути меняет только Оператор отдельным MR).
 - Никогда: ослабление или удаление существующих тестов, гейтов, лимитов,
   guard-проверок и инвариантов — только Оператор через ADR в docs/adr/
   (принцип целостности, ADR-0002). Если твоя задача требует такого
   изменения — эскалируй с обоснованием, решение примет Оператор.
+- Никогда: чтение путей под каталогом пула канарейки (`~/.artel-canary`),
+  команды `git clone`/`gh repo clone`/`git remote add` на репозиторий
+  пула — курируемый слой роли отказывает в этом на уровне CLI
+  (`.artel/home/.claude/settings.json`, SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ,
+  требование 13); это напоминание текстом, не замена того отказа.

 ## Стиль коммуникации
```

**`.github/workflows/ci.yml`** (требование 7/AC-7 — новый джоб между
`id-format-greplint` и `python`, тот же приём: diff только новых строк
PR, только `pull_request`):

```diff
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -57,6 +57,29 @@
             exit 1
           fi

+  canary-guid-leak:
+    name: Линт — GUID канареечного пула не протекает в промпты ролей
+    if: github.event_name == 'pull_request'
+    runs-on: ubuntu-latest
+    steps:
+      - uses: actions/checkout@v4
+        with: { fetch-depth: 0 }
+      - name: diff не добавляет отметку canary-guid в skills/, templates/, docs/
+        env:
+          BASE_SHA: ${{ github.event.pull_request.base.sha }}
+        run: |
+          # SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 7/AC-7: каждый
+          # шаблон пула несёт машиночитаемую метку `canary-guid:` (см.
+          # orchestrator/canary.py, модульный докстринг) — сама метка НЕ
+          # существует нигде в коде пульта (пул живёт вне git), так что
+          # её появление в skills/, templates/ или docs/ пульта
+          # однозначно означает утечку контекста роли в пул (требование
+          # 13). Список конкретных GUID не нужен — паттерн общий.
+          ADDED=$(git diff "$BASE_SHA"...HEAD -- 'skills/*' 'templates/*' 'docs/*' \
+            | grep -E '^\+' | grep -Ev '^\+\+\+' | grep -Ei 'canary-guid:' || true)
+          if [ -n "$ADDED" ]; then
+            echo "::error::диф добавляет отметку canary-guid в skills/, templates/ или docs/ — утечка пула канарейки (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 7):"
+            echo "$ADDED"
+            exit 1
+          fi
+
   python:
     name: Синтаксис и тесты оркестратора
     runs-on: ubuntu-latest
```

`git apply --check` подтверждение — оба файла проверены на чистом
дереве `main` перед сдачей (команда и результат — см. коммит этой
задачи).

## Риски

- Реальный `git clone` эфемерного клона на большом `config.ROOT`
  (полная история) — ощутимое время/диск на боевом прогоне; вне
  объёма этой задачи чинить (`--depth`/alternates), SPEC не требует
  быстроты, только изоляцию. Если станет узким местом — отдельная
  задача.
- `doctor.check_token_repo_scope` (AC-16) — единственный источник
  истины (реальный охват PAT на GitHub) недетерминирован и недоступен
  offline (см. `markers.py`, AC-16) — реализация best-effort, Оператор
  проверяет оба исхода на приёмке вручную.

## Предложения системе
