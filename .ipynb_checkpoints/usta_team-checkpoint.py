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
    home_facility: Facility  # Now this is automatically a string due to __future__ import
    captain: Optional[str] = None
    preferred_days: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate team data"""
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"Team ID must be a positive integer, got: {self.id}")
        
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Team name must be a non-empty string")
        
        # Runtime validation using hasattr instead of isinstance for circular imports
        if not hasattr(self.league, 'id'):
            raise ValueError("League must be a League object")
        
        if not hasattr(self.home_facility, 'id'):
            raise ValueError("Home facility must be a Facility object")
        
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
    
    def get_home_facility(self) -> Facility:
        """Get the home facility object"""
        return self.home_facility
    
    def get_captain(self) -> Optional[str]:
        """Get the team captain name"""
        return self.captain
    
    def get_preferred_days(self) -> List[str]:
        """Get the list of preferred playing days"""
        return self.preferred_days.copy()
    
    def get_league_id(self) -> int:
        """Get the ID of the league this team belongs to"""
        return self.league.id
    
    def get_home_facility_id(self) -> int:
        """Get the ID of the home facility"""
        return self.home_facility.id
    
    def get_home_facility_name(self) -> str:
        """Get the name of the home facility"""
        return self.home_facility.name

    def to_dict(self) -> Dict[str, Any]:
        """Convert team to dictionary for serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'league_id': self.league.id,
            'home_facility_id': self.home_facility.id,
            'captain': self.captain,
            'preferred_days': self.preferred_days
        }    