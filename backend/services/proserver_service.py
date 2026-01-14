"""
ProServer Service - DYNAMIC VERSION
====================================
- Removed hardcoded SQL from notification functions.
- Now uses 'send_axe_message' which accepts building_name dynamically.
- Fetches states and buildings using the Admin-configured queries.
"""

import socket
from sqlalchemy import text
from sqlalchemy.orm import Session
from logger import get_logger
from config import get_db_connection, engine, PROSERVER_IP, PROSERVER_PORT
from query_config import get_query

logger = get_logger(__name__)


# --- TCP/IP NOTIFICATION FUNCTIONS ---

def send_axe_message(building_name: str, is_armed: bool):
    """
    Sends a formatted AXE alert to the ProServer.
    
    Args:
        building_name: The name of the building (resolved via dynamic query)
        is_armed: True for 'Is_Armed', False for 'Is_Disarmed'
    """
    if not building_name:
        logger.warning("❌ Cannot send AXE message: Building name is empty")
        return

    state_str = "Is_Armed" if is_armed else "Is_Disarmed"
    message = f"axe,{building_name}_{state_str}@"
    
    # logger.info(f"📤 Sending {state_str} notification for '{building_name}'...")
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3.0) # Prevent hanging
            s.connect((PROSERVER_IP, PROSERVER_PORT))
            s.sendall(message.encode())
            logger.info(f"✅ Notification sent successfully: {message}")
    except Exception as e:
        logger.error(f"❌ Failed to send notification to ProServer: {e}")


# --- DATABASE QUERY FUNCTIONS ---

def get_proevents_for_building_from_db(building_id: int) -> list[dict]:
    """
    Fetches all ProEvents for a building.
    This remains standard as ProEvents (triggers) structure usually doesn't change 
    even if the Panel Device definition changes.
    """
    query_sql = """
        SELECT
            p.pevReactive_FRK,
            p.ProEvent_PRK,
            p.pevAlias_TXT,
            b.bldBuildingName_TXT
        FROM
            ProEvent_TBL AS p
        LEFT JOIN
            Building_TBL AS b ON p.pevBuilding_FRK = b.Building_PRK
        WHERE
            p.pevBuilding_FRK = :building_id
    """
    
    sql = text(query_sql)
    results = []

    try:
        with get_db_connection() as db:
            result = db.execute(sql, {"building_id": building_id})
            rows = result.fetchall()
            
            for row in rows:
                results.append({
                    "id": row.ProEvent_PRK,
                    "state": row.pevReactive_FRK,
                    "name": row.pevAlias_TXT,
                    "building_name": row.bldBuildingName_TXT
                })
            
            db.commit()
        return results
        
    except Exception as e:
        logger.error(f"❌ Failed to query ProEvents from database: {e}")
        return []


def set_proevent_reactive_state_bulk(target_states: list[dict]) -> bool:
    """
    Updates ProEvent reactive states in bulk.
    """
    if not target_states:
        return True
    
    sql = text("""
        UPDATE ProEvent_TBL 
        SET pevReactive_FRK = :state 
        WHERE ProEvent_PRK = :proevent_id
    """)
    
    data_to_update = [
        {"state": item['state'], "proevent_id": item['id']} 
        for item in target_states
    ]
    
    try:
        with get_db_connection() as db:
            db.execute(sql, data_to_update)
            db.commit()
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to bulk update ProEvent states: {e}")
        return False


def get_all_live_building_arm_states() -> dict:
    """
    Returns current panel state using the DYNAMIC ADMIN QUERY.
    
    Dynamic Logic:
    - Executes the SQL configured in Admin Panel ('device_query').
    - Expects result columns: [BuildingID, StateText]
    - If StateText contains 'AreaArmingStates.2', it counts as DISARMED.
    - All other states count as ARMED.
    """
    try:
        query_sql = get_query('device')
        if not query_sql:
            logger.error("❌ Query 'device' not found in configuration!")
            return {}

        with Session(engine) as session:
            query = text(query_sql)
            rows = session.execute(query).fetchall()

        result = {}
        
        for row in rows:
            if len(row) < 2: 
                continue # Safety check
                
            building_id = row[0]
            state_txt = row[1]
            
            if not building_id:
                continue

            state_str = str(state_txt or "").strip()

            # Dynamic Logic: "AreaArmingStates.2" = Disarmed.
            # If you change the device type, ensure your new query returns 
            # a state string that contains this keyword for disarmed states,
            # or update this logic if the new device uses completely different keywords.
            if "AreaArmingStates.2" in state_str:
                is_armed = False
            else:
                is_armed = True

            result[int(building_id)] = is_armed

        return result

    except Exception as e:
        logger.error(f"❌ Failed to fetch building panel states: {e}")
        return {}


def get_all_distinct_buildings_from_db() -> list[dict]:
    """
    Fetches buildings using the DYNAMIC ADMIN QUERY ('building_query').
    Expects result columns: [BuildingID, BuildingName]
    """
    query_sql = get_query('building')
    
    if not query_sql:
        return []
    
    sql = text(query_sql)
    results = []

    try:
        with get_db_connection() as db:
            result = db.execute(sql)
            rows = result.fetchall()
            
            for row in rows:
                if len(row) >= 2:
                    results.append({
                        "id": row[0],
                        "name": row[1]
                    })
            
            db.commit()
        return results
        
    except Exception as e:
        logger.error(f"❌ Failed to query buildings: {e}")
        return []