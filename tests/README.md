# UIProtectAlarms Tests

This directory contains tests for the UIProtectAlarms Home Assistant integration.

## Test Structure

The tests are organized into two main directories:

### `pyuiprotectalarms/`
Unit tests for the core PyUIProtectAlarms Python library that handles UniFi Protect API communication.
- API functionality tests
- Helper function tests  
- Mock API responses in `api_responses/` folder
- All tests inherit from `TestBase` class

### `uiprotectalarms/`
Tests for the Home Assistant integration layer.
- Config flow tests
- Entity tests
- Integration tests
- Platform tests (switches, sensors, etc.)

## Running Tests

```bash
# Run all tests
pytest

# Run only pyuiprotectalarms tests
pytest tests/pyuiprotectalarms/

# Run only Home Assistant integration tests
pytest tests/uiprotectalarms/

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=custom_components.uiprotectalarms
```

## Test Requirements

Required packages are listed in `requirements.test.txt`:
- pytest
- pytest-asyncio
- pytest-homeassistant-custom-component (for Home Assistant integration tests)

Install with:
```bash
pip install -r requirements.test.txt
```

## Contributing Tests

Please feel free to contribute more tests! When adding tests:
- Place library tests in `pyuiprotectalarms/`
- Place Home Assistant integration tests in `uiprotectalarms/`
- Add API response mocks to `pyuiprotectalarms/api_responses/`
- Redact sensitive information from mock responses