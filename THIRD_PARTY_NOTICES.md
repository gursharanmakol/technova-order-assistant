# Third-party notices

This repository bundles no third-party code, models, or data. Everything in it is covered by the repository `LICENSE`.

The lab depends on third-party Python packages. `uv` or `pip` downloads them from PyPI during setup, and each keeps its own license. `uv.lock` and `requirements.txt` pin the exact versions. They name the packages but do not contain them.

TechNova, its products, orders, and teams are fictional.

## Direct dependencies

| Package | Version | License | Used for |
| --- | --- | --- | --- |
| `mcp` (MCP Python SDK) | 2.3.0 | MIT, Copyright (c) 2024 Anthropic, PBC | The MCP server, client, and stdio transport. Source: https://github.com/modelcontextprotocol/python-sdk |
| `pytest` | 9.2.0 | MIT | Running the regression test |

## Packages installed with them

These are the licenses each package declares in its own package metadata. Check each project for the authoritative terms.

| Package | Version | Declared license |
| --- | --- | --- |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| attrs | 26.1.0 | MIT |
| cffi | 2.1.1 | MIT-0 |
| click | 8.5.0 | BSD-3-Clause |
| colorama (Windows only) | 0.4.6 | BSD |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| h11 | 0.16.0 | MIT |
| httpcore2 | 2.16.0 | BSD-3-Clause |
| httpx2 | 2.16.0 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| mcp-types | 2.3.0 | MIT |
| opentelemetry-api | 1.45.2 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.7.0 | MIT |
| pycparser | 3.12 | BSD-3-Clause |
| pydantic | 2.14.2 | MIT |
| pydantic-core | 2.50.2 | MIT |
| pygments | 2.21.0 | BSD-2-Clause |
| pyjwt | 2.15.1 | MIT |
| python-multipart | 0.0.33 | Apache-2.0 |
| pywin32 (Windows only) | 312 | See https://github.com/mhammond/pywin32 |
| referencing | 0.37.0 | MIT |
| rpds-py | 2026.9.1 | MIT |
| sse-starlette | 3.6.0 | BSD-3-Clause |
| starlette | 1.10.0 | BSD-3-Clause |
| truststore | 0.10.5 | MIT |
| typing-extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.4 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |

`httpx2-jsfetch` appears in `uv.lock` for the browser (Emscripten) platform only, and is never installed on Windows, macOS, or Linux.
