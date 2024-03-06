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
from rich import print

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


@dataclass
class File:
    """ Объект с содержанием Vm/Dto и наименованием результирующего файла """
    name: str
    content: str


@dataclass
class Property:
    """
    Свойство сущности

    Attributes:
        name: имя свойства
        _prop_type: тип свойства
        _summary: описание свойства
        required_namespace: объект Namespace, в котором содержится тип свойства
        file_class: ссылка на класс сущности
    """
    name: str
    _prop_type: str
    _summary: Optional[str]
    file_class: EntityClass
    required_namespace: Optional[Namespace] = None

    @property
    def summary(self) -> Optional[str]:
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
        """ Проверка, является ли навигационным свойством """
        return not self.is_enum and self.prop_type not in default_properties

    @property
    def prop_type(self) -> str:
        return self.non_listed_prop_type.removesuffix('?')

    @property
    def is_enum(self) -> bool:
        """ Проверка, является ли тип свойства перечислением """
        return self.prop_type in self.file_class.enums_namespace.classes

    @property
    def raw_type(self) -> str:
        return self._prop_type

    @property
    def is_list_generic(self) -> bool:
        return self._prop_type.startswith("List<")

    @property
    def non_listed_prop_type(self) -> Optional[str]:
        """ Тип свойства, извлеченный из List<*> """
        if self.is_list_generic:
            return re.search(r"List<(.*)>", self._prop_type).group(1)
        return self._prop_type


@dataclass
class Namespace:
    """ Пространство имени """
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
    """ Коллекция для пространств имён (множество) """
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


class BaseEntityClass:
    """
    Базовый класс представления c#-класса сущности или её Vm/Dto

    Attributes:
        enums_namespace: объект типа Namespace под енамы
        file_path: абсолютный путь до файла сущности (объект Path)
        class_name: имя класса (пр. "Appeal")
        namespace: объект типа Namespace сущности
        solution_name: наименование решения (пр. "MinstroyGasDistributionNetworks")
        solution_path: абсолютный путь решения, объект Path (пр. "/home/alex/Documents/RiderProjects/MinstroyGasDistributionNetworks")
        used_entities_namespaces: использованные в коде сущности пространства имён, относящиеся к сущностям в Domain
        properties: список извлеченных из класса свойств типа Property
    """
    def __init__(self, path: Union[str, Path]):
        self.file_text = ''
        self.file_lines = None
        self.namespace = None
        self.enums_namespace = None
        self.solution_name = None
        self.solution_path = None
        self.used_entities_namespaces = NamespaceCollection()
        self.properties: Optional[list[Property]] = None

        self.file_path = Path(path)
        self.class_name = self.file_path.name.removesuffix('.cs')

        self._read_file()

    def _read_file(self):
        with open(self.file_path, "r", encoding='utf-8') as file:
            self.file_lines = file.readlines()
            self.file_text = ''.join(self.file_lines)

    def _get_body_lines(self) -> list[str]:
        """
        :return: строки файла, начиная с тела класса сущности
        """
        start_line = 0
        for i, line in enumerate(self.file_lines):
            if line.find(f'public class {self.class_name}') != -1:
                start_line = i + 1
                break
        return self.file_lines[start_line:]

    def _index_self_namespace(self):
        """
        Определить наименование решения и вычислить Namespace сущности и файлов Enum
        """
        regex = r"^namespace ([^;{]*)(?:;|\n)"
        namespace = re.search(regex, self.file_text, re.MULTILINE).group(1)
        namespace_parts = namespace.split('.')
        self.solution_name = namespace_parts[0]
        self.namespace = self._get_namespace_obj(namespace)
        self.enums_namespace = self._get_namespace_obj(f'{self.solution_name}.Domain.Enums')

    def _get_namespace_obj(self, namespace: str) -> Namespace:
        """
        Сформировать объект Namespace, вычисляя абсолютный путь до директории и все лежащие в ней классы
        :param namespace: строка namespace
        :return: Объект Namespace
        """
        directory = Path(self.solution_path) / namespace.removeprefix(f'{self.solution_name}.').replace('.', '/')
        directory.mkdir(parents=True, exist_ok=True)
        classes = (file.name.removesuffix('.cs') for file in directory.iterdir() if
                   file.is_file() and file.name.endswith('.cs'))
        return Namespace(name=namespace, classes=set(classes), path=directory)

    def _index_used_namespaces(self):
        """
        Вычислить объекты Namespace для использованных в коде сущности Namespace
        """
        regex = re.compile(r"using (" + re.escape(self.solution_name) + r"\.Domain\..*);")
        matches = regex.finditer(self.file_text)
        for match in matches:
            namespace = match.group(1)
            namespace_obj = self._get_namespace_obj(namespace)
            self.used_entities_namespaces.add(namespace_obj)


class VmDtoClass(BaseEntityClass):
    """
    Класс представления Vm/Dto

    Attributes:
        base_entity: сущность в которую/от которой маппится vm/dto
        substituted_file_text: замененный текст файла на содержащий summaries
        tabs: отступ перед 'public ...'
    """
    def __init__(self, path: Union[str, Path]):
        super().__init__(path)

        self.base_entity: Optional[EntityClass] = None
        self.substituted_file_text = self.file_text
        self.tabs = 8

        str_path = str(path)
        self.solution_path = Path(str_path[:str_path.index('Application')])

        self._index_self_namespace()
        self._index_used_namespaces()
        self._get_base_entity()
        self._extract_meta()

    def _extract_meta(self):
        """ Определить отступы """
        regex = r'^namespace ([^;{]*);'
        file_scoped_namespace = re.search(regex, self.file_text, re.MULTILINE)
        if file_scoped_namespace:
            self.tabs = 4

    def _get_base_entity(self):
        """ Определить сущность в которую/от которой маппится vm/dto """
        regex = r"IMap(?:From|To)<(.*)>"
        if match := re.search(regex, self.file_text, re.MULTILINE):
            entity_name = match.group(1)
        else:
            regex = r"profile\.CreateMap<(.*),(?:.*)>"
            entity_name = re.search(regex, self.file_text, re.MULTILINE).group(1).removesuffix('Dto').removesuffix('Vm')

        if entity_name not in self.used_entities_namespaces:
            raise FileNotFoundError(f"No such entity: {entity_name}")

        namespace = self.used_entities_namespaces.last_found
        self.base_entity = EntityClass(namespace.path / f'{entity_name}.cs', filter_properties=False)

    def add_properties_summaries(self):
        """ Внести комментарии к свойствам vm/dto из базовой сущности """
        class_body_lines = self._get_body_lines()
        class_body_text = ''.join(class_body_lines)
        regex = re.compile(r"(?:<summary>\s*(?P<summary>(?:.|\n)*?)\s*/// </summary>\s*)?(?P<attributes>(?:\[.+]\s*)+)?\s*public (?P<type>[^\s]+)\s(?P<name>[^\s]+)(?=\s\{ ?get;)")

        matches = regex.finditer(class_body_text)

        for match in matches:
            if match.group('summary'):
                continue
            t = self.tabs
            name = match.group('name')
            prop: Optional[Property] = next(filter(lambda p: p.name == match.group('name'), self.base_entity.properties), None)
            if prop and prop.summary or name == 'Id':
                summary = prop.summary if prop else '/// Идентификатор'
                added_summary = ' '*t + '/// <summary>\n' + ' '*t + summary + '\n' + ' '*t + '/// </summary>\n'
                quantifier = f'{{{self.tabs}}}'
                regex = rf"(?P<nl>}}\n)?(?P<emptylines>(?: {{,{self.tabs}}}\n)*)?(?: {quantifier})?(?P<attributes>(?:\[.+]\s*)+)?(?P<beginning> {quantifier}public [^\s]+\s)" + re.escape(name) + r'(?P<ending>.*)'
                substituted = r'\g<nl>' + '\n' + added_summary + r'\g<beginning>' + name + r'\g<ending>'
                if attrs := match.group('attributes'):
                    attrs = attrs.strip()
                    substituted = r'\g<nl>' + '\n' + added_summary + ' '*t + attrs + '\n' + r'\g<beginning>' + name + r'\g<ending>'
                self.substituted_file_text = re.sub(regex, substituted, self.substituted_file_text)

        self.substituted_file_text = re.sub(r'{\n\n', r'{\n', self.substituted_file_text)
        self._write_substituted_file()

    def add_class_summary(self):
        """ Добавить описание классу vm/dto """
        regex = rf'(?<!/// </summary>\n){" "*(self.tabs-4)}public class '
        if re.search(regex, self.file_text, re.MULTILINE):
            if summary := self.base_entity.class_summary:
                if self.class_name.endswith('Vm'):
                    summary = (f'{" "*(self.tabs-4)}/// <summary>\n'
                               f'{" "*(self.tabs-4)}/// Модель отображения сущности "{summary}"\n'
                               f'{" "*(self.tabs-4)}/// </summary>\n')
                elif self.class_name.endswith('Dto'):
                    summary = (f'{" "*(self.tabs-4)}/// <summary>\n'
                               f'{" "*(self.tabs-4)}/// Объект передачи данных для сущности "{summary}"\n'
                               f'{" "*(self.tabs-4)}/// </summary>\n')
                substituted = summary + f'{" "*(self.tabs-4)}public class '
                self.substituted_file_text = re.sub(regex, substituted, self.substituted_file_text)

        self._write_substituted_file()

    def _write_substituted_file(self):
        with open(self.file_path, mode='w', encoding='utf-8') as file:
            file.write(self.substituted_file_text)


class EntityClass(BaseEntityClass):
    """
    Класс представления сущности.

    Attributes:
        properties: список извлеченных из сущности свойств типа Property
        class_summary: summary самой сущности
        upper_namespaces: коллекция NamespaceCollection для выявления расположения файлов-навигационных свойств сущности, не расположенных непосредственно в директории сущности
        required_solution_namespaces: необходимые для декларирования в файлах vm/dto пространства имён
        required_system_namespaces: необходимые для декларирования в файлах vm/dto пространства имён (системные)
        included_files: набор классов FileClass для vm/dto, которые должны быть созданы помимо vm/dto основной сущности
        pluralized_class_name: имя сущности в мн. числе (пр. "Appeals")
    """
    def __init__(self, path: Union[str, Path], factory_property: Optional[Property] = None, filter_properties: bool = True):
        """
        :param path: абсолютный путь до файла сущности
        :param factory_property: навигационное свойство сущности, на основе которого был инициализирован класс
        :param filter_properties: Отфильтровать свойства сущности в соответствии с флагами '!' и '@"
        """
        super().__init__(path)
        self.factory_property = factory_property
        self.namespace = None
        self.enums_namespace = None
        self.class_summary = None
        self.upper_namespaces = NamespaceCollection()
        self.used_entities_namespaces = NamespaceCollection()
        self.required_solution_namespaces = NamespaceCollection()
        self.required_system_namespaces = NamespaceCollection()
        self.included_files: set[EntityClass] = set()

        self.pluralized_class_name = pluralize(self.class_name)
        str_path = str(path)
        self.solution_path = Path(str_path[:str_path.index('Domain')])

        self._get_class_summary()
        self._index_self_namespace()
        self._index_upper_namespaces()
        self._index_used_namespaces()
        self._extract_properties(filter_properties)
        self._fill_required_namespaces()
        self._calculate_included_files()

    @property
    def validation_properties(self):
        return [p for p in self.properties if p.prop_type == 'string' or p.is_enum]

    def __repr__(self):
        return f'{self.class_name}, {id(self)}'

    def _index_upper_namespaces(self):
        namespace_parts = self.namespace.name.split('.')
        prev_part = self.solution_name
        for i in range(1, len(namespace_parts) - 1):
            prev_part += '.' + namespace_parts[i]
            namespace_obj = self._get_namespace_obj(prev_part)
            self.upper_namespaces.add(namespace_obj)

    def _get_class_summary(self):
        """
        Извлечь summary сущности
        """
        regex = r"/// <summary>\s*/// ((?:.|\n)*?)\s*/// </summary>\s*public class"
        if match := re.search(regex, self.file_text, re.MULTILINE):
            self.class_summary = match.group(1)

    def _extract_properties(self, filter_properties: bool = False):
        """
        Извлечь свойства сущности и относящуюся к ним информацию
        """
        class_body_lines = self._get_body_lines()
        class_body_text = ''.join(class_body_lines)
        regex = re.compile(
            r"(?:<summary>\s*(?P<summary>(?:.|\n)*?)\s*/// </summary>\s*)?(?P<attributes>(?:\[.+]\s*)+)?\s*public (?P<type>[^\s]+)\s(?P<name>[^\s]+)(?=\s\{ ?get;)")
        matches = regex.finditer(class_body_text)

        self.properties = [
            Property(name=match.group('name'), _prop_type=match.group('type'), _summary=match.group('summary'),
                     file_class=self)
            for match in matches
        ]

        if filter_properties:
            self.properties = list(filter(self.filter_property, self.properties))

    @staticmethod
    def filter_property(prop: Property) -> bool:
        summary = prop._summary
        if summary:
            if summary.startswith("!"):
                return False
            if summary.startswith("@"):
                return True

        return not prop.is_navigation

    def _fill_required_namespaces(self):
        """ Определить необходимые пространства имен для файлов vm/dto """
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

    def _calculate_included_files(self):
        """ Сформировать объекты FileClass для каждого из навигационного свойства сущности """
        for prop in self.properties:
            if prop.is_navigation and prop.required_namespace:
                if namespace_path := prop.required_namespace.path:
                    file = EntityClass(namespace_path / f'{prop.prop_type}.cs', factory_property=prop)
                    self.included_files.add(file)

    def _create_template(self, target_namespace: str, template: str, for_update: bool, ientity: bool = False) -> File:
        """
        Сформировать vm/dto по шаблону
        :param target_namespace: пространство имен сформированной vm/dto
        :param template: шаблон vm/dto
        :param for_update: флаг для передачи в шаблон, dto для редактирования сущности
        :param ientity: флаг для передачи в шаблон, реализация интерфейса IEntityWithId у VM
        :return: объект типа File с наименованием и содержанием vm/dto
        """
        template = env.get_template(template)
        output = template.render(
            file=self,
            target_namespace=target_namespace,
            for_update=for_update,
            ientity=ientity)
        return File(self.class_name, output)

    def create_templates(self, target_namespace: str, template: str, for_update: bool = False, ientity: bool = False) -> list[File]:
        """
        Сформировать vm/dto по шаблону для исходной и навигационных сущностей
        :param target_namespace: пространство имен сформированной vm/dto
        :param template: шаблон vm/dto
        :param for_update: флаг для передачи в шаблон, dto для редактирования сущности
        :param ientity: флаг для передачи в шаблон, реализация интерфейса IEntityWithId у VM
        :return: список объектов типа File с наименованиями и содержаниями vm/dto
        """
        storage = []
        self._recursive_create_templates(target_namespace, template, for_update, storage)
        storage[0] = self._create_template(target_namespace, template, for_update, ientity)
        return storage

    def _recursive_create_templates(self, target_namespace: str, template: str, for_update: bool, storage: list):
        self_template = self._create_template(target_namespace, template, for_update)
        storage.append(self_template)
        for file in self.included_files:
            file._recursive_create_templates(target_namespace, template, for_update, storage)

    def clear_summaries_flags(self):
        """ Очистить '!' и '@' из summaries свойств сущности """
        cleaned_text = self.file_text.replace('<summary>!', '<summary>').replace('<summary>@', '<summary>')
        with open(self.file_path, 'w', encoding='utf-8') as file:
            file.write(cleaned_text)


class Executor:
    """
    Класс с методами для создания CRUD'а и файла контроллера сущности

    Attributes:
        entity: сущность типа FileClass для которой создаются элементы
        target_application_namespace: неполный (базовый) объект Namespace /Application/Work/..
        target_webui_namespace: неполный (базовый) объект Namespace /Application/Work/..
        meta: мета-информация о проекте
        command_namespaces: пространства имен команд и запросов
        changed_directories: директории, в которых сгенерированы файлы
        created_files_num: число сгенерированных файлов
    """
    def __init__(self, obj: EntityClass):
        self.entity = obj
        self.target_application_namespace = None
        self.target_webui_namespace = None
        self.meta = SolutionMeta()
        self.command_namespaces = None
        self.changed_directories = set()
        self.created_files_num = 0

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

    def _extract_meta(self):
        """ Извлечь мета-информацию, необходимую для генерации """
        self.meta.webapi = (self.entity.solution_path / 'WebApi').exists()
        self.meta.sieve = (self.entity.solution_path / 'Application' / 'Common' / 'Services' / 'SieveService.cs').exists()

        with open(self.entity.solution_path / 'Application' / 'Application.csproj', "r", encoding='utf-8') as file:
            text = file.read()
            self.meta.mediator = 'MediatR' not in text

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

    def _log_directory(self, namespace: Namespace):
        self.created_files_num += 1
        self.changed_directories.add(namespace.name.replace('.', '/'))

    def output_data(self):
        print(f'Сгенерировано {self.created_files_num} файлов в директориях:')
        for directory in self.changed_directories:
            print(str(directory).removeprefix(self.entity.solution_name))

    def cleanup_files(self):
        """ Очистить '!' и '@' из summaries свойств всех задействованных сущностей """
        self.entity.clear_summaries_flags()
        for file in self.entity.included_files:
            file.clear_summaries_flags()
