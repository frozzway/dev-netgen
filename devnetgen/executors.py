import os
import re
import subprocess

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from itertools import chain

from devnetgen.entities import Namespace, Entity, VmDto
from devnetgen.constructors import *


@dataclass
class SolutionMeta:
    """
    Мета-информация о проекте

    Attributes:
        mediator: использование библиотеки Mediator/MediatR
        webapi: директория с контроллерами WebAPI/WebUI
        sieve: использование Sieve/Devexpress для грида
    """
    mediator: Optional[bool] = None
    webapi: Optional[bool] = None
    sieve: Optional[bool] = None


class Executor:
    """
    Attributes:
        meta: мета-информация о проекте
        changed_directories: директории, в которых сгенерированы файлы
        changed_files_num: число сгенерированных файлов
        solution_name: наименование решения (пр. "MinstroyGasDistributionNetworks")
        solution_path: абсолютный путь решения, объект Path (пр. "/home/alex/Documents/RiderProjects/MinstroyGasDistributionNetworks")
    """
    meta: SolutionMeta
    changed_directories: set[Path | str]
    changed_files_num: int
    solution_name: str
    solution_path: Path

    def __init__(self, solution_path: Path, solution_name: str):
        self.meta = SolutionMeta()
        self.changed_directories = set()
        self.changed_files_num = 0
        self.solution_name = solution_name
        self.solution_path = solution_path

    def _extract_meta(self):
        """ Извлечь мета-информацию, необходимую для генерации """
        self.meta.webapi = (self.solution_path / 'WebApi').exists()
        self.meta.sieve = (self.solution_path / 'Application' / 'Common' / 'Services' / 'SieveService.cs').exists()

        with open(self.solution_path / 'Application' / 'Application.csproj', "r", encoding='utf-8') as file:
            text = file.read()
            self.meta.mediator = 'MediatR' not in text

    def output_data(self):
        print(f'Сгенерировано {self.changed_files_num} файлов в директориях:')
        for directory in self.changed_directories:
            print(str(directory).removeprefix(self.solution_name))


class CrudExecutor(Executor):
    """
    Класс с методами для создания CRUD'а и файла контроллера сущности

    Attributes:
        entity: сущность для которой создаются элементы
        application_namespace: неполный (базовый) объект Namespace /Application/Work/..
        webui_namespace: неполный (базовый) объект Namespace /Application/Work/..
        command_namespaces: пространства имен команд и запросов
    """
    entity: Entity
    application_namespace: Namespace
    webui_namespace: Namespace
    command_namespaces: dict[str, Namespace]

    def __init__(self, entity: Entity):
        super().__init__(entity.sources_path, entity.solution_name)

        self.entity = entity
        self.command_namespaces = {}

    def create_crud(self, legacy_controller: bool = False):
        """
        Сгенерировать и записать на диск CRUD, файл контроллера и вывести результат в stdout
        :param legacy_controller: флаг для генерации файла контроллера в legacy проектах
        """
        self._extract_meta()
        self._calculate_namespaces()
        self._create_crud_files(legacy_controller)
        self.cleanup_files()
        self.output_data()

    def _calculate_namespaces(self):
        """ Определить базовые директории генерации файлов и соответствующие неполные неймспейсы"""
        controller_path = next(self.entity.sources_path.glob('**/Controllers'))

        if match := re.search("^.*References?(.*)", self.entity.namespace.name):
            target = match.group(1)

            application_path_results = tuple((self.entity.sources_path / 'Application').glob('**/References'))
            if len(application_path_results) == 0:
                application_path_results = tuple((self.entity.sources_path / 'Application').glob('**/Reference'))
            application_path = application_path_results[0] / target.removeprefix('.').replace('.', '/')

            webui_path_results = tuple(controller_path.glob('**/References'))
            if len(application_path_results) == 0:
                webui_path_results = tuple(controller_path.glob('**/Reference'))
            webui_path = webui_path_results[0] / target.removeprefix('.').replace('.', '/')

        else:
            target = re.search("^.*Entities(.*)", self.entity.namespace.name).group(1)

            application_path = self.entity.sources_path / 'Application' / 'Work' / target.removeprefix('.').replace('.', '/')
            webui_path = controller_path / 'Work' / target.removeprefix('.').replace('.', '/')

        application_posix = application_path.as_posix()
        namespace_name = self.entity.solution_name + application_posix[application_posix.index('/Application'):].replace('/', '.')
        self.application_namespace = self.entity.get_namespace_obj(namespace_name + f'.{self.entity.pluralized_class_name}')

        webui_posix = webui_path.as_posix()
        prefix = '/WebApi' if self.meta.webapi else '/WebUI'
        namespace_name = self.entity.solution_name + webui_posix[webui_posix.index(prefix):].replace('/', '.')
        self.webui_namespace = self.entity.get_namespace_obj(namespace_name)

    def _create_crud_files(self, legacy_controller: bool):
        """ Сгенерировать и записать на диск CRUD сущности и файл контроллера"""
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

    @staticmethod
    def add_to_git(directory_path: Path):
        """ Добавить все файлы директории в git """
        directory_str = str(directory_path)
        os.chdir(directory_str)
        subprocess.run(["git", "add", '.'])

    def get_template_vars(self):
        mediator_data = {
            "mediator_lib": 'Mediator' if self.meta.mediator else 'MediatR',
            "return_value": 'ValueTask' if self.meta.mediator else 'Task'
        }
        return {
            'mediator': mediator_data,
            'webui': 'WebApi' if self.meta.webapi else 'WebUI'
        }

    def cleanup_files(self):
        """ Очистить '!' и '@' из summaries свойств всех задействованных сущностей """
        self.entity.clear_summaries_flags()
        for file in self.entity.included_files:
            file.clear_summaries_flags()

    def log_directory(self, namespace: Namespace):
        self.changed_files_num += 1
        self.changed_directories.add(namespace.name.replace('.', '/'))


class SummariesExecutor(Executor):
    def __init__(self, entity: Entity):
        super().__init__(entity.sources_path, entity.solution_name)
        self.entity = entity

    def add_summaries(self):
        application_path = self.solution_path / 'Application'
        vm_files = application_path.rglob(f'{self.entity.class_name}Vm.cs')
        dto_files = application_path.rglob(f'{self.entity.class_name}Dto.cs')

        for file_path in chain(vm_files, dto_files):
            file = VmDto(file_path)
            file.add_properties_summaries()
            file.add_class_summary()
            if file.substituted_file_text != file.file_text:
                self._log_file(file_path)

        self.output_data()

    def _log_file(self, path: Path):
        posix_dir = path.as_posix()
        path = posix_dir[posix_dir.index('/Application'):]
        self.changed_files_num += 1
        self.changed_directories.add(path)

    def output_data(self):
        print(f'Изменено {self.changed_files_num} файлов:')
        for directory in self.changed_directories:
            print(str(directory).removeprefix(self.solution_name))