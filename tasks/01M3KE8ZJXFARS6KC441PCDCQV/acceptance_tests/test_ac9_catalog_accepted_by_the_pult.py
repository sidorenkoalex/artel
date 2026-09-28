"""AC-9 — 01M3KE8ZJXFARS6KC441PCDCQV: на новом каталоге `artel.py models`
и `artel.py doctor` не дают красных строк, которых не было до правки.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. Полный набор `tests/` зелёный; `artel.py models` и `artel.py
doctor` на новом каталоге не дают красных строк, которых не было до
правки.

«Не было до правки» планка берёт буквально: одни и те же проверки
гоняются ДВАЖДЫ — на каталоге базы сравнения и на каталоге после
приложения PLAN, — и сравниваются их вердикты. Всё остальное, от чего
зависят `models` и `doctor` (локальный слой `.artel/models.yaml` вне git
и карта исполнителей `roles.yaml`), берётся фикстурой во временном
каталоге: это крутилки Оператора, и тест, читающий их настоящие файлы,
краснел бы от правки, не связанной с задачей (skills/test-authoring.md,
«Окружение теста»).

Первую половину критерия — «полный набор `tests/` зелёный» — планка не
повторяет: его на этом же гейте гоняет сам пульт
(`orchestrator/acceptance.py::full_suite`) и CI ветки; вторым прогоном
внутри планки он ничего бы не добавил. То, что литерал состава каталога
сходится с новым каталогом (единственное место набора, которое ломает
именно эта задача), проверяет `test_ac4_composition_literal.py`.

Красен до реализации: PLAN.md с приложением `models.yaml` ещё нет —
каталога «после правки» не существует, и сравнивать вердикты не с чем.
"""
import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _catalog  # noqa: E402

from orchestrator import config, doctor, models  # noqa: E402

#: Карта исполнителей сценария: одна agent-роль с ярусом — этого хватает,
#: чтобы `doctor` прошёл цепочку «роль → ярус → модель → провайдер».
ROLES_TEXT = """\
roles:
  developer:
    executor: agent
    token_slot: artel-developer
    skills: [conventions-core]
    model_tier: strong
token_fallback: artel-token
"""

LOCAL_TEMPLATE = """\
tiers:
  strong: {model}
  standard: {model}
  cheap: {model}
"""


class CatalogAcceptedByThePultTest(unittest.TestCase):
    """Каталог после приложения читается пультом так же, как читался
    каталог до него."""

    def setUp(self):
        self.applied = _catalog.applied()
        self.tdir = Path(tempfile.mkdtemp(prefix="artel-plank-ac9-"))
        self.addCleanup(self._drop)

        roles_path = self.tdir / "roles.yaml"
        roles_path.write_text(ROLES_TEXT, encoding="utf-8")
        local_path = self.tdir / "models-local.yaml"
        local_path.write_text(
            LOCAL_TEMPLATE.format(model=self.shared_model()), encoding="utf-8")

        for attr, value in (("ROLES", roles_path),
                            ("MODELS_LOCAL", local_path)):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _drop(self):
        shutil.rmtree(self.tdir, ignore_errors=True)

    def shared_model(self) -> str:
        """Модель, которая есть и в базе сравнения, и после приложения, и
        в обоих каталогах `supported`: ярус фикстуры обязан разрешаться в
        ОБОИХ прогонах, иначе сравнивать вердикты не с чем."""
        both = [model_id for model_id in sorted(self.applied.catalog.models)
                if model_id in self.applied.base_catalog.models
                and self.applied.catalog.models[model_id].status
                == models.STATUS_SUPPORTED
                and self.applied.base_catalog.models[model_id].status
                == models.STATUS_SUPPORTED]
        self.assertTrue(both, "ни одной модели, пережившей правку со "
                              "статусом supported — ярусу пульта не на что "
                              "указывать")
        return both[0]

    def verdicts(self, catalog_path: Path) -> dict:
        """{имя строки doctor: (статус, текст)} по двум строкам о слоях
        моделей, посчитанным на каталоге `catalog_path`."""
        with mock.patch.object(config, "MODELS", catalog_path):
            checks = [doctor.check_models_catalog(), doctor.check_models_local()]
        return {check.name: (check.status, check.detail) for check in checks}

    def test_ac9_doctor_gains_no_red_line_from_the_new_catalog(self):
        """Строки `models-catalog` и `models-local` на каталоге после
        приложения не хуже, чем на каталоге базы сравнения.

        Ловит мутацию: у новой записи пропущена одна из четырёх цен или
        проставлен ноль (в таблице требования 1 у `gpt-6-luna` стоит
        0.125 и 0.01 — цифры, на которых легко потерять разряд):
        `models.load_catalog` отказывает `IncompletePriceError`/
        `ZeroPriceError`, и `doctor` даёт `fail` «каталог моделей не
        разобран», которого до правки не было.
        """
        before = self.verdicts(
            self.applied.dir / "models.base.yaml")
        after = self.verdicts(self.applied.path)

        self.assertEqual(sorted(before), sorted(after))
        for name in sorted(before):
            was, _ = before[name]
            now, detail = after[name]
            with self.subTest(check=name):
                self.assertFalse(
                    now != was and was == "ok",
                    f"строка {name} стала {now} на новом каталоге "
                    f"(до правки — {was}): {detail}")

    def test_ac9_models_command_prints_the_new_catalog(self):
        """`artel.py models` на новом каталоге печатает таблицу: команда
        не отказывает, новые записи в ней есть, снятой — нет.

        Ловит мутацию: приложение положило запись мимо раздела
        `models:` провайдера (отступ на два пробела меньше — форма файла
        ограничена `orchestrator/yamlmini.py`, блочные отображения
        вложены отступом): каталог разберётся, но модели в таблице не
        будет, и ярус на неё не разрешится.
        """
        buffer = io.StringIO()
        with mock.patch.object(config, "MODELS", self.applied.path):
            with redirect_stdout(buffer):
                models.cmd_models()
        printed = buffer.getvalue()

        for model_id in sorted(_catalog.NEW_RECORDS):
            with self.subTest(model=model_id):
                self.assertIn(model_id, printed)
        self.assertNotIn(_catalog.WITHDRAWN_MODEL, printed)
        self.assertIn(self.shared_model(), printed)


if __name__ == "__main__":
    unittest.main()
