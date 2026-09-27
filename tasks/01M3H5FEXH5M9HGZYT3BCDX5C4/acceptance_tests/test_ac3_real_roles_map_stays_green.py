"""AC-3: четыре названных критерием файла `tests/` зелены на НАСТОЯЩЕЙ
карте исполнителей репозитория — без всякой подмены, прогоном в самом
дереве кода.

Прогон подпроцессом, а не импортом: `tests/sandbox.py` при импорте
уводит `config.MODELS_LOCAL` в свой временный каталог и патчит
`shutil.which` на весь процесс — втянуть эти файлы в процесс планки
значило бы менять предмет проверки.

Зелёный с рождения: на сегодняшней карте (все agent-роли на одном ярусе)
все четыре файла проходят — критерий сторожит, чтобы покрытие всех
ярусов, добавляемое ради AC-1, не сломало их и в обычной конфигурации
пульта.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402

TARGETS = (_util.STACK_TEST, _util.ROLE_MODEL_TEST, _util.PREFLIGHT_TEST,
           _util.DOCTOR_TEST)


class RealRolesMapTest(unittest.TestCase):
    """Прогоны в дереве кода как есть — карта исполнителей не трогается."""

    def test_ac3_four_files_are_green_on_the_real_roles_map(self):
        """Каждый из четырёх файлов прогоняется в корне дерева кода на
        настоящем `roles.yaml` и обязан пройти без провалов и ошибок.

        Ловит мутацию: локальный слой песочницы собирается перебором
        `models.TIERS` с ошибкой в форме записи (ярус и модель поменяны
        местами, потерян ключ `tiers:`, потеряны две пробела отступа) —
        слой перестаёт разбираться вовсе, `resolve_role` отказывает
        `LocalLayerError` у КАЖДОЙ роли, и файлы краснеют уже на обычной
        конфигурации пульта, где до правки были зелёными.
        """
        for target in TARGETS:
            with self.subTest(target=target):
                self.assertTrue((_util.REPO_ROOT / target).is_file(), target)
                result = _util.run_pytest(_util.REPO_ROOT, [target],
                                          timeout=25)
                self.assertEqual(_util.failed_nodeids(result.stdout), [],
                                 _util.run_report(result))
                self.assertEqual(result.returncode, 0,
                                 _util.run_report(result))


if __name__ == "__main__":
    unittest.main()