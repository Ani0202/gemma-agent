Implemented the 399-line self-contained kernel, push wrapper, summary CLI, and offline tests under `eval/`. Also fixed gold-calibration diagnostics leaking raw error text and isolated its test fixture.

Tests passed using the requested interpreter with cached pytest supplied through `PYTHONPATH`:

```text
365 passed, 1 skipped, 4 subtests passed in 3.34s
```

Dry run staged a **27,776-byte script** for `fastapi_14258` and `fastapi_14372`. [Staged metadata](/tmp/timing-kernel-push.qxQlio/kernel-metadata.json) specifies:

- GPU enabled; internet disabled
- Wheelhouse dataset and competition inputs
- Model: `google/gemma-4/other/gemma-4-e4b-it-qat-w4a16-ct/2`

Open issues: GPU execution remains untested; model metadata uses the requested offline assumption. Harness inspection triggered an automatic LiteLLM lookup that failed on DNS; no network data was fetched.

No Kaggle pushes or git commits were made.
