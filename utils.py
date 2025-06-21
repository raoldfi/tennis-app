#======================= Utility functions ==================

# Import itertools if not already available
import itertools
from collections import defaultdict
from typing import List, Set
from usta import Team, Match, League, Facility
from typing import List, Optional, Dict, Any, Optional
from datetime import datetime, timedelta
import yaml
import os


def generate_matches(teams: List['Team']) -> List['Match']:
    """
    Generate a list of unscheduled Match objects from the list of teams.
        
    This algorithm ensures:
    - Fair distribution of matches for each team
    - Balanced home/away games
    - Optimal pairing distribution
    - Handles odd numbers of teams by adjusting match count
    - Deterministic sequential match IDs that prevent duplicate scheduling
    
    Match IDs are generated deterministically: the same league always gets the same
    starting match ID, then matches are numbered sequentially. This ensures that
    regenerating matches for the same league produces the identical sequence of IDs.
    
    Args:
        teams: List of Team objects in this league
        
    Returns:
        List of Match objects with deterministic sequential IDs (unscheduled)
        
    Raises:
        ValueError: If teams list is invalid
    """
    
    if len(teams) < 2:
        raise ValueError("Need at least 2 teams to generate matches")

    # All teams need to be in the same league -- initialize to first league
    league = teams[0].league
    
    # Validate all teams are in this league
    for team in teams:
        if not isinstance(team, Team):
            raise ValueError("All items in teams list must be Team objects")
        if team.league.id != league.id: 
            raise ValueError(f"Team {team.name} is not in league {league.name} (ID: {league.id})")
    
    team_list = teams
    num_matches = league.num_matches
    
    # Generate all permutations of team pairs
    permutations = list(itertools.permutations(team_list, 2))
    total_usage_counts = defaultdict(int)  # Use team IDs as keys
    first_usage_counts = defaultdict(int)  # Tracks home game counts (use team IDs)
    selected_pairs = []
    pair_counts = defaultdict(int)  # Use tuple of team IDs as keys
    
    # If odd number of teams, adjust num_matches to be fair
    if len(team_list) % 2 == 1:
        n = len(team_list)
        k = num_matches // (n - 1)
        m = num_matches % (n - 1)
        if m > 0:
            num_matches = (k + 1) * (n - 1)
        else:
            num_matches = k * (n - 1)
    
    # Calculate total number of pairs needed
    num_pairs = num_matches * len(team_list) // 2
    
    # Keep backup of all permutations
    backup_permutations = permutations.copy()
    
    # Select pairs iteratively
    for _ in range(num_pairs):
        # Sort permutations by total usage (least used teams first), then by home game balance
        # Use team IDs for dictionary lookups
        permutations.sort(key=lambda pair: (
            total_usage_counts[pair[0].id] + total_usage_counts[pair[1].id], 
            first_usage_counts[pair[0].id]
        ))
        
        # If we run out of permutations, reset to backup
        if not permutations:
            permutations = backup_permutations.copy()
        
        if permutations:
            selected_pair = permutations.pop(0)
            inverse_pair = (selected_pair[1], selected_pair[0])
            
            # Choose home/away based on balance
            # If first team has more home games than second team, swap them
            if first_usage_counts[selected_pair[0].id] > first_usage_counts[selected_pair[1].id]:
                selected_pair = inverse_pair
            
            # Create hashable keys for pair counting (using team IDs)
            selected_pair_key = (selected_pair[0].id, selected_pair[1].id)
            inverse_pair_key = (selected_pair[1].id, selected_pair[0].id)
            
            # If this exact pairing has been used more than its inverse, use the inverse
            if pair_counts[selected_pair_key] > pair_counts[inverse_pair_key]:
                selected_pair = inverse_pair
                selected_pair_key = inverse_pair_key
            
            # Add the selected pair
            selected_pairs.append(selected_pair)
            
            # Update usage counts using team IDs as keys
            total_usage_counts[selected_pair[0].id] += 1  # Home team total matches
            total_usage_counts[selected_pair[1].id] += 1  # Away team total matches
            first_usage_counts[selected_pair[0].id] += 1  # Home team home matches
            pair_counts[selected_pair_key] += 1             # This specific pairing count
            
            # Remove the used pair and its inverse from available permutations
            # Compare by team IDs to ensure proper matching
            selected_ids = (selected_pair[0].id, selected_pair[1].id)
            inverse_ids = (selected_pair[1].id, selected_pair[0].id)
            permutations = [p for p in permutations 
                          if (p[0].id, p[1].id) != selected_ids and (p[0].id, p[1].id) != inverse_ids]
    
    # Generate deterministic starting match ID for this league
    base_match_id = _generate_deterministic_start_id(league)
    
    # Convert team pairs to Match objects with sequential IDs from deterministic base
    matches = []
    for i, (home_team, visitor_team) in enumerate(selected_pairs):
        match_id = base_match_id + i + 1  # Sequential: base+1, base+2, base+3, etc.
        
        # For matches, we still need facility_id for scheduling, but we can derive it
        # from the home team's facility name. For now, we'll leave facility_id as None
        # since this is for unscheduled matches, and it will be resolved during scheduling.
        
        # Create Match with object references instead of IDs
        match = Match(
            id=match_id,
            league=league,                     # League object instead of league_id
            home_team=home_team,               # Team object instead of home_team_id
            visitor_team=visitor_team,         # Team object instead of visitor_team_id
            facility=None,                     # Unscheduled
            date=None,                         # Unscheduled initially
            scheduled_times = []               # Unscheduled initially
        )
        matches.append(match)
    
    return matches


def _generate_deterministic_start_id(league : 'League') -> int:
    """Generate a deterministic starting match ID based on league properties"""
    # Use league ID, year, and hash of name to create deterministic base
    import hashlib
    league_string = f"{league.id}-{league.year}-{league.name}-{league.section}-{league.division}"
    hash_value = int(hashlib.md5(league_string.encode()).hexdigest()[:8], 16)
    # Scale to a reasonable range (100000 to 999999) and ensure it's positive
    base_id = 100000 + (hash_value % 900000)
    return base_id


def get_optimal_scheduling_dates(match: 'Match', start_date: Optional[str] = None,
                               end_date: Optional[str] = None,
                               num_dates: Optional[int] = 50) -> List[str]:
    """
    Find optimal dates for scheduling a specific match, prioritizing team preferences
    Updated to work with Match objects directly.
    
    Args:
        match: Match object to find dates for
        start_date: Start date for search (defaults to league start_date)
        end_date: End date for search (defaults to league end_date)  
        num_dates: Number of dates to return
        
    Returns:
        List of date strings in YYYY-MM-DD format, ordered by preference
        (team preferred days first, then league preferred days, then backup days)
    """

    # Check if match object exists and is not None
    if match is None:
        raise ValueError("Match object cannot be None")

    
    print(f"DEBUG: Getting optimal dates for match {match.id}")
    print(f"DEBUG: League start_date: {match.league.start_date}")
    print(f"DEBUG: League end_date: {match.league.end_date}")
    print(f"DEBUG: League preferred_days: {match.league.preferred_days}")
    print(f"DEBUG: League backup_days: {match.league.backup_days}")
    print(f"DEBUG: Home team preferred_days: {getattr(match.home_team, 'preferred_days', 'NOT_SET')}")
    print(f"DEBUG: Visitor team preferred_days: {getattr(match.visitor_team, 'preferred_days', 'NOT_SET')}")


    try:
        # Use league dates or reasonable defaults
        search_start = start_date or match.league.start_date or datetime.now().strftime('%Y-%m-%d')
        search_end = end_date or match.league.end_date
        
        if not search_end:
            # Default to 16 weeks from start
            start_dt = datetime.strptime(search_start, '%Y-%m-%d')
            end_dt = start_dt + timedelta(weeks=16)
            search_end = end_dt.strftime('%Y-%m-%d')
        
        # Generate candidate dates with priority system
        start_dt = datetime.strptime(search_start, '%Y-%m-%d')
        end_dt = datetime.strptime(search_end, '%Y-%m-%d')
        
        candidate_dates = []
        current = start_dt
        
        # Create combined team preferred days (intersection is highest priority)
        # RON's ASSUMPTION -- THESE ARE REQUIRED
        hp = set(match.home_team.preferred_days)
        vp = set(match.visitor_team.preferred_days)

        # Start with no required days
        required_days = None
        
        # if both teams have preferred days, but the intersection is null-set, error.
        if (hp and vp):
            rd = hp & vp
            if not rd:
                raise ValueError(f"Teams have preferred dates that don't overlap: "
                                 f"h={hp}, v={vp}")
                
        # One is non-empty, so we use the union
        elif (hp or vp):
            required_days = hp | vp

        # If both are empty, anyday works.  Set required_days to None
        else:
            required_days = None

        print(f"\n\n===== REQUIRED DAYS {required_days}\n\n") 
        
        # Priority levels:
        # 1 = required days (no other days matter)
        # 2 = One team prefers this day
        # 3 = League prefers this day (but no team preference)
        # 4 = League backup day (but no team preference)
        # 5 = Day is allowed but not preferred by anyone
        
        while current <= end_dt:
            day_name = current.strftime('%A')
            date_str = current.strftime('%Y-%m-%d')
            
            # Skip days that the league doesn't allow
            if day_name not in match.league.preferred_days and day_name not in match.league.backup_days:
                current += timedelta(days=1)
                continue
            
            # Determine priority based on team and league preferences
            priority = 5  # Default: allowed but not preferred

            if required_days:
                if day_name in required_days and day_name in match.league.preferred_days:
                    priority = 1  # preferred day
                elif day_name in required_days and day_name in match.league.backup_days:
                    priority = 2  # backup day
                else:
                    current += timedelta(days=1)
                    continue
                    
            elif day_name in match.league.preferred_days:
                priority = 3  # League prefers this day
            elif day_name in match.league.backup_days:
                priority = 4  # League backup day
            
            candidate_dates.append((date_str, priority))
            current += timedelta(days=1)
        
        # Sort by priority (lower number = higher priority)
        # For same priority, maintain chronological order
        candidate_dates.sort(key=lambda x: (x[1], x[0]))

        print(f"\n\n===== CANDIDATE DATES: num_dates={num_dates}, dates={candidate_dates}\n\n")
        # Return the requested number of dates
        return [date for date, _ in candidate_dates[:num_dates]]
        
    except Exception as e:
        raise RuntimeError(f"Error getting optimal scheduling dates for match {match.id}: {e}")


def get_date_intersection(dates_list1: List[str], dates_list2: List[str], 
                         preserve_order: bool = True, 
                         sort_result: bool = False) -> List[str]:
    """
    Find the intersection of two date lists - dates that exist in both lists.
    
    Args:
        dates_list1: First list of date strings in YYYY-MM-DD format
        dates_list2: Second list of date strings in YYYY-MM-DD format
        preserve_order: If True, preserve order from first list; if False, return in arbitrary order
        sort_result: If True, sort the result chronologically (overrides preserve_order)
        
    Returns:
        List of date strings that exist in both input lists
        
    Examples:
        >>> dates1 = ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"]
        >>> dates2 = ["2025-01-02", "2025-01-04", "2025-01-05", "2025-01-06"]
        >>> get_date_intersection(dates1, dates2)
        ["2025-01-02", "2025-01-04"]
        
        >>> # Sort result chronologically
        >>> get_date_intersection(dates1, dates2, sort_result=True)
        ["2025-01-02", "2025-01-04"]
        
        >>> # Preserve order from second list
        >>> get_date_intersection(dates2, dates1, preserve_order=True)
        ["2025-01-02", "2025-01-04"]
    """
    
    # Input validation
    if not isinstance(dates_list1, list):
        raise TypeError(f"dates_list1 must be a list, got: {type(dates_list1)}")
    
    if not isinstance(dates_list2, list):
        raise TypeError(f"dates_list2 must be a list, got: {type(dates_list2)}")
    
    # Handle empty lists
    if not dates_list1 or not dates_list2:
        return []
    
    # Validate date formats (sample a few dates from each list)
    def validate_date_format(date_str: str) -> bool:
        """Validate that a string is in YYYY-MM-DD format"""
        if not isinstance(date_str, str):
            return False
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    # Sample validation - check first few dates in each list
    sample_size = min(3, len(dates_list1), len(dates_list2))
    
    for date_str in dates_list1[:sample_size]:
        if not validate_date_format(date_str):
            raise ValueError(f"Invalid date format in dates_list1: '{date_str}'. Expected YYYY-MM-DD format")
    
    for date_str in dates_list2[:sample_size]:
        if not validate_date_format(date_str):
            raise ValueError(f"Invalid date format in dates_list2: '{date_str}'. Expected YYYY-MM-DD format")
    
    # Convert second list to set for O(1) lookup
    dates_set2 = set(dates_list2)
    
    # Find intersection
    if preserve_order and not sort_result:
        # Preserve order from first list
        intersection = [date for date in dates_list1 if date in dates_set2]
    else:
        # Use set intersection for efficiency
        intersection_set = set(dates_list1) & dates_set2
        intersection = list(intersection_set)
    
    # Sort result if requested
    if sort_result:
        intersection.sort()
    
    return intersection


def get_multiple_date_intersection(*date_lists: List[str], 
                                  sort_result: bool = True) -> List[str]:
    """
    Find the intersection of multiple date lists - dates that exist in ALL lists.
    
    Args:
        *date_lists: Variable number of date string lists
        sort_result: If True, sort the result chronologically
        
    Returns:
        List of date strings that exist in all input lists
        
    Examples:
        >>> dates1 = ["2025-01-01", "2025-01-02", "2025-01-03"]
        >>> dates2 = ["2025-01-02", "2025-01-03", "2025-01-04"]
        >>> dates3 = ["2025-01-03", "2025-01-04", "2025-01-05"]
        >>> get_multiple_date_intersection(dates1, dates2, dates3)
        ["2025-01-03"]
    """
    
    # Input validation
    if not date_lists:
        return []
    
    if len(date_lists) == 1:
        return sorted(date_lists[0]) if sort_result else list(date_lists[0])
    
    # Start with first list and progressively intersect with others
    result = set(date_lists[0])
    
    for date_list in date_lists[1:]:
        if not isinstance(date_list, list):
            raise TypeError(f"All arguments must be lists, got: {type(date_list)}")
        result = result & set(date_list)
        
        # Short circuit if intersection becomes empty
        if not result:
            return []
    
    # Convert back to list
    intersection = list(result)
    
    if sort_result:
        intersection.sort()
    
    return intersection


def get_date_union(dates_list1: List[str], dates_list2: List[str], 
                  remove_duplicates: bool = True,
                  sort_result: bool = True) -> List[str]:
    """
    Find the union of two date lists - all dates that exist in either list.
    
    Args:
        dates_list1: First list of date strings in YYYY-MM-DD format
        dates_list2: Second list of date strings in YYYY-MM-DD format
        remove_duplicates: If True, remove duplicate dates
        sort_result: If True, sort the result chronologically
        
    Returns:
        List of date strings that exist in either input list
        
    Examples:
        >>> dates1 = ["2025-01-01", "2025-01-02"]
        >>> dates2 = ["2025-01-02", "2025-01-03"]
        >>> get_date_union(dates1, dates2)
        ["2025-01-01", "2025-01-02", "2025-01-03"]
    """
    
    # Input validation
    if not isinstance(dates_list1, list):
        raise TypeError(f"dates_list1 must be a list, got: {type(dates_list1)}")
    
    if not isinstance(dates_list2, list):
        raise TypeError(f"dates_list2 must be a list, got: {type(dates_list2)}")
    
    # Combine lists
    if remove_duplicates:
        # Use set to remove duplicates
        union_set = set(dates_list1) | set(dates_list2)
        union = list(union_set)
    else:
        # Simple concatenation
        union = dates_list1 + dates_list2
    
    if sort_result:
        union.sort()
    
    return union


def get_date_difference(dates_list1: List[str], dates_list2: List[str],
                       sort_result: bool = True) -> List[str]:
    """
    Find dates in first list that are NOT in second list (set difference).
    
    Args:
        dates_list1: First list of date strings in YYYY-MM-DD format
        dates_list2: Second list of date strings in YYYY-MM-DD format
        sort_result: If True, sort the result chronologically
        
    Returns:
        List of date strings in dates_list1 but not in dates_list2
        
    Examples:
        >>> dates1 = ["2025-01-01", "2025-01-02", "2025-01-03"]
        >>> dates2 = ["2025-01-02", "2025-01-04"]
        >>> get_date_difference(dates1, dates2)
        ["2025-01-01", "2025-01-03"]
    """
    
    # Input validation
    if not isinstance(dates_list1, list):
        raise TypeError(f"dates_list1 must be a list, got: {type(dates_list1)}")
    
    if not isinstance(dates_list2, list):
        raise TypeError(f"dates_list2 must be a list, got: {type(dates_list2)}")
    
    # Convert second list to set for efficient lookup
    dates_set2 = set(dates_list2)
    
    # Find difference
    difference = [date for date in dates_list1 if date not in dates_set2]
    
    if sort_result:
        difference.sort()
    
    return difference

