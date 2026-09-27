"""Юнит-тесты `orchestrator.catalog.spawn_subtask`
(01M1SHJZCE0Y4DXAAWQ2W585A7, требования 1-2) — заведение одной подзадачи
деления в изоляции от `fsm._approve_spec_gate`.

Сквозной путь (approve с секцией «## Деление» находит подраздел, заводит
подзадачу, журналирует родителя) уже закрывают приёмочные тесты
`tasks/01M1SHJZCE0Y4DXAAWQ2W585A7/acceptance_tests/test_ac5_*`/
`test_ac11_*` — не дублируется здесь. Этот файл проверяет саму функцию:
`SPEC.md` подзадачи — байт-в-байт шаблон `templates/SPEC.md` с
подставленными `task`/названием (тот же шаблон, что и `cmd_new`), а
`TZ.md` несёт ссылку на родителя первой строкой и сохраняет поля
`Зоны:`/`Порядок:` подраздела текстом (требование 2 — «эта задача не
учит cmd_new новым параметрам зон/бюджета»).

Предварительные зоны подзадачи и предупреждение о пересечении зон (SPEC
01M3H1Z489CKJ8FHSRS4TYTPX2) — `SubtaskZonesTest`/`SubtaskZoneOverlapTest`
в конце файла: сами общие функции (`_record_preliminary_zones`,
`_warn_zone_overlap`) со стороны `cmd_new` уже покрывает
`tests/test_catalog_zone_overlap.py`, предмет здесь — что `spawn_subtask`
их зовёт, в нужном порядке и с target'ом подзадачи.
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artifact_branch, catalog, config, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

PARENT_ID = "01SPAWNUNITPARENTTASK001"
PARENT_TITLE = "Родитель юнит-теста spawn_subtask"
TZ_BODY = ("Зоны: orchestrator/foo.py\nПорядок: первая, без "
          "зависимостей\n\nТекст ТЗ подзадачи юнит-теста.")


class SpawnSubtaskTest(RealGitSandbox):

    def test_spec_is_the_unmodified_template_with_title_and_task_id(self):
        """Ловит мутацию: `spawn_subtask` подставляет своё название/id в
        шаблон SPEC вместо `title`/`task_id` подзадачи, либо правит шаблон
        сверх подстановки `TASK_ID`/`<название задачи>` — SPEC подзадачи
        обязан оставаться байт-в-байт тем же шаблоном, что у `cmd_new`."""
        sub_id = catalog.spawn_subtask(PARENT_ID, PARENT_TITLE,
                                       "Подзадача spawn", TZ_BODY)

        spec = artifact_branch.read_tree(sub_id)[f"tasks/{sub_id}/SPEC.md"]
        template = (config.TEMPLATES / "SPEC.md").read_text(encoding="utf-8")
        expected = template.replace("TASK_ID", sub_id).replace(
            "<название задачи>", "Подзадача spawn")
        self.assertEqual(spec, expected)

    def test_tz_starts_with_the_parent_link_and_keeps_field_text(self):
        """Ловит мутацию: ссылка на родителя дописывается в конец `TZ.md`
        вместо первой строки, либо поля `Зоны:`/`Порядок:` подраздела
        теряются/парсятся при сборке TZ — требование 2 явно запрещает
        `spawn_subtask` разбирать эти поля, они остаются сырым текстом."""
        sub_id = catalog.spawn_subtask(PARENT_ID, PARENT_TITLE,
                                       "Подзадача с полями", TZ_BODY)

        tz = artifact_branch.read_tree(sub_id)[f"tasks/{sub_id}/TZ.md"]
        link_line = f"Родительская задача: {PARENT_ID} — {PARENT_TITLE}"

        self.assertLess(
            tz.index(link_line), tz.index(TZ_BODY),
            f"ссылка на родителя не предшествует телу подраздела: {tz!r}")
        # Требование 2: поля Зоны:/Порядок: остаются literal-текстом,
        # cmd_new их не парсит и не превращает во frontmatter подзадачи.
        self.assertIn("Зоны: orchestrator/foo.py", tz)
        self.assertIn("Порядок: первая, без зависимостей", tz)

    def test_new_task_row_starts_in_spec_writing_like_cmd_new(self):
        """Ловит мутацию: подзадача заводится в состоянии, отличном от
        `spec_writing` (например, копирует состояние родителя `spec_gate`)
        — общий скелет `_new_task_row` обязан заводить строку так же, как
        `cmd_new`, независимо от того, откуда пришло ТЗ."""
        sub_id = catalog.spawn_subtask(PARENT_ID, PARENT_TITLE,
                                       "Подзадача состояния", TZ_BODY)

        row = store.get_task(store.db(), sub_id)

        self.assertEqual(row["state"], "spec_writing")
        self.assertEqual(row["title"], "Подзадача состояния")

    def test_target_defaults_to_config_default_target(self):
        """Ловит мутацию: `spawn_subtask` без явного `target` заводит
        подзадачу с пустым/родительским `target` вместо `config.
        DEFAULT_TARGET` — та же логика дефолта, что у `cmd_new`."""
        sub_id = catalog.spawn_subtask(PARENT_ID, PARENT_TITLE,
                                       "Подзадача таргета", TZ_BODY)

        row = store.get_task(store.db(), sub_id)

        self.assertEqual(row["target"], config.DEFAULT_TARGET)


SHARED_ZONE = "orchestrator/pull.py"
OTHER_ZONE = "docs/operator-session.md"
FOREIGN_TARGET = "acme"


def tz_body(zones: str) -> str:
    """Тело подраздела «## Деление» со строкой «Зоны:» ПЕРВОЙ строкой —
    так его отдаёт `guard.parse_division_subsections`, и потому ссылка на
    родителя оказывается ровно перед ней."""
    return (f"Зоны: {zones}.\nПорядок: первая, без зависимостей\n\n"
            f"Текст ТЗ подзадачи юнит-теста зон.")


TZ_BODY_NO_ZONES_LINE = ("Порядок: первая, без зависимостей\n\n"
                        "Текст ТЗ подзадачи без строки зон.")
TZ_BODY_EMPTY_ZONES_LINE = ("Зоны:\nПорядок: первая, без зависимостей\n\n"
                           "Текст ТЗ подзадачи с пустой строкой зон.")


class SpawnSubtaskZoneSandbox(RealGitSandbox):
    """Родитель деления строкой БД в `spec_gate` — состоянии, из которого
    `fsm._spawn_division_subtasks` зовёт `spawn_subtask` (в `killed`
    родитель уходит ПОСЛЕ всех подзадач). Зоны родителя по умолчанию
    `NULL`: пересечение с ним — предмет отдельного сценария."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.insert_task(self.conn, PARENT_ID, PARENT_TITLE, "spec_gate",
                          f"task/{PARENT_ID.lower()}-delenie",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def spawn(self, body: str, *, title: str = "Часть деления",
              target: str | None = None) -> tuple:
        """(stdout, id подзадачи) — `tests.sandbox.capture` здесь не
        годится: она не возвращает значение функции, а `target` у
        `spawn_subtask` keyword-only."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            sub_id = catalog.spawn_subtask(PARENT_ID, PARENT_TITLE, title,
                                           body, target=target)
        return buf.getvalue(), sub_id

    def zones_of(self, task_id: str):
        return store.get_task(self.conn, task_id)["zones"]

    def details(self, task_id: str, action: str) -> str:
        return " | ".join(r["detail"] or "" for r
                          in store.task_steps(self.conn, task_id)
                          if r["action"] == action)


class SubtaskZonesTest(SpawnSubtaskZoneSandbox):

    def test_zones_line_of_the_subsection_lands_in_the_task_row(self):
        """Ловит мутацию: `spawn_subtask` не зовёт
        `_record_preliminary_zones` (или пишет зоны родителю, не
        подзадаче) — колонка `tasks.zones` подзадачи осталась бы `NULL` до
        approve её гейта SPEC, и прогноз очереди зон не видел бы ни одной
        части деления; либо запись сделана молча, без журнала, и Оператор
        не узнал бы, откуда взялось значение колонки."""
        _out, sub_id = self.spawn(tz_body(f"{SHARED_ZONE}, {OTHER_ZONE}"))

        self.assertEqual(f"{OTHER_ZONE}, {SHARED_ZONE}",
                         self.zones_of(sub_id))
        detail = self.details(sub_id, catalog.PRELIMINARY_ZONES_ACTION)
        self.assertIn(SHARED_ZONE, detail)
        self.assertIn(OTHER_ZONE, detail)

    def test_the_parent_link_line_does_not_leak_into_the_zones_column(self):
        """Ловит мутацию: на разбор подан не текст `TZ.md`, а что-то ещё —
        либо `tz_body` без ссылки (тогда сценарий «ссылка не мешает
        разбору» не наблюдается вовсе), либо весь текст документа вместо
        раздела «Зоны:» (тогда путь из НАЗВАНИЯ родителя затёк бы в
        колонку зон подзадачи)."""
        title = f"Родитель, правящий {OTHER_ZONE}"
        buf = io.StringIO()
        with redirect_stdout(buf):
            sub_id = catalog.spawn_subtask(PARENT_ID, title, "Часть",
                                           tz_body(SHARED_ZONE))

        tz = artifact_branch.read_tree(sub_id)[f"tasks/{sub_id}/TZ.md"]
        lines = tz.splitlines()
        link_line = f"Родительская задача: {PARENT_ID} — {title}"
        self.assertTrue(lines[lines.index(link_line) + 1].startswith("Зоны:"),
                        f"строка «Зоны:» не идёт сразу за ссылкой:\n{tz}")
        self.assertEqual(SHARED_ZONE, self.zones_of(sub_id))

    def test_a_subsection_without_zones_leaves_the_column_null(self):
        """Ловит мутацию: запись зон сделана безусловно, мимо проверки
        пустого перечня в `_record_preliminary_zones` — колонка получила
        бы пустую строку, и «зон не заявлено вовсе» (`NULL`, признак,
        который читают `checkpoint._zone_paths` и гейт зон) стало бы
        неотличимо от «зоны заявлены пустыми»."""
        for body in (TZ_BODY_NO_ZONES_LINE, TZ_BODY_EMPTY_ZONES_LINE):
            with self.subTest(body=body.splitlines()[0]):
                _out, sub_id = self.spawn(body)

                self.assertIsNone(self.zones_of(sub_id))


class SubtaskZoneOverlapTest(SpawnSubtaskZoneSandbox):

    def overlap_lines(self, out: str, task_id: str, zone: str) -> list:
        """Строки вывода, называющие РАЗОМ id пересекающейся задачи и общий
        путь: одного id мало — строку «… создана делением <id родителя> …»
        печатает само заведение."""
        return [ln for ln in out.splitlines() if task_id in ln and zone in ln]

    def test_the_next_part_of_the_division_is_warned_about_the_previous(self):
        """Ловит мутацию: запись зон вынесена ПОСЛЕ заведения всех частей
        (одним проходом в `fsm._spawn_division_subtasks`) — к моменту
        заведения второй части колонка первой ещё пуста, и пересечение
        внутри одной волны деления не обнаруживается ни выводом, ни
        журналом."""
        _out, first = self.spawn(tz_body(SHARED_ZONE), title="Первая")

        out, second = self.spawn(tz_body(SHARED_ZONE), title="Вторая")

        self.assertTrue(self.overlap_lines(out, first, SHARED_ZONE), out)
        self.assertIn(first, self.details(second,
                                         catalog.ZONE_OVERLAP_ACTION))

    def test_overlap_with_the_still_living_parent_is_reported(self):
        """Ловит мутацию: родитель исключён из сверки как заведомо
        уходящий в `killed` (`exclude_task_id` родителя или фильтр по
        `parent_task_id`) — Оператор не увидел бы, что часть наследует
        зону, которую родитель ещё держит в полёте."""
        store.update_task(self.conn, PARENT_ID, zones=SHARED_ZONE)

        out, sub_id = self.spawn(tz_body(SHARED_ZONE))

        self.assertTrue(self.overlap_lines(out, PARENT_ID, SHARED_ZONE), out)
        self.assertIn(PARENT_ID, self.details(sub_id,
                                             catalog.ZONE_OVERLAP_ACTION))

    def test_a_part_of_a_foreign_target_gets_no_warning(self):
        """Ловит мутацию: `target` подзадачи в сверку не передан (вызов
        `_warn_zone_overlap` без четвёртого аргумента, то есть с дефолтом
        «основной») — часть внешнего target'а уносила бы в журнал обещание
        очереди замка зон, которой для её target'а не бывает; асимметрия с
        парной механикой `cmd_new` осталась бы незамеченной."""
        store.update_task(self.conn, PARENT_ID, zones=SHARED_ZONE)

        out, foreign = self.spawn(tz_body(SHARED_ZONE),
                                  target=FOREIGN_TARGET)

        self.assertEqual([], self.overlap_lines(out, PARENT_ID, SHARED_ZONE),
                         out)
        self.assertEqual("", self.details(foreign,
                                         catalog.ZONE_OVERLAP_ACTION))
        # То же заведение на основном target'е предупреждение даёт — иначе
        # тест зеленел бы и на сверке, сломанной целиком.
        out_main, _main = self.spawn(tz_body(SHARED_ZONE))
        self.assertTrue(self.overlap_lines(out_main, PARENT_ID, SHARED_ZONE),
                        out_main)

    def test_the_warning_does_not_turn_the_spawn_into_a_refusal(self):
        """Ловит мутацию: сверка оформлена отказом по образцу соседнего
        `_tz_path_refusal` (`sys.exit`) — заведение подняло бы `SystemExit`
        посреди деления, оставив родителя поделённым на часть частей; либо
        запись зон слита с привязкой к родителю в один `store.update_task`
        и `parent_task_id` из него выпал."""
        store.update_task(self.conn, PARENT_ID, zones=SHARED_ZONE)

        _out, sub_id = self.spawn(tz_body(SHARED_ZONE))

        row = store.get_task(self.conn, sub_id)
        self.assertEqual("spec_writing", row["state"])
        self.assertEqual(PARENT_ID, row["parent_task_id"])
        self.assertEqual(SHARED_ZONE, row["zones"])


if __name__ == "__main__":
    import unittest
    unittest.main()
