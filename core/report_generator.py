"""
RailBlock AI - Official Indian Railways Memo & Report Generator
Generates:
1. Form S&T T/351 (Disconnection Notice for Points/Signals/Circuits)
2. TRD Power Block Permit & Message
3. COA Section Controller Block Sanction Order
4. Multi-Horizon Executive Maintenance Report
"""

from typing import Dict, Any, List
from datetime import datetime
from .models import ScheduledBlock, MaintenanceTask, Department, BlockType


class ReportGenerator:
    @staticmethod
    def generate_t351_memo(block: ScheduledBlock, task: MaintenanceTask) -> str:
        """Generates official Indian Railways Form S&T T/351 Disconnection Notice."""
        station = task.station_code or (block.section_id.split('_')[1] if '_' in block.section_id else "STN")
        return f"""
================================================================================
           INDIAN RAILWAYS - FORM S&T T/351 (DISCONNECTION NOTICE)
================================================================================
Reference No: {block.st_disconnection_memo_t351}
Date / Time: {block.date_str} {block.start_time_str} IST
Division: Delhi Division (Northern Railway)
Section: {block.section_id} (KM {task.start_km:.1f} to {task.end_km:.1f})

To: Station Master / Section Controller [{station}]
From: Senior Section Engineer (Signals & Telecom)

1. Notice is hereby given that the following Signalling & Interlocking gear 
   will be DISCONNECTED for urgent maintenance:
   - Gear Details: {task.task_name} (Category: {task.task_category})
   - Track Line: {block.track_line} Line
   - Location: KM {task.start_km:.1f} - {task.end_km:.1f}

2. Block Window Requested:
   - Start Time: {block.start_time_str} IST
   - End Time:   {block.end_time_str} IST (Duration: {block.duration_mins} Minutes)

3. Safety Precautions:
   - Point clamp & padlocked under manual pilotage where applicable.
   - S&T Staff Gang: {', '.join(task.required_gangs) if task.required_gangs else 'S&T MAINT GANG'}

4. Integrated Shadow Block:
   - Joint Working with: {', '.join(d.value for d in block.departments_involved)}
   - BDMS Sanction ID: {block.block_permit_no}

(Signed)
Senior Section Engineer (Signals)
Transmission Acknowledged by: Station Master / Section Controller [{block.coa_control_grant_id}]
================================================================================
"""

    @staticmethod
    def generate_power_block_memo(block: ScheduledBlock, task: MaintenanceTask) -> str:
        """Generates official TRD Power Block Permit & Message."""
        station = task.station_code or (block.section_id.split('_')[1] if '_' in block.section_id else "STN")
        substation = task.required_power_cut_substation or "TSS_GZB_25KV"
        return f"""
================================================================================
       INDIAN RAILWAYS - ELECTRICAL TRACTION DISTRIBUTION (TRD)
               POWER BLOCK PERMIT & ISOLATION MESSAGE
================================================================================
Permit ID: {block.trd_power_permit_no}
Date: {block.date_str}
Section / Line: {block.section_id} [{block.track_line} Line] (KM {block.start_km:.1f} - {block.end_km:.1f})

To: Traction Power Controller (TPC) / Section Controller (SCR)
From: Field In-Charge, Senior Section Engineer (TRD)

1. Purpose of Power Block:
   - Maintenance Task: {task.task_name}
   - Heavy Machines: {', '.join(task.required_machines) if task.required_machines else 'Tower Wagon'}

2. 25kV OHE Isolation Boundaries:
   - Feeding Substation: {substation}
   - Elementary Section / Isolators: ISO-{station}-01 / ISO-{station}-02 to be OPENED
   - Earthing Discharge Rods: To be placed at KM {block.start_km:.1f} and KM {block.end_km:.1f}

3. Timings:
   - Power Cut Approved: {block.start_time_str} IST
   - Power Restoration: {block.end_time_str} IST (Total: {block.duration_mins} Mins)

4. Shadow Co-location:
   - Synchronized with Civil Track & S&T Disconnections under Block {block.block_id}.

(Signed)
Traction Power Controller (TPC) Approval: TPC-NR-GRANT-PASS
================================================================================
"""

    @staticmethod
    def generate_coa_block_grant(block: ScheduledBlock) -> str:
        """Generates Chief Controller Block Sanction and Train Regulation Order."""
        regulated_summary = ""
        if block.trains_regulated:
            for t in block.trains_regulated:
                regulated_summary += f"   - Train {t['train_no']} ({t['train_name']}): Action -> {t['action']} (+{t['delay_mins']} min)\n"
        else:
            regulated_summary = "   - No passenger train regulation (White-space window utilized).\n"

        return f"""
================================================================================
             CONTROL OFFICE APPLICATION (COA) / BDMS
                  OFFICIAL TRAFFIC BLOCK ADVICE
================================================================================
Sanction No: {block.coa_control_grant_id}
Permit ID: {block.block_permit_no}
Date of Block: {block.date_str}
Block Type: {block.block_type.value} {'[INTEGRATED SHADOW BLOCK]' if block.is_shadow_block else ''}

Section: {block.section_id} ({block.track_line} Line)
Geographical Limits: KM {block.start_km:.1f} to KM {block.end_km:.1f}
Sanctioned Window: {block.start_time_str} IST to {block.end_time_str} IST ({block.duration_mins} Minutes)

Departments Authorized on Track:
{', '.join('â–¶ ' + d.value for d in block.departments_involved)}

Tasks Covered in Single Possession:
{chr(10).join(' - [' + t.department.value + '] ' + t.task_name for t in block.tasks)}

Train Regulation & Traffic Diversions:
{regulated_summary}

Operating Rules:
1. Block will be operated under absolute safety protocol.
2. Track and Power clearance memos must be transmitted prior to signal normalization.

(Issued by Order of Chief Controller / Sr. DOM, Delhi Division)
================================================================================
"""
