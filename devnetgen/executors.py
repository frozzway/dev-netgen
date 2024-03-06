import os
import re
import subprocess

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from itertools import chain

from devnetgen.entities import Namespace, Entity, VmDto, File
from devnetgen.config import env


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
    def __init__(self, solution_path, solution_name):
        self.solution_path = solution_path
        self.solution_name = solution_name
        self.meta = SolutionMeta()
        self.changed_directories = set()
        self.changed_files_num = 0

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
        entity: сущность типа FileClass для которой создаются элементы
        target_application_namespace: неполный (базовый) объект Namespace /Application/Work/..
        target_webui_namespace: неполный (базовый) объект Namespace /Application/Work/..
        command_namespaces: пространства имен команд и запросов
    """
    def __init__(self, obj: Entity):
        super().__init__(obj.solution_path, obj.solution_name)

        self.entity = obj
        self.target_application_namespace = None
        self.target_webui_namespace = None
        self.command_namespaces = None

        self.dto_template = 'DtoTemplate.cs.j2'
        self.vm_template = 'VmTemplate.cs.j2'
        self.validator_template = 'Validator.cs.j2'
        self.create_command_template = 'CreateCommand.cs.j2'
        self.delete_command_template = 'DeleteCommand.cs.j2'
        self.update_command_template = 'UpdateCommand.cs.j2'
        self.query_entity_template = 'GetEntityQuery.cs.j2'
        self.query_entities_template = 'GetEntitiesQuery.cs.j2'
        self.query_entity_grid_template = 'GetEntityGridQuery.cs.j2'
        self.controller_template = 'Controller.cs.j2'
        self.legacy_controller_template = 'LegacyController.cs.j2'

    def create_all(self, legacy_controller: bool = False):
        """
        Сгенерировать и записать на диск CRUD, файл контроллера и вывести результат в stdout
        :param legacy_controller: флаг для генерации файла контроллера в legacy проектах
        """
        self._extract_meta()
        self._calculate_namespaces()
        self._create_template_files()
        self._write_controller(legacy_controller)
        self.cleanup_files()
        self.output_data()

    def _calculate_namespaces(self):
        """ Определить базовые директории генерации файлов и соответствующие неполные неймспейсы"""
        controller_path = next(self.entity.solution_path.glob('**/Controllers'))

        if match := re.search("^.*References?(.*)", self.entity.namespace.name):
            target = match.group(1)

            application_path_results = tuple((self.entity.solution_path / 'Application').glob('**/References'))
            if len(application_path_results) == 0:
                application_path_results = tuple((self.entity.solution_path / 'Application').glob('**/Reference'))
            application_path = application_path_results[0] / target.removeprefix('.').replace('.', '/')

            webui_path_results = tuple(controller_path.glob('**/References'))
            if len(application_path_results) == 0:
                webui_path_results = tuple(controller_path.glob('**/Reference'))
            webui_path = webui_path_results[0] / target.removeprefix('.').replace('.', '/')

        else:
            target = re.search("^.*Entities(.*)", self.entity.namespace.name).group(1)

            application_path = self.entity.solution_path / 'Application' / 'Work' / target.removeprefix('.').replace('.', '/')
            webui_path = controller_path / 'Work' / target.removeprefix('.').replace('.', '/')

        application_posix = application_path.as_posix()
        namespace_name = self.entity.solution_name + application_posix[application_posix.index('/Application'):].replace('/', '.')
        self.target_application_namespace = self.entity._get_namespace_obj(namespace_name + f'.{self.entity.pluralized_class_name}')

        webui_posix = webui_path.as_posix()
        prefix = '/WebApi' if self.meta.webapi else '/WebUI'
        namespace_name = self.entity.solution_name + webui_posix[webui_posix.index(prefix):].replace('/', '.')
        self.target_webui_namespace = self.entity._get_namespace_obj(namespace_name)

    def _create_template_files(self):
        """ Сгенерировать и записать на диск CRUD сущности """
        namespace_outputs: list[tuple[Namespace, list[File], str, str, str]] = []

        create_command_namespace = self.entity._get_namespace_obj(f'{self.target_application_namespace.name}.Commands.Create{self.entity.class_name}')
        update_command_namespace = self.entity._get_namespace_obj(f'{self.target_application_namespace.name}.Commands.Update{self.entity.class_name}')
        delete_command_namespace = self.entity._get_namespace_obj(f'{self.target_application_namespace.name}.Commands.Delete{self.entity.class_name}')

        create_dto_outputs = self.entity.create_templates(create_command_namespace.name, self.dto_template, for_update=False)
        update_dto_outputs = self.entity.create_templates(update_command_namespace.name, self.dto_template, for_update=True)

        get_entity_query_namespace = self.entity._get_namespace_obj(f'{self.target_application_namespace.name}.Queries.Get{self.entity.class_name}')
        get_entities_query_namespace = self.entity._get_namespace_obj(f'{self.target_application_namespace.name}.Queries.Get{self.entity.pluralized_class_name}')
        get_grid_query_namespace = self.entity._get_namespace_obj(f'{self.target_application_namespace.name}.Queries.Get{self.entity.class_name}Grid')

        get_vm_outputs = self.entity.create_templates(get_entity_query_namespace.name, self.vm_template, ientity=True)
        get_list_vm_outputs = self.entity.create_templates(get_entities_query_namespace.name, self.vm_template)
        get_grid_vm_outputs = self.entity.create_templates(get_grid_query_namespace.name, self.vm_template)

        namespace_outputs.extend([
            (create_command_namespace, create_dto_outputs, 'Dto.cs', self.create_command_template, 'Command'),
            (update_command_namespace, update_dto_outputs, 'Dto.cs', self.update_command_template, 'Command'),
            (delete_command_namespace, [], '', self.delete_command_template, 'Command'),
            (get_entity_query_namespace, get_vm_outputs, 'Vm.cs', self.query_entity_template, 'Query'),
            (get_entities_query_namespace, get_list_vm_outputs, 'Vm.cs', self.query_entities_template, 'Query'),
            (get_grid_query_namespace, get_grid_vm_outputs, 'Vm.cs', self.query_entity_grid_template, 'Query')
        ])

        self._write_validator(create_command_namespace, 'Create')
        self._write_validator(update_command_namespace, 'Update')

        for namespace, outputs, suffix, command_template, command_type in namespace_outputs:
            namespace.path.mkdir(parents=True, exist_ok=True)

            for output in outputs:
                filepath = namespace.path / f"{output.name}{suffix}"
                if filepath.exists():
                    continue
                with open(filepath, "w", encoding='utf-8') as file:
                    file.write(output.content)
                    self._log_directory(namespace)

            template = env.get_template(command_template)
            output = template.render(file=self.entity,
                                     target_namespace=namespace.name,
                                     sieve=self.meta.sieve,
                                     **self._get_template_vars()['mediator'])

            command_name = f"{namespace.last_name_part}{command_type}"
            filepath = namespace.path / f'{command_name}.cs'
            if not filepath.exists():
                with open(filepath, "w", encoding='utf-8') as file:
                    file.write(output)
                    self._log_directory(namespace)

            self.add_to_git(namespace.path)

        self.command_namespaces = {
            'create_namespace': create_command_namespace,
            'update_namespace': update_command_namespace,
            'delete_namespace': delete_command_namespace,
            'get_namespace': get_entity_query_namespace,
            'get_list_namespace': get_entities_query_namespace,
            'get_grid_namespace': get_grid_query_namespace
        }

    def _write_validator(self, namespace: Namespace, action: str):
        """
        Сгенерировать и записать на диск файл валидатора
        :param namespace: пространство имен команды, для которой генерируется валидатор
        :param action: Update или Create
        """
        namespace.path.mkdir(parents=True, exist_ok=True)
        filepath = namespace.path / f'{namespace.last_name_part}CommandValidator.cs'
        if filepath.exists():
            return
        template = env.get_template(self.validator_template)
        output = template.render(file=self.entity, action=action, target_namespace=namespace.name)
        with open(filepath, "w", encoding='utf-8') as file:
            file.write(output)
            self._log_directory(namespace)

    @staticmethod
    def add_to_git(directory_path: Path):
        """ Добавить все файлы директории в git """
        directory_str = str(directory_path)
        os.chdir(directory_str)
        subprocess.run(["git", "add", '.'])

    def _get_template_vars(self):
        mediator_data = {
            "mediator_lib": 'Mediator' if self.meta.mediator else 'MediatR',
            "return_value": 'ValueTask' if self.meta.mediator else 'Task'
        }
        return {
            'mediator': mediator_data,
            'webui': 'WebApi' if self.meta.webapi else 'WebUI'
        }

    def _write_controller(self, legacy_controller: bool):
        """
        Сгенерировать и записать на диск файл контроллера
        :param legacy_controller: флаг для генерации файла контроллера в legacy проектах
        """
        filepath = self.target_webui_namespace.path / f'{self.entity.class_name}Controller.cs'
        if filepath.exists():
            return

        template_vars = self._get_template_vars()
        if legacy_controller:
            template = env.get_template(self.legacy_controller_template)
        else:
            template = env.get_template(self.controller_template)
        output = template.render(
            file=self.entity,
            target_namespace=self.target_webui_namespace.name,
            webui=template_vars['webui'],
            command_namespaces=self.command_namespaces.values(),
            sieve=self.meta.sieve,
            **template_vars['mediator'],
            **self.command_namespaces)

        with open(filepath, "w", encoding='utf-8') as file:
            file.write(output)
            self._log_directory(self.target_webui_namespace)

        self.add_to_git(self.target_webui_namespace.path)

    def cleanup_files(self):
        """ Очистить '!' и '@' из summaries свойств всех задействованных сущностей """
        self.entity.clear_summaries_flags()
        for file in self.entity.included_files:
            file.clear_summaries_flags()

    def _log_directory(self, namespace: Namespace):
        self.changed_files_num += 1
        self.changed_directories.add(namespace.name.replace('.', '/'))


class SummariesExecutor(Executor):
    def __init__(self, obj: Entity):
        super().__init__(obj.solution_path, obj.solution_name)
        self.entity = obj

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