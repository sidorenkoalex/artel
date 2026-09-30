---
task: 01M3SK48D7RDQPSEN78894GDA5
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Канарейка не меняет боевой дом codex пульта

# ТЗ: Канарейка не меняет боевой дом codex пульта

Источник: решение Оператора 30.09.2026; строка копилки 30.09 (П2) «Канарейка
меняет боевой дом codex пульта»; ADR-0021 (пульт неизменен во время
работы).

Факты (пин 34b298c7, main bd538307):
- `orchestrator/canary.py` (блок эфемерного клона, около стр. 1100) для
  ролей на codex ставит процессу клона дом codex ПУЛЬТА:
  `codex_provider.set_codex_home_override(saved["ROLE_HOME"] /
  DEPLOYED_HOME_DIR)`, и `--codex-home` уходит в `canary_drive`. Вход в
  ChatGPT при этом берётся из связки ключей через указатель
  (`_install_codex_pointer`), учётные данные в клон не копируются.
- codex каждого шага роли в клоне дописывает в
  `.artel/home/.codex/config.toml` пульта запись
  `[projects."<временный клон>"] trust_level = "trusted"`. К 30.09 их 44 и
  более; `doctor` — WARN `codex-role-home` «развёрнутый слой отличается
  от референса: config.toml» (референс —
  `docs/reference/role-home/codex/config.toml`).
- Прогон канарейки меняет файл боевого окружения пульта, которым
  пользуются настоящие задачи.

Требуется:
1. Прогон канарейки не меняет ни одного файла в `.artel/home/.codex/`
   пульта. Способ выбирает SPEC по коду провайдера codex
   (`orchestrator/providers/codex.py`): отдельный дом codex клона, в
   который переносится только то, что нужно шагу (без учётных данных —
   вход по-прежнему через указатель связки ключей; копирование файлов
   входа запрещено: обновление токена в копии рассогласует его с
   пультом), либо запуск codex с доверием каталога, заданным при запуске,
   а не записью в `config.toml`. Если ни один способ не годится без
   ослабления изоляции — эскалация, а не обход.
2. Настоящие задачи (не канарейка) запускают codex как прежде; поведение
   их дома не меняется.
3. `doctor` по-прежнему сверяет дом с референсом; записи, уже
   накопленные канарейкой, эта задача не чистит (чистка — решение
   Оператора после мержа).
4. Тесты в `tests/`: прогон канарейки с ролью на codex (подменённый
   запуск codex, дописывающий доверие в `config.toml` своего дома)
   оставляет `config.toml` дома пульта байт в байт прежним («Ловит
   мутацию: клон получает дом codex пульта»); вход клона по-прежнему
   проверяется и отказывает без указателя; настоящая задача пишет в свой
   дом как прежде.

Зоны: orchestrator/canary.py, orchestrator/canary_drive.py, orchestrator/providers/codex.py, tests/.

Только чтение (не менять): orchestrator/providers/base.py,
orchestrator/providers/claude.py, orchestrator/runner.py,
orchestrator/config.py, orchestrator/doctor/, docs/reference/,
orchestrator/pin.py, orchestrator/fsm_merge_gate.py, scripts/guard.py,
skills/, templates/, docs/adr/, docs/invariants.md,
tests/test_invariants.py, docs/backlog.md, tasks/, .artel/home/.codex/, .artel/home/.codex/config.toml (боевой дом пульта: задача его не пишет).

Не входит: чистка накопленных записей в доме пульта; изменение
референса дома; дом Claude.

Рамка: $25.
