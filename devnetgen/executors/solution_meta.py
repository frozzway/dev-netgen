from dataclasses import dataclass


@dataclass
class SolutionMeta:
    """
    Мета-информация о проекте

    Attributes:
        mediator: использование библиотеки Mediator/MediatR
        webapi: директория с контроллерами WebAPI/WebUI
        sieve: использование Sieve/Devexpress для грида
    """
    mediator: bool | None = None
    webapi: bool | None = None
    sieve: bool | None = None
