from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
import itertools
import re
from collections import defaultdict

# Predefined USTA categories for validation
USTA_SECTIONS = [
    "Caribbean",
    "Eastern", 
    "Florida",
    "Hawaii Pacific",
    "Intermountain",
    "Mid-Atlantic",
    "Middle States", 
    "Midwest",
    "Missouri Valley",
    "New England",
    "Northern",
    "Northern California",
    "Pacific Northwest",
    "Southern",
    "Southern California",
    "Southwest",
    "Texas"
]

# For now, just regions in the Southwest section
USTA_REGIONS = [
    "Northern Arizona",
    "Northern New Mexico",
    "Southern New Mexico", 
    "Southern Arizona",
    "Phoenix",
    "Greater El Paso"
]

USTA_AGE_GROUPS = [
    "18 & Over",
    "40 & Over", 
    "55 & Over",
    "65 & Over"
]

USTA_DIVISIONS = [
    "2.5 Women",
    "3.0 Women", 
    "3.5 Women",
    "4.0 Women",
    "4.5 Women",
    "5.0 Women",
    "2.5 Men",
    "3.0 Men",
    "3.5 Men", 
    "4.0 Men",
    "4.5 Men",
    "5.0 Men",
    "6.0 Mixed",
    "7.0 Mixed",
    "8.0 Mixed",
    "9.0 Mixed",
    "10.0 Mixed"
]

def get_usta_constants() -> Dict[str, list]:
    """Get USTA constants from the usta module"""
    from usta import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS
    return {
        'sections': USTA_SECTIONS,
        'regions': USTA_REGIONS,
        'age_groups': USTA_AGE_GROUPS,
        'divisions': USTA_DIVISIONS
    }

