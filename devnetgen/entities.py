from __future__ import annotations
import re
from dataclasses import field
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from collections.abc import Set
from typing import Union

from devnetgen.pluralize import pluralize

system_namespace = 'System'
generic_collections_namespace = 'System.Collections.Generic'
default_properties = {'int', 'bool', 'float', 'string', 'decimal', 'long', 'short', 'double'}
system_properties = {'DateTime', 'DateOnly', 'DateTimeOffset'}
default_properties.update(system_properties)


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
    file_class: Entity
    required_namespace: Optional[Namespace] = None

    @property
    def summary(self) -> Optional[str]:
        summary = self._summary
        if summary:
            if not self.file_class.vm or self.file_class.vm.tabs == 4:
                summary = summary.replace(' '*8, ' '*4)
            if self.file_class.vm and self.file_class.vm.tabs == 8 and self.file_class.tabs == 4:
                summary = summary.replace(' '*4, ' '*8)
        if self.is_navigation:
            summary = summary.removeprefix('@\n    ').removeprefix('    ')
            match = re.search(r"^/// (?:Навигационное свойство - )?(?:[с|С]ущность)?\s*(.*)", summary, re.S)
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
        return any(self.prop_type in namespace.classes for namespace in self.file_class.enums_namespaces)

    @property
    def raw_type(self) -> str:
        return self._prop_type

    @property
    def is_nullable(self) -> bool:
        return self._prop_type.endswith('?') or self.non_listed_prop_type.endswith('?')

    @property
    def to_validate(self) -> bool:
        return any([
            self.is_enum,
            self.prop_type == 'string',
            all([not self.is_nullable, self.prop_type == 'long', self.name.endswith('Id')])
        ])

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


class BaseEntity:
    """
    Базовый класс представления c#-класса сущности или её Vm/Dto

    Attributes:
        tabs: отступы перед 'public ...'
        file_text: содержимое файла сущности
        file_lines: содержимое файла сущности построчно
        file_path: абсолютный путь до файла сущности (объект Path)
        class_name: имя класса (пр. "Appeal")
        namespace: объект типа Namespace сущности
        enums_namespaces: объекты типа Namespace под енамы
        solution_name: наименование решения (пр. "MinstroyGasDistributionNetworks")
        sources_path: абсолютный путь решения, объект Path (пр. "/home/alex/Documents/RiderProjects/MinstroyGasDistributionNetworks")
        used_entities_namespaces: использованные в коде сущности пространства имён, относящиеся к сущностям в Domain
        properties: список извлеченных из класса свойств типа Property
    """
    tabs: int = 8
    file_text: str
    file_lines: list[str]
    file_path: Path
    class_name: str
    namespace: Namespace
    enums_namespaces: set[Namespace]
    solution_name: str
    sources_path: Path
    used_entities_namespaces: NamespaceCollection
    properties: list[Property]

    def __init__(self, path: str | Path):
        self.used_entities_namespaces = NamespaceCollection()

        self.file_path = Path(path)
        self.class_name = self.file_path.name.removesuffix('.cs')

        self._read_file()
        self._extract_tabs()

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
        self.solution_name = self._find_sln_file(self.file_path) or namespace_parts[0]
        self.namespace = self.get_namespace_obj(namespace)
        self.enums_namespaces = self._index_enums_namespaces(f'{self.solution_name}.Domain.Enums')

    @staticmethod
    def _find_sln_file(start_path: Path):
        current_path = start_path.resolve()

        while True:
            for file in current_path.glob('*.sln'):
                return file.stem
            if current_path.parent == current_path:
                break
            current_path = current_path.parent

        return None

    def _index_enums_namespaces(self, base_namespace: str) -> set[Namespace]:
        """
        Сформировать набор объектов Namespace для Enum'ов
        :param base_namespace: пространство имен до корня директории с Enums
        :return: множество объектов Namespace для Enum'ов
        """
        namespaces: set[Namespace] = set()
        base_enum_directory = Path(self.sources_path) / base_namespace.removeprefix(f'{self.solution_name}.').replace('.', '/')
        enum_directories = [d for d in base_enum_directory.rglob('*') if d.is_dir()]
        enum_directories.append(base_enum_directory)
        for directory in enum_directories:
            target_index = directory.parts.index('Enums')
            sub_namespace = '.'.join(directory.parts[target_index + 1:])
            namespace = base_namespace + '.' + sub_namespace
            namespaces.add(self.get_namespace_obj(namespace))
        return namespaces

    def get_namespace_obj(self, namespace: str, for_tests: bool = False) -> Namespace:
        """
        Сформировать объект Namespace, вычисляя абсолютный путь до директории и все лежащие в ней классы
        :param namespace: строка namespace
        :param for_tests: вычисление для генерации тестов
        :return: Объект Namespace
        """
        root_dir = self.sources_path if not for_tests else self.tests_path
        end_dir = namespace.removeprefix(f'{self.solution_name}.').replace('.', '/')
        if for_tests:
            end_dir = end_dir.replace("Application/IntegrationTests", "Application.IntegrationTests")
        directory = Path(root_dir) / end_dir
        directory.mkdir(parents=True, exist_ok=True)
        classes = (file.name.removesuffix('.cs') for file in directory.iterdir() if
                   file.is_file() and file.name.endswith('.cs'))
        return Namespace(name=namespace, classes=set(classes), path=directory)

    @property
    def tests_path(self) -> Path:
        return Path(self.sources_path.as_posix()
                    .replace("src", "tests")
                    .replace("source", "tests")
                    .replace("sources", "tests"))

    def _index_used_namespaces(self):
        """
        Вычислить объекты Namespace для использованных в коде сущности Namespace
        """
        regex = re.compile(r"using (" + re.escape(self.solution_name) + r"\.Domain\..*);")
        matches = regex.finditer(self.file_text)
        for match in matches:
            namespace = match.group(1)
            namespace_obj = self.get_namespace_obj(namespace)
            self.used_entities_namespaces.add(namespace_obj)

    def _extract_tabs(self):
        """ Определить отступы """
        regex = r'^namespace ([^;{]*);'
        file_scoped_namespace = re.search(regex, self.file_text, re.MULTILINE)
        if file_scoped_namespace:
            self.tabs = 4


class VmDto(BaseEntity):
    """
    Класс представления Vm/Dto

    Attributes:
        base_entity: сущность в которую/от которой маппится vm/dto
        substituted_file_text: замененный текст файла на содержащий summaries
    """
    base_entity: Entity
    substituted_file_text: str

    def __init__(self, path: Union[str, Path]):
        super().__init__(path)
        self.substituted_file_text = self.file_text

        str_path = str(path)
        self.sources_path = Path(str_path[:str_path.index('Application')])

        self._index_self_namespace()
        self._index_used_namespaces()
        self._get_base_entity()

    def _get_base_entity(self):
        """ Определить сущность в которую/от которой маппится vm/dto """
        regex = r"IMap(?:From|To)<(.*)>"
        if match := re.search(regex, self.file_text, re.MULTILINE):
            entity_name = match.group(1)
        else:
            regex = r"profile\.CreateMap<(.*),(?:.*)>"
            entity_name = re.search(regex, self.file_text, re.MULTILINE).group(1).removesuffix('Dto').removesuffix('Vm')

        if entity_name in self.used_entities_namespaces:
            namespace = self.used_entities_namespaces.last_found
            self.base_entity = Entity(namespace.path / f'{entity_name}.cs', filter_properties=False, vm=self)

    def add_properties_summaries(self):
        """ Внести комментарии к свойствам vm/dto из базовой сущности """
        if not self.base_entity:
            return

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
        if not self.base_entity:
            return

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


class Entity(BaseEntity):
    """
    Класс представления сущности.

    Attributes:
        class_summary: summary сущности
        upper_namespaces: коллекция NamespaceCollection для выявления расположения файлов-навигационных свойств
         сущности, не расположенных непосредственно в директории сущности
        required_solution_namespaces: необходимые для декларирования в файлах vm/dto пространства имён
        required_system_namespaces: необходимые для декларирования в файлах vm/dto пространства имён (системные)
        included_files: набор классов FileClass для vm/dto, которые должны быть созданы помимо vm/dto основной сущности
        pluralized_class_name: имя сущности в мн. числе (пр. "Appeals")
    """
    class_summary: str
    factory_property: Property | None
    vm: VmDto | None
    upper_namespaces: NamespaceCollection
    used_entities_namespaces: NamespaceCollection
    required_solution_namespaces: NamespaceCollection
    required_system_namespaces: NamespaceCollection
    included_files: set[Entity]
    pluralized_class_name: str

    def __init__(self, path: Union[str, Path], factory_property: Property = None,
                 filter_properties: bool = True, vm: VmDto = None):
        """
        :param path: абсолютный путь до файла сущности
        :param factory_property: навигационное свойство сущности, на основе которого был инициализирован класс
        :param filter_properties: Отфильтровать свойства сущности в соответствии с флагами '!' и '@"
        :param vm: Обратная ссылка на vm/dto
        """
        super().__init__(path)
        self.vm = vm
        self.factory_property = factory_property
        self.upper_namespaces = NamespaceCollection()
        self.used_entities_namespaces = NamespaceCollection()
        self.required_solution_namespaces = NamespaceCollection()
        self.required_system_namespaces = NamespaceCollection()
        self.included_files: set[Entity] = set()

        self.pluralized_class_name = pluralize(self.class_name)
        str_path = str(path)
        self.sources_path = Path(str_path[:str_path.index('Domain')])

        self._get_class_summary()
        self._index_self_namespace()
        self._index_upper_namespaces()
        self._index_used_namespaces()
        self._extract_properties(filter_properties)
        self._fill_required_namespaces()
        self._calculate_included_files()

    @property
    def validation_properties(self):
        return [p for p in self.properties if p.to_validate]

    def __repr__(self):
        return f'{self.class_name}, {id(self)}'

    def _index_upper_namespaces(self):
        namespace_parts = self.namespace.name.split('.')
        prev_part = self.solution_name
        for i in range(1, len(namespace_parts) - 1):
            prev_part += '.' + namespace_parts[i]
            namespace_obj = self.get_namespace_obj(prev_part)
            self.upper_namespaces.add(namespace_obj)

    def _get_class_summary(self):
        """
        Извлечь summary сущности
        """
        regex = r"/// <summary>\s*/// (?P<summary>(?:.|\n)*?)\s*/// </summary>\s*(?P<tags>(?:///.+>\s*)+)?(?P<attributes>(?:\[.+]\s*)+)?\s*public class"
        if match := re.search(regex, self.file_text, re.MULTILINE):
            self.class_summary = match.group('summary')

    def _extract_properties(self, filter_properties: bool = False):
        """
        Извлечь свойства сущности и относящуюся к ним информацию
        """
        class_body_lines = self._get_body_lines()
        class_body_text = ''.join(class_body_lines)
        regex = re.compile(
            r"(?:<summary>\s*(?P<summary>(?:.|\n)*?)\s*/// </summary>\s*)?(?P<attributes>(?:\[.+]\s*)+)?\s*public (?P<type>[^\s]+)\s(?P<name>[^\s]+)(?=\s\{ ?get;)", re.S)
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

            if prop_type in system_properties:
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
                required_enum_namespace = next(namespace for namespace in self.enums_namespaces if prop_type in namespace.classes)
                self.required_solution_namespaces.add(required_enum_namespace)

        self.required_solution_namespaces.add(self.namespace)

    def _calculate_included_files(self):
        """ Сформировать объекты FileClass для каждого из навигационного свойства сущности """
        for prop in self.properties:
            if prop.is_navigation and prop.required_namespace:
                if namespace_path := prop.required_namespace.path:
                    file = Entity(namespace_path / f'{prop.prop_type}.cs', factory_property=prop)
                    self.included_files.add(file)

    def clear_summaries_flags(self):
        """ Очистить '!' и '@' из summaries свойств сущности """
        cleaned_text = self.file_text.replace('<summary>!', '<summary>').replace('<summary>@', '<summary>')
        with open(self.file_path, 'w', encoding='utf-8') as file:
            file.write(cleaned_text)
