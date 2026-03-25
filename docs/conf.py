# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import sys
import os

# Add path for autodoc
sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Laser Studio"
copyright = "2025 Ledger, Olivier Hériveaux, Michaël Mouchous"
author = "Olivier Hériveaux, Michaël Mouchous"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "myst_parser",
    "sphinx.ext.autosectionlabel",
    # "sphinx_togglebutton",
]

# Make sure the target is unique
autosectionlabel_prefix_document = True

# Add heading anchors for internal references
myst_heading_anchors = 2

myst_enable_extensions = [
    "colon_fence",
]

# togglebutton_hint = ""
# togglebutton_hint_hide = ""

version = "1.1.0b1"

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
# html_theme = "sphinx_book_theme"
html_static_path = []

html_logo = "images/logo.png"
