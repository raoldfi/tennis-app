"""
USTA Tennis Module - Central imports
This module provides a single point of import for all USTA classes
to avoid circular import issues.

IMPORTANT: This file must be imported AFTER fixing all the circular imports
in the individual modules. Do not use this until the modules are fixed.
"""

# Import constants first (no dependencies)
from usta_constants import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS

# Import facility next (minimal dependencies)  
from usta_facility import Facility, WeeklySchedule, DaySchedule, TimeSlot

# Import league (depends on constants only after fixing imports)
from usta_league import League

# Import team (depends on league and facility - after fixing imports)
from usta_team import Team

# Import line if it exists (depends on team)
# from usta_line import Line

# Import match last (depends on league, team, facility, and potentially line)
from usta_match import Match, MatchType

# Export all classes for easy importing
__all__ = [
    'USTA_SECTIONS', 'USTA_REGIONS', 'USTA_AGE_GROUPS', 'USTA_DIVISIONS'
    'Facility', 'WeeklySchedule', 'DaySchedule', 'TimeSlot',
    'League',
    'Team',
    'Match',
    'MatchType'
]

