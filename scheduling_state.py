import traceback
import argparse
import json
import sys
import os
from typing import Dict, Any, Optional, List, Tuple
import logging
from dataclasses import dataclass, field

from usta import Match, MatchType, League, Team, Facility

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from tennis_db_factory import TennisDBFactory, DatabaseBackend, TennisDBManager
except ImportError as e:
    print(f"Error: Could not import tennis database modules: {e}", file=sys.stderr)
    sys.exit(1)


@dataclass
class SchedulingState:
    """In-memory scheduling state for conflict detection"""
    facility_bookings: Dict[Tuple[int, str, str], int] = field(default_factory=dict)  # (facility_id, date, time) -> match_id
    team_bookings: Dict[Tuple[int, str], int] = field(default_factory=dict)            # (team_id, date) -> match_id
    operations: List[Dict] = field(default_factory=list)
    
    def initialize_from_database(self, db):
        """Load existing scheduled matches into state"""
        try:
            scheduled_matches = db.list_matches(match_type=MatchType.SCHEDULED)
            
            for match in scheduled_matches:
                if match.facility and match.date and match.scheduled_times:
                    # Record facility bookings
                    for time in match.scheduled_times:
                        self.facility_bookings[(match.facility.id, match.date, time)] = match.id
                    
                    # Record team bookings
                    self.team_bookings[(match.home_team.id, match.date)] = match.id
                    self.team_bookings[(match.visitor_team.id, match.date)] = match.id
        except Exception as e:
            print(f"Warning: Could not initialize scheduling state: {e}")
    
    def is_time_available(self, facility_id: int, date: str, time: str) -> bool:
        """Check if time slot is available"""
        return (facility_id, date, time) not in self.facility_bookings
    
    def has_team_conflict(self, team_id: int, date: str) -> bool:
        """Check if team has conflict on this date"""
        return (team_id, date) in self.team_bookings
    
    def has_facility_conflict(self, facility_id: int, date: str, time: str, courts_needed: int = 1) -> bool:
        """
        Check if facility has a conflict at the specified time
        
        Args:
            facility_id: Facility ID to check
            date: Date in YYYY-MM-DD format
            time: Time in HH:MM format
            courts_needed: Number of courts needed (default 1)
            
        Returns:
            True if there's a conflict, False if available
        """
        # For simplicity, check if the exact time slot is already booked
        # More sophisticated logic could account for courts_needed vs available courts
        return (facility_id, date, time) in self.facility_bookings
    
    def book_time_slot(self, match_id: int, facility_id: int, date: str, time: str):
        """Book a time slot"""
        self.facility_bookings[(facility_id, date, time)] = match_id
    
    def book_team_date(self, match_id: int, team_id: int, date: str):
        """Book a team date"""
        self.team_bookings[(team_id, date)] = match_id
    
    def schedule_match(self, match: Match, facility_id: int, date: str, times: List[str]):
        """
        Schedule a match in the state (for dry-run tracking)
        
        Args:
            match: Match object
            facility_id: Facility ID
            date: Date string
            times: List of time strings
        """
        # Book facility time slots
        for time in times:
            self.book_time_slot(match.id, facility_id, date, time)
        
        # Book team dates
        self.book_team_date(match.id, match.home_team.id, date)
        self.book_team_date(match.id, match.visitor_team.id, date)
        
        # Record operation for rollback if needed
        self.operations.append({
            'type': 'schedule_match',
            'match_id': match.id,
            'facility_id': facility_id,
            'date': date,
            'times': times
        })
    
    def unschedule_match(self, match: Match):
        """
        Unschedule a match from the state
        
        Args:
            match: Match object to unschedule
        """
        if not match.facility or not match.date or not match.scheduled_times:
            return
        
        # Remove facility bookings
        for time in match.scheduled_times:
            booking_key = (match.facility.id, match.date, time)
            if booking_key in self.facility_bookings:
                del self.facility_bookings[booking_key]
        
        # Remove team bookings
        home_key = (match.home_team.id, match.date)
        visitor_key = (match.visitor_team.id, match.date)
        
        if home_key in self.team_bookings:
            del self.team_bookings[home_key]
        if visitor_key in self.team_bookings:
            del self.team_bookings[visitor_key]
        
        # Record operation
        self.operations.append({
            'type': 'unschedule_match',
            'match_id': match.id
        })
    
    def clear(self):
        """Clear all bookings and operations"""
        self.facility_bookings.clear()
        self.team_bookings.clear()
        self.operations.clear()
        
    
    def get_facility_usage(self, facility_id: int, date: str) -> List[str]:
        """Get all booked times for a facility on a specific date"""
        booked_times = []
        for (fid, dt, time), match_id in self.facility_bookings.items():
            if fid == facility_id and dt == date:
                booked_times.append(time)
        return sorted(booked_times)
    
    def get_team_schedule(self, team_id: int) -> List[str]:
        """Get all dates when a team is scheduled"""
        scheduled_dates = []
        for (tid, date), match_id in self.team_bookings.items():
            if tid == team_id:
                scheduled_dates.append(date)
        return sorted(list(set(scheduled_dates)))  # Remove duplicates and sort