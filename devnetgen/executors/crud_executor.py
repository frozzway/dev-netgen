from __future__ import annotations
from typing import TYPE_CHECKING

from devnetgen.executors import SourceGeneratorExecutor
from devnetgen.constructors import *

if TYPE_CHECKING:
    from devnetgen.entities import Namespace, Entity


class CrudExecutor(SourceGeneratorExecutor):
    """ Класс с методами для создания CRUD'а и файла контроллера сущности """

    def __init__(self, entity: Entity):
        super().__init__(entity)

        self.constructors: list[CRUDConstructor] = [
            CreateConstructor(executor=self),
            UpdateConstructor(executor=self),
            DeleteConstructor(executor=self),
            GetEntityConstructor(executor=self),
            GetEntitiesConstructor(executor=self),
            GetEntityGridConstructor(executor=self),
        ]

    def create_crud(self, legacy_controller: bool = False):
        """
        Сгенерировать и записать на диск CRUD, файл контроллера и вывести результат в stdout
        :param legacy_controller: флаг для генерации файла контроллера в legacy проектах
        """
        self._create_crud_files(legacy_controller)
        self._cleanup_files()
        self._output_data()

    def calculate_namespaces(self) -> dict[str, Namespace]:
        for constructor in self.constructors:
            key = constructor.namespace_identifier
            self.command_namespaces[key] = constructor.namespace
        return self.command_namespaces

    def _create_crud_files(self, legacy_controller: bool):
        """ Сгенерировать и записать на диск CRUD сущности и файл контроллера """
        for constructor in self.constructors:
            constructor.create_files()

        self.calculate_namespaces()

        controller = ControllerConstructor(self, legacy_controller)
        controller.create_files()

    def get_template_vars(self):
        mediator_data = {
            "mediator_lib": 'Mediator' if self.meta.mediator else 'MediatR',
            "return_value": 'ValueTask' if self.meta.mediator else 'Task'
        }
        return {
            'mediator': mediator_data,
            'webui': 'WebApi' if self.meta.webapi else 'WebUI'
        }

    def _cleanup_files(self):
        """ Очистить '!' и '@' из summaries свойств всех задействованных сущностей """
        self.entity.clear_summaries_flags()
        for file in self.entity.included_files:
            file.clear_summaries_flags()
