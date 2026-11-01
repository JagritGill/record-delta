# Dependencies and provenance

Runtime and tests use only Python's standard library. Python is supplied by
the user's environment and is not vendored. Python software and documentation
use the [PSF License Version 2](https://docs.python.org/3/license.html), with
additional terms for incorporated components as documented there.

GitHub CI uses external GitHub actions, pinned to release commits. They retain
their own MIT license notices:

- `actions/checkout` v7.0.1: [license](https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/LICENSE)
- `actions/setup-python` v7.1.0: [license](https://github.com/actions/setup-python/blob/6d4fd22b20465ccc0f7354476588e8df7c9ca0e0/LICENSE)

Field paths use the escaping convention specified by [RFC 6901](https://www.rfc-editor.org/rfc/rfc6901).
The standard is a reference, not copied application source. The Python
[JSON decoder documentation](https://docs.python.org/3/library/json.html)
documents the hooks used for duplicate-key and exact-number handling.

Application code, tests, examples, and documentation were created with AI
assistance in Codex in a fresh isolated folder for this portfolio project.
All example records and test fixtures are synthetic. No private repositories,
employer/business source, or third-party application implementations were read
or copied. Merge joins and structural comparison are established techniques;
this project does not claim their invention.

Original project files use the [MIT License](LICENSE). That license does not
relicense Python, external CI actions, or referenced standards. No third-party
packages, datasets, images, fonts, or other assets are bundled.
