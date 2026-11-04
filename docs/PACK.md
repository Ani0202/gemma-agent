# Bundle validation and packaging

Run from the repository root:

```sh
bin/pack bundles/31b/v000
bin/pack bundles/e4b/v000 --zip
python3 -m pytest -q eval/tests/test_pack.py
```

Validation requires `agent.yaml` and `eval_config.yaml` at the bundle root.
The timing cap must be positive, finite, and satisfy
`evaluation.max_time_minutes * 125 + 30 <= 660`.
All agents must explicitly declare the same allowed quantized Gemma model.

`!include` paths resolve relative to the containing YAML file. `config_path`
references resolve relative to the bundle root. Both reject absolute paths,
null bytes and every `..` component, even when traversal would stay inside the
bundle. Place included files beside their consuming YAML, or beneath it.
Includes support Markdown/text and recursive YAML, with cycle detection and
a maximum depth of ten. Config reference cycles also fail validation.

PyYAML is used when installed. Without it, the conservative fallback supports
block mappings and lists, plain and quoted scalars, JSON flow collections,
literal/folded text blocks, and `!include`. Advanced YAML such as anchors and
non-JSON flow collections requires PyYAML; unsupported syntax fails validation.
The tests exercise both parsers and invoke `python3 -S` to verify the fallback.

`--zip` writes `dist/<parent-directory>-<bundle-directory>.zip` under this
repository, e.g. `dist/31b-v000.zip`. The archive contains sorted files with
fixed timestamps and permissions, with `agent.yaml` at its root. It omits only
the root `MANIFEST.md`. A manifest cannot be an include/config target because
it will not be shipped. File contents are streamed to avoid loading adapter
weights into RAM. The command prints SHA-256 and compressed size and refreshes
one `zip sha256: <digest>` line in the bundle manifest. Validation without
`--zip` writes nothing. Invalid bundles exit nonzero with a `FAIL:` message.
