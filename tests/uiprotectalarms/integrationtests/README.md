# UIProtectAlarms Integration Tests

This directory contains Home Assistant integration tests that verify the complete integration behavior including entity creation, state management, and service calls.

## Test Files

- `integrationtestbase.py` - Base class for integration tests with mocking setup
- `test_switch_entities.py` - Tests for switch entity creation and attributes
- `imports.py` - Centralized imports
- `defaults.py` - Default test values

## What These Tests Verify

Integration tests verify the full integration behavior:
- Config entry creation and setup
- Entity registration in Home Assistant
- Entity state management
- Service call handling
- Integration lifecycle (setup, reload, unload)

## Running Tests

```bash
# Run all integration tests
pytest tests/uiprotectalarms/integrationtests/ -v

# Run specific test file
pytest tests/uiprotectalarms/integrationtests/test_switch_entities.py -v

# Run with Home Assistant fixtures
pytest tests/uiprotectalarms/integrationtests/ -v --log-cli-level=DEBUG
```

## Requirements

These tests require:
- `pytest-homeassistant-custom-component` package
- Home Assistant test fixtures
- Mock config entries

Install with:
```bash
pip install pytest-homeassistant-custom-component
```

## Adding New Tests

When adding integration tests:
1. Inherit from `IntegrationTestBase`
2. Use `@pytest.mark.asyncio` for async tests
3. Use `hass` fixture for Home Assistant instance
4. Create mock config entries with `MockConfigEntry`
5. Verify entity creation and behavior
