from devnetgen.executors import SourceGeneratorExecutor
from devnetgen.constructors import *


class CrudExecutor(SourceGeneratorExecutor):
    """ Класс с методами для создания CRUD'а и файла контроллера сущности """

    def create_crud(self, legacy_controller: bool = False):
        """
        Сгенерировать и записать на диск CRUD, файл контроллера и вывести результат в stdout
        :param legacy_controller: флаг для генерации файла контроллера в legacy проектах
        """
        self._create_crud_files(legacy_controller)
        self._cleanup_files()
        self._output_data()

    def _create_crud_files(self, legacy_controller: bool):
        """ Сгенерировать и записать на диск CRUD сущности и файл контроллера """
        constructors: list[CRUDConstructor] = [
            CreateConstructor(self),
            UpdateConstructor(self),
            DeleteConstructor(self),
            GetEntityConstructor(self),
            GetEntitiesConstructor(self),
            GetEntityGridConstructor(self),
        ]

        for constructor in constructors:
            constructor.create_files()
            key = constructor.namespace_identifier
            self.command_namespaces[key] = constructor.namespace

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
