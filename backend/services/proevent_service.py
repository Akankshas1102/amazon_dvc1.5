"""
ProEvent Service - FIXED VERSION
=================================
FIXED: When ProEvent is unchecked from ignore list, it becomes REACTIVE (state = 0) immediately
"""

from services import proserver_service, device_service, cache_service
import sqlite_config
import pytz
from datetime import datetime
from logger import get_logger

logger = get_logger(__name__)

# --- EXISTING FUNCTIONS ---

def get_all_proevents_for_building(building_id: int, search: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    """
    Gets all ProEvents for a building with their current reactive state.
    
    Returns:
        list[dict]: ProEvents with 'reactive_state' field (0=armed/reactive, 1=disarmed/non-reactive)
    """
    try:
        proevents = device_service.get_devices(
            building_id=building_id, search=search, limit=limit, offset=offset
        )
        if not proevents:
            return []
        
        return proevents
        
    except Exception as e:
        logger.error(f"Error getting ProEvents for building {building_id}: {e}")
        return []


def set_proevent_reactive_for_building(building_id: int, reactive_state: int, ignore_ids: list[int] | None = None) -> int:
    """
    Sets the reactive state for ProEvents in a building, skipping ignored IDs.
    
    Args:
        building_id: Building ID
        reactive_state: 0 = ARMED (reactive), 1 = DISARMED (non-reactive)
        ignore_ids: List of ProEvent IDs to skip
        
    Returns:
        int: Number of ProEvents updated
    """
    if ignore_ids is None:
        ignore_ids = []
    
    logger.info(f"Setting reactive state to {reactive_state} ({'ARMED' if reactive_state == 0 else 'DISARMED'}) for building {building_id}, ignoring {len(ignore_ids)} IDs.")
    
    try:
        proevents = device_service.get_devices(building_id=building_id, limit=1000)
        if not proevents:
            logger.warning(f"No ProEvents found for building {building_id}, nothing to update.")
            return 0
            
        proevent_ids_to_update = [
            p["id"] for p in proevents if p["id"] not in ignore_ids
        ]

        if not proevent_ids_to_update:
            logger.info(f"All ProEvents in building {building_id} were on the ignore list. No updates sent.")
            return 0

        target_states = [{"id": pid, "state": reactive_state} for pid in proevent_ids_to_update]
        success = proserver_service.set_proevent_reactive_state_bulk(target_states)
        
        return len(proevent_ids_to_update) if success else 0
        
    except Exception as e:
        logger.error(f"Error in set_proevent_reactive_for_building (Building {building_id}): {e}")
        return 0


def manage_proevents_on_panel_state_change():
    """
    FIXED LOGIC - Monitors panel state changes and manages ProEvent reactive states.
    
    CORRECT BEHAVIOR:
    - Panel ARMED (AreaArmingStates.4) -> Make ALL user-selected ProEvents REACTIVE (state = 0)
    - Panel DISARMED (AreaArmingStates.2) -> Make user-selected (ignored) ProEvents NON-REACTIVE (state = 1)
    - Respects manually set non-reactive ProEvents (always keeps them at state = 1)
    """
    try:
        # Get current panel states from database
        live_states = proserver_service.get_all_live_building_arm_states()
        
        # Get cached panel states
        cached_states = cache_service.get_cache_value("panel_state_cache") or {}
        new_cached_states = cached_states.copy()

        for building_id, is_panel_armed in live_states.items():
            prev_state = cached_states.get(str(building_id))
            
            current_state_str = 'ARMED (AreaArmingStates.4)' if is_panel_armed else 'DISARMED (AreaArmingStates.2)'
            prev_state_str = 'ARMED' if prev_state else 'DISARMED' if prev_state is not None else 'UNKNOWN'
            
            logger.debug(f"[Building {building_id}] Panel state: {current_state_str}, Previous: {prev_state_str}")

            # First run → store and continue
            if prev_state is None:
                new_cached_states[str(building_id)] = is_panel_armed
                logger.info(f"[Building {building_id}] Initial panel state cached: {current_state_str}")
                continue

            # No change → skip
            if prev_state == is_panel_armed:
                continue

            # Panel state changed
            state_change_str = f"{'DISARMED' if prev_state else 'ARMED'} → {'ARMED' if is_panel_armed else 'DISARMED'}"
            logger.info(f"🔄 [Building {building_id}] Panel state changed: {state_change_str}")

            # Apply the correct ProEvent states based on new panel state
            apply_proevent_states_for_building(building_id, is_panel_armed)
            
            # Update cache
            new_cached_states[str(building_id)] = is_panel_armed

        # Update cache with new states
        cache_service.set_cache_value("panel_state_cache", new_cached_states)

    except Exception as e:
        logger.error(f"❌ Error in manage_proevents_on_panel_state_change: {e}", exc_info=True)


def apply_proevent_states_for_building(building_id: int, is_panel_armed: bool):
    """
    Applies the correct ProEvent reactive states based on panel state.
    RESPECTS manually set non-reactive ProEvents.
    
    Args:
        building_id: Building ID
        is_panel_armed: True if panel is ARMED (AreaArmingStates.4), False if DISARMED (AreaArmingStates.2)
    """
    try:
        # Fetch all ProEvents for this building from database
        all_proevents = proserver_service.get_proevents_for_building_from_db(building_id)
        if not all_proevents:
            logger.warning(f"[Building {building_id}] No ProEvents found in database.")
            return

        # Load user-selected (ignored) ProEvents from SQLite
        ignored_map = sqlite_config.get_ignored_proevents()
        user_ignored_ids = {
            pid for pid, data in ignored_map.items()
            if data.get("building_frk") == building_id and data.get("ignore_on_disarm")
        }

        # Identify manually non-reactive ProEvents (those currently at state=1 that aren't in user's ignore list)
        manually_non_reactive_ids = {
            p["id"] for p in all_proevents 
            if p["state"] == 1 and p["id"] not in user_ignored_ids
        }

        logger.info(f"[Building {building_id}] Total ProEvents: {len(all_proevents)}, "
                   f"User-ignored: {len(user_ignored_ids)}, "
                   f"Manually non-reactive: {len(manually_non_reactive_ids)}")

        target_states = []

        # === PANEL ARMED (AreaArmingStates.4) ===
        if is_panel_armed:
            # Make user-selected ProEvents REACTIVE (state = 0)
            # Keep manually non-reactive ProEvents as NON-REACTIVE (state = 1)
            for p in all_proevents:
                if p["id"] in manually_non_reactive_ids:
                    # Keep manually non-reactive ProEvents at state = 1
                    target_states.append({"id": p["id"], "state": 1})
                else:
                    # Make all others REACTIVE (state = 0)
                    target_states.append({"id": p["id"], "state": 0})
            
            success = proserver_service.set_proevent_reactive_state_bulk(target_states)
            if success:
                reactive_count = sum(1 for s in target_states if s["state"] == 0)
                non_reactive_count = len(target_states) - reactive_count
                logger.info(f"✅ [Building {building_id}] Panel ARMED → "
                          f"{reactive_count} ProEvents set to REACTIVE (0), "
                          f"{non_reactive_count} kept NON-REACTIVE (1)")
            else:
                logger.error(f"❌ [Building {building_id}] Failed to set ProEvent states on panel ARM")

        # === PANEL DISARMED (AreaArmingStates.2) ===
        else:
            # Make user-selected ProEvents NON-REACTIVE (state = 1)
            # Keep manually non-reactive ProEvents as NON-REACTIVE (state = 1)
            # Keep others as REACTIVE (state = 0)
            for p in all_proevents:
                if p["id"] in user_ignored_ids or p["id"] in manually_non_reactive_ids:
                    # Make user-ignored and manually non-reactive ProEvents NON-REACTIVE (state = 1)
                    target_states.append({"id": p["id"], "state": 1})
                else:
                    # Keep others REACTIVE (state = 0)
                    target_states.append({"id": p["id"], "state": 0})
            
            success = proserver_service.set_proevent_reactive_state_bulk(target_states)
            if success:
                non_reactive_count = sum(1 for s in target_states if s["state"] == 1)
                reactive_count = len(target_states) - non_reactive_count
                logger.info(f"✅ [Building {building_id}] Panel DISARMED → "
                          f"{non_reactive_count} ProEvents set to NON-REACTIVE (1), "
                          f"{reactive_count} kept REACTIVE (0)")
            else:
                logger.error(f"❌ [Building {building_id}] Failed to set ProEvent states on panel DISARM")

    except Exception as e:
        logger.error(f"❌ Failed to apply ProEvent states for building {building_id}: {e}", exc_info=True)


def check_and_manage_scheduled_states():
    """
    Checks if current time matches building start_time and sends alert if panel is disarmed.
    """
    try:
        tz = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(tz).strftime("%H:%M")
        live_building_arm_states = proserver_service.get_all_live_building_arm_states()

        for building_id, is_panel_armed in live_building_arm_states.items():
            schedule = sqlite_config.get_building_time(building_id)
            if not schedule:
                continue

            start_time = (schedule.get("start_time") or "20:00")[:5]

            if current_time != start_time:
                continue

            if is_panel_armed:
                logger.info(f"[Building {building_id}] Panel ARMED (AreaArmingStates.4) at start time {start_time}. No alert sent.")
            else:
                logger.warning(f"⚠️ [Building {building_id}] Panel DISARMED (AreaArmingStates.2) at start time {start_time}. Sending AXE alert.")
                proserver_service.send_disarmed_axe_message(building_id)

    except Exception as e:
        logger.error(f"❌ Error in check_and_manage_scheduled_states: {e}", exc_info=True)


def reevaluate_building_state(building_id: int):
    """
    FIXED - Triggers an immediate re-application of ProEvent states for a building.
    This is called when user changes ignore settings.
    
    CRITICAL FIX: When a ProEvent is unchecked (removed from ignore list), it should become
    REACTIVE (state = 0) immediately, regardless of panel state.
    """
    try:
        logger.info(f"[Building {building_id}] Manual re-evaluation triggered - applying ProEvent states based on current settings...")
        
        # Get current panel state
        live_states = proserver_service.get_all_live_building_arm_states()
        is_panel_armed = live_states.get(building_id)
        
        if is_panel_armed is None:
            logger.warning(f"[Building {building_id}] Could not determine panel state during re-evaluation")
            return
        
        panel_state_str = 'ARMED (AreaArmingStates.4)' if is_panel_armed else 'DISARMED (AreaArmingStates.2)'
        logger.info(f"[Building {building_id}] Current panel state: {panel_state_str}")
        
        # FIXED LOGIC: Apply the correct ProEvent states
        # This will set unchecked ProEvents to REACTIVE (state = 0) immediately
        apply_proevent_states_for_building(building_id, is_panel_armed)
        
        logger.info(f"✅ [Building {building_id}] Re-evaluation completed - ProEvent states updated")
        
    except Exception as e:
        logger.error(f"❌ Error in reevaluate_building_state (Building {building_id}): {e}", exc_info=True)
        raise


# --- SNAPSHOT FUNCTIONS (KEPT FOR COMPATIBILITY) ---

def take_snapshot_and_apply_schedule(building_id: int):
    """
    Takes snapshot and applies scheduled state.
    NOTE: This function is kept for compatibility but may not be used in current flow.
    """
    try:
        all_proevents = proserver_service.get_proevents_for_building_from_db(building_id)
        
        if not all_proevents:
            logger.warning(f"[Building {building_id}] No ProEvents found in database to snapshot.")
            return

        # Save snapshot (current states: 0=reactive/armed, 1=non-reactive/disarmed)
        snapshot_data = [
            {"id": proevent["id"], "state": proevent["state"]} 
            for proevent in all_proevents
        ]
        
        sqlite_config.save_snapshot(building_id, snapshot_data)
        logger.info(f"[Building {building_id}] Snapshot saved with {len(snapshot_data)} ProEvents")
        
        # Get user-ignored ProEvents
        ignored_map = sqlite_config.get_ignored_proevents()
        ignored_ids = {
            pid for pid, data in ignored_map.items()
            if data.get("building_frk") == building_id and data.get("ignore_on_disarm")
        }
        
        # Apply scheduled state
        target_states = []
        for proevent in snapshot_data:
            proevent_id = proevent['id']
            
            if proevent_id in ignored_ids:
                # User-ignored ProEvents -> NON-REACTIVE (state = 1)
                target_states.append({"id": proevent_id, "state": 1})
            else:
                # Others -> REACTIVE (state = 0)
                target_states.append({"id": proevent_id, "state": 0})

        logger.info(f"[Building {building_id}] Applying schedule: "
                   f"{len(ignored_ids)} ProEvents to NON-REACTIVE (1), "
                   f"{len(target_states) - len(ignored_ids)} to REACTIVE (0)")
        
        proserver_service.set_proevent_reactive_state_bulk(target_states)

    except Exception as e:
        logger.error(f"❌ Failed to take snapshot for building {building_id}: {e}", exc_info=True)


def revert_snapshot(building_id: int, snapshot_data: list[dict]):
    """
    Reverts ProEvents to their original states from snapshot.
    
    Args:
        building_id: Building ID
        snapshot_data: List of {"id": proevent_id, "state": original_state}
    """
    try:
        logger.info(f"[Building {building_id}] Reverting {len(snapshot_data)} ProEvents to their original states.")
        
        proserver_service.set_proevent_reactive_state_bulk(snapshot_data)
        sqlite_config.clear_snapshot(building_id)
        
        logger.info(f"✅ [Building {building_id}] Snapshot reverted successfully")

    except Exception as e:
        logger.error(f"❌ Failed to revert snapshot for building {building_id}: {e}", exc_info=True)