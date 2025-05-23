import requests
from referencing import Registry, Resource
from referencing._core import Resolver
import json
import logging
import os.path

logger = logging.getLogger("Config Generator")


# Fetch the JSON schema from the URL
BASE_URL = "https://raw.githubusercontent.com/Ledger-Donjon/laserstudio/main/laserstudio/config_schema/"


def set_base_url(url: str):
    global BASE_URL
    BASE_URL = url


def resolve_references(uri: str):
    return _resolve(_resolver.lookup(uri).contents, _resolver)


def _retrieve(uri: str):
    if BASE_URL.startswith("/"):
        with open(os.path.join(BASE_URL, uri)) as f:
            return Resource.from_contents(json.load(f))
    elif BASE_URL.startswith("http"):
        response = requests.get(BASE_URL + uri)
        return Resource.from_contents(response.json())
    else:
        raise ValueError("Invalid base URL")


_registry = Registry(retrieve=_retrieve)
_resolver = _registry.resolver()


def _resolve(schema, resolver: Resolver):
    if "oneOf" in schema:
        schema["oneOf"] = [
            _resolve(subschema, resolver) for subschema in schema["oneOf"]
        ]
    if "allOf" in schema:
        schema["allOf"] = [
            _resolve(subschema, resolver) for subschema in schema["allOf"]
        ]
        schema = _flatten(schema)

    if "$ref" in schema:
        ref = schema["$ref"]
        del schema["$ref"]
        logger.info(f"Resolving reference: {ref}")
        resolved = resolver.lookup(ref).contents
        resolved = _resolve(resolved, resolver)
        return resolved
    elif "properties" in schema:
        for key, subschema in schema["properties"].items():
            schema["properties"][key] = _resolve(subschema, resolver)
    elif "items" in schema:
        schema["items"] = _resolve(schema["items"], resolver)
    return schema


def _flatten(schema: dict):
    # Combine 'allOf's into one schema
    keys = list(schema.keys())
    # Get the position of "allOf" in the keys
    try:
        allOf_index = keys.index("allOf")
    except ValueError:
        allOf_index = None
    if allOf_index is None:
        return schema
    # Get the position of "properties" in the keys
    try:
        properties_index = keys.index("properties")
    except ValueError:
        properties_index = None

    allOfFirst = (
        allOf_index < properties_index if properties_index is not None else True
    )

    allOf = schema["allOf"]
    del schema["allOf"]
    for subschema in allOf:
        # Keep order according to the position of "allOf" in the keys
        first, second = (subschema, schema) if allOfFirst else (schema, subschema)
        # Merge properties
        if "properties" in subschema:
            schema["properties"] = {
                **first.get("properties", {}),
                **second.get("properties", {}),
            }
            del subschema["properties"]

        # Merge required list
        if "required" in subschema:
            req = first.get("required", []) + second.get("required", [])
            if len(req):
                schema["required"] = req
            del subschema["required"]

        # Merge everything else, with schema taking precedence
        schema = {**subschema, **schema}

    return schema
