def pluralize(word):
    # Список исключений, которые не подчиняются общим правилам
    exceptions = {
        "child": "children",
        "foot": "feet",
        "person": "people",
        "mouse": "mice",
        "goose": "geese",
        "sheep": "sheep",
        "fish": "fish",
        "deer": "deer",
        "ox": "oxen",
        "tooth": "teeth",
        "louse": "lice",
        "cactus": "cacti",
        "nucleus": "nuclei",
        "fungus": "fungi",
        "analysis": "analyses",
        "crisis": "crises",
        "thesis": "theses",
        "phenomenon": "phenomena",
        "criterion": "criteria",
        "datum": "data",
        "man": "men",
        "woman": "women"
    }
    # Если слово есть в списке исключений, возвращаем его множественную форму
    if word in exceptions:
        return exceptions[word]
    # Если слово заканчивается на -y, заменяем его на -ies, если перед ним согласная
    elif word.endswith("y") and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    # Если слово заканчивается на -s, -x, -z, -sh или -ch, добавляем -es
    elif word[-1] in "sxz" or word[-2:] in ["sh", "ch"]:
        return word + "es"
    # Если слово заканчивается на -f или -fe, заменяем его на -ves
    elif word.endswith("f") or word.endswith("fe"):
        return word.rstrip("fe") + "ves"
    # Если слово заканчивается на -o, добавляем -es, если перед ним согласная
    elif word.endswith("o") and word[-2] not in "aeiou":
        return word + "es"
    # В остальных случаях просто добавляем -s
    else:
        return word + "s"