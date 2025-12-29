"""Tests for UIProtectAlarms automations."""
# pylint: disable=used-before-assignment
import logging
from unittest.mock import patch
import pytest
from .imports import * # pylint: disable=W0401,W0614
from .integrationtestbase import IntegrationTestBase, PATCH_CALL_UIPROTECT_API
from custom_components.uiprotectalarms.switch import get_entries

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TestUIProtectAutomations(IntegrationTestBase):
    """Test PyUIProtectAlarms automation loading and control."""

    def test_load_automations(self):
        """Load automations and test basic properties."""

        self.api_response_file_name = "automations_1.json"
        self.manager.load_automations()
        
        # Verify automations were loaded
        assert len(self.manager.automations) == 33
        
        # Get the first automation
        automation_id = list(self.manager.automations.keys())[0]
        automation = self.manager.automations[automation_id]
        
        # Test initial state is not None
        assert automation.name is not None
        assert automation.enabled is not None
        
        logger.info(f"Loaded automation: {automation.name} (enabled: {automation.enabled})")
        
        # Test that switch entities are created from automations
        switch_entities = get_entries(self.manager.automations)
        
        # Should have 33 switch entities (one per automation)
        assert len(switch_entities) == 33
        
        # Verify first entity has proper attributes
        first_entity = switch_entities[0]
        assert first_entity is not None
        assert hasattr(first_entity, 'pyuiprotectalarms_automation')
        
        logger.info(f"Created {len(switch_entities)} switch entities")

    def test_enable_disable_automation(self):
        """Test enabling and disabling an automation."""

        self.api_response_file_name = "automations_1.json"
        self.manager.load_automations()
        
        # Get an automation
        automation_id = list(self.manager.automations.keys())[0]
        automation = self.manager.automations[automation_id]
        
        initial_state = automation.enabled
        logger.info(f"Initial state: {initial_state}")
        
        # Test disabling via property setter
        with patch(PATCH_CALL_UIPROTECT_API) as mock_api:
            mock_api.return_value = ({}, 200)
            automation.enabled = False
            # Verify API was called
            assert mock_api.called
        
        # Test enabling via property setter
        with patch(PATCH_CALL_UIPROTECT_API) as mock_api:
            mock_api.return_value = ({}, 200)
            automation.enabled = True
            # Verify API was called
            assert mock_api.called

    def test_automation_properties(self):
        """Test all automation properties are accessible."""

        self.api_response_file_name = "automations_1.json"
        self.manager.load_automations()
        
        # Verify all automations have required properties
        for automation_id, automation in self.manager.automations.items():
            # Each automation should have an ID
            assert automation.id is not None
            assert automation.id == automation_id
            
            # Each automation should have a name
            assert automation.name is not None
            assert len(automation.name) > 0
            
            # Each automation should have an enabled state
            assert automation.enabled is not None
            assert isinstance(automation.enabled, bool)
            
            logger.debug(f"Automation: {automation.name} - ID: {automation_id} - Enabled: {automation.enabled}")

    def test_update_automation_state(self):
        """Test updating automation state from server."""

        self.api_response_file_name = "automations_1.json"
        self.manager.load_automations()
        
        # Get an automation
        automation_id = list(self.manager.automations.keys())[0]
        automation = self.manager.automations[automation_id]
        
        # Test state update (note: update_state expects "enable" not "isEnabled")
        new_state = {"id": automation_id, "name": automation.name, "enable": False}
        automation.update_state(new_state)
        
        # Verify state was updated
        assert automation.enabled is False
        
        # Update again
        new_state = {"id": automation_id, "name": automation.name, "enable": True}
        automation.update_state(new_state)
        
        # Verify state was updated
        assert automation.enabled is True
