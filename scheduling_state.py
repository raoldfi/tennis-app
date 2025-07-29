import traceback
import argparse
import json
import sys
import os
from typing import Dict, Any, Optional, List, Tuple
import logging
from dataclasses import dataclass, field
from datetime import date

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
    facility_bookings: Dict[Tuple[int, date, str], List[int]] = field(default_factory=dict)  # (facility_id, date, time) -> [match_id1, match_id2, ...]
    team_bookings: Dict[Tuple[int, date], int] = field(default_factory=dict)            # (team_id, date) -> match_id
    operations: List[Dict] = field(default_factory=list)
    
    def initialize_from_database(self, db):
        """Load existing scheduled matches into state"""
        try:
            scheduled_matches = db.list_matches(match_type=MatchType.SCHEDULED)
            
            for match in scheduled_matches:
                if match.facility and match.date and match.scheduled_times:
                    # Record facility bookings
                    for time in match.scheduled_times:
                        booking_key = (match.facility.id, match.date, time)
                        if booking_key not in self.facility_bookings:
                            self.facility_bookings[booking_key] = []
                        self.facility_bookings[booking_key].append(match.id)
                    
                    # Record team bookings
                    self.team_bookings[(match.home_team.id, match.date)] = match.id
                    self.team_bookings[(match.visitor_team.id, match.date)] = match.id
        except Exception as e:
            print(f"Warning: Could not initialize scheduling state: {e}")
    
    def is_time_available(self, facility_id: int, date: date, time: str, courts_needed: int = 1) -> bool:
        """Check if time slot is available for the requested number of courts"""
        booking_key = (facility_id, date, time)
        if booking_key not in self.facility_bookings:
            return True
        
        # Check if there are enough courts available
        booked_courts = len(self.facility_bookings[booking_key])
        # Note: We would need facility object to get total courts, but for now assume conflict if any booking exists
        # This method should probably be replaced by has_facility_conflict which has the facility object
        return booked_courts < courts_needed
    
    def has_team_conflict(self, team_id: int, date: date) -> bool:
        """Check if team has conflict on this date"""
        return (team_id, date) in self.team_bookings

    def has_facility_conflict(self, facility: Facility, date: date, time: str, courts_needed: int = 1) -> bool:
        """
        Check if facility has a conflict at the specified time. This function 
        returns True if there are not enough courts available for the particular time slot
        
        Args:
            facility: Facility object to check
            date: Date object
            time: Time in HH:MM format
            courts_needed: Number of courts needed (default 1)
            
        Returns:
            True if there's a conflict, False if available
        """

        # Get the number of courts available at this facility, date, and time
        reservable_courts = facility.get_available_courts_on_date_time(date, time)
        if reservable_courts < courts_needed:
            logger.debug(
                f"Facility {facility.id} on {date} at {time} has only {reservable_courts} courts available, "
                f"but {courts_needed} are needed."
            )
            return True

        # Check how many courts are already booked at this specific time
        booking_key = (facility.id, date, time)
        if booking_key in self.facility_bookings:
            booked_courts = len(self.facility_bookings[booking_key])
            available_courts = reservable_courts - booked_courts
            
            if available_courts < courts_needed:
                logger.debug(
                    f"Facility {facility.id} on {date} at {time}: {booked_courts} courts already booked, "
                    f"{available_courts} available, but {courts_needed} needed."
                )
                return True

        return False
    
    def book_time_slot(self, match_id: int, facility_id: int, date: date, time: str):
        """Book a time slot"""
        booking_key = (facility_id, date, time)
        if booking_key not in self.facility_bookings:
            self.facility_bookings[booking_key] = []
        bookings = self.facility_bookings[booking_key]
        self.facility_bookings[booking_key].append(match_id)
    
    def book_team_date(self, match_id: int, team_id: int, date: date):
        """Book a team date"""
        self.team_bookings[(team_id, date)] = match_id
    
    def schedule_match(self, match: Match, facility_id: int, date: date, times: List[str]):
        """
        Schedule a match in the state (for dry-run tracking)
        
        Args:
            match: Match object
            facility_id: Facility ID
            date: Date object
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
                # Remove this match from the list
                if match.id in self.facility_bookings[booking_key]:
                    self.facility_bookings[booking_key].remove(match.id)
                # If no more matches at this time, remove the key entirely
                if not self.facility_bookings[booking_key]:
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
    
    def clear_match_bookings(self, match_id: int):
        """Clear all bookings for a specific match"""
        # Remove facility bookings for this match
        keys_to_update = []
        for booking_key, match_ids in self.facility_bookings.items():
            if match_id in match_ids:
                keys_to_update.append(booking_key)
        
        for booking_key in keys_to_update:
            self.facility_bookings[booking_key].remove(match_id)
            # If no more matches at this time, remove the key entirely
            if not self.facility_bookings[booking_key]:
                del self.facility_bookings[booking_key]
        
        # Remove team bookings for this match
        team_keys_to_remove = []
        for team_key, booked_match_id in self.team_bookings.items():
            if booked_match_id == match_id:
                team_keys_to_remove.append(team_key)
        
        for team_key in team_keys_to_remove:
            del self.team_bookings[team_key]

    def update_match_bookings(self, match_id: int, facility_id: int, date: str, 
                              times: List[str], home_team_id: int, visitor_team_id: int):
        """
        Atomically update bookings for a match to avoid race conditions during scheduling.
        This method clears existing bookings and adds new ones in a single operation.
        """
        # Clear existing bookings first
        self.clear_match_bookings(match_id)
        
        # Book new time slots and team dates
        if times:
            for time in times:
                self.book_time_slot(match_id, facility_id, date, time)
            self.book_team_date(match_id, home_team_id, date)
            self.book_team_date(match_id, visitor_team_id, date)
    
    def clear(self):
        """Clear all bookings and operations"""
        self.facility_bookings.clear()
        self.team_bookings.clear()
        self.operations.clear()
        
    
    def get_facility_usage(self, facility_id: int, date: date) -> List[str]:
        """Get all booked times for a facility on a specific date (with duplicates for multiple matches)"""
        booked_times = []
        for (fid, dt, time), match_ids in self.facility_bookings.items():
            if fid == facility_id and dt == date:
                # Add the time once for each match booked at this time
                booked_times.extend([time] * len(match_ids))
        return sorted(booked_times)
    
    def get_team_schedule(self, team_id: int) -> List[str]:
        """Get all dates when a team is scheduled"""
        scheduled_dates = []
        for (tid, date), _ in self.team_bookings.items():
            if tid == team_id:
                scheduled_dates.append(date)
        return sorted(list(set(scheduled_dates)))  # Remove duplicates and sort
    
    def get_facility_usage_count(self, facility_id: int, date: date, time: str) -> int:
        """Get the number of matches booked at a specific facility, date, and time"""
        booking_key = (facility_id, date, time)
        if booking_key in self.facility_bookings:
            return len(self.facility_bookings[booking_key])
        return 0
    
    def get_facility_available_courts(self, facility: Facility, date: date, time: str) -> int:
        """Get the number of available courts at a facility for a specific date and time"""
        total_courts = facility.get_available_courts_on_date_time(date, time)
        booked_courts = self.get_facility_usage_count(facility.id, date, time)
        return max(0, total_courts - booked_courts)
    
    def get_all_facility_bookings(self, facility_id: int, date: date) -> Dict[str, List[int]]:
        """Get all bookings for a facility on a specific date, organized by time"""
        bookings = {}
        for (fid, dt, time), match_ids in self.facility_bookings.items():
            if fid == facility_id and dt == date:
                bookings[time] = match_ids.copy()  # Return a copy to prevent modification
        return bookings