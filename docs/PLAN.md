# Decision plans

Run `odfa11y plan original.odt` to print a source-bound TOML plan. Review each
question, supply its answer and enable only the reviewed decision tables. Pass
`--plan reviewed.plan.toml` to `remediate` or `pipeline`. `compare` reads its fidelity
policy. Plans are never loaded automatically.

## Example

The SHA-256 value must identify the exact reviewed source bytes. Generate it with
the `plan` command; the value below is illustrative.

```toml
[plan]
format = 1
generator = "0.8.0"
source.sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

[decisions."document.metadata"]
title = "Example report"
description = "Summary of the reporting period"
language = "en-GB"

[fidelity]
pagination = "same"
```

Each registered decision kind defines its fields. Document decisions bind through
the header. Targeted decisions additionally require the canonical target path and
16-character fingerprint printed by the audit or plan command. Do not invent
fingerprints or infer answers from filenames. Unknown fields, old configuration
tables, invalid types and missing binding metadata are rejected.

`--rebind` explicitly permits a different source digest. It does not bypass target
fingerprints or preservation checks. Reapplying a reviewed answer to a remediated
source therefore requires rebind and still checks the target's preserved identity.

Remediation reports every operation outcome and structured refusal. A refused
candidate is not published and exits 2. A successful `--dry-run` exits 0 with
`published=false`; a failing preview exits 2 and retains the refusal evidence.

<!-- generated decisions -->
## Registered decisions

### `document.odf_version`

Scope: document.

```json
{
  "type": "object",
  "properties": {
    "version": {
      "type": "string",
      "enum": [
        "1.3",
        "1.4"
      ],
      "description": "ODF version whose result must satisfy schema guards."
    }
  },
  "required": [
    "version"
  ],
  "additionalProperties": false
}
```

### `document.metadata`

Scope: document.

```json
{
  "type": "object",
  "properties": {
    "title": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "odfa11y-xml-text",
      "description": "Document title identifying its purpose.",
      "pattern": "\\S"
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "odfa11y-xml-text",
      "description": "Document description and context.",
      "pattern": "\\S"
    },
    "language": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "pattern": "\\S",
      "description": "Intended default language, preserving explicit local overrides.",
      "format": "odfa11y-language-tag"
    }
  },
  "required": [],
  "additionalProperties": false,
  "anyOf": [
    {
      "required": [
        "title"
      ],
      "properties": {
        "title": {
          "not": {
            "type": "null"
          }
        }
      }
    },
    {
      "required": [
        "description"
      ],
      "properties": {
        "description": {
          "not": {
            "type": "null"
          }
        }
      }
    },
    {
      "required": [
        "language"
      ],
      "properties": {
        "language": {
          "not": {
            "type": "null"
          }
        }
      }
    }
  ]
}
```

### `text.linkify_addresses`

Scope: document.

```json
{
  "type": "object",
  "properties": {
    "enabled": {
      "type": "boolean",
      "description": "Enable only after reviewing all affected content."
    }
  },
  "required": [
    "enabled"
  ],
  "additionalProperties": false
}
```

### `text.remove_spacers`

Scope: document.

```json
{
  "type": "object",
  "properties": {
    "enabled": {
      "type": "boolean",
      "description": "Enable only after reviewing all affected content."
    }
  },
  "required": [
    "enabled"
  ],
  "additionalProperties": false
}
```

### `graphic.alternative`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

```json
{
  "type": "object",
  "properties": {
    "title": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "odfa11y-xml-text",
      "description": "Accessible title; empty text explicitly clears it."
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "odfa11y-xml-text",
      "description": "Explain the graphic's meaning; empty text clears it."
    },
    "decorative": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "description": "Explicit decorative role, subject to source safety guards."
    }
  },
  "required": [],
  "additionalProperties": false,
  "anyOf": [
    {
      "required": [
        "title"
      ],
      "properties": {
        "title": {
          "not": {
            "type": "null"
          }
        }
      }
    },
    {
      "required": [
        "description"
      ],
      "properties": {
        "description": {
          "not": {
            "type": "null"
          }
        }
      }
    },
    {
      "required": [
        "decorative"
      ],
      "properties": {
        "decorative": {
          "not": {
            "type": "null"
          }
        }
      }
    }
  ]
}
```

### `heading.level`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

```json
{
  "type": "object",
  "properties": {
    "level": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10,
      "description": "Intended outline level."
    }
  },
  "required": [
    "level"
  ],
  "additionalProperties": false
}
```

### `table.headers`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

```json
{
  "type": "object",
  "properties": {
    "rows": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "minimum": 1,
      "description": "Number of leading logical header rows."
    },
    "columns": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "minimum": 1,
      "description": "Number of leading logical header columns."
    }
  },
  "required": [],
  "additionalProperties": false,
  "anyOf": [
    {
      "required": [
        "rows"
      ],
      "properties": {
        "rows": {
          "not": {
            "type": "null"
          }
        }
      }
    },
    {
      "required": [
        "columns"
      ],
      "properties": {
        "columns": {
          "not": {
            "type": "null"
          }
        }
      }
    }
  ]
}
```

### `text.spacing`

Scope: document.

```json
{
  "type": "object",
  "properties": {
    "reference_text": {
      "type": "string",
      "pattern": "\\S",
      "description": "Authored text identifying the reference paragraph."
    },
    "target_styles": {
      "type": "array",
      "items": {
        "type": "string",
        "pattern": "\\S"
      },
      "minItems": 1,
      "description": "Existing paragraph styles selected for spacing normalization."
    },
    "exact_reference": {
      "type": "boolean",
      "description": "Match the entire reference paragraph."
    },
    "include_headings": {
      "type": "boolean",
      "description": "Also apply to headings using the selected styles."
    }
  },
  "required": [
    "reference_text",
    "target_styles"
  ],
  "additionalProperties": false
}
```

### `link.description`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

```json
{
  "type": "object",
  "properties": {
    "description": {
      "type": "string",
      "format": "odfa11y-xml-text",
      "description": "Explain the link's purpose in its reading context.",
      "pattern": "\\S"
    }
  },
  "required": [
    "description"
  ],
  "additionalProperties": false
}
```

### `database.description`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

```json
{
  "type": "object",
  "properties": {
    "text": {
      "type": "string",
      "format": "odfa11y-xml-text",
      "description": "Explain the declared object without changing SQL or bindings.",
      "pattern": "\\S"
    }
  },
  "required": [
    "text"
  ],
  "additionalProperties": false
}
```

### `formula.alternative`

Scope: document.

```json
{
  "type": "object",
  "properties": {
    "alternative": {
      "type": "string",
      "format": "odfa11y-xml-text",
      "description": "Write the formula's spoken meaning in its intended language.",
      "pattern": "\\S"
    }
  },
  "required": [
    "alternative"
  ],
  "additionalProperties": false
}
```

### `page.metadata`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

```json
{
  "type": "object",
  "properties": {
    "title": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "odfa11y-xml-text",
      "description": "Accessible page title."
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "odfa11y-xml-text",
      "description": "Page purpose and context."
    }
  },
  "required": [],
  "additionalProperties": false,
  "anyOf": [
    {
      "required": [
        "title"
      ],
      "properties": {
        "title": {
          "not": {
            "type": "null"
          }
        }
      }
    },
    {
      "required": [
        "description"
      ],
      "properties": {
        "description": {
          "not": {
            "type": "null"
          }
        }
      }
    }
  ]
}
```

### `page.navigation`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

```json
{
  "type": "object",
  "properties": {
    "navigation": {
      "type": "array",
      "items": {
        "type": "string",
        "pattern": "\\S",
        "format": "odfa11y-xml-text"
      },
      "description": "Complete reading order of the page's existing shape identities."
    }
  },
  "required": [
    "navigation"
  ],
  "additionalProperties": false
}
```

### `sheet.name`

Scope: target.

Use the audit's canonical target and mandatory fingerprint.

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "format": "odfa11y-sheet-name",
      "description": "Name identifying what the sheet contains."
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```
