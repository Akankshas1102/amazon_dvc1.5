"""
ProEvent Service - FIXED PRESERVATION LOGIC
============================================
- RESTORED: Manual Non-Reactive devices (State 1) are preserved "irrespective of panel state".
- FIXED: Unchecking items from Ignore List forces them to Reactive (0) immediately.
- DYNAMIC: Uses dynamic queries for building/device names.
"""

from services import proserver_service, device_service, cache_service
import sqlite_config
import pytz
from datetime import datetime
from logger import get_logger

logger = get_logger(__name__)

# --- EXISTING FUNCTIONS ---

def get_all_proevents_for_building(building_id: int, search: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    """Gets all ProEvents for a building."""
    try:
        proevents = device_service.get_devices(
            building_id=building_id, search=search, limit=limit, offset=offset
        )
        return proevents if proevents else []
    except Exception as e:
        logger.error(f"Error getting ProEvents for building {building_id}: {e}")
        return []


def set_proevent_reactive_for_building(building_id: int, reactive_state: int, ignore_ids: list[int] | None = None) -> int:
    """Legacy function kept for compatibility."""
    if ignore_ids is None:
        ignore_ids = []
    
    try:
        proevents = device_service.get_devices(building_id=building_id, limit=1000)
        if not proevents:
            return 0
            
        proevent_ids_to_update = [p["id"] for p in proevents if p["id"] not in ignore_ids]

        if not proevent_ids_to_update:
            return 0

        target_states = [{"id": pid, "state": reactive_state} for pid in proevent_ids_to_update]
        success = proserver_service.set_proevent_reactive_state_bulk(target_states)
        
        return len(proevent_ids_to_update) if success else 0
    except Exception as e:
        logger.error(f"Error in set_proevent_reactive_for_building (Building {building_id}): {e}")
        return 0


def manage_proevents_on_panel_state_change():
    """
    Monitors panel state changes.
    """
    try:
        live_states = proserver_service.get_all_live_building_arm_states()
        
        cached_states = cache_service.get_cache_value("panel_state_cache") or {}
        new_cached_states = cached_states.copy()

        for building_id, is_panel_armed in live_states.items():
            prev_state = cached_states.get(str(building_id))
            
            if prev_state != is_panel_armed:
                current_state_str = 'ARMED' if is_panel_armed else 'DISARMED'
                prev_state_str = 'ARMED' if prev_state else 'DISARMED' if prev_state is not None else 'UNKNOWN'
                logger.info(f"🔄 [Building {building_id}] Panel state changed: {prev_state_str} → {current_state_str}")
                new_cached_states[str(building_id)] = is_panel_armed

            # Apply states (No force IDs here, pure scheduler logic)
            apply_proevent_states_for_building(building_id, is_panel_armed)

        cache_service.set_cache_value("panel_state_cache", new_cached_states)

    except Exception as e:
        logger.error(f"❌ Error in manage_proevents_on_panel_state_change: {e}", exc_info=True)


def apply_proevent_states_for_building(building_id: int, is_panel_armed: bool, force_reactive_ids: list[int] = None):
    """
    Applies ProEvent states with CONSERVATIVE LOGIC (Preserves Manual Settings).
    
    Args:
        building_id: The building to update.
        is_panel_armed: Current panel state.
        force_reactive_ids: List of IDs that MUST be set to 0 (Reactive), overriding manual preservation.
                           (Used when user explicitly unchecks items in frontend).
    """
    if force_reactive_ids is None:
        force_reactive_ids = []

    try:
        # 1. Fetch current states from DB (Crucial for preservation)
        all_proevents = proserver_service.get_proevents_for_building_from_db(building_id)
        if not all_proevents:
            return

        # 2. Determine which items are currently IGNORED by configuration
        ignored_map = sqlite_config.get_ignored_proevents()
        active_ignored_ids = set()
        
        for pid, data in ignored_map.items():
            if data.get("building_frk") != building_id:
                continue
            
            # Use 'ignore_on_arm' if armed, 'ignore_on_disarm' if disarmed
            if is_panel_armed:
                 if data.get("ignore_on_arm"):
                     active_ignored_ids.add(pid)
            else:
                 if data.get("ignore_on_disarm"):
                     active_ignored_ids.add(pid)

        target_states = []

        # 3. Calculate Target States
        for p in all_proevents:
            pid = p["id"]
            current_state = p.get("state") # 0=Reactive, 1=Non-Reactive
            
            # RULE A: Force Reactive (User explicitly unchecked this)
            if pid in force_reactive_ids:
                target_states.append({"id": pid, "state": 0})
                continue

            # RULE B: Configuration Ignore (User checked this)
            if pid in active_ignored_ids:
                target_states.append({"id": pid, "state": 1})
                continue
            
            # RULE C: Manual Preservation
            # If it is currently Non-Reactive (1), and NOT handled by A or B...
            # assume it was set manually by backend user -> KEEP IT 1.
            if current_state == 1:
                target_states.append({"id": pid, "state": 1})
                continue
            
            # RULE D: Default Reactive
            # If it's 0, stays 0. If it was undefined, becomes 0.
            target_states.append({"id": pid, "state": 0})


        # 4. Diff Check (Optimization)
        final_updates = []
        for target in target_states:
            current_device = next((x for x in all_proevents if x["id"] == target["id"]), None)
            
            if current_device:
                if current_device.get("state") != target["state"]:
                    final_updates.append(target)

        if not final_updates:
            return

        logger.info(f"⚡ [Building {building_id}] Syncing {len(final_updates)} states (Preserving Manual Non-Reactive).")
        proserver_service.set_proevent_reactive_state_bulk(final_updates)

    except Exception as e:
        logger.error(f"❌ Failed to apply ProEvent states for building {building_id}: {e}", exc_info=True)


def check_and_manage_scheduled_states():
    """Checks scheduled times and sends alerts."""
    try:
        tz = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(tz).strftime("%H:%M")
        
        live_building_arm_states = proserver_service.get_all_live_building_arm_states()
        buildings_list = proserver_service.get_all_distinct_buildings_from_db()
        building_map = {b['id']: b['name'] for b in buildings_list}

        for building_id, is_panel_armed in live_building_arm_states.items():
            schedule = sqlite_config.get_building_time(building_id)
            if not schedule:
                continue

            start_time = (schedule.get("start_time") or "20:00")[:5]

            if current_time != start_time:
                continue
            
            building_name = building_map.get(building_id, f"Building_{building_id}")

            if is_panel_armed:
                logger.info(f"[Building {building_id}] Panel ARMED at start time {start_time}. No alert sent.")
            else:
                logger.warning(f"⚠️ [Building {building_id}] Panel DISARMED at start time {start_time}. Sending AXE alert.")
                proserver_service.send_axe_message(building_name, is_armed=False)

    except Exception as e:
        logger.error(f"❌ Error in check_and_manage_scheduled_states: {e}", exc_info=True)


def reevaluate_building_state(building_id: int, force_reactive_ids: list[int] = None):
    """
    Triggers re-evaluation. 
    Accepts force_reactive_ids to handle immediate uncheck updates.
    """
    try:
        live_states = proserver_service.get_all_live_building_arm_states()
        is_panel_armed = live_states.get(building_id)
        
        if is_panel_armed is None:
            return
        
        apply_proevent_states_for_building(building_id, is_panel_armed, force_reactive_ids)
        
    except Exception as e:
        logger.error(f"❌ Error in reevaluate_building_state (Building {building_id}): {e}", exc_info=True)
        raise


# --- SNAPSHOT FUNCTIONS ---

def take_snapshot_and_apply_schedule(building_id: int):
    """Standard snapshot logic."""
    try:
        all_proevents = proserver_service.get_proevents_for_building_from_db(building_id)
        if not all_proevents:
            return

        snapshot_data = [{"id": p["id"], "state": p["state"]} for p in all_proevents]
        sqlite_config.save_snapshot(building_id, snapshot_data)
        
        # Apply simulated schedule logic (Force Disarm Profile)
        # Note: We simulate Disarmed profile here, keeping Manual logic might be tricky,
        # but for Snapshot/Revert we usually want strict Schedule application.
        ignored_map = sqlite_config.get_ignored_proevents()
        ignored_ids = {
            pid for pid, data in ignored_map.items()
            if data.get("building_frk") == building_id and data.get("ignore_on_disarm")
        }
        
        target_states = []
        for proevent in snapshot_data:
            pid = proevent['id']
            if pid in ignored_ids:
                target_states.append({"id": pid, "state": 1})
            else:
                target_states.append({"id": pid, "state": 0})

        proserver_service.set_proevent_reactive_state_bulk(target_states)

    except Exception as e:
        logger.error(f"❌ Failed to take snapshot for building {building_id}: {e}", exc_info=True)


def revert_snapshot(building_id: int, snapshot_data: list[dict]):
    """Standard revert logic."""
    try:
        proserver_service.set_proevent_reactive_state_bulk(snapshot_data)
        sqlite_config.clear_snapshot(building_id)
        logger.info(f"✅ [Building {building_id}] Snapshot reverted successfully")
    except Exception as e:
        logger.error(f"❌ Failed to revert snapshot for building {building_id}: {e}", exc_info=True)