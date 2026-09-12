---
task: 01M2B6K02YVJBWE1JDWP85EJH0
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Канарейка на целевом sha — pin-update без зависимости от кода пина

## Подход

Источник целевого sha прогона канарейки меняется в одном месте
(`canary.py`), а `pin.py`/`doctor/canary_pool.py` подхватывают его
через уже существующий примитив `gitcmd.fetch_ref_sha`/
`fetch_origin_main_sha` — атомарная смена семантики, как и требует
секция «Деление» SPEC (монолит, не резать).

- `canary._resolve_target_sha(explicit_sha)` — новая маршрутизация: явный
  `--sha` возвращается как есть, БЕЗ обращения к `origin` (AC-2); без
  `--sha` — голова `origin/<config.MAIN_BRANCH>` через
  `gitcmd.fetch_ref_sha("origin", config.MAIN_BRANCH)` (AC-1). Отказ
  самого `fetch` (нет `origin` вовсе, сеть недоступна) — деградация на
  `gitcmd.head_sha()` главной копии, тем же приёмом, что и
  `doctor.check_root_pin`/`check_pin_unpushed`: без этого стенд без
  единого `origin` (локальная планка ДРУГОЙ, уже смерженной задачи —
  `tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/`, которая гоняла
  `canary` до этой задачи вовсе без `origin`) потерял бы возможность
  прогнать канарейку целиком, хотя ни один критерий приёмки ЭТОЙ задачи
  такой стенд не описывает.
- `canary._ephemeral_clone(target_sha)` — checkout целевого sha ПОСЛЕ
  обычного `git clone` (`git checkout -q -B <MAIN_BRANCH> <target_sha>`),
  до создания origin-заглушки клона (чтобы она тоже несла
  `MAIN_BRANCH` на `target_sha`). Локальный клон копирует/хардлинкает
  каталог `objects/` целиком, поэтому только что подтянутый (и потом
  обезличенный, приватная ссылка удалена) объект `target_sha`
  добирается до клона даже будучи недостижимым ни с одной ветки
  `outer_root` — проверено эмпирически прогоном `tasks/
  01M2B6K02YVJBWE1JDWP85EJH0/acceptance_tests/` (AC-3/AC-4).
- `canary._run_one_task` пишет `main_sha = target_sha` (не
  `gitcmd.head_sha()`, снятый после выхода из клона) и печатает пометку
  происхождения (`_sha_label`) в заголовке и итоговой строке (AC-8).
- `pin.cmd_pin_update` уже искал зелёный прогон на истории переданного
  `sha`, не `gitcmd.head_sha()` пина (сам гейт не менялся) — правка
  только в тексте отказа: команда получения прогона теперь несёт
  `--sha <sha>` (AC-6).
- `doctor.check_canary_trigger` переведён на тот же источник
  (`doctor.fetch_origin_main_sha()`, уже существующий примитив
  `orchestrator/doctor/root_pin.py`) вместо `gitcmd.head_sha()`; текст
  проверки называет sha, текст АЛЕРТА (участвующий в дедупе) остаётся
  фиксированным, чтобы не сломать дедуп по `(kind, source, message)`
  (регресс класса R1-F2, `tasks/01M1NGFK3N6MRMYGCC09H975V3/REVIEW.md`).
- `artel.py`: флаг `--sha` разбирается новой `_sha_arg`, передаётся в
  `canary.cmd_canary` наравне с `--k`.

**Обратная совместимость с чужими залоченными планками.** Две planки
ДРУГИХ, уже смерженных задач зовут внутренние функции `canary.py`
напрямую со старой сигнатурой:
`tasks/01M1SC3Y20YBTTJVQDJBF2NDQW/acceptance_tests/
test_canary_report_kill_reason.py` зовёт `_run_one_task(template,
run_stamp, ratio)` (3 позиционных аргумента) и
`tasks/01M2ARQD7C472KZACB3SZXGF1N/acceptance_tests/
test_canary_dev_retry.py` мокает саму `_ephemeral_clone` нульарной
функцией. Правка их планки требует отдельного мандата Оператора,
которого эта задача не получала (тот же принцип, что уже задокументирован
у `_kill_at_verifying`). Поэтому `target_sha`/`sha_label` —
необязательные параметры `_run_one_task` (`None` — прежнее поведение
байт-в-байт: целевой sha снимается уже ПОСЛЕ выхода из клона тем же
`gitcmd.head_sha()`, что и раньше), а вызов `_ephemeral_clone` внутри
`_run_one_task` сохраняет прежнюю АРНОСТЬ (ноль аргументов), когда
`target_sha` не передан явно — иначе моки, ожидающие ровно старую
сигнатуру, падают `TypeError` независимо от значения аргумента.
`cmd_canary` (единственный боевой вызывающий) всегда передаёт оба
параметра явно, так что реальное поведение (SPEC AC-1..AC-8) от этой
совместимости не страдает.

## Шаги

1. `orchestrator/canary.py`: `_resolve_target_sha`, `_sha_label`,
   checkout в `_ephemeral_clone`, `main_sha`/отчёт в `_run_one_task`,
   `cmd_canary(*, k, sha=None)`.
2. `orchestrator/pin.py`: текст отказа `cmd_pin_update` несёт
   `--sha <sha>`.
3. `orchestrator/doctor/canary_pool.py`: `check_canary_trigger` —
   источник sha `doctor.fetch_origin_main_sha()`, текст называет sha.
4. `orchestrator/artel.py`: `_sha_arg`, wiring в `_cmd_canary`, usage-
   строки.
5. Тесты: `tests/test_canary.py` (`ResolveTargetShaTest`, `ShaLabelTest`,
   checkout-мутация `_ephemeral_clone`, обновлённые вызовы старой
   сигнатуры), `tests/test_pin.py` (`PinUpdateRefusalMessageTest`),
   `tests/test_doctor.py` (`CanaryTriggerCheckTest` — реальный `origin`),
   `tests/test_new_argv_parsing.py` (`--sha` в `_cmd_canary`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 4 |
| 2 | 2 |
| 3 | 3 |
| 4 | 1 |
| 5 | 1, 2, 3 (планка не ослаблена) |

## Влияние на систему

- `doctor.check_canary_trigger` теперь делает `git fetch` (через
  `fetch_origin_main_sha`) вместо чисто локального чтения — тот же
  сетевой профиль, что уже несёт соседний `check_pin_unpushed`
  (деградация до `warn` на недоступном `origin`, не `fail`); инвариант
  35 («тесты не читают сеть по DNS-имени») не затронут — он про тесты,
  не про поведение doctor в проде, и локальные bare-origin в песочницах
  под инвариант не подпадают.
  `tests/test_doctor.py::CanaryTriggerCheckTest` переведён на реальный
  bare `origin` (`add_synced_origin`), иначе новый источник sha не с чем
  сверять.
- `pin.cmd_pin_update`'s гейт (арифметика возраста) не менялся — только
  текст отказа; `tests/test_pin.py` полностью зелёный без правок, кроме
  добавленного теста.
- Обратная совместимость с чужими залоченными планками — см. «Подход»;
  проверено прогоном обеих (`tasks/01M1SC3Y20YBTTJVQDJBF2NDQW`,
  `tasks/01M2ARQD7C472KZACB3SZXGF1N`) и полного набора `tasks/
  01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/` (canary v2, без единого
  `origin` в стенде — деградация `_resolve_target_sha` покрывает именно
  этот случай).
- Откат: правки локальны к `canary.py`/`pin.py`/`doctor/canary_pool.py`/
  `artel.py` и их тестам; `git revert` коммита задачи достаточно.

**ADR-0013 («Не входит» SPEC).** Формулировка «канарейка тестирует код
пина» в разделе «Исключение 12.09.2026» — часть исторического
нарратива конкретного инцидента (что БЫЛО в момент инцидента), не общее
описание механики канарейки нигде больше в файле; правки не требует —
diff не приложен.

## Риски

- Локальный `git clone` полагается на файловую копию/хардлинк каталога
  `objects/` целиком (эмпирически подтверждено прогоном приёмочных
  тестов на этой машине) — задокументировано в докстринге
  `_ephemeral_clone`; если когда-нибудь git сменит эту оптимизацию на
  выборочную (как у сетевого fetch), checkout недостижимого с веток
  `outer_root` `target_sha` перестанет находить объект. Из «Не входит»
  SPEC правка `gitcmd.py` — вне объёма; если это когда-нибудь
  проявится, чинить явным `git fetch outer_root <target_sha>` в клон
  ДО checkout.

## Предложения системе

- `orchestrator/doctor/canary_pool.py::check_canary_trigger` не роняет
  название источника sha в самом коде AC-описания SPEC-соседних задач —
  найдено дважды за эту задачу (сначала эта функция, потом
  `pin.cmd_pin_update`), что источник sha гейта/триггера дублируется в
  двух модулях без общего примитива именования; `fetch_origin_main_sha`
  уже общий, но сам факт «канарейка по умолчанию берёт этот же источник»
  нигде не зафиксирован одним местом кроме этого PLAN — стоит вынести в
  комментарий `gitcmd.fetch_ref_sha` ссылку на всех трёх потребителей.
