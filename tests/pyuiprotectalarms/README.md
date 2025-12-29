# PyUIProtectAlarms Library Tests

This directory contains unit tests for the PyUIProtectAlarms library - the core Python library that interfaces with the UniFi Protect API.

## Test Files

- `test_all_devices.py` - Tests for general API functionality including authentication and device loading
- `test_helpers.py` - Tests for helper utility functions (redaction, token decoding, etc.)
- `testbase.py` - Base test class with fixtures and mocking setup
- `defaults.py` - Default values and constants used in tests
- `call_json.py` - Helper functions for API call mocking
- `imports.py` - Centralized imports for tests
- `api_responses/` - Mock API response JSON files

## Running Tests

From the project root:

```bash
# Run all pyuiprotectalarms tests
pytest tests/pyuiprotectalarms/

# Run specific test file
pytest tests/pyuiprotectalarms/test_helpers.py

# Run with verbose output
pytest tests/pyuiprotectalarms/ -v
```
