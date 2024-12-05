import json
from jsonschema import validate, ValidationError
from prompt_toolkit import prompt
from typing import Any
import ref_resolve
import logging
from colorama import init as colorama_init
from colorama import Fore, Style
import yaml

logger = logging.getLogger("Config Generator")


def generate_array_interactive(schema: dict[str, Any], key: str = "???"):

def bold(s: str) -> str:
    return Style.BRIGHT + s + Style.RESET_ALL


def green(s: str) -> str:
    return Fore.GREEN + s + Fore.RESET


def blue(s: str) -> str:
    return Fore.BLUE + s + Fore.RESET


def red(s: str) -> str:
    return Fore.RED + s + Fore.RESET

    item_schema = schema.get("items", {})

    if item_schema.get("type") == "object":
        name = item_schema.get("title", key)
        result = []
        # The user will be prompted to instanciate or not the object
        while True:
            subresult = generate_json_interactive(item_schema, name, ask_user=True)
            if subresult is None:
                break
            assert type(subresult) is dict
            result.append(subresult)
        return result
    else:
        result = prompt(
            f"Give a list of {item_schema.get('type')}, with comma-separated values: "
        )
        # TODO Validate the input according to type
        return result.split(",")


# Function to generate JSON data interactively based on the schema
def generate_json_interactive(schema: dict[str, Any], key: str = "???", ask_user=False):
    # Identify which type of schema we are dealing with
    element_type = schema.get("type")

    # If the schema does not have a 'type' key, assume it is an object
    if key in ["camera", "stage"]:
        ask_user = True

    if element_type is None:
        logger.debug(json.dumps(schema, indent=2))
        logger.info(
            "Schema should have a 'type' key, inducing the type of the element to 'object'"
        )
        element_type = "object"

    # Give the possibiltiy not to instanciate an object
    if ask_user and element_type == "object":
        name = schema.get("title", key)
        if prompt(f"Do you want to instanciate a '{name}'? (y/n) ") == "n":
            return None

    result = {}

    # Generate multiple schemas from the "allOf" list
    if "allOf" in schema:
        # The "allOf" list contains multiple schemas that must all be satisfied
        logger.info(f"Satisfy {len(schema['allOf'])} schemas in 'allOf'")
        for subschema in schema["allOf"]:
            subresult = generate_json_interactive(subschema)
            assert type(subresult) is dict
            result.update(subresult)

    # Generate one schema from the "oneOf" list
    if "oneOf" in schema:
        # The "oneOf" list contains multiple schemas and the user must choose one
        print("Choose one of the following options:")
        for i, option in enumerate(schema["oneOf"]):
            print(f"Option {i + 1}: {json.dumps(option, indent=2)}")
        choice = int(prompt("Enter the option number: ")) - 1
        subresult = generate_json_interactive(schema["oneOf"][choice])
        assert type(subresult) is dict
        result.update(subresult)

    # Array of objects
    if element_type == "array":
        return generate_array_interactive(schema, key)

    if element_type == "object":
        obj = result
        for key, subschema in schema.get("properties", {}).items():
            logger.info(
                f"Instantiation of property '{key}'"
                + (f" (of type {subschema['type']})" if "type" in subschema else "")
                + ":"
            )
            obj[key] = generate_json_interactive(subschema, key)
        return obj

    # Handle enums and constants
    if "enum" in schema:
        print("Choose one of following values:")
        for i, value in enumerate(schema["enum"]):
            print(f"{i + 1}: {value}")
        choice = int(prompt("Enter the option number: ")) - 1
        return schema["enum"][choice]

    elif "const" in schema:
        logger.info(f"{key}'s value must be {schema['const']}.")
        return schema["const"]

    elif element_type == "string":
        return prompt("Enter a string value: ")

    elif element_type == "integer":
        return int(prompt("Enter an integer value: "))

    elif element_type == "number":
        return float(prompt("Enter a number value: "))

    elif element_type == "boolean":
        value = prompt("Enter a boolean value (true/false): ").lower()
        return value == "true"

    else:
        raise ValueError(f"Unsupported schema type: {element_type}")


def main(
    schema_uri: str = "config.schema.json",
    base_url: str = "https://raw.githubusercontent.com/Ledger-Donjon/laserstudio/main/config_schema/",
):
    ref_resolve.set_base_url(base_url)
    colorama_init()

    # Fetch the JSON schema from the URL
    schema = ref_resolve.resolve_references(schema_uri)
    logger.info("Schema loaded successfully")
    logger.debug(json.dumps(schema, indent=2))
    input(f"Press {green(bold('Enter'))} to continue...")
    logger.info("\n" * 2)

    # Generate JSON data interactively based on the schema
    generated_json = generate_json_interactive(schema)

    # Print the generated JSON data
    print("\nGenerated config.yaml:")
    print(yaml.dump(generated_json, indent=2))

    # Validate the generated JSON data against the schema
    try:
        validate(instance=generated_json, schema=schema)
        logger.info("Generated JSON is valid according to the schema")
    except ValidationError as e:
        logger.error(f"Generated JSON is not valid: {e.message}")

    # Print the generated JSON data
    logger.debug(json.dumps(generated_json, indent=2))
    return 0


if __name__ == "__main__":
    logger.setLevel(logging.CRITICAL)
    logger.info("Starting config generator")
    main(base_url="/Volumes/Work/Gits/Ledger-Donjon/laserstudio/config_schema/")
