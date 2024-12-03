import requests
from referencing import Registry, Resource
from referencing._core import Resolver
import json

# Fetch the JSON schema from the URL
BASE_URL = (
    "https://raw.githubusercontent.com/Ledger-Donjon/laserstudio/main/config_schema/"
)


def set_base_url(url: str):
    global BASE_URL
    BASE_URL = url


def resolve_references(uri: str):
    return _resolve(_resolver.lookup(uri).contents, _resolver)


def _retrieve(uri: str):
    if BASE_URL.startswith("/"):
        with open(BASE_URL + uri) as f:
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

    if "$ref" in schema:
        ref = schema["$ref"]
        del schema["$ref"]
        print("Resolving reference:", ref)
        resolved = resolver.lookup(ref).contents
        resolved = _resolve(resolved, resolver)
        return resolved
    elif "properties" in schema:
        for key, subschema in schema["properties"].items():
            schema["properties"][key] = _resolve(subschema, resolver)
    elif "items" in schema:
        schema["items"] = _resolve(schema["items"], resolver)
    return schema
