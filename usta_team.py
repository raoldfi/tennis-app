from __future__ import annotations  # This makes all type hints strings automatically

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, TYPE_CHECKING
from datetime import date, datetime, timedelta
import itertools
import re
from collections import defaultdict

# Use TYPE_CHECKING for all USTA classes to avoid circular imports
if TYPE_CHECKING:
    from usta_league import League
    from usta_facility import Facility

@dataclass
class Team:
    """Represents a tennis team"""
    id: int
    name: str
    league: League  # Now this is automatically a string due to __future__ import
    preferred_facilities: List[Facility]  
    captain: Optional[str] = None
    preferred_days: List[str] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Validate team data"""
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"Team ID must be a positive integer, got: {self.id}")
        
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Team name must be a non-empty string")
        
        # Runtime validation using hasattr instead of isinstance for circular imports
        if not hasattr(self.league, 'id'):
            raise ValueError("League must be a League object")
        
        # Validate preferred_facilities list
        if not isinstance(self.preferred_facilities, list):
            raise ValueError("preferred_facilities must be a list")
        
        if len(self.preferred_facilities) == 0:
            raise ValueError("Team must have at least one preferred facility")
        
        for i, facility in enumerate(self.preferred_facilities):
            if not hasattr(facility, 'id'):
                raise ValueError(f"Facility at index {i} must be a Facility object")
        
        # Check for duplicate facilities
        facility_ids = [f.id for f in self.preferred_facilities]
        if len(facility_ids) != len(set(facility_ids)):
            raise ValueError("Duplicate facilities found in preferred_facilities list")
        
        if self.captain is not None and (not isinstance(self.captain, str) or not self.captain.strip()):
            raise ValueError("Captain must be a non-empty string or None")
        
        # Validate preferred_days
        if not isinstance(self.preferred_days, list):
            raise ValueError("preferred_days must be a list")
        
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for day in self.preferred_days:
            if not isinstance(day, str) or day not in valid_days:
                raise ValueError(f"Invalid preferred day: {day}. Must be one of: {valid_days}")

    # All getter methods - type hints are automatically strings due to __future__ import
    def get_id(self) -> int:
        """Get the team ID"""
        return self.id
    
    def get_name(self) -> str:
        """Get the team name"""
        return self.name
    
    def get_league(self) -> League:
        """Get the league this team belongs to"""
        return self.league
    
    def get_preferred_facilities(self) -> List[Facility]:
        """Get the list of preferred facilities"""
        return self.preferred_facilities.copy()
    
    def get_primary_facility(self) -> Facility:
        """Get the primary (first) preferred facility"""
        return self.preferred_facilities[0]
    
    def get_captain(self) -> Optional[str]:
        """Get the team captain name"""
        return self.captain
    
    def get_preferred_days(self) -> List[str]:
        """Get the list of preferred playing days"""
        return self.preferred_days.copy()
    
    def get_league_id(self) -> int:
        """Get the ID of the league this team belongs to"""
        return self.league.id
    
    def get_primary_facility_id(self) -> int:
        """Get the ID of the primary facility"""
        return self.preferred_facilities[0].id
    
    def get_primary_facility_name(self) -> str:
        """Get the name of the primary facility"""
        return self.preferred_facilities[0].name

    def add_preferred_facility(self, facility: 'Facility', priority: Optional[int] = None) -> None:
        """Add a facility to the preferred facilities list"""
        if not hasattr(facility, 'id'):
            raise ValueError("Facility must be a Facility object")
        
        # Check if facility already exists
        if any(f.id == facility.id for f in self.preferred_facilities):
            raise ValueError(f"Facility {facility.id} is already in preferred facilities")
        
        if priority is None or priority >= len(self.preferred_facilities):
            # Add to the end
            self.preferred_facilities.append(facility)
        else:
            # Insert at specific position
            self.preferred_facilities.insert(priority, facility)
    
    def remove_preferred_facility(self, facility: 'Facility') -> bool:
        """Remove a facility from preferred facilities list. Returns True if removed."""
        if len(self.preferred_facilities) <= 1:
            raise ValueError("Team must have at least one preferred facility")
        
        for i, f in enumerate(self.preferred_facilities):
            if f.id == facility.id:
                self.preferred_facilities.pop(i)
                return True
        return False
    
    def reorder_preferred_facilities(self, facility_ids: List[int]) -> None:
        """Reorder preferred facilities by facility IDs"""
        if len(facility_ids) != len(self.preferred_facilities):
            raise ValueError("facility_ids must contain all current facility IDs")
        
        # Check that all current facility IDs are in the new list
        current_ids = {f.id for f in self.preferred_facilities}
        new_ids = set(facility_ids)
        if current_ids != new_ids:
            raise ValueError("facility_ids must contain exactly the same facilities")
        
        # Create new ordered list
        facility_map = {f.id: f for f in self.preferred_facilities}
        self.preferred_facilities = [facility_map[fid] for fid in facility_ids]

    def to_dict(self) -> Dict[str, Any]:
        """Convert team to dictionary for serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'league_id': self.league.id,
            'preferred_facility_ids': [f.id for f in self.preferred_facilities],
            'captain': self.captain,
            'preferred_days': self.preferred_days
        }    