from devnetgen.constructors import *
from devnetgen.executors import CrudExecutor
from devnetgen.executors import SourceGeneratorExecutor


class TestsExecutor(SourceGeneratorExecutor):
    """ Класс с методами для создания тестов под CRUD-команды и запросы сущности """

    def create_tests(self):
        crud_executor = CrudExecutor(self.entity)
        self.command_namespaces = crud_executor.calculate_namespaces()

        constructors: list[TestsConstructor] = [
            CreateEntityTestsConstructor(executor=self),
            UpdateEntityTestsConstructor(executor=self),
            DeleteEntityTestsConstructor(executor=self),
            GetEntityTestsConstructor(executor=self),
            GetEntitiesTestsConstructor(executor=self),
            GetEntityGridTestsConstructor(executor=self),
        ]

        for constructor in constructors:
            constructor.create_files()

        self._output_data()
