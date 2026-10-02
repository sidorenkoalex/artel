"""Команда `models` показывает фактическую модель роли: столбец ролей по
разрешению `resolve_role` с источником (ярус либо `role_models`) и
итоговые строки «роль → модель → провайдер (источник)» под таблицей.

Группа: долгоживущий

Критерии приёмки, которые покрывает файл:

AC-1. Локальный слой с `tiers:`, в котором ярус роли ведёт на модель A,
и `role_models:`, переводящей эту роль на модель B чужого провайдера:
строка модели B несёт роль с источником `role_models: <роль>`, строка
модели A этой роли не несёт. Роль без записи `role_models` печатается в
строке модели своего яруса с источником `<ярус>: <роль>`. Заголовок
столбца ролей — не «роли по ярусам».

AC-2. Под таблицей — по одной итоговой строке на каждую роль-агента
карты исполнителей «роль → модель → провайдер (источник)»; модель и
провайдер совпадают с `resolve_role` на тех же слоях.

AC-3. Роль с отказом `ResolutionError` печатается в итоговых строках с
текстом отказа; команда не падает, таблица и строки прочих ролей
напечатаны.

AC-4. Нечитаемый локальный слой и нечитаемая карта исполнителей — прежние
строки-причины над таблицей, команда не падает; прогон не меняет файлов
слоёв, каталога и карты и не пишет в журнал.

AC-5. `docs/stack.md`, пункт «посмотреть, что где действует», описывает
столбец ролей с источником и итоговые строки.

Каталог, локальный слой и карта исполнителей — фикстуры во временном
каталоге песочницы (`TmpRootTest`), не боевые файлы пульта: их состав —
крутилка Оператора. Имена ролей, сопоставление ярусов моделям и выбор
переведённых записью `role_models` ролей случайны при каждом запуске;
зерно печатается и входит в текст провала.

Строка таблицы модели ищется по содержанию, а не по позиции столбца:
строка, где есть идентификатор модели и её прейскурант (у каждой модели
фикстуры — свой) и нет стрелки «→» итоговых строк.

Красен до реализации: `cmd_models` строит столбец ролей только по
`tiers:` и печатает заголовок «роли по ярусам», раздела `role_models:` не
читает и итоговых строк «роль → модель → провайдер» не печатает; пункт
`docs/stack.md` описывает прежний столбец «роли по ярусам».
"""
import io
import random
import re
import string
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import config, models, store
from tests.sandbox import TmpRootTest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Модели фикстуры: провайдер и прейскурант (input/output/cache_write/
#: cache_read). Прейскурант у каждой модели свой — по нему строка модели
#: в таблице отличается от строк соседей.
CATALOG_MODELS = {
    "mdl-alfa-fikstury": ("claude", (1.0, 11.0, 1.5, 0.1)),
    "mdl-beta-fikstury": ("claude", (2.0, 12.0, 2.5, 0.2)),
    "gpt-gamma-fikstury": ("codex", (3.0, 13.0, 3.5, 0.3)),
    "gpt-delta-fikstury": ("codex", (4.0, 14.0, 4.5, 0.4)),
}
CLAUDE_MODELS = tuple(m for m, (p, _) in CATALOG_MODELS.items()
                      if p == "claude")
CODEX_MODELS = tuple(m for m, (p, _) in CATALOG_MODELS.items()
                     if p == "codex")
MISSING_MODEL = "mdl-net-v-kataloge-fikstury"

HEADER_OLD = "роли по ярусам"
ARROW = "→"


def catalog_text() -> str:
    sections = {"claude": ("claude", "1.0.0", "true"),
                "codex": ("codex", "0.155.1", "false")}
    text = "providers:\n"
    for provider, (cli, minimum, cost_from_cli) in sections.items():
        text += (f"  {provider}:\n    cli: {cli}\n"
                 f"    min_cli_version: {minimum}\n"
                 f"    cost_from_cli: {cost_from_cli}\n    models:\n")
        for model_id, (owner, prices) in CATALOG_MODELS.items():
            if owner != provider:
                continue
            text += (f"      {model_id}:\n"
                     f"        min_cli_version: {minimum}\n"
                     f"        status: supported\n"
                     f"        list_price_usd_per_mtok:\n")
            for kind, value in zip(models.PRICE_KINDS, prices):
                text += f"          {kind}: {value}\n"
            text += "        price_date: 2026-09-20\n"
    return text


def price_text(model_id: str) -> str:
    """Прейскурант модели так, как его печатает таблица (`5/25/6.25/0.5`)."""
    return "/".join(f"{value:g}" for value in CATALOG_MODELS[model_id][1])


def roles_text(tier_of_role: dict) -> str:
    text = "roles:\n"
    for role, tier in tier_of_role.items():
        text += (f"  {role}:\n    executor: agent\n"
                 f"    token_slot: artel-{role}\n"
                 f"    skills: [conventions-core]\n"
                 f"    model_tier: {tier}\n")
    return text + "token_fallback: artel-token\n"


def layer_text(tiers: dict, role_models: dict = None,
               role_providers: dict = None) -> str:
    text = "tiers:\n" + "".join(f"  {tier}: {model}\n"
                                for tier, model in tiers.items())
    if role_providers:
        text += "role_providers:\n" + "".join(
            f"  {role}: {name}\n" for role, name in role_providers.items())
    if role_models:
        text += "role_models:\n" + "".join(
            f"  {role}: {model}\n" for role, model in role_models.items())
    return text


class _ModelsCommandSandbox(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.catalog_path = self.use_catalog_fixture(catalog_text())
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def msg(self, text: str = "") -> str:
        return f"зерно {self.seed}: {text}"

    def role_names(self, count: int) -> list:
        """Случайные имена ролей: разные, не подстроки друг друга и
        фиксированных текстов вывода (8 строчных латинских букв)."""
        names = set()
        while len(names) < count:
            names.add("".join(self.rng.choice(string.ascii_lowercase)
                              for _ in range(8)))
        return sorted(names)

    def use_roles(self, tier_of_role: dict) -> Path:
        path = self.root / ".artel" / "roles-fikstura.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(roles_text(tier_of_role), encoding="utf-8")
        patcher = mock.patch.object(config, "ROLES", path)
        patcher.start()
        self.addCleanup(patcher.stop)
        return path

    def use_layer(self, text: str) -> Path:
        path = Path(config.MODELS_LOCAL)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def scenario(self) -> dict:
        """Три роли — по одной на ярус; ярусы ведут на модели `claude`
        случайно; одна или две роли переведены записью `role_models` на
        РАЗНЫЕ модели `codex` (чужой провайдер). Одной переведённой роли
        с вероятностью 1/2 провайдер назван `role_providers:` явно."""
        names = self.role_names(len(models.TIERS))
        self.rng.shuffle(names)
        tier_of_role = dict(zip(names, models.TIERS))
        tiers = {tier: self.rng.choice(CLAUDE_MODELS) for tier in models.TIERS}
        swapped = self.rng.sample(names, self.rng.choice((1, 2)))
        targets = self.rng.sample(CODEX_MODELS, len(swapped))
        role_models = dict(zip(swapped, targets))
        role_providers = {}
        if self.rng.random() < 0.5:
            role_providers[swapped[0]] = "claude"
        self.use_roles(tier_of_role)
        self.use_layer(layer_text(tiers, role_models, role_providers))
        return {"tier_of_role": tier_of_role, "tiers": tiers,
                "role_models": role_models}

    def run_cmd(self) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            models.cmd_models()
        return buf.getvalue()

    def table_row(self, out: str, model_id: str) -> str:
        rows = [line for line in out.splitlines()
                if model_id in line and price_text(model_id) in line
                and ARROW not in line]
        self.assertEqual(len(rows), 1, self.msg(
            f"строка таблицы модели {model_id} не найдена однозначно:\n{out}"))
        return rows[0]

    def summary_lines(self, out: str, role: str) -> list:
        return [line for line in out.splitlines()
                if re.search(rf"(^|\s){re.escape(role)} {ARROW} ", line)]

    def header_index(self, out: str) -> int:
        lines = out.splitlines()
        for index, line in enumerate(lines):
            if "источник тарифа" in line and "прейскурант" in line:
                return index
        self.fail(self.msg(f"заголовок таблицы не найден:\n{out}"))


class RolesColumnTest(_ModelsCommandSandbox):
    """AC-1: столбец ролей — по фактическому разрешению роли."""

    def test_ac1_roles_column_follows_role_models_with_source(self):
        """Роль, переведённая `role_models:` на модель `codex`, — в строке
        этой модели с источником `role_models: <роль>` и НЕ в строке модели
        своего яруса; роль без записи — в строке модели яруса с
        источником `<ярус>: <роль>`; заголовок — не «роли по ярусам».

        Сценарий повторяется на нескольких случайных раскладках ролей,
        ярусов и записей.

        Ловит мутацию: столбец строится только по `tiers:` (как до
        задачи) — переведённая роль печатается «strong: <роль>» у модели
        `claude` своего яруса, у модели `codex` стоит «—»; либо роль у
        новой модели добавлена, но у модели яруса не снята; либо источник
        у записи `role_models` печатается ярусом.
        """
        for _ in range(4):
            fixture = self.scenario()
            out = self.run_cmd()
            tier_of_role = fixture["tier_of_role"]
            for role, model_b in fixture["role_models"].items():
                model_a = fixture["tiers"][tier_of_role[role]]
                self.assertIn(f"role_models: {role}",
                              self.table_row(out, model_b),
                              self.msg(f"роль {role} у {model_b}:\n{out}"))
                self.assertNotIn(role, self.table_row(out, model_a),
                                 self.msg(f"роль {role} у {model_a}:\n{out}"))
            for role, tier in tier_of_role.items():
                if role in fixture["role_models"]:
                    continue
                model_a = fixture["tiers"][tier]
                row = self.table_row(out, model_a)
                self.assertRegex(
                    row, rf"(^|\s){tier}: ([a-z]+, )*{role}\b",
                    self.msg(f"роль {role} по ярусу {tier} у {model_a}:\n"
                             f"{out}"))
                self.assertNotIn(f"role_models: {role}", out, self.msg(out))
            self.assertNotIn(HEADER_OLD, out, self.msg(out))


class SummaryLinesTest(_ModelsCommandSandbox):
    """AC-2/AC-3: итоговые строки «роль → модель → провайдер (источник)»."""

    def test_ac2_summary_line_per_role_matches_resolve_role(self):
        """По одной итоговой строке на роль-агента; модель и провайдер в
        ней — те, что `resolve_role` отдаёт этой роли на тех же слоях, и
        для роли с записью `role_models`, и для роли по ярусу.

        Провайдер переведённой роли случайно назван `role_providers:`
        (`claude` при модели `codex`) — тогда только разрешение
        `resolve_role` даёт верного провайдера.

        Ловит мутацию: итог считается своей копией правила — по ярусу
        мимо `role_models` (модель яруса вместо модели записи) либо
        провайдером модели из каталога мимо `role_providers:`
        (`codex` вместо `claude`); либо строка роли печатается дважды
        (раз от яруса, раз от записи) или пропущена.
        """
        for _ in range(4):
            fixture = self.scenario()
            out = self.run_cmd()
            catalog, local = models.load_catalog(), models.load_local()
            for role in fixture["tier_of_role"]:
                resolved = models.resolve_role(role, catalog, local)
                lines = self.summary_lines(out, role)
                self.assertEqual(len(lines), 1, self.msg(
                    f"итоговых строк роли {role}: {len(lines)}\n{out}"))
                self.assertRegex(
                    lines[0],
                    rf"{re.escape(role)} {ARROW} "
                    rf"{re.escape(resolved.model)} {ARROW} "
                    rf"{re.escape(resolved.provider)} \(\S[^)]*\)",
                    self.msg(f"роль {role}:\n{out}"))

    def test_ac3_resolution_error_is_printed_and_the_rest_survives(self):
        """Одна роль не разрешается — ярус не сопоставлен модели либо
        модель записи `role_models` вне каталога (выбор случаен); её
        итоговая строка несёт текст отказа `resolve_role`, команда
        завершается без исключения и без `SystemExit`, строки таблицы
        всех моделей каталога и итоговые строки прочих ролей напечатаны.

        Ловит мутацию: `ResolutionError` одной роли не перехвачен —
        команда падает трейсбеком и Оператор не видит таблицу вовсе; либо
        перехвачен на весь цикл — строки прочих ролей не печатаются; либо
        отказ гасится молча — роль без строки, причина не названа.
        """
        for _ in range(4):
            names = self.role_names(len(models.TIERS))
            self.rng.shuffle(names)
            tier_of_role = dict(zip(names, models.TIERS))
            broken = self.rng.choice(names)
            tiers = {tier: self.rng.choice(CLAUDE_MODELS)
                     for tier in models.TIERS}
            role_models = {}
            if self.rng.random() < 0.5:
                del tiers[tier_of_role[broken]]
            else:
                role_models[broken] = MISSING_MODEL
            self.use_roles(tier_of_role)
            self.use_layer(layer_text(tiers, role_models))
            with self.assertRaises(models.ResolutionError) as ctx:
                models.resolve_role(broken)
            refusal = str(ctx.exception)

            try:
                out = self.run_cmd()
            except (Exception, SystemExit) as exc:  # noqa: BLE001
                self.fail(self.msg(f"models упала на отказе роли {broken}: "
                                   f"{exc!r}"))

            self.assertTrue(
                any(broken in line and refusal in line
                    for line in out.splitlines()),
                self.msg(f"нет строки роли {broken} с отказом "
                         f"«{refusal}»:\n{out}"))
            for model_id in CATALOG_MODELS:
                self.table_row(out, model_id)
            for role in names:
                if role == broken:
                    continue
                resolved = models.resolve_role(role)
                lines = self.summary_lines(out, role)
                self.assertEqual(len(lines), 1, self.msg(
                    f"итоговых строк роли {role}: {len(lines)}\n{out}"))
                self.assertIn(
                    f"{role} {ARROW} {resolved.model} {ARROW} "
                    f"{resolved.provider} (", lines[0], self.msg(out))


class ReadOnlyAndReasonsTest(_ModelsCommandSandbox):
    """AC-4: строки-причины над таблицей и ни одной записи."""

    def snapshot(self, paths) -> dict:
        return {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in paths if p.exists()}

    def seed_journal(self) -> None:
        conn = store.db()
        try:
            store.create_schema(conn)
            store.journal(conn, "T0", "тест", "затравка")
            conn.commit()
        finally:
            conn.close()

    def journal_rows(self) -> int:
        conn = store.db()
        try:
            return conn.execute("SELECT COUNT(*) FROM steps").fetchone()[0]
        finally:
            conn.close()

    def run_read_only(self, paths) -> str:
        """Прогон `models` со сверкой: файлы слоёв, каталога и карты
        байт-в-байт и по времени изменения прежние, журнал не вырос."""
        self.seed_journal()
        rows_before = self.journal_rows()
        before = self.snapshot(paths)
        try:
            out = self.run_cmd()
        except (Exception, SystemExit) as exc:  # noqa: BLE001
            self.fail(self.msg(f"models упала: {exc!r}"))
        self.assertEqual(self.snapshot(paths), before, self.msg(
            "models изменила файл слоя, каталога или карты"))
        self.assertEqual(self.journal_rows(), rows_before,
                         self.msg("models записала в журнал"))
        return out

    def test_ac4_unreadable_layers_named_above_table_nothing_written(self):
        """Три прогона: исправные слои; нечитаемый локальный слой
        (файла нет либо раздела `tiers:` нет — выбор случаен); нечитаемая
        карта исполнителей. В каждом команда не падает, файлы слоёв,
        каталога и карты не меняются, журнал `steps` не растёт; во втором
        над таблицей — «локальный слой не прочитан: …», в третьем — строка
        о неполноте столбца ролей с причиной «карта исполнителей не
        прочитана».

        Ловит мутацию: новый столбец зовёт `resolve_role` без перехвата
        отказа слоя — нечитаемый локальный слой роняет команду
        `LocalLayerError`; либо причина о карте исполнителей больше не
        печатается (гасится молча) или печатается под таблицей; либо
        разрешение ролей в команде кладёт шаблон слоя/пишет журнал.
        """
        self.scenario()
        roles_path = Path(config.ROLES)
        layer_path = Path(config.MODELS_LOCAL)
        paths = (roles_path, layer_path, self.catalog_path)

        self.run_read_only(paths)

        if self.rng.random() < 0.5:
            layer_path.unlink()
        else:
            self.use_layer("role_models:\n  x: y\n")
        out = self.run_read_only(paths)
        self.assertFalse(layer_path.exists() and layer_path.read_text(
            encoding="utf-8").startswith("# Локальный слой"),
            self.msg("models положила шаблон локального слоя"))
        header = self.header_index(out)
        reasons = [i for i, line in enumerate(out.splitlines())
                   if "локальный слой не прочитан: " in line]
        self.assertTrue(reasons and reasons[0] < header, self.msg(out))
        for model_id in CATALOG_MODELS:
            self.assertIn(model_id, out, self.msg(out))

        self.scenario()
        roles_path = Path(config.ROLES)
        roles_path.write_text("roles: не-отображение\n", encoding="utf-8")
        out = self.run_read_only((roles_path, Path(config.MODELS_LOCAL),
                                  self.catalog_path))
        header = self.header_index(out)
        reasons = [i for i, line in enumerate(out.splitlines())
                   if "карта исполнителей не прочитана" in line]
        self.assertTrue(reasons and reasons[0] < header, self.msg(out))
        for model_id in CATALOG_MODELS:
            self.assertIn(model_id, out, self.msg(out))


class StackDocTest(unittest.TestCase):
    """AC-5: пункт «посмотреть, что где действует» `docs/stack.md`."""

    def bullet(self) -> str:
        text = (REPO_ROOT / "docs" / "stack.md").read_text(encoding="utf-8")
        start = text.find("**посмотреть, что где действует**")
        self.assertNotEqual(start, -1, "пункт не найден в docs/stack.md")
        end = text.find("\n- **", start)
        return " ".join(text[start:end if end != -1 else None].split())

    def test_ac5_stack_doc_describes_roles_source_and_summary_lines(self):
        """Пункт называет столбец ролей с источником — ярус или запись
        `role_models` — и итоговые строки «роль → модель → провайдер
        (источник)».

        Ловит мутацию: код команды переделан, а пункт документа оставлен
        прежним («роли по ярусам», без `role_models` и без итоговых
        строк) — Оператор читает в документации таблицу, которой команда
        больше не печатает.
        """
        bullet = self.bullet()

        self.assertIn("role_models", bullet)
        self.assertIn("ярус", bullet)
        self.assertIn("роль → модель → провайдер (источник)", bullet)


if __name__ == "__main__":
    unittest.main()
