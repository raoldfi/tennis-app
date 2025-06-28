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
from tennis_db_interface import TennisDBInterface


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

    # every team should play every other team once in a round
    matches_per_round = len(permutations) // 2

    # The number of rounds does not need to be an integer (we can have additional random matches)
    num_rounds = num_pairs / matches_per_round
    
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
            # Select the first available pair
            # This ensures we always select the least used pair first
            # and maintain balance between home/away games
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
    
    round = 1

    for i, (home_team, visitor_team) in enumerate(selected_pairs):
        match_id = base_match_id + i + 1  # Sequential: base+1, base+2, base+3, etc.
        
        # increment round number if we reach the end of a round
        if i > 0 and i % matches_per_round == 0:
            round += 1

        # Ensure teams are valid Team objects
        if not isinstance(home_team, Team) or not isinstance(visitor_team, Team):
            raise ValueError("Both home_team and visitor_team must be Team objects")
        # For matches, we still need facility_id for scheduling, but we can derive it
        # from the home team's facility name. For now, we'll leave facility_id as None
        # since this is for unscheduled matches, and it will be resolved during scheduling.
        
        # Create Match with object references instead of IDs
        match = Match(
            id=match_id,
            round=round,                       # Round number for this match
            num_rounds=num_rounds,             # The number of rounds for this league
            league=league,                     # League object 
            home_team=home_team,               # Team object 
            visitor_team=visitor_team,         # Team object 
            facility=None,                     # Unscheduled initially
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
            try:
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
            except Exception as date_error:
                # FIXED: Handle individual date processing errors without crashing
                print(f"\n\nGET_OPTIMAL_DATES: Error processing date {current_date_str}: {date_error}")
                current += timedelta(days=1)
                raise date_error
        
        # Sort by priority (lower number = higher priority)
        # For same priority, maintain chronological order
        candidate_dates.sort(key=lambda x: (x[1], x[0]))

        print(f"\n\n===== CANDIDATE DATES: num_dates={num_dates}, dates={candidate_dates}\n\n")
        # Return the requested number of dates
        return [date for date, _ in candidate_dates[:num_dates]]
        
    except Exception as e:
        raise RuntimeError(f"Error getting optimal scheduling dates for match {match.id}: {e}")


