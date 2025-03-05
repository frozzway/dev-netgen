# dev-netgen

Плагин для автоматической генерации c# кода - CRUD'а с файлом контроллера и комментариев на основе выбранной сущности.
### CRUD и controller
Включает генерацию валидатора с правилами `.NotEmpty()` для полей типа `string` и `IsInEnum()` для полей типа перечислений сущности.

Сгенерированный CRUD содержит комментарии, взятые из summaries сущности и её полей.

Есть поддержка для legacy-проектов, в контроллерах которых используются `ControllerHelper.GetResultWithErrorAsync()`

##### Возможности

Создаёт Vm и Dto подмодели для каждого навигационного свойства, если в после открывающегося тэга `summary` сущности стоит **'@'**
```c#
/// <summary>@
/// Навигационное свойство - список соглашений
/// </summary>
public List<Agreement> Agreements { get; } = new();   
```

Не включает поля, помеченные знаком **'!'** у сущности, в результирующие Vm/Dto
```c#
/// <summary>!
/// Текстовое поле с информацией, которое не попадет в Vm
/// </summary>
public string Data { get; set; }
```

После генерации отметки очищаются

### Summaries для Vm и Dto

Копирует все имеющиеся комментарии к свойствам сущности в целевую или во все относящиеся к ней Vm/Dto. Добавляет комментарий к классу, если он отсутствует.


## Установка

#### Установить python 3.10

```shell
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.10
```

#### Установить python пакет (python >= 3.10) с помощью [pipx](https://pipx.pypa.io/stable/installation/#installing-pipx)

```shell
pipx install devnetgen
```

#### Установить плагин в IDE

1. Установить плагин `LivePlugin` by Dmitry Kandalov (иногда встаёт с 2 попытки )
2. Добавить новый пользовательский Kotlin плагин через окно `LivePlugin` и скопировать в него код из _LivePlugin IntelliJ/plugin.kts_
3. Активировать пользовательский плагин в том же окне

## Использование

#### Из IDE
ПКМ по сущности - `NetGen: генерация` ->
- `Сгенерировать CRUD`
- `Сгенерировать CRUD на legacy controller`
- `Сгенерировать <summary> в файле(-ах) Vm/Dto на основе сущности`
#### Через консоль
```shell
dev-netgen all [path/to/entity.cs] --legacy-controller
```

```shell
dev-netgen summary [path/to/class_or_entity.cs]
```