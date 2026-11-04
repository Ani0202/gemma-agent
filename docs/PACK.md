# Bundle validation and packaging

Run from the repository root:

```sh
bin/pack bundles/31b/v000
bin/pack bundles/e4b/v000 --zip
python3 -m pytest -q eval/tests/test_pack.py
```

`PASS` means the bundle passed the static checks below. Pack does not invoke the
harness compiler, launch a model, execute skill scripts, run an agent or grade a
patch. It does not guarantee full ADK schema compatibility, harness acceptance,
model/adapter compatibility, runtime completion, patch production or test success.
It does not determine whether prompts forbid editing tests, require scratch work
in `/tmp`, or implement a fallback diff. Those require separate review and runtime
evaluation. Harness limits and the nine-tool registry are a local snapshot derived
from `data/raw/HARNESS_README.md` sections 2.3–2.4 and 6, not a live registry lookup.

Pack requires `agent.yaml` and `eval_config.yaml` at the bundle root, and rejects
alternative root agent filenames alongside `agent.yaml`. Every root, inline,
referenced and standalone agent declaration must have a nonempty string `name`
and explicitly declare the same allowed quantized Gemma model (31b, 12b, e4b or
e2b). Supported classes are `LlmAgent` (default), `SequentialAgent`,
`ParallelAgent` and `LoopAgent`. This repository's explicit-model rule also
applies to workflow agents and is stricter than the harness's workflow schema.

Tools must form a list of registry names, inline agent mappings, or
`agent_tool: {config_path: ..., skip_summarization: ...}` references. Registry
names are exactly `run_command`, `submit_patch`, `get_status`, `read_file`,
`edit_file`, `write_file`, `get_code_neighbors`, `search_similar_code` and
`get_code_subgraph`. Skills are an optional list of relative directory paths:
absolute paths, null bytes and any `..` component are forbidden. Each directory
must exist in the bundle, contain `SKILL.md`, and contain at most 50 MiB of files.
Pack does not validate skill metadata or execute scripts.

The inclusive structural ceilings are:

| Check | Limit |
| --- | --- |
| Shipped files | 10,000 |
| YAML files (`.yaml` and `.yml`) | 1,000 |
| Each YAML / text include and cumulative include expansion per document | 50 MiB |
| Combined `instruction` and `global_instruction` per agent | 1,000,000 characters |
| Instruction characters across agent occurrences | 10,000,000 |
| Each agent's `description` | 1,000,000 characters |
| Agent occurrences | 500 |
| Nested agent edges below a root (depth zero) | 50 |
| Skill references across agent occurrences | 1,000 |
| `LoopAgent.max_iterations` | Integer 1–500; default 500 |

Repeated config references and aliases count separately when they create agent
occurrences. Referenced agent documents are not counted again as standalone
agents. Unreferenced agent documents are also validated and included in totals.
Include expansion counts source UTF-8 bytes plus each transitive include's byte
count on every occurrence, even when parsing uses a cache. The include recursion
ceiling remains ten nested includes, separate from the agent depth limit.
Instruction counts use decoded characters, including included text.

`generate_content_config` must be a mapping or null. Its allowed fields are
`temperature`, `top_p`, `top_k`, `max_output_tokens`, `presence_penalty`,
`frequency_penalty`, `stop_sequences`, `response_mime_type`, `seed` and
`thinking_config`. All other fields are rejected, including `http_options`,
`tools`, `system_instruction`, `safety_settings` and `response_schema`.
Pack checks integer `max_output_tokens` in 1–32,768, integer thinking budgets
in 0–32,768, the documented thinking levels, and boolean `include_thoughts`.
It does not validate the types/ranges of the other sampling fields or every
other ADK agent field.

The required `evaluation.max_time_minutes` must be positive, finite, and satisfy
`max_time_minutes * 125 + 30 <= 660`. Optional `timeout_seconds`,
`max_tool_calls` and `max_turns` must be positive integers when present
(booleans are rejected). This arithmetic checks the repository's declared
budget policy; it does not prove that the runtime enforces those budgets.

`!include` paths resolve relative to the containing YAML file. `config_path`
references resolve relative to the bundle root and must target YAML mappings.
Both reject absolute paths, null bytes and every `..` component, even when
traversal would stay inside the bundle. Includes support Markdown/text and
recursive YAML; include/reference cycles and recursive YAML aliases fail.
Duplicate YAML keys and null bytes in text also fail. Instruction/prompt
placeholders matching `{identifier}` or `{identifier?}` are rejected except
`{problem_description}`; this is a conservative lint, not a template parser.
Text files anywhere under a `prompts` directory receive the same placeholder
check. Referenced adapters must have both `adapters/<name>/adapter_config.json`
and `adapter_model.safetensors`; pack does not inspect their binary validity.

PyYAML is used when installed. Without it, the conservative fallback supports
block mappings and lists, single-line quoted/plain scalars, JSON flow
collections, literal/folded text blocks, and `!include`. Advanced YAML such as
anchors, multiline quoted strings and non-JSON flow collections requires
PyYAML; unsupported syntax fails validation. Existing v000 bundles require
PyYAML for their multiline quoted prompts. Tests exercise both parsers and
invoke `python3 -S` to verify the fallback.

Only `.yaml`, `.yml`, `.md`, `.txt`, `.py`, `.json` and `.safetensors`
files are allowed. Symlinks, special files and unsafe paths fail. Shipped
unpacked bytes must be strictly less than 3 GiB (3,221,225,472 bytes), including
adapter weights. The root `MANIFEST.md` is excluded from shipped size/file
counts, content checks and the archive, and cannot be an include/config target.
Its filesystem type is still checked. Nested manifests are shipped normally.

`--zip` writes `dist/<parent-directory>-<bundle-directory>.zip` under this
repository, e.g. `dist/31b-v000.zip`. The archive contains sorted files with
fixed timestamps and permissions, with `agent.yaml` at its root. File contents
are streamed to avoid loading adapter weights into RAM. The command prints
SHA-256 and compressed size and refreshes one `zip sha256: <digest>` line in
the bundle manifest. Archive output is reproducible for unchanged source bytes
under the same compression implementation. Keep the source directory unchanged
between validation and archive completion; pack does not snapshot files or
protect against concurrent mutation. Validation without `--zip` writes nothing.
Invalid bundles exit nonzero with a `FAIL:` message.
