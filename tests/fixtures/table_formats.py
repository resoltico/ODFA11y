# SPDX-License-Identifier: MPL-2.0
"""Explicit Writer number formatting needed to retain native numeric cell values."""

NUMERIC_STYLES = (
    '<number:number-style xmlns:number="urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0" '
    'style:name="N1"><number:number number:decimal-places="0" number:min-integer-digits="1"/>'
    '</number:number-style><style:style style:name="Numeric" style:family="table-cell" '
    'style:data-style-name="N1"/>'
)
