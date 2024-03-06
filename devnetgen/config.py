from jinja2 import Environment, PackageLoader, select_autoescape


env = Environment(
    loader=PackageLoader('devnetgen'),
    autoescape=select_autoescape(),
    lstrip_blocks=True,
    trim_blocks=True
)
