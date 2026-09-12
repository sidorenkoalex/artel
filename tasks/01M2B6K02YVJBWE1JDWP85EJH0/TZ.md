---
task: 01M2B6K02YVJBWE1JDWP85EJH0
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Канарейка на целевом sha: pin-update без зависимости от кода пина

Источник: бэклог docs/backlog.md, строка П2 «Канарейка гоняется на целевом
sha, а не на пине» (cd9a477b) и копилка П2 12.09 «Разовый сдвиг пина в
обход гейта канарейки» (ADR-0013, исключение 12.09). Решение Оператора
12.09: волна 4, после мержа 01M2ARQD7C (зона canary.py свободна).

Факты:
- `canary` берёт `main_sha = gitcmd.head_sha()` (orchestrator/canary.py:
  ~1087) — код ГЛАВНОЙ КОПИИ, то есть пина, и клонирует его
  (`_ephemeral_clone`, ~478–521: `git clone` outer_root в эфемерный
  каталог + bare --shared); прогон пишется в `canary_runs` с этим
  `main_sha`.
- `pin.cmd_pin_update(sha)` (orchestrator/pin.py:37–50) требует зелёный
  прогон не старше `CANARY_MAX_MERGES_SINCE_GREEN = 10` мержей на истории
  целевого sha (`canary.merges_since_last_green_run`, ~850–870).
- Взаимная блокировка 12.09: дефект канарейки (чтение SPEC, 01M2A22CG2)
  исправлен в origin/main, прогон на пине 699fa124 оставался красным,
  пин не двигался; сдвиг сделан вручную в обход ADR-0013 с записью
  исключения. Тот же тупик повторится с правкой 01M2ARQD7C (повтор
  developer в цикле канарейки, в main с 12.09): она заработает только на
  прогоне кода, где она есть.
- `doctor` сверяет триггер канарейки (`doctor.check_canary_trigger`)
  тем же источником sha.

Требуется:
1. `canary --k <N> [--sha <sha>]`: прогон клонирует и тестирует КОД
   целевого sha; по умолчанию целевой sha — голова `origin/<MAIN_BRANCH>`
   (через примитив без FETCH_HEAD, `gitcmd.fetch_ref_sha`, задача
   01M2ARQGY5), не HEAD главной копии; `main_sha` в `canary_runs` = целевой
   sha. Эфемерный клон делает checkout целевого sha (объекты берутся из
   главной копии после fetch), пул и изоляция — как сегодня.
2. `pin-update <sha>` ищет зелёный прогон на истории именно `<sha>`
   (арифметика возраста не меняется, меняется только то, что прогон на
   целевом sha теперь возможен до сдвига пина); отказ называет, на каком
   sha прогона нет и какой командой его сделать (`artel.py canary --k 1
   --sha <sha>`).
3. `doctor.check_canary_trigger` — тот же источник целевого sha
   (origin/<main>), не HEAD главной копии; текст проверки называет sha.
4. Отчёт прогона (строка «шагов=… исход=…» и заголовок) несёт целевой
   sha и пометку «код пина»/«код origin/main»/«код <sha>».
5. Тесты (tests/test_canary.py, tests/test_pin.py, tests/test_doctor_*.py
   по образцу существующих): (а) прогон с `--sha`, отличным от HEAD
   главной копии, пишет в `canary_runs` целевой sha, клон стоит на нём
   (мутация «клон на HEAD» — красный); (б) `pin-update` принимает зелёный
   прогон на целевом sha при красном/отсутствующем на пине; (в) отказ
   `pin-update` называет sha без прогона и команду; (г) по умолчанию
   целевой sha = origin/<main> (стенд с bare origin); (д) существующие
   тесты канарейки, пина и doctor — без ослабления.

Зоны: orchestrator/canary.py, orchestrator/pin.py, orchestrator/doctor/,
tests/.

Приложением: docs/adr/0013-emergency-mode-and-pin-rollback.md (гейт
пина и исключение 12.09 — защищённый путь; если ADR требует правки
формулировки «прогон на пине» -> «прогон на целевом sha», unified diff
приложением к PLAN), orchestrator/gitcmd.py (`fetch_ref_sha`,
`head_sha`), docs/backlog.md (строки cd9a477b и П2 12.09).

Не входит: изменение `CANARY_MAX_MERGES_SINCE_GREEN`; правка gitcmd.py;
сам сдвиг пина; правка docs/adr напрямую.

Рамка: $35.
