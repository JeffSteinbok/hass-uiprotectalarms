# UIProtectAlarms Home Assistant Integration Tests

This directory contains tests for the Home Assistant integration layer that wraps the PyUIProtectAlarms library.

## Test Organization

Tests in this directory verify:
- Config flow functionality
- Entity creation and management
- Home Assistant service calls
- Integration initialization and setup
- Platform-specific functionality (switches, sensors, etc.)

## Running Tests

From the project root:

```bash
# Run all Home Assistant integration tests
pytest tests/uiprotectalarms/

# Run with Home Assistant test fixtures
pytest tests/uiprotectalarms/ -v
```

## Future Tests

This directory is prepared for Home Assistant integration tests. Common test patterns include:
- `test_init.py` - Integration initialization tests
- `test_config_flow.py` - Configuration flow tests
- `test_switch.py` - Switch platform tests
- Integration test directories for more complex scenarios
