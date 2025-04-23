from devnetgen.constructors import *
from devnetgen.executors import SourceGeneratorExecutor


class TestsExecutor(SourceGeneratorExecutor):
    """ Класс с методами для создания тестов под CRUD-команды и запросы сущности """

    def create_tests(self):
        constructors: list[TestsConstructor] = [
            CreateTestsConstructor(self)
        ]

        for constructor in constructors:
            constructor.create_files()

        self._output_data()
