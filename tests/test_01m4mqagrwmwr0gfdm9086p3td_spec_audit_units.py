"""Аудит SPEC — свойства без прогона шагов: роль состояния spec_audit, модель аудитора под набором задачи, схема артефакта SPEC-AUDIT.md в guard, белый список каталога задачи, состояние spec_audit в перечнях пульта.

Группа: долгоживущий
Красен до реализации: ключа spec_audit в config.STATE_ROLE нет (step_role задачи в spec_audit — None), guard не знает тип spec_audit (годный SPEC-AUDIT.md отказан «неизвестный тип», правило раздела «Эскалация» к нему не применяется), SPEC-AUDIT.md вне TASK_ROOT_ALLOWED_MD, spec_audit нет в zone_lock/merge_after/report; зелены с рождения AC-6 (разрешение модели роли по ярусу и по составу набора — существующая цепочка models.resolve_task_role, роль spec_auditor задана фикстурой карты) и проверка, что SPEC-AUDIT2.md посторонний.

Окружение — фикстуры `tests/sandbox.py`: каталог моделей
(`use_catalog_fixture`, дополнен моделью `claude-opus-5-5` раздела
`claude`), карта исполнителей и локальный слой (`use_role_map`, роль
`spec_auditor` добавлена сценарием), файл решений `model_sets.yaml` — в
корне песочницы. Строки задач заводятся публичным `store.insert_task`,
guard проверяет текст артефакта публичным `guard.check_content`.
Идентификаторы задач, пути зон, метки текстов, модели и порядок вариантов
берутся из `random`; зерно печатается и входит в текст каждого провала.

Планка провалидирована временным стабом реализации (ключ `STATE_ROLE`, тип
`spec_audit` guard с полями и правилом «Эскалация», белый список, перечни
состояний): все методы зелёные; мутация «имя вне белого списка» красила
AC-11; стаб удалён, код не тронут.
"""
import json
import random
import re
import unittest

from orchestrator import (catalog, config, merge_after, models, report, runner,
                          store, zone_lock)
from scripts import guard
from tests.sandbox import (CATALOG_FIXTURE_TEXT, FIXTURE_CODEX_MODEL,
                           FIXTURE_OTHER_MODEL, FIXTURE_TIER,
                           FIXTURE_TIER_MODEL, InitializedTmpRootTest, capture)

AUDIT = "spec_audit"
AUDITOR = "spec_auditor"
AUDIT_FILE = "SPEC-AUDIT.md"
OPUS = "claude-opus-5-5"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
SECTIONS = ("ТЗ и SPEC", "Факты против кода", "Проверяемость критериев",
            "Зоны", "Матрица неослабления", "Пути обхода гейтов", "Вердикт")
FIELDS = ("verdict", "signals", "spec_sha")
MATRIX_TABLE = (
    "| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, "
    "проверка — файл:строка) | Остаётся ли свойство после изменения | Чем "
    "покрыто после (тест файл:строка) или «не покрыто» | Решение |\n"
    "|---|---|---|---|---|\n"
    "| Фикстура | Фикстура | Да | Фикстура | Фикстура |\n")

OPUS_BLOCK = f"""\
      {OPUS}:
        min_cli_version: 1.0.0
        status: supported
        list_price_usd_per_mtok:
          input: 5.0
          output: 25.0
          cache_write: 6.25
          cache_read: 0.50
        price_date: 2026-10-11
"""
_OTHER_ANCHOR = f"      {FIXTURE_OTHER_MODEL}:\n"
CATALOG_WITH_OPUS = CATALOG_FIXTURE_TEXT.replace(
    _OTHER_ANCHOR, OPUS_BLOCK + _OTHER_ANCHOR, 1)

AUDITOR_FIELDS = {"executor": "agent", "token_slot": "artel-spec-auditor",
                  "skills": ["conventions-core", "escalation-rules"],
                  "model_tier": FIXTURE_TIER}


def random_task_id(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def word(rng: random.Random, length: int = 8) -> str:
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(length))


def audit_text(task: str, rng: random.Random, *, drop_section: str = "",
               drop_field: str = "", fields: dict | None = None,
               status: str = "ready", escalation: str = "") -> str:
    values = {"verdict": rng.choice(["pass", "concerns", "fail"]),
              "signals": rng.choice(["нет", "а) «Меняемое поведение» непуст"]),
              "spec_sha": "".join(rng.choice("0123456789abcdef") for _ in range(40))}
    values.update(fields or {})
    meta = "".join(f"{key}: {value}\n" for key, value in values.items()
                   if key != drop_field)
    body = ""
    for name in SECTIONS:
        if name == drop_section:
            continue
        text = MATRIX_TABLE if name == "Матрица неослабления" else (
            f"Разбор {word(rng)} (SPEC.md:{rng.randrange(10, 99)}).")
        body += f"## {name}\n\n{text}\n\n"
    if escalation:
        body += ("## Эскалация\n\n"
                 f"- **Вопросы** — {escalation}\n"
                 "- **Контекст** — фикстура.\n"
                 "- **Блокирует** — вердикт аудита.\n")
    return (f"---\ntask: {task}\ntype: spec_audit\nauthor_role: {AUDITOR}\n"
            f"status: {status}\n{meta}---\n\n# SPEC-AUDIT: фикстура\n\n{body}")


class _Seeded(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"


class _SeededRoot(InitializedTmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def insert(self, state: str, zones: str = "", **kwargs) -> str:
        task = random_task_id(self.rng)
        store.insert_task(store.db(), task, f"Задача {word(self.rng)}", state,
                          f"task/{task.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD, **kwargs)
        if zones:
            store.update_task(store.db(), task, zones=zones)
        return task


# ---------------------------------------------------------------- AC-1

class AuditStateRoleTest(_SeededRoot):

    def test_ac1_state_role_and_step_role_of_spec_audit(self):
        """Состояние spec_audit резолвится в роль spec_auditor через STATE_ROLE.

        Сценарий: `config.STATE_ROLE["spec_audit"]` — `spec_auditor`;
        строка задачи в `spec_audit` (заведена `store.insert_task`) —
        `runner.step_role` возвращает `spec_auditor`.

        Ловит мутацию: ключ состояния не заведён или назван иначе
        (`spec_auditor` вместо `spec_audit`) — `KeyError`/`None`; роль
        резолвится особым случаем, а `STATE_ROLE` не дополнен — проверка
        словаря краснеет.
        """
        self.assertEqual(config.STATE_ROLE.get(AUDIT), AUDITOR,
                         self.msg(f"STATE_ROLE: {config.STATE_ROLE}"))
        task = self.insert(AUDIT)
        self.assertEqual(runner.step_role(store.get_task(store.db(), task)),
                         AUDITOR, self.msg(task))


# ---------------------------------------------------------------- AC-6

class AuditorModelTest(_SeededRoot):

    def setUp(self):
        super().setUp()
        self.use_catalog_fixture(CATALOG_WITH_OPUS)
        self.use_role_map(roles={AUDITOR: dict(AUDITOR_FIELDS)},
                          tiers={FIXTURE_TIER: OPUS},
                          allow_experimental=(FIXTURE_CODEX_MODEL,))

    def write_model_sets(self, pairs: dict) -> None:
        lines = ["sets:", "pairs:"]
        for role, model in pairs.items():
            lines += [f"  {role}:", f"    {model}:", "      date: 2026-10-11",
                      "      basis: решение Оператора", "      state: допущена"]
        lines.append("canary_templates:")
        models.model_sets_path().write_text("\n".join(lines) + "\n",
                                            encoding="utf-8")

    def task_on_set(self, members: dict):
        task = self.insert(AUDIT, model_set="codex-all",
                           model_set_members=json.dumps(members))
        return store.get_task(store.db(), task)

    def test_ac6_auditor_without_set_entry_resolves_by_tier_not_analyst(self):
        """Под набором codex-all без записи spec_auditor аудитор — модель яруса strong, а не модель аналитика набора.

        Сценарий: локальный слой фикстуры называет ярусу `strong` модель
        `claude-opus-5-5` (раздел `claude` каталога); задача на наборе
        `codex-all`, где аналитик — модель раздела `codex`, записи
        `spec_auditor` нет. `models.resolve_task_role("spec_auditor", задача)`
        — `claude-opus-5-5` провайдера `claude`; аналитик той же задачи —
        модель набора провайдера `codex` (контроль: набор действует).

        Ловит мутацию: аудитор наследует модель аналитика из набора задачи
        — модель `codex`; ярус аудитора задан не `strong` — модель
        другого яруса.
        """
        self.write_model_sets({"analyst": FIXTURE_CODEX_MODEL})
        row = self.task_on_set({"analyst": FIXTURE_CODEX_MODEL})
        auditor = models.resolve_task_role(AUDITOR, row).resolution
        analyst = models.resolve_task_role("analyst", row).resolution
        context = self.msg(f"аудитор: {auditor}; аналитик: {analyst}")
        self.assertEqual(analyst.provider, "codex", context)
        self.assertEqual(auditor.model, OPUS, context)
        self.assertEqual(auditor.provider, "claude", context)

    def test_ac6_auditor_set_entry_wins(self):
        """Запись spec_auditor в наборе задачи — модель этой записи.

        Сценарий: тот же набор, но в составе есть `spec_auditor` →
        другая модель каталога (случайно из моделей раздела `claude`,
        отличных от `claude-opus-5-5`), пара допущена в `model_sets.yaml`.
        `resolve_task_role("spec_auditor", задача)` — модель этой записи.

        Ловит мутацию: аудитор жёстко закреплён на модели яруса (запись
        набора игнорируется) — снова `claude-opus-5-5`.
        """
        chosen = self.rng.choice([FIXTURE_OTHER_MODEL, FIXTURE_TIER_MODEL])
        self.assertNotEqual(chosen, OPUS)
        self.write_model_sets({"analyst": FIXTURE_CODEX_MODEL, AUDITOR: chosen})
        row = self.task_on_set({"analyst": FIXTURE_CODEX_MODEL, AUDITOR: chosen})
        auditor = models.resolve_task_role(AUDITOR, row).resolution
        self.assertEqual(auditor.model, chosen, self.msg(f"аудитор: {auditor}"))


# ---------------------------------------------------------------- AC-10

class AuditSchemaTest(_Seeded):

    def label(self, task: str) -> str:
        return "/".join(("tasks", task, AUDIT_FILE))

    def check(self, task: str, text: str) -> list:
        return guard.check_content(self.label(task), text)

    def test_ac10_valid_audit_passes_and_each_defect_is_refused(self):
        """Годный SPEC-AUDIT.md валиден; без раздела, без поля, с чужим verdict или пустым signals — отказ.

        Сценарий: файл со всеми семью разделами, `verdict` из перечня,
        непустыми `signals` и `spec_sha` — `guard.check_content` без
        ошибок (на нескольких случайных вариантах). Затем по одному
        дефекту на вариант: снят каждый из разделов «ТЗ и SPEC» … «Вердикт»;
        снято каждое из полей `verdict`, `signals`, `spec_sha`; `verdict` —
        случайное слово вне `pass`/`concerns`/`fail`; `signals:` пуст.
        Каждый дефект даёт хотя бы одну ошибку.

        Ловит мутацию: в правиле типа `spec_audit` пропущен раздел
        (например «Пути обхода гейтов») — файл без него валиден; поле
        `spec_sha` не обязательно; перечень вердиктов не сверяется
        (`verdict: ok` валиден); пустой `signals` принимается за значение.
        """
        task = random_task_id(self.rng)
        for _ in range(3):
            text = audit_text(task, self.rng)
            self.assertEqual(self.check(task, text), [], self.msg(text))
        defects = [(f"нет раздела {name}", {"drop_section": name})
                   for name in SECTIONS]
        defects += [(f"нет поля {name}", {"drop_field": name}) for name in FIELDS]
        defects.append(("чужой verdict", {"fields": {"verdict": word(self.rng)}}))
        defects.append(("пустой signals", {"fields": {"signals": ""}}))
        self.rng.shuffle(defects)
        for case, kwargs in defects:
            with self.subTest(дефект=case):
                text = audit_text(task, self.rng, **kwargs)
                self.assertNotEqual(self.check(task, text), [],
                                    self.msg(f"{case}:\n{text}"))


# ---------------------------------------------------------------- AC-11

class TaskRootWhitelistTest(_Seeded):

    def test_ac11_spec_audit_is_not_extraneous_but_neighbours_are(self):
        """SPEC-AUDIT.md в каталоге задачи не посторонний; SPEC-AUDIT2.md и иные имена вне списка — посторонние.

        Сценарий: `guard.is_extraneous_task_root_file("SPEC-AUDIT.md")` —
        `False`; для `SPEC-AUDIT2.md` и случайных имён вида
        `SPEC-AUDIT-<слово>.md`, `<СЛОВО>.md` — `True`.

        Ловит мутацию: имя не внесено в белый список — первый вызов
        `True`; список расширен маской-префиксом (`SPEC-AUDIT.*`) —
        `SPEC-AUDIT2.md` перестаёт быть посторонним.
        """
        self.assertFalse(guard.is_extraneous_task_root_file(AUDIT_FILE))
        others = ["SPEC-AUDIT2.md", f"SPEC-AUDIT-{word(self.rng)}.md",
                  f"{word(self.rng).upper()}.md"]
        for name in others:
            with self.subTest(имя=name):
                self.assertTrue(guard.is_extraneous_task_root_file(name),
                                self.msg(name))


# ---------------------------------------------------------------- AC-18

class AuditEscalationSectionTest(_Seeded):

    def test_ac18_questions_with_ready_status_refused_by_guard(self):
        """SPEC-AUDIT.md с непустыми «Вопросы» раздела «Эскалация» при status ready — отказ guard этим правилом.

        Сценарий: годный файл с разделом «Эскалация» (Вопросы, Контекст,
        Блокирует) и `status: ready` — среди ошибок `guard.check_content`
        есть ошибка правила «эскалация текстом без статуса escalate»; тот
        же файл со `status: escalate` этой ошибки не несёт.

        Ловит мутацию: правило раздела «Эскалация» применяется только к
        типам plan/review/spec — у `spec_audit` ошибки правила нет; статус
        `escalate` не входит в перечень статусов типа — файл с ним отказан.
        """
        task = random_task_id(self.rng)
        question = f"Как понимать {word(self.rng)}?"
        label = "/".join(("tasks", task, AUDIT_FILE))
        ready = guard.check_content(label, audit_text(
            task, self.rng, escalation=question))
        context = self.msg(f"ошибки: {ready}")
        self.assertTrue(any(guard.ESCALATION_STATUS_REASON in e for e in ready),
                        context)
        escalate = guard.check_content(label, audit_text(
            task, self.rng, escalation=question, status="escalate"))
        self.assertEqual(escalate, [], self.msg(f"status escalate: {escalate}"))


# ---------------------------------------------------------------- AC-22

class AuditStateListsTest(_SeededRoot):

    def test_ac22_audit_task_in_zone_forecast_and_status_suffix(self):
        """Задача в spec_audit с зоной, пересекающей чужую, видна в прогнозе зон и получает «зона занята» в status.

        Сценарий: задача в `in_dev` и задача в `spec_audit` со случайной
        общей зоной `orchestrator/<слово>.py`. `zone_lock.forecast_overlaps`
        по этой зоне называет задачу аудита с её состоянием; строка задачи
        аудита в `catalog.cmd_status` несёт «[зона занята: <id задачи in_dev>]».

        Ловит мутацию: `spec_audit` не дописан в `zone_lock.LATER_STATES`
        (а значит и в прогноз) — прогноз задачу не видит, добавки в строке
        нет.
        """
        zone = f"orchestrator/z_{word(self.rng)}.py"
        holder = self.insert("in_dev", zone)
        waiter = self.insert(AUDIT, zone)
        overlaps = zone_lock.forecast_overlaps(store.db(), {zone})
        context = self.msg(f"прогноз: {overlaps}")
        self.assertIn((zone, waiter, AUDIT), overlaps, context)
        lines = [line for line in capture(catalog.cmd_status).splitlines()
                 if line.startswith(waiter)]
        self.assertEqual(len(lines), 1, self.msg(f"status: {lines}"))
        self.assertIn(f"[зона занята: {holder}]", lines[0], self.msg(lines[0]))

    def test_ac22_audit_state_in_merge_after_and_report_lists(self):
        """spec_audit входит в merge_after.STATUS_DECLARED_STATES и в перечень состояний отчёта.

        Сценарий: `"spec_audit" in merge_after.STATUS_DECLARED_STATES` и
        `"spec_audit" in report.STATE_ORDER`.

        Ловит мутацию: состояние не дописано в один из перечней — `status`
        не показывает объявленные зависимости мержа задачи на аудите, борд
        отчёта уводит колонку в хвост неизвестных.
        """
        self.assertIn(AUDIT, merge_after.STATUS_DECLARED_STATES)
        self.assertIn(AUDIT, report.STATE_ORDER)


if __name__ == "__main__":
    unittest.main()
