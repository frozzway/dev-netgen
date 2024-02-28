from __future__ import annotations
import re
import subprocess
import os
from dataclasses import field
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from collections.abc import Set
from typing import Union

from jinja2 import Environment, PackageLoader, select_autoescape

from devnetgen.pluralize import pluralize

env = Environment(
    loader=PackageLoader('devnetgen'),
    autoescape=select_autoescape(),
    lstrip_blocks=True,
    trim_blocks=True
)

system_namespace = 'System'
generic_collections_namespace = 'System.Collections.Generic'
default_properties = {'int', 'bool', 'float', 'string', 'decimal', 'long', 'DateTime', 'double'}


@dataclass
class File:
    name: str
    content: str


@dataclass
class Property:
    name: str
    _prop_type: str
    _summary: Optional[str]
    file_class: FileClass
    required_namespace: Optional[Namespace] = None

    @property
    def summary(self):
        summary = self._summary
        if self.is_navigation:
            summary = summary.removeprefix('@\n    ')
            match = re.search(r"^/// (?:Навигационное свойство - )?(?:[с|С]ущность)?\s*(.*)", summary)
            if match:
                summary = match.group(1).capitalize()
                if summary.startswith('"'):
                    summary = summary.strip('"').capitalize()
        return summary

    @property
    def is_navigation(self) -> bool:
        return not self.is_enum and self.prop_type not in default_properties

    @property
    def prop_type(self) -> str:
        return self.non_listed_prop_type.removesuffix('?')

    @property
    def is_enum(self) -> bool:
        return self.prop_type in self.file_class.enums_namespace.classes

    @property
    def raw_type(self) -> str:
        return self._prop_type

    @property
    def is_list_generic(self) -> bool:
        return self._prop_type.startswith("List<")

    @property
    def non_listed_prop_type(self) -> Optional[str]:
        if self.is_list_generic:
            return re.search(r"List<(.*)>", self._prop_type).group(1)
        return self._prop_type


@dataclass
class Namespace:
    name: str
    classes: set[str] = field(default_factory=set)
    path: Optional[Path] = None

    @property
    def last_name_part(self):
        return self.name.split('.')[-1:][0]

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, Namespace):
            return self.name == other.name
        return False


class NamespaceCollection(Set):

    def __init__(self):
        self.namespaces = set()
        self._last_found = None

    def __iter__(self):
        return self.namespaces.__iter__()

    def __contains__(self, item: Union[str, Namespace]):
        if isinstance(item, Namespace):
            return item in self.namespaces

        for namespace in self.namespaces:
            if item in namespace.classes:
                self._last_found = namespace
                return True
        return False

    def __len__(self):
        return len(self.namespaces)

    def add(self, namespace: Namespace):
        self.namespaces.add(namespace)

    @property
    def last_found(self) -> Namespace:
        return self._last_found


class FileClass:
    def __init__(self, path: Union[str, Path], factory_property=None):
        self.factory_property = factory_property
        self.file_text = None
        self.file_lines = None
        self.solution_name = None
        self.namespace = None
        self.enums_namespace = None
        self.properties: Optional[list[Property]] = None
        self.class_summary = None
        self.upper_namespaces = NamespaceCollection()
        self.used_entities_namespaces = NamespaceCollection()
        self.required_solution_namespaces = NamespaceCollection()
        self.required_system_namespaces = NamespaceCollection()
        self.included_files: set[FileClass] = set()

        self.file_path = Path(path)
        self.class_name = self.file_path.name.removesuffix('.cs')
        self.pluralized_class_name = pluralize(self.class_name)
        str_path = str(path)
        self.solution_path = Path(str_path[:str_path.index('Domain')])

        self.read_file()
        self.index_self_namespace()
        self.get_class_summary()
        self.extract_properties()
        self.index_used_namespaces()
        self.fill_required_namespaces()
        self.calculate_included_files()

    @property
    def validation_properties(self):
        return [p for p in self.properties if p.prop_type == 'string' or p.is_enum]

    def __repr__(self):
        return f'{self.class_name}, {id(self)}'

    def read_file(self):
        with open(self.file_path, "r", encoding='utf-8') as file:
            self.file_lines = file.readlines()
            self.file_text = ''.join(self.file_lines)

    def index_self_namespace(self):
        regex = r"^namespace ([^;]*);"
        namespace = re.search(regex, self.file_text, re.MULTILINE).group(1)
        namespace_parts = namespace.split('.')
        self.solution_name = namespace_parts[0]
        self.namespace = self.get_namespace_obj(namespace)
        self.enums_namespace = self.get_namespace_obj(f'{self.solution_name}.Domain.Enums')
        prev_part = self.solution_name
        for i in range(1, len(namespace_parts) - 1):
            prev_part += '.' + namespace_parts[i]
            namespace_obj = self.get_namespace_obj(prev_part)
            self.upper_namespaces.add(namespace_obj)

    def get_class_summary(self):
        regex = r"namespace [^;]*;\s*/// <summary>\s*/// ((?:.|\n)*?)\s*/// </summary>"
        if match := re.search(regex, self.file_text, re.MULTILINE):
            self.class_summary = match.group(1)

    def extract_properties(self):
        class_body_lines = self.get_body_lines()
        class_body_text = ''.join(class_body_lines)
        regex = re.compile(
            r"(?:<summary>\s*(?P<summary>(?:.|\n)*?)\s*/// </summary>\s*)?public (?P<type>[^\s]+)\s(?P<name>[^\s]+)(?=\s\{ ?get;)",
            re.S)
        matches = regex.finditer(class_body_text)

        properties = [
            Property(name=match.group('name'), _prop_type=match.group('type'), _summary=match.group('summary'),
                     file_class=self)
            for match in matches
        ]

        self.properties = list(filter(self.filter_property, properties))

    def get_body_lines(self) -> list[str]:
        start_line = 0
        for i, line in enumerate(self.file_lines):
            if line.find(f'public class {self.class_name}') != -1:
                start_line = i + 1
                break
        return self.file_lines[start_line:]

    @staticmethod
    def filter_property(prop: Property) -> bool:
        summary = prop._summary
        if summary:
            if summary.startswith("!"):
                return False
            if summary.startswith("@"):
                return True

        return not prop.is_navigation

    def get_namespace_obj(self, namespace: str) -> Namespace:
        directory = Path(self.solution_path) / namespace.removeprefix(f'{self.solution_name}.').replace('.', '/')
        directory.mkdir(parents=True, exist_ok=True)
        classes = (file.name.removesuffix('.cs') for file in directory.iterdir() if
                   file.is_file() and file.name.endswith('.cs'))
        return Namespace(name=namespace, classes=set(classes), path=directory)

    def index_used_namespaces(self):
        regex = re.compile(r"using (" + re.escape(self.solution_name) + r"\.Domain\..*);")
        matches = regex.finditer(self.file_text)
        for match in matches:
            namespace = match.group(1)
            namespace_obj = self.get_namespace_obj(namespace)
            self.used_entities_namespaces.add(namespace_obj)

    def fill_required_namespaces(self):
        for prop in self.properties:
            prop_type = prop.prop_type

            if prop.is_list_generic:
                self.required_system_namespaces.add(Namespace(generic_collections_namespace))

            if prop_type == 'DateTime':
                self.required_system_namespaces.add(Namespace(system_namespace))

            if prop.is_navigation:
                namespace = None

                if prop_type in self.used_entities_namespaces:
                    namespace = self.used_entities_namespaces.last_found
                elif prop_type in self.upper_namespaces:
                    namespace = self.upper_namespaces.last_found
                elif prop_type in self.namespace.classes:
                    namespace = self.namespace

                if namespace:
                    prop.required_namespace = namespace

            if prop.is_enum:
                self.required_solution_namespaces.add(self.enums_namespace)

        self.required_solution_namespaces.add(self.namespace)

    def calculate_included_files(self):
        for prop in self.properties:
            if prop.is_navigation and prop.required_namespace:
                if namespace_path := prop.required_namespace.path:
                    file = FileClass(namespace_path / f'{prop.prop_type}.cs', factory_property=prop)
                    self.included_files.add(file)

    def _create_template(self, target_namespace: str, template: str, for_update: bool, ientity: bool = False) -> File:
        template = env.get_template(template)
        output = template.render(
            file=self,
            target_namespace=target_namespace,
            for_update=for_update,
            ientity=ientity)
        return File(self.class_name, output)

    def create_templates(self, target_namespace: str, template: str, for_update: bool = False, ientity: bool = False) -> list[File]:
        storage = []
        self._recursive_create_templates(target_namespace, template, for_update, storage)
        storage[0] = self._create_template(target_namespace, template, for_update, ientity)
        return storage

    def _recursive_create_templates(self, target_namespace: str, template: str, for_update: bool, storage: list):
        self_template = self._create_template(target_namespace, template, for_update)
        storage.append(self_template)
        for file in self.included_files:
            file._recursive_create_templates(target_namespace, template, for_update, storage)


class Executor:
    def __init__(self, obj: FileClass):
        self.entity = obj
        self.target_application_namespace = None
        self.target_webui_namespace = None
        self.mediator = True
        self.webapi = False
        self.command_namespaces = None
        self.sieve = False

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

    def create_dto(self, legacy_controller: bool = False):
        self._extract_meta()
        self._calculate_namespaces()
        self._create_template_files()
        self._write_controller(legacy_controller)

    def _calculate_namespaces(self):
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
        self.target_application_namespace = self.entity.get_namespace_obj(namespace_name + f'.{self.entity.pluralized_class_name}')

        webui_posix = webui_path.as_posix()
        prefix = '/WebApi' if self.webapi else '/WebUI'
        namespace_name = self.entity.solution_name + webui_posix[webui_posix.index(prefix):].replace('/', '.')
        self.target_webui_namespace = self.entity.get_namespace_obj(namespace_name)

    def _extract_meta(self):
        with open(self.entity.solution_path / 'Application' / 'Application.csproj', "r", encoding='utf-8') as file:
            text = file.read()
            if 'MediatR' in text:
                self.mediator = False

        if (self.entity.solution_path / 'WebApi').exists():
            self.webapi = True

        if (self.entity.solution_path / 'Application' / 'Common' / 'Services' / 'SieveService.cs').exists():
            self.sieve = True

    def _create_template_files(self):
        namespace_outputs: list[tuple[Namespace, list[File], str, str, str]] = []

        create_command_namespace = self.entity.get_namespace_obj(f'{self.target_application_namespace.name}.Commands.Create{self.entity.class_name}')
        update_command_namespace = self.entity.get_namespace_obj(f'{self.target_application_namespace.name}.Commands.Update{self.entity.class_name}')
        delete_command_namespace = self.entity.get_namespace_obj(f'{self.target_application_namespace.name}.Commands.Delete{self.entity.class_name}')

        create_dto_outputs = self.entity.create_templates(create_command_namespace.name, self.dto_template, for_update=False)
        update_dto_outputs = self.entity.create_templates(update_command_namespace.name, self.dto_template, for_update=True)

        get_entity_query_namespace = self.entity.get_namespace_obj(f'{self.target_application_namespace.name}.Queries.Get{self.entity.class_name}')
        get_entities_query_namespace = self.entity.get_namespace_obj(f'{self.target_application_namespace.name}.Queries.Get{self.entity.pluralized_class_name}')
        get_grid_query_namespace = self.entity.get_namespace_obj(f'{self.target_application_namespace.name}.Queries.Get{self.entity.class_name}Grid')

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

            template = env.get_template(command_template)
            output = template.render(file=self.entity,
                                     target_namespace=namespace.name,
                                     sieve=self.sieve,
                                     **self._get_template_vars()['mediator'])

            command_name = f"{namespace.last_name_part}{command_type}"
            filepath = namespace.path / f'{command_name}.cs'
            if not filepath.exists():
                with open(filepath, "w", encoding='utf-8') as file:
                    file.write(output)

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
        namespace.path.mkdir(parents=True, exist_ok=True)
        filepath = namespace.path / f'{namespace.last_name_part}CommandValidator.cs'
        if filepath.exists():
            return
        template = env.get_template(self.validator_template)
        output = template.render(file=self.entity, action=action, target_namespace=namespace.name)
        with open(filepath, "w", encoding='utf-8') as file:
            file.write(output)

    @staticmethod
    def add_to_git(directory_path: Path):
        directory_str = str(directory_path)
        os.chdir(directory_str)
        subprocess.run(["git", "add", '.'])

    def _get_template_vars(self):
        mediator_data = {
            "mediator_lib": 'Mediator' if self.mediator else 'MediatR',
            "return_value": 'ValueTask' if self.mediator else 'Task'
        }
        return {
            'mediator': mediator_data,
            'webui': 'WebApi' if self.webapi else 'WebUI'
        }

    def _write_controller(self, legacy_controller: bool):
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
            sieve=self.sieve,
            **template_vars['mediator'],
            **self.command_namespaces)

        with open(filepath, "w", encoding='utf-8') as file:
            file.write(output)

        self.add_to_git(self.target_webui_namespace.path)
