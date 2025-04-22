from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devnetgen.executors import CrudExecutor

from devnetgen.config import env
from devnetgen.constructors.base_crud_constructors import Constructor


class ControllerConstructor(Constructor):
    """Сборщик файла контроллера"""
    controller_template = 'Controller.cs.j2'
    legacy_controller_template = 'LegacyController.cs.j2'

    def __init__(self, executor: CrudExecutor, legacy_controller: bool):
        """
        Метод инициализации сборщика файла контроллера
        :param legacy_controller: флаг для генерации файла контроллера в legacy проектах
        """
        super().__init__(executor)
        self.legacy_controller = legacy_controller

    def create_files(self) -> None:
        """Сгенерировать и записать на диск файл контроллера"""
        template_vars = self.executor.get_template_vars()
        template_type = self.legacy_controller_template if self.legacy_controller else self.controller_template
        template = env.get_template(template_type)

        content = template.render(
            file=self.entity,
            target_namespace=self.executor.webui_namespace.name,
            webui=template_vars['webui'],
            command_namespaces=self.executor.command_namespaces.values(),
            sieve=self.executor.meta.sieve,
            **template_vars['mediator'],
            **self.executor.command_namespaces)

        filename = f'{self.entity.class_name}Controller.cs'
        self._create_file_if_not_exists(self.executor.webui_namespace, filename, content)
        self.executor.add_to_git(self.executor.webui_namespace.path)
