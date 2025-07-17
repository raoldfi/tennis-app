from __future__ import annotations  # This makes all type hints strings automatically

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, TYPE_CHECKING
from datetime import date, datetime, timedelta
import itertools
import re
from collections import defaultdict

# Import only constants directly - no circular imports
from usta_constants import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS

# Use TYPE_CHECKING for all other USTA classes
if TYPE_CHECKING:
    from usta_team import Team
    from usta_facility import Facility
    from usta_match import Match




@dataclass
class League:
    """Represents a tennis league"""
    id: int
    name: str
    year: int
    section: str
    region: str
    age_group: str
    division: str
    num_lines_per_match: int = 3  # Default to 3 lines per match (common for team tennis)
    num_matches: int = 10  # Default number of matches per team in the league
    allow_split_lines: bool = False  # Whether lines can be split across different time slots
    preferred_days: List[str] = field(default_factory=list)  # Preferred days for scheduling (e.g., ["Saturday", "Sunday"])
    backup_days: List[str] = field(default_factory=list)  # Backup days for scheduling
    start_date: Optional[str] = None  # League start date in YYYY-MM-DD format
    end_date: Optional[str] = None  # League end date in YYYY-MM-DD format

    # Penalty constants for quality scoring (make this configurable?)
    TEAM_PENALTY: int = 80  # Penalty for scheduling on a day not preferred by any team
    LEAGUE_PENALTY: int = 40  # Penalty for scheduling on a day not preferred by the league
    ROUND_PENALTY: int = 20  # Penalty for scheduling outside the preferred round
    FACILITY_PENALTY: int = 1  # Penalty for facility preference based on index


    def __post_init__(self) -> None:
        """Validate league data against USTA constants"""
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"League ID must be a positive integer, got: {self.id}")
        
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("League name must be a non-empty string")
        
        if not isinstance(self.year, int) or self.year < 1900 or self.year > 2100:
            raise ValueError(f"Year must be between 1900 and 2100, got: {self.year}")
        
        if self.section not in USTA_SECTIONS:
            raise ValueError(f"Invalid section: {self.section}. Must be one of: {USTA_SECTIONS}")
        
        if self.region not in USTA_REGIONS:
            raise ValueError(f"Invalid region: {self.region}. Must be one of: {USTA_REGIONS}")
        
        if self.age_group not in USTA_AGE_GROUPS:
            raise ValueError(f"Invalid age group: {self.age_group}. Must be one of: {USTA_AGE_GROUPS}")
        
        if self.division not in USTA_DIVISIONS:
            raise ValueError(f"Invalid division: {self.division}. Must be one of: {USTA_DIVISIONS}")
        
        if not isinstance(self.num_lines_per_match, int) or self.num_lines_per_match <= 0:
            raise ValueError(f"Number of lines per match must be a positive integer, got: {self.num_lines_per_match}")
        
        # Validate reasonable range for lines per match (1-10 is typical)
        if self.num_lines_per_match > 10:
            raise ValueError(f"Number of lines per match seems unusually high: {self.num_lines_per_match}. Expected 1-10.")

    
    def generate_deterministic_start_id(self) -> int:
        """Generate a deterministic starting match ID based on league properties"""
        # Use league ID, year, and hash of name to create deterministic base
        import hashlib
        league_string = f"{self.id}-{self.year}-{self.name}-{self.section}-{self.division}"
        hash_value = int(hashlib.md5(league_string.encode()).hexdigest()[:8], 16)
        # Scale to a reasonable range (100000 to 999999) and ensure it's positive
        base_id = 100000 + (hash_value % 900000)
        return base_id
    
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert league to dictionary for serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'year': self.year,
            'section': self.section,
            'region': self.region,
            'age_group': self.age_group,
            'division': self.division,
            'num_lines_per_match': self.num_lines_per_match,
            'num_matches': self.num_matches,
            'allow_split_lines': self.allow_split_lines,
            'preferred_days': self.preferred_days,
            'backup_days': self.backup_days,
            'start_date': self.start_date,
            'end_date': self.end_date
        }



    
