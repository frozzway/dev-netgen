from devnetgen.constructors.base_tests_constructors import CommandTestsConstructor
from devnetgen.constructors.base_tests_constructors import QueryTestsConstructor


class CreateEntityTestsConstructor(CommandTestsConstructor):
    filename_prefix = 'Create'
    template = "tests/commands/CreateEntityTests.cs.j2"


class UpdateEntityTestsConstructor(CommandTestsConstructor):
    filename_prefix = 'Update'
    template = "tests/commands/UpdateEntityTests.cs.j2"


class DeleteEntityTestsConstructor(CommandTestsConstructor):
    filename_prefix = 'Delete'
    template = "tests/commands/DeleteEntityTests.cs.j2"


class GetEntityTestsConstructor(QueryTestsConstructor):
    template = "tests/queries/GetEntityTests.cs.j2"


class GetEntitiesTestsConstructor(QueryTestsConstructor):
    template = "tests/queries/GetEntitiesTests.cs.j2"

    @property
    def filename_middle_part(self):
        return self.entity.pluralized_class_name


class GetEntityGridTestsConstructor(QueryTestsConstructor):
    template = "tests/queries/GetEntityGridTests.cs.j2"

    @property
    def filename_middle_part(self):
        return self.entity.pluralized_class_name + 'Grid'
