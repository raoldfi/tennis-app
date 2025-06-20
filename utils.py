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
                if day_name in required_days:
                    priority = 1  # required day
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

# ========== YAML Export Functions ==========

def export_facilities_to_yaml(facilities: List['Facility'], filename: str) -> None:
    """
    Export facilities to YAML file
    
    Args:
        facilities: List of Facility objects to export
        filename: Path to output YAML file
    """
    try:
        facilities_data = []
        for facility in facilities:
            facilities_data.append(facility.to_yaml_dict())
        
        with open(filename, 'w') as f:
            yaml.dump({
                'facilities': facilities_data
            }, f, default_flow_style=False, sort_keys=False)
            
    except Exception as e:
        raise RuntimeError(f"Failed to export facilities to YAML: {e}")


def export_leagues_to_yaml(leagues: List['League'], filename: str) -> None:
    """
    Export leagues to YAML file
    
    Args:
        leagues: List of League objects to export
        filename: Path to output YAML file
    """
    try:
        leagues_data = []
        for league in leagues:
            league_dict = {
                'id': league.id,
                'name': league.name,
                'year': league.year,
                'section': league.section,
                'region': league.region,
                'age_group': league.age_group,
                'division': league.division,
                'num_lines_per_match': league.num_lines_per_match,
                'num_matches': league.num_matches,
                'allow_split_lines': league.allow_split_lines,
                'preferred_days': league.preferred_days,
                'backup_days': league.backup_days,
                'start_date': league.start_date,
                'end_date': league.end_date
            }
            leagues_data.append(league_dict)
        
        with open(filename, 'w') as f:
            yaml.dump({
                'leagues': leagues_data
            }, f, default_flow_style=False, sort_keys=False)
            
    except Exception as e:
        raise RuntimeError(f"Failed to export leagues to YAML: {e}")


def export_teams_to_yaml(teams: List['Team'], filename: str) -> None:
    """
    Export teams to YAML file with foreign key references
    
    Args:
        teams: List of Team objects to export
        filename: Path to output YAML file
    """
    try:
        teams_data = []
        for team in teams:
            team_dict = {
                'id': team.id,
                'name': team.name,
                'league_id': team.league.id,
                'home_facility_id': team.home_facility.id,
                'captain': team.captain,
                'preferred_days': team.preferred_days
            }
            teams_data.append(team_dict)
        
        with open(filename, 'w') as f:
            yaml.dump({
                'teams': teams_data
            }, f, default_flow_style=False, sort_keys=False)
            
    except Exception as e:
        raise RuntimeError(f"Failed to export teams to YAML: {e}")


def export_matches_to_yaml(matches: List['Match'], filename: str) -> None:
    """
    Export matches to YAML file with foreign key references
    
    Args:
        matches: List of Match objects to export
        filename: Path to output YAML file
    """
    try:
        matches_data = []
        for match in matches:
            match_dict = {
                'id': match.id,
                'league_id': match.league.id,
                'home_team_id': match.home_team.id,
                'visitor_team_id': match.visitor_team.id,
                'facility_id': match.facility.id if match.facility else None,
                'date': match.date,
                'scheduled_times': match.scheduled_times
            }
            matches_data.append(match_dict)
        
        with open(filename, 'w') as f:
            yaml.dump({
                'matches': matches_data
            }, f, default_flow_style=False, sort_keys=False)
            
    except Exception as e:
        raise RuntimeError(f"Failed to export matches to YAML: {e}")


def export_all_to_yaml(leagues: List['League'], facilities: List['Facility'], 
                       teams: List['Team'], matches: List['Match'], filename: str) -> None:
    """
    Export all data to a single YAML file
    
    Args:
        leagues: List of League objects
        facilities: List of Facility objects
        teams: List of Team objects
        matches: List of Match objects
        filename: Path to output YAML file
    """
    try:
        # Convert facilities
        facilities_data = []
        for facility in facilities:
            facilities_data.append(facility.to_yaml_dict())
        
        # Convert leagues
        leagues_data = []
        for league in leagues:
            league_dict = {
                'id': league.id,
                'name': league.name,
                'year': league.year,
                'section': league.section,
                'region': league.region,
                'age_group': league.age_group,
                'division': league.division,
                'num_lines_per_match': league.num_lines_per_match,
                'num_matches': league.num_matches,
                'allow_split_lines': league.allow_split_lines,
                'preferred_days': league.preferred_days,
                'backup_days': league.backup_days,
                'start_date': league.start_date,
                'end_date': league.end_date
            }
            leagues_data.append(league_dict)
        
        # Convert teams with foreign key references
        teams_data = []
        for team in teams:
            team_dict = {
                'id': team.id,
                'name': team.name,
                'league_id': team.league.id,
                'home_facility_id': team.home_facility.id,
                'captain': team.captain,
                'preferred_days': team.preferred_days
            }
            teams_data.append(team_dict)
        
        # Convert matches with foreign key references
        matches_data = []
        for match in matches:
            match_dict = {
                'id': match.id,
                'league_id': match.league.id,
                'home_team_id': match.home_team.id,
                'visitor_team_id': match.visitor_team.id,
                'facility_id': match.facility.id if match.facility else None,
                'date': match.date,
                'scheduled_times': match.scheduled_times
            }
            matches_data.append(match_dict)
        
        # Combine all data
        all_data = {
            'leagues': leagues_data,
            'facilities': facilities_data,
            'teams': teams_data,
            'matches': matches_data
        }
        
        with open(filename, 'w') as f:
            yaml.dump(all_data, f, default_flow_style=False, sort_keys=False)
            
    except Exception as e:
        raise RuntimeError(f"Failed to export all data to YAML: {e}")


# ========== YAML Import Functions ==========

def import_facilities_from_yaml(filename: str) -> List['Facility']:
    """
    Import facilities from YAML file
    
    Args:
        filename: Path to YAML file
        
    Returns:
        List of Facility objects
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"YAML file not found: {filename}")
    
    try:
        with open(filename, 'r') as f:
            data = yaml.safe_load(f)
        
        facilities = []
        facilities_data = data.get('facilities', [])
        
        for facility_dict in facilities_data:
            facility = Facility.from_yaml_dict(facility_dict)
            facilities.append(facility)
        
        return facilities
        
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to import facilities from YAML: {e}")


def import_leagues_from_yaml(filename: str) -> List['League']:
    """
    Import leagues from YAML file
    
    Args:
        filename: Path to YAML file
        
    Returns:
        List of League objects
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"YAML file not found: {filename}")
    
    try:
        with open(filename, 'r') as f:
            data = yaml.safe_load(f)
        
        leagues = []
        leagues_data = data.get('leagues', [])
        
        for league_dict in leagues_data:
            league = League(**league_dict)
            leagues.append(league)
        
        return leagues
        
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to import leagues from YAML: {e}")


def import_teams_from_yaml(filename: str, db) -> List['Team']:
    """
    Import teams from YAML file, resolving object references from database
    
    Args:
        filename: Path to YAML file
        db: Database interface instance (TennisDBInterface)
        
    Returns:
        List of Team objects with resolved object references
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"YAML file not found: {filename}")
    
    try:
        with open(filename, 'r') as f:
            data = yaml.safe_load(f)
        
        teams = []
        teams_data = data.get('teams', [])
        
        for team_dict in teams_data:
            # Resolve object references from database
            league = db.get_league(team_dict['league_id'])
            home_facility = db.get_facility(team_dict['home_facility_id'])
            
            if not league:
                raise ValueError(f"League with ID {team_dict['league_id']} not found in database")
            if not home_facility:
                raise ValueError(f"Facility with ID {team_dict['home_facility_id']} not found in database")
            
            # Create Team object with resolved references
            team = Team(
                id=team_dict['id'],
                name=team_dict['name'],
                league=league,
                home_facility=home_facility,
                captain=team_dict.get('captain'),
                preferred_days=team_dict.get('preferred_days', [])
            )
            teams.append(team)
        
        return teams
        
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to import teams from YAML: {e}")


def import_matches_from_yaml(filename: str, db) -> List['Match']:
    """
    Import matches from YAML file, resolving object references from database
    
    Args:
        filename: Path to YAML file
        db: Database interface instance (TennisDBInterface)
        
    Returns:
        List of Match objects with resolved object references
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"YAML file not found: {filename}")
    
    try:
        with open(filename, 'r') as f:
            data = yaml.safe_load(f)
        
        matches = []
        matches_data = data.get('matches', [])
        
        for match_dict in matches_data:
            # Resolve object references from database
            league = db.get_league(match_dict['league_id'])
            home_team = db.get_team(match_dict['home_team_id'])
            visitor_team = db.get_team(match_dict['visitor_team_id'])
            
            facility = None
            if match_dict.get('facility_id'):
                facility = db.get_facility(match_dict['facility_id'])
            
            if not league:
                raise ValueError(f"League with ID {match_dict['league_id']} not found in database")
            if not home_team:
                raise ValueError(f"Home team with ID {match_dict['home_team_id']} not found in database")
            if not visitor_team:
                raise ValueError(f"Visitor team with ID {match_dict['visitor_team_id']} not found in database")
            
            # Create Match object with resolved references
            match = Match(
                id=match_dict['id'],
                league=league,
                home_team=home_team,
                visitor_team=visitor_team,
                facility=facility,
                date=match_dict.get('date'),
                scheduled_times=match_dict.get('scheduled_times', [])
            )
            matches.append(match)
        
        return matches
        
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to import matches from YAML: {e}")


def import_all_from_yaml(filename: str, db) -> Dict[str, List]:
    """
    Import all data from YAML file, resolving object references from database
    
    Args:
        filename: Path to YAML file
        db: Database interface instance (TennisDBInterface)
        
    Returns:
        Dictionary with keys 'leagues', 'facilities', 'teams', 'matches' containing lists of objects
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"YAML file not found: {filename}")
    
    try:
        with open(filename, 'r') as f:
            data = yaml.safe_load(f)
        
        result = {
            'leagues': [],
            'facilities': [],
            'teams': [],
            'matches': []
        }
        
        # Import leagues first (no dependencies)
        leagues_data = data.get('leagues', [])
        for league_dict in leagues_data:
            league = League(**league_dict)
            result['leagues'].append(league)
        
        # Import facilities (no dependencies)
        facilities_data = data.get('facilities', [])
        for facility_dict in facilities_data:
            facility = Facility.from_yaml_dict(facility_dict)
            result['facilities'].append(facility)
        
        # Import teams (depends on leagues and facilities being in database)
        teams_data = data.get('teams', [])
        for team_dict in teams_data:
            league = db.get_league(team_dict['league_id'])
            home_facility = db.get_facility(team_dict['home_facility_id'])
            
            if not league:
                raise ValueError(f"League with ID {team_dict['league_id']} not found in database")
            if not home_facility:
                raise ValueError(f"Facility with ID {team_dict['home_facility_id']} not found in database")
            
            team = Team(
                id=team_dict['id'],
                name=team_dict['name'],
                league=league,
                home_facility=home_facility,
                captain=team_dict.get('captain'),
                preferred_days=team_dict.get('preferred_days', [])
            )
            result['teams'].append(team)
        
        # Import matches (depends on leagues, teams, and facilities being in database)
        matches_data = data.get('matches', [])
        for match_dict in matches_data:
            league = db.get_league(match_dict['league_id'])
            home_team = db.get_team(match_dict['home_team_id'])
            visitor_team = db.get_team(match_dict['visitor_team_id'])
            
            facility = None
            if match_dict.get('facility_id'):
                facility = db.get_facility(match_dict['facility_id'])
            
            if not all([league, home_team, visitor_team]):
                raise ValueError(f"Missing references for match {match_dict.get('id', 'Unknown')}")
            
            match = Match(
                id=match_dict['id'],
                league=league,
                home_team=home_team,
                visitor_team=visitor_team,
                facility=facility,
                date=match_dict.get('date'),
                scheduled_times=match_dict.get('scheduled_times', [])
            )
            result['matches'].append(match)
        
        return result
        
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to import all data from YAML: {e}")


# ========== Convenience Functions ==========

def export_database_to_yaml(db, filename: str) -> None:
    """
    Export entire database to YAML file
    
    Args:
        db: Database interface instance (TennisDBInterface)
        filename: Path to output YAML file
    """
    try:
        leagues = db.list_leagues()
        facilities = db.list_facilities()
        teams = db.list_teams()
        matches = db.list_matches()
        
        export_all_to_yaml(leagues, facilities, teams, matches, filename)
        
    except Exception as e:
        raise RuntimeError(f"Failed to export database to YAML: {e}")


def import_database_from_yaml(db, filename: str, clear_existing: bool = False) -> Dict[str, int]:
    """
    Import entire database from YAML file
    
    Args:
        db: Database interface instance (TennisDBInterface)
        filename: Path to YAML file
        clear_existing: Whether to clear existing data before import
        
    Returns:
        Dictionary with counts of imported objects
    """
    if clear_existing:
        # Clear in reverse dependency order
        for match in db.list_matches():
            db.delete_match(match)
        for team in db.list_teams():
            db.delete_team(team)
        for facility in db.list_facilities():
            db.delete_facility(facility)
        for league in db.list_leagues():
            db.delete_league(league)
    
    try:
        # Import in dependency order
        all_data = import_all_from_yaml(filename, db)
        
        # Add to database in dependency order
        for league in all_data['leagues']:
            db.add_league(league)
        
        for facility in all_data['facilities']:
            db.add_facility(facility)
        
        for team in all_data['teams']:
            db.add_team(team)
        
        for match in all_data['matches']:
            db.add_match(match)
        
        return {
            'leagues': len(all_data['leagues']),
            'facilities': len(all_data['facilities']),
            'teams': len(all_data['teams']),
            'matches': len(all_data['matches'])
        }
        
    except Exception as e:
        raise RuntimeError(f"Failed to import database from YAML: {e}")


# Example usage function
def demo_yaml_functions():
    """Demonstrate YAML import/export functionality"""
    print("YAML Import/Export Functions Available:")
    print("  - export_facilities_to_yaml(facilities, filename)")
    print("  - export_leagues_to_yaml(leagues, filename)")
    print("  - export_teams_to_yaml(teams, filename)")
    print("  - export_matches_to_yaml(matches, filename)")
    print("  - export_all_to_yaml(leagues, facilities, teams, matches, filename)")
    print("  - import_facilities_from_yaml(filename)")
    print("  - import_leagues_from_yaml(filename)")
    print("  - import_teams_from_yaml(filename, db)")
    print("  - import_matches_from_yaml(filename, db)")
    print("  - import_all_from_yaml(filename, db)")
    print("  - export_database_to_yaml(db, filename)")
    print("  - import_database_from_yaml(db, filename, clear_existing=False)")
    