# Demo Fixture Mode

This folder supports deterministic demo runs using saved HTML from real public URLs.

1. Save HTML files captured from public event/association pages in this directory.
2. Add URL mappings in `manifest.json`.
3. Enable fixture mode with:
- `DEMO_FIXTURE_MODE=true`
- `DEMO_FIXTURE_MANIFEST=data/demo_fixtures/manifest.json`

Manifest format:

```json
{
  "https://example.org/": {
    "status": "success",
    "fixture_file": "example_org_home.html",
    "reason": "captured_2026-03-06"
  }
}
```

Only include fixtures sourced from real public pages.
