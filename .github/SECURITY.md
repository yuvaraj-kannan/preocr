# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.7.x   | :white_check_mark: |
| 1.6.x   | :white_check_mark: |
| < 1.6   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in PreOCR, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email the maintainer directly at the email associated with the
[repository owner's GitHub profile](https://github.com/yuvaraj3855).

### What to include in your report

- A description of the vulnerability
- Steps to reproduce the issue
- The potential impact
- Any suggested fix (if you have one)

### What to expect

- **Acknowledgment**: You will receive a response within **72 hours** confirming receipt of your report.
- **Assessment**: The maintainer will assess the severity and impact within **7 days**.
- **Fix timeline**: Critical vulnerabilities will be patched within **14 days**. Non-critical issues will be addressed in the next minor release.
- **Disclosure**: Once a fix is released, the vulnerability will be disclosed publicly with credit to the reporter (unless you prefer to remain anonymous).

## Security Best Practices for Users

### Cache File Permissions

PreOCR stores cached results in `~/.preocr/cache/` by default. Cache files are created with
restricted permissions (`0o600` — owner read/write only) to prevent other users on shared systems
from reading cached document metadata.

### File Processing

- PreOCR processes files locally and does not transmit any data externally.
- No API keys or network connections are required.
- Be cautious when processing untrusted PDFs, as underlying PDF libraries (pdfplumber, PyMuPDF) may have their own security considerations.

## Dependencies

PreOCR depends on several third-party libraries. We recommend keeping dependencies up to date:

```bash
pip install --upgrade preocr
```

For a full list of dependencies and their versions, see [pyproject.toml](../pyproject.toml).
