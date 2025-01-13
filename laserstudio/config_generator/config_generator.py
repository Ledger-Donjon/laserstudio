import json
from jsonschema import validate, ValidationError
from typing import Any, Optional, Union

try:
    from .ref_resolve import set_base_url, resolve_references
except ImportError:
    from ref_resolve import set_base_url, resolve_references

import logging
import sys
from colorama import init as colorama_init
from colorama import Fore, Style
import yaml
import os.path


class ConfigGenerator:
    def __init__(
        self,
        schema_uri="config.schema.json",
        base_url="https://raw.githubusercontent.com/Ledger-Donjon/laserstudio/main/config_schema/",
    ):
        self.schema_uri = schema_uri
        self.base_url = base_url
        self.logger = logging.getLogger("Config Generator")
        colorama_init()

    @staticmethod
    def dim(s: str) -> str:
        """
        Convenience function to make a string dimmed.
        """
        return Style.DIM + s + Style.RESET_ALL

    @staticmethod
    def bold(s: str) -> str:
        """
        Convenience function to make a string bold.
        """
        return Style.BRIGHT + s + Style.RESET_ALL

    @staticmethod
    def green(s: str) -> str:
        """
        Convenience function to make a string green.
        """
        return Fore.GREEN + s + Fore.RESET

    @staticmethod
    def blue(s: str) -> str:
        """
        Convenience function to make a string blue.
        """
        return Fore.BLUE + s + Fore.RESET

    @staticmethod
    def yellow(s: str) -> str:
        """
        Convenience function to make a string orange.
        """
        return Fore.YELLOW + s + Fore.RESET

    @staticmethod
    def red(s: str) -> str:
        """
        Convenience function to make a string red.
        """
        return Fore.RED + s + Fore.RESET

    @staticmethod
    def finput(input: str) -> str:
        return ConfigGenerator.bold(ConfigGenerator.yellow(input))

    @staticmethod
    def finstrument(name: str) -> str:
        return ConfigGenerator.bold(ConfigGenerator.blue(name))

    @staticmethod
    def fproperty(key: str, is_required=False) -> str:
        return ConfigGenerator.bold(
            ConfigGenerator.green(key)
            + (ConfigGenerator.red("*") if is_required else "")
        )

    def prompt_with_hint(
        self,
        key: str,
        type: str,
        hint: Optional[str],
        is_array=False,
        is_required=False,
    ) -> Optional[
        Union[list[Union[str, float, int, bool]], Union[str, float, int, bool]]
    ]:
        if hint is None:
            hint = f"No description for property {ConfigGenerator.fproperty(key)} is available."

        if is_array:
            question = f"For property {ConfigGenerator.fproperty(key, is_required)}, give a list of {ConfigGenerator.finput(type)}s, with comma-separated values{ConfigGenerator.dim(' optional') if not is_required else ''}: "
            x = ConfigGenerator.prompt(question, hint)
        else:
            question = f"For property {ConfigGenerator.fproperty(key, is_required)}, enter a{'n' if type=='integer' else ''} {ConfigGenerator.finput(type)} value{ConfigGenerator.dim(' optional') if not is_required else ''}: "
            if type == "boolean":
                x = ConfigGenerator.prompt(
                    question, hint, ["true", "false"], allow_empty=not is_required
                )
            else:
                x = ConfigGenerator.prompt(question, hint, [])

        # If the user does not provide any value, return None
        if x == "":
            if is_required:
                self.logger.error(
                    f"Property {ConfigGenerator.fproperty(key, is_required)} is {ConfigGenerator.red('required')} and cannot be empty"
                )
                return self.prompt_with_hint(key, type, hint, is_array, is_required)

            return None

        if is_array:
            # Convert all elements in the array, and check if they are valid
            values: list[Union[str, float, int, bool]] = []
            for i, x in enumerate(x.split(",")):
                try:
                    if type == "integer":
                        x = int(x)
                    elif type == "number":
                        x = float(x)
                    elif type == "boolean":
                        if x.lower() not in ["true", "false"]:
                            raise ValueError(f"{x} is an invalid boolean value")
                        x = x.lower() == "true"
                    values.append(x)

                except Exception as e:
                    self.logger.error(
                        f"The {i+1}th value for property {ConfigGenerator.fproperty(key)} is invalid: {e}"
                    )
                    return self.prompt_with_hint(key, type, hint, is_array)
            return values

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
            self.logger.error(
                f"Invalid value for property {ConfigGenerator.fproperty(key)}: {e}"
            )
            return self.prompt_with_hint(key, type, hint)

    def prompt_key(
        self, key: str, key_type: str, hint: str, required: bool
    ) -> Optional[Union[str, float, int, bool]]:
        """
        Prompt the user to enter a value for a given key/property, with the given type and hint.
        The function will recursively call itself if the user enters an invalid value.

        :param key: The name of the property.
        :param key_type: The type, which can be "string", "integer", "number", or "boolean".
        :param hint: The content of the "description" field in the schema.
        :param required: Indicates if the field is contained in the 'required' list
        :return: The value entered by the user, or None if the user did not provide any value.
        """
        if key_type not in ["string", "integer", "number", "boolean"]:
            raise ValueError(f"Unsupported schema type: {key_type}")

        x = self.prompt_with_hint(key, key_type, hint, is_required=required)

        if x is None and not required:
            return None

        assert type(x) is str or type(x) is bool or type(x) is int or type(x) is float

        return x

    @staticmethod
    def describe_property(schema: dict[str, Any], key: str, is_required: bool) -> str:
        # Name of property
        res = f"{ConfigGenerator.fproperty(key, is_required)}:"
        # Description of property
        if "description" in schema:
            res += " " + schema["description"]
        # Type of property or constant value
        if "const" in schema:
            res += f" ({ConfigGenerator.bold(schema['const'])} fixed value)."
        elif "type" in schema and schema["type"] != "object":
            if (
                schema["type"] == "array"
                and "items" in schema
                and "type" in schema["items"]
            ):
                res += f" as list of {schema['items']['type']}s."
            else:
                res += f" as {schema['type']}."

        if "examples" in schema:
            res += f" Examples: {schema['examples']}."
        if "default" in schema:
            res += f" Default value: {schema['default']}."
        if "pattern" in schema:
            res += f" Must match the regular expression '{schema['pattern']}'."
        if "minimum" in schema:
            res += f" Minimum value: {schema['minimum']}."
        if "maximum" in schema:
            res += f" Maximum value: {schema['maximum']}."
        if "exclusiveMinimum" in schema:
            res += f" Minimum value (exclusive): {schema['exclusiveMinimum']}."
        if "exclusiveMaximum" in schema:
            res += f" Maximum value (exclusive): {schema['exclusiveMaximum']}."

        if not is_required:
            res += f" {ConfigGenerator.dim('optional')}"
        return res

    @staticmethod
    def describe_schema_properties(
        schema: dict[str, Any], name: str, required_keys: set[str]
    ) -> str:
        """
        Generate a description of the properties of a schema, by providing the list of
        properties and their types, and a description if available.

        :param schema: The schema to describe.
        :param name: The name of the current object from which the schema is comming from.
        :return: A string describing the properties of the schema.
        """
        res = ""
        if "properties" in schema:
            res += f"Properties for {ConfigGenerator.bold(name)}:\n"

            for key, subschema in schema["properties"].items():
                # Description of property
                res += (
                    "  - "
                    + ConfigGenerator.describe_property(
                        subschema,
                        key,
                        key in required_keys or key in schema.get("required", []),
                    )
                    + "\n"
                )
        return res

    @staticmethod
    def prompt(
        question: str, hint: str, answers: list[str] = [], allow_empty=False
    ) -> str:
        """
        Prompt the user with a question, and return the user's answer.
        If the user enters an invalid answer, the function will prompt the user again.
        If the user enters '?', the function will print the hint.

        :param question: The question to ask the user.
        :param hint: The hint to display if the user enters '?'.
        :param answers: The list of valid answers. If empty, any answer is valid.
        :param allow_empty: Indicates if the user can provide an empty answer.
        :return: User's answer.
        """

        banswers = [ConfigGenerator.finput(answer) for answer in answers]
        if banswers:
            question = question + " " + "/".join(banswers) + " "

        if not hint:
            hint = "No description available."

        x = input(question).strip().lower()
        while x.startswith("?") or x not in answers:
            if x.startswith("?"):
                print(hint)
                x = input(question).strip().lower()
                continue

            if allow_empty and x == "":
                break

            if len(answers) == 0:
                break

            x = (
                input(
                    ConfigGenerator.red("Invalid choice.")
                    + f" Please enter {' or '.join(banswers)}. "
                )
                .strip()
                .lower()
            )
        print()
        return x

    def generate_array_interactive(
        self, schema: dict[str, Any], key: str, required_keys: set[str]
    ):
        item_schema = schema.get("items", {})
        element_type = item_schema.get("type", "string")
        if element_type == "object":
            name: Any | None = item_schema.get("title")
            if name is not None:
                name = ConfigGenerator.finstrument(name)
            result = []
            while True:
                question = f"Do you want to instanciate a{'nother' if len(result) else ''} {name or ConfigGenerator.fproperty(key)}?"
                hint = ConfigGenerator.describe_property(
                    schema, name or key, key in required_keys
                )
                if "n" == ConfigGenerator.prompt(question, hint, ["y", "n"]):
                    break

                subresult = self.generate_json_interactive(
                    item_schema, key, required_keys, ask_user=False
                )
                if subresult is None:
                    break
                assert type(subresult) is dict
                result.append(subresult)
            return result

        hint = ConfigGenerator.describe_property(schema, key, key in required_keys)
        result = self.prompt_with_hint(
            key, element_type, hint, is_array=True, is_required=key in required_keys
        )

        # If the user does not provide any value, return None
        if result is None:
            return None

        assert type(result) is list

        return result

    # Function to generate JSON data interactively based on the schema
    def generate_json_interactive(
        self,
        schema: Optional[dict[str, Any]] = None,
        key: str = "",
        required_keys: set[str] = set(),
        ask_user: Optional[bool] = None,
    ):
        if schema is None:
            schema = self.schema

        # Identify which type of element we are dealing with
        element_type = schema.get("type")

        # Populate the list of required keys
        self.logger.debug(
            f"{key}: Required keys: {required_keys} + {schema.get('required', [])}"
        )
        required_keys = set(required_keys)
        for r in schema.get("required", []):
            required_keys.add(r)

        # If the schema does not have a 'type' key, assume it is an object
        if element_type is None:
            self.logger.debug(json.dumps(schema, indent=2))
            self.logger.debug(
                f"Schema should have a '{ConfigGenerator.bold('type')}' key, inducing the type of the element to '{ConfigGenerator.bold('object')}'"
            )
            element_type = "object"

        if element_type == "array":
            name = schema.get("items", {}).get("title")
        else:
            name = schema.get("title")
        if name is not None:
            name = ConfigGenerator.finstrument(name)

        # We ask the user to instantiate or not the object.
        # If the object is a camera or a stage, we ask the user to instantiate it.
        if (ask_user is not None and ask_user) or (
            ask_user is None and key in ["camera", "stage"]
        ):
            question = f"Do you want to instanciate a {name or ConfigGenerator.fproperty(key)}?"
            hint = self.describe_property(schema, name or key, key in required_keys)

            if "n" == self.prompt(question, hint, ["y", "n"]):
                return None

        result = {}

        # Generate multiple schemas from the "allOf" list
        # Should not exist anymore, as the schema is "flattened" in ref_resolve.py
        if "allOf" in schema:
            # The "allOf" list contains multiple schemas that must all be satisfied
            self.logger.info(f"Satisfy {len(schema['allOf'])} schemas in 'allOf'")
            for subschema in schema["allOf"]:
                subresult = self.generate_json_interactive(
                    subschema, key, required_keys, ask_user=False
                )
                assert type(subresult) is dict
                result.update(subresult)

        # Generate schema from the "anyOf" list
        if "anyOf" in schema:
            if len(schema["anyOf"]) == 1:
                # The "anyOf" list contains only one schema
                subresult = self.generate_json_interactive(
                    schema["anyOf"][0], key, required_keys
                )
                assert type(subresult) is dict
                result.update(subresult)
            else:
                # The "anyOf" list contains multiple schemas and the user must choose at least one
                has_instanciated_one_schema = False
                while not has_instanciated_one_schema:
                    print(
                        f"There are {len(schema['anyOf'])} possible schemas for {name or ConfigGenerator.fproperty(key)}, containing those {ConfigGenerator.fproperty('properties')} (among others). You have to instanciate {ConfigGenerator.finput('at least one')}:"
                    )
                    for i, option in enumerate(schema["anyOf"]):
                        print(
                            ConfigGenerator.bold(f"Schema {i + 1}: ")
                            + self.describe_schema_properties(
                                option, name or key, required_keys
                            )
                        )
                    for i, option in enumerate(schema["anyOf"]):
                        if (
                            self.prompt(
                                f"Do you want to instanciate {ConfigGenerator.bold(f'Schema {i+1}')}?",
                                hint="",
                                answers=["y", "n"],
                            )
                            == "n"
                        ):
                            continue

                        subresult = self.generate_json_interactive(
                            option, key, required_keys, ask_user=False
                        )
                        if type(subresult) is dict:
                            result.update(subresult)
                            has_instanciated_one_schema = True
                    if not has_instanciated_one_schema:
                        print(
                            ConfigGenerator.red("Invalid choices:")
                            + f" You must instanciate {ConfigGenerator.red('at least one')} of proposed schema..."
                        )

        # Generate one schema from the "oneOf" list
        if "oneOf" in schema:
            oneOfSchemas = schema["oneOf"]
            if len(oneOfSchemas) > 1:
                # The "oneOf" list contains multiple schemas and the user must choose one
                print(
                    f"There are {len(schema['oneOf'])} possible schemas {'for ' + (name or ConfigGenerator.fproperty(key))}, containing those {ConfigGenerator.fproperty('properties')} (among others). Choose one of the following:"
                )
                for i, option in enumerate(oneOfSchemas):
                    print(
                        ConfigGenerator.bold(f"Schema {i + 1}: ")
                        + ConfigGenerator.describe_schema_properties(
                            option, name or key, required_keys
                        )
                    )
                x = ConfigGenerator.prompt(
                    "Enter the schema number:",
                    hint="",
                    answers=[str(i) for i in range(1, len(oneOfSchemas) + 1)],
                )
                choice = int(x) - 1
            else:
                choice = 0

            subresult = self.generate_json_interactive(
                oneOfSchemas[choice], key, required_keys, ask_user=False
            )
            if type(subresult) is dict:
                result.update(subresult)

        # Array of objects
        if element_type == "array":
            array = self.generate_array_interactive(schema, key, required_keys)
            if array is None or len(array) == 0:
                return None
            else:
                return array

        # Handle enums and constants
        if "enum" in schema:
            question = f"For property {ConfigGenerator.fproperty(key)}, choose one of following values:"
            hint = schema.get(
                "description",
                f"No description available for {ConfigGenerator.fproperty(key)}.",
            )
            values = schema["enum"]
            x = self.prompt(question, hint, values)
            return x

        if "const" in schema:
            self.logger.info(
                f"For property {ConfigGenerator.fproperty(key)}, value is constant and will be {ConfigGenerator.bold(schema['const'])}."
            )
            return schema["const"]

        # Handle object by generating its properties
        if element_type == "object":
            for key, subschema in schema.get("properties", {}).items():
                self.logger.info(
                    f"Instantiation of property '{key}'"
                    + (f" (of type {subschema['type']})" if "type" in subschema else "")
                    + ":"
                )
                generated_item = self.generate_json_interactive(
                    subschema, key, required_keys
                )
                if generated_item is not None:
                    result[key] = generated_item
            if name:
                print(f"{ConfigGenerator.finstrument(name)} instanciated.\n")
            return result

        # Handle simple types (string, integer, number, boolean)
        hint = ConfigGenerator.describe_property(schema, key, key in required_keys)

        while True:
            x = self.prompt_key(key, element_type, hint, key in required_keys)
            if (key not in required_keys) and x is None:
                return None

            try:
                validate(x, schema)
                return x
            except ValidationError as e:
                self.logger.error(
                    f"Invalid value for property {ConfigGenerator.fproperty(key)}: {e.message}"
                )
                continue

    def get_flags(self):
        # Check if -V flag is present for augmenting log level to VERBOSE
        if "-V" in sys.argv:
            logging.basicConfig(level=logging.INFO)

        # Check if -D flag is present for augmenting log level to DEBUG
        if "-D" in sys.argv:
            logging.basicConfig(level=logging.DEBUG)

        # Check if -L flag is present for retrieve schema from local directory
        if "-L" in sys.argv:
            __dirname = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
            )
            self.base_url = os.path.join(__dirname, "config_schema")

    def load_schema(self):
        # Fetch the JSON schema from the URL
        set_base_url(self.base_url)
        print("Loading schemas... ", end="")
        sys.stdout.flush()
        schema = resolve_references(self.schema_uri)
        print("done.")
        self.logger.info("Schema loaded successfully")
        self.logger.debug(json.dumps(schema, indent=2))
        self.schema = schema

    @staticmethod
    def print_intro():
        input(f"""Welcome to {ConfigGenerator.finstrument('Laser Studio')} config.yaml file generator.
            
    This tool permits you to create a configuration file for the Laser Studio software to describe your bench setup.
    You will be prompted to instanciate (or not) some {ConfigGenerator.finstrument('instruments')} and their {ConfigGenerator.fproperty('properties')}.
    Enter values for each requested {ConfigGenerator.fproperty('property')}.

    For some {ConfigGenerator.fproperty('properties')} or {ConfigGenerator.finstrument('instruments')}, you may have to choose between several options (called schemas).

    If you need help, type {ConfigGenerator.finput('?')} and you will be provided with a description of the {ConfigGenerator.fproperty('property')}.
    If the {ConfigGenerator.fproperty('property')} is required, it will be marked with a {ConfigGenerator.bold(ConfigGenerator.red('*'))}.
    If you want to skip a {ConfigGenerator.fproperty('property')}, just press {ConfigGenerator.finput('Enter')} without any value.

    Press {ConfigGenerator.finput('Enter')} when you are ready...
    """)


def main():
    config_generator = ConfigGenerator()
    config_generator.logger.info("Starting config generator")

    config_generator.get_flags()
    set_base_url(config_generator.base_url)

    # Load all schemas
    config_generator.load_schema()

    # Print the introduction message
    config_generator.print_intro()

    # Generate JSON data interactively based on the main schema
    generated_json = config_generator.generate_json_interactive()

    if not generated_json:
        print("No configuration file was generated.")
        return 0

    # Print the generated JSON data
    print("\nGenerated config.yaml:")
    print(yaml.dump(generated_json, indent=2))

    # Validate the generated JSON data against the schema
    try:
        validate(instance=generated_json, schema=config_generator.schema)
        print(
            "Generated JSON is "
            + ConfigGenerator.bold(ConfigGenerator.green("valid"))
            + " according to the schema"
        )
    except ValidationError as e:
        print(
            "Generated JSON is "
            + ConfigGenerator.bold(ConfigGenerator.red("invalid"))
            + ": "
            + e.message
        )
        return -1
    if (
        ConfigGenerator.prompt(
            "Do you want to save the generated configuration file?", "", ["y", "n"]
        )
        == "y"
    ):
        if os.path.exists("config.yaml"):
            if (
                ConfigGenerator.prompt(
                    "A configuration file already exists. Do you want to overwrite it?",
                    "",
                    ["y", "n"],
                )
                == "n"
            ):
                return 0
        with open("config.yaml", "w+") as f:
            f.write(yaml.dump(generated_json, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
