import os
import subprocess
from pathlib import Path

from devnetgen.executors import SolutionMeta


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

    def _output_data(self):
        print(f'Сгенерировано {self.changed_files_num} файлов в директориях:')
        for directory in self.changed_directories:
            print(str(directory).removeprefix(self.solution_name))

    @staticmethod
    def add_to_git(directory_path: Path):
        """ Добавить все файлы директории в git """
        directory_str = str(directory_path)
        os.chdir(directory_str)
        subprocess.run(["git", "add", '.'])
