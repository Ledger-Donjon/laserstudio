import json
from jsonschema import validate, ValidationError
from typing import Any, Optional, Union
from .ref_resolve import set_base_url, resolve_references
import logging
import sys
from colorama import init as colorama_init
from colorama import Fore, Style
import yaml

logger = logging.getLogger("Config Generator")


def prompt_key(
    key: str, type: str, hint: Optional[str], required=False
) -> Optional[Union[Union[Union[str, int], float], bool]]:
    """
    Prompt the user to enter a value for a given key/property, with the given type and hint.
    The function will recursively call itself if the user enters an invalid value.

    :param key: The name of the property.
    :param type: The type, which can be "string", "integer", "number", or "boolean".
    :param hint: The content of the "description" field in the schema.
    :param required: Indicates if the field is contained in the 'required' list, defaults to False
    :return: The value entered by the user, or None if the user did not provide any value.
    """
    if type not in ["string", "integer", "number", "boolean"]:
        raise ValueError(f"Unsupported schema type: {type}")

    x = "?"
    while x.startswith("?"):
        x = input(
            f"For property {bold(key)}, enter a{'n' if type=='integer' else ''} {bold(type)} value{' (true/false)' if type=='boolean' else ''}: "
        )
        if x.startswith("?"):
            if hint is None:
                print(f"No description for property {bold(key)} is available.")
                x = ""
                break
            print(f"Description: {hint}")

    if x == "" and not required:
        return None

    try:
        if type == "integer":
            x = int(x)
        elif type == "number":
            x = float(x)
        elif type == "boolean":
            if x.lower() not in ["true", "false"]:
                raise ValueError(f"{x} is an invalid boolean value")
            x = x.lower() == "true"
        return x

    except Exception as e:
        logger.error(f"Invalid value for property {bold(key)}: {e}")
        return prompt_key(key, type, hint)


def bold(s: str) -> str:
    """
    Convenience function to make a string bold.
    """
    return Style.BRIGHT + s + Style.RESET_ALL


def green(s: str) -> str:
    """
    Convenience function to make a string green.
    """
    return Fore.GREEN + s + Fore.RESET


def blue(s: str) -> str:
    """
    Convenience function to make a string blue.
    """
    return Fore.BLUE + s + Fore.RESET


def red(s: str) -> str:
    """
    Convenience function to make a string red.
    """
    return Fore.RED + s + Fore.RESET


def describe_schema_properties(schema: dict[str, Any], name: str) -> str:
    """
    Generate a description of the properties of a schema, by providing the list of
    properties and their types, and a description if available.

    :param schema: The schema to describe.
    :param name: The name of the current object from which the schema is comming from.
    :return: A string describing the properties of the schema.
    """
    res = ""
    if "properties" in schema:
        res += f"Properties for {bold(name)}:\n"

        for key, subschema in schema["properties"].items():
            # Name of property
            res += f"  - {bold(key)}:"
            # Description of property
            if "description" in subschema:
                res += " " + subschema["description"]
            # Type of property or constant value
            if "const" in subschema:
                res += f" ('{subschema['const']}' fixed value)"
            elif "type" in subschema:
                res += f" (as {subschema['type']})"
            if "examples" in subschema:
                res += f" Examples: {subschema['examples']}"
            if "default" in subschema:
                res += f" Default: {subschema['default']}"
            res += "\n"
    return res


def generate_array_interactive(schema: dict[str, Any], key: str):
    item_schema = schema.get("items", {})
    element_type = item_schema.get("type", "string")
    if element_type == "object":
        name = item_schema.get("title", key)
        result = []
        while True:
            subresult = generate_json_interactive(item_schema, name)
            if subresult is None:
                break
            assert type(subresult) is dict
            result.append(subresult)
        return result

    hint = item_schema.get("description")
    while True:
        result = input(
            f"For property {bold(key)}, give a list of {bold(element_type)}s, with comma-separated values: "
        )
        # Check if the user wants to see the description
        if result.startswith("?"):
            print(
                f"Description: {hint}"
                if hint is not None
                else f"No description for property {bold(key)} is available."
            )
        else:
            break

    # If the user does not provide any value, return None
    if result == "":
        return None

    # Convert all elements in the array, and check if they are valid
    values = []
    for i, x in enumerate(result.split(",")):
        try:
            if element_type == "integer":
                x = int(x)
            elif element_type == "number":
                x = float(x)
            elif element_type == "boolean":
                if x.lower() not in ["true", "false"]:
                    raise ValueError(f"{x} is an invalid boolean value")
                x = x.lower() == "true"
            values.append(x)

        except Exception as e:
            logger.error(f"The {i+1}th value for property {bold(key)} is invalid: {e}")
            return generate_array_interactive(schema, key)

    return values


# Function to generate JSON data interactively based on the schema
def generate_json_interactive(schema: dict[str, Any], key):
    # Identify which type of element we are dealing with
    element_type = schema.get("type")

    # If the schema does not have a 'type' key, assume it is an object
    ask_user = key in ["camera", "stage", "lasers", "probes"]

    if element_type is None:
        logger.debug(json.dumps(schema, indent=2))
        logger.info(
            "Schema should have a 'type' key, inducing the type of the element to 'object'"
        )
        element_type = "object"

    name = (
        schema.get("items", {}).get("title", key)
        if element_type == "array"
        else schema.get("title", key)
    )

    # Give the possibiltiy not to instanciate an object
    if ask_user:
        if (
            x := input(f"Do you want to instanciate a {bold(name)}? (y/N) ")
        ) == "" or x.strip().lower().startswith("n"):
            return None

    result = {}

    # Generate multiple schemas from the "allOf" list
    # Should not exist anymore, as the schema is "flattened" in ref_resolve.py
    if "allOf" in schema:
        # The "allOf" list contains multiple schemas that must all be satisfied
        logger.info(f"Satisfy {len(schema['allOf'])} schemas in 'allOf'")
        for subschema in schema["allOf"]:
            subresult = generate_json_interactive(subschema, key)
            assert type(subresult) is dict
            result.update(subresult)

    # Generate schema from the "anyOf" list
    if "anyOf" in schema:
        if len(schema["anyOf"]) == 1:
            # The "anyOf" list contains only one schema
            subresult = generate_json_interactive(schema["anyOf"][0], key)
            assert type(subresult) is dict
            result.update(subresult)
        else:
            # The "anyOf" list contains multiple schemas and the user must choose at least one
            has_instanciated_one_schema = False
            while not has_instanciated_one_schema:
                print(
                    f"There are {len(schema['anyOf'])} possible schemas for {bold(name)}, you have to instanciate {bold('at least one')}:"
                )
                for i, option in enumerate(schema["anyOf"]):
                    print(
                        bold(f"Schema {i + 1}: ")
                        + describe_schema_properties(option, name)
                    )
                for i, option in enumerate(schema["anyOf"]):
                    if (
                        x := input(f"Do you want to instanciate Schema {i}? (y/N) ")
                    ) == "" or x.strip().lower().startswith("n"):
                        continue
                    subresult = generate_json_interactive(option, key)
                    if type(subresult) is dict:
                        result.update(subresult)
                        has_instanciated_one_schema = True
                if not has_instanciated_one_schema:
                    print(
                        f"You must instanciate {bold('at least one')} of proposed schema..."
                    )

    # Generate one schema from the "oneOf" list
    if "oneOf" in schema:
        if len(schema["oneOf"]) > 1:
            # The "oneOf" list contains multiple schemas and the user must choose one
            print(
                f"There are {len(schema['oneOf'])} possible schemas {('for ' + bold(name)) if name else key if key else 'to instanciate'}, choose one of the following:"
            )
            for i, option in enumerate(schema["oneOf"]):
                print(
                    bold(f"Schema {i + 1}: ") + describe_schema_properties(option, name)
                )
            choice = int(input("Enter the schema number: ")) - 1
        else:
            choice = 0

        subresult = generate_json_interactive(schema["oneOf"][choice], "")
        if type(subresult) is dict:
            result.update(subresult)

    # Array of objects
    if element_type == "array":
        array = generate_array_interactive(schema, key)
        if array is None:
            return None
        else:
            return array

    # Handle enums and constants
    if "enum" in schema:
        print(f"For property {bold(key)}, choose one of following values:")
        for i, value in enumerate(schema["enum"]):
            print(f"{i + 1}: {value}")
        choice = int(input("Enter the option number: ")) - 1
        return schema["enum"][choice]

    if "const" in schema:
        logger.info(
            f"For property {bold(key)}, value is constant and will be {bold(schema['const'])}."
        )
        return schema["const"]

    # Handle object by generating its properties
    if element_type == "object":
        for key, subschema in schema.get("properties", {}).items():
            logger.info(
                f"Instantiation of property '{key}'"
                + (f" (of type {subschema['type']})" if "type" in subschema else "")
                + ":"
            )
            generated_item = generate_json_interactive(subschema, key)
            if generated_item is not None:
                result[key] = generated_item
        if name:
            print(f"{bold(name)} instanciated.\n")
        return result

    # Handle simple types (string, integer, number, boolean)
    return prompt_key(key, element_type, schema.get("description"))


def main(
    schema_uri="config.schema.json",
    base_url="https://raw.githubusercontent.com/Ledger-Donjon/laserstudio/main/config_schema/",
):
    # Check if -D flag is present
    if "-D" in sys.argv:
        logging.basicConfig(level=logging.DEBUG)

    if "-L" in sys.argv:
        base_url = "/Volumes/Work/Gits/Ledger-Donjon/laserstudio/config_schema/"

    logger.info("Starting config generator")

    colorama_init()

    set_base_url(base_url)
    # Fetch the JSON schema from the URL
    schema = resolve_references(schema_uri)
    logger.info("Schema loaded successfully")
    logger.debug(json.dumps(schema, indent=2))
    input(f"Press {green(bold('Enter'))} to continue...")
    logger.info("\n" * 2)

    # Generate JSON data interactively based on the schema
    generated_json = generate_json_interactive(schema, "")

    # Print the generated JSON data
    print("\nGenerated config.yaml:")
    print(yaml.dump(generated_json, indent=2))

    # Validate the generated JSON data against the schema
    try:
        validate(instance=generated_json, schema=schema)
        print("Generated JSON is " + bold(green("valid")) + " according to the schema")
    except ValidationError as e:
        print("Generated JSON is " + bold(red("invalid")) + ": " + e.message)
        return -1

    return 0


if __name__ == "__main__":
    sys.exit(main())
