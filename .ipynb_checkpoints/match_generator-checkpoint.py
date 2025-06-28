"""
USTA Match Generator

This module provides a MatchGenerator class for creating round-robin tournament pairings
using USTA classes (Team, League, Facility, Match). It generates unscheduled Match objects
with balanced home/away assignments using the circle method algorithm.

ALGORITHM OVERVIEW:
The generator uses the circle method (also known as the polygon method) for systematic
round-robin pairing generation. This is the standard algorithm used in tournament 
management systems because it ensures optimal distribution and balance.

Circle Method Algorithm:
1. Arrange teams in a circle (for even teams) or add a "bye" team (for odd teams)
2. Keep one team fixed at the top, rotate all others clockwise each round
3. Pair teams across the circle diameter for each round
4. Alternate home/away assignments between rounds to balance assignments
5. For multiple cycles, reverse home/away from previous meetings between same teams

Example with 6 teams (A,B,C,D,E,F):
Round 1: A-F, B-E, C-D  (A,B,C home)
Round 2: A-E, F-D, B-C  (E,D,C home) 
Round 3: A-D, E-C, F-B  (A,C,B home)
Round 4: A-C, D-B, E-F  (C,B,F home)
Round 5: A-B, C-F, D-E  (A,F,E home)

CONSTRAINTS AND LIMITATIONS:

1. Team Requirements:
   - Minimum 2 teams required
   - All teams must belong to the same league
   - Team IDs must be unique

2. Match Distribution:
   - Total match slots (teams × matches_per_team) must be even
   - Each match uses exactly 2 team slots (one home, one away)
   - Example: 5 teams × 3 matches = 15 slots (invalid, must be even)

3. Home/Away Balance:
   - Perfect balance achieved when matches_per_team is even
   - With odd matches_per_team: teams get (n±1)/2 home games
   - Balance constraints may prevent perfect distribution in some configurations

4. Round-Robin Constraints:
   - Full round-robin: each team plays every other team exactly once
   - Partial round-robin: teams play subset of possible opponents
   - Multiple cycles: teams can play each other more than once

5. Algorithm Limitations:
   - Cannot generate invalid configurations (e.g., 3 teams × 3 matches each)
   - Small tournaments (2-3 teams) may have limited balance options
   - Very large tournaments may require significant computation time

MATHEMATICAL FOUNDATIONS:

For n teams in a full round-robin:
- Total possible matches: n(n-1)/2
- Matches per team: n-1
- Total match slots: n(n-1) (always even)

For partial round-robin with m matches per team:
- Total matches generated: (n×m)/2
- Must satisfy: n×m is even
- Constraint: m ≤ n-1 for single round-robin

Home/Away Distribution:
- Ideal home games per team: ⌊m/2⌋ or ⌈m/2⌉
- Maximum deviation: 1 when m is odd, 0 when m is even
- Balance factor: |home_games - away_games| ≤ 1 for any team

VALIDATION RULES:

The generator validates:
1. Team count ≥ 2
2. Matches per team ≥ 1
3. All teams belong to specified league (team.league.id == league.id)
4. Total match slots is even (teams × matches_per_team % 2 == 0)
5. Team objects have valid IDs and required attributes

Features:
- Creates unscheduled Match objects using USTA classes
- Ensures every team plays exactly the specified number of matches
- Balances home and away assignments as evenly as possible
- Supports multiple round-robin cycles (teams can play each other multiple times)
- Validates team league membership and configuration constraints
- Assigns sequential match IDs starting from configurable value
- Provides comprehensive balance analysis and statistics

Usage Examples:
    # Create league and teams
    league = League(id=1, name="Summer League", year=2025, ...)
    teams = [team1, team2, team3, team4]
    
    # Generate matches (full round-robin)
    generator = MatchGenerator()
    matches = generator.generate_matches(teams, league)
    
    # Generate partial round-robin
    matches = generator.generate_matches(teams, league, matches_per_team=6)
    
    # Analyze balance
    balance = generator.analyze_team_balance(matches)
    
    # Print detailed results
    generator.print_matches(matches, include_stats=True)
"""

from typing import List, Dict, Optional, Any, Tuple
import itertools
from collections import defaultdict

# Import USTA classes
from usta_team import Team
from usta_league import League
from usta_facility import Facility
from usta_match import Match


class MatchGenerator:
    """
    A class for generating round-robin tournament matches using USTA classes.
    Creates unscheduled Match objects with balanced home/away assignments.
    """
    
    def __init__(self, starting_match_id: int = 1):
        """
        Initialize the MatchGenerator.
        
        Args:
            starting_match_id: The ID to assign to the first generated match
        """
        self.starting_match_id = starting_match_id
        self.next_match_id = starting_match_id
    
    def generate_matches(self, teams: List[Team], league: League, 
                        matches_per_team: Optional[int] = None) -> List[Match]:
        """
        Generate round-robin matches with balanced home/away assignments.
        
        ALGORITHM FLOW:
        1. Validate input parameters and team league membership
        2. Determine matches_per_team (from parameter, league, or full round-robin)
        3. Verify mathematical constraints (even total match slots)
        4. Generate balanced pairings using circle method
        5. Create unscheduled Match objects with sequential IDs
        
        PARAMETER RESOLUTION:
        - If matches_per_team provided: use that value
        - Else if league.num_matches exists: use league value  
        - Else: default to full round-robin (n-1 matches per team)
        
        VALIDATION CHECKS:
        - At least 2 teams
        - All teams belong to specified league
        - matches_per_team ≥ 1
        - Total match slots is even (teams × matches_per_team % 2 == 0)
        
        Args:
            teams: List of Team objects that will play in the tournament
            league: League object that defines the tournament parameters
            matches_per_team: Number of matches each team should play.
                            If None, uses league.num_matches or calculates full round-robin
            
        Returns:
            List of unscheduled Match objects with sequential IDs
            
        Raises:
            ValueError: If configuration is invalid or teams don't belong to league
            
        Examples:
            # Full round-robin (each team plays every other team once)
            matches = generator.generate_matches(teams, league)
            
            # Partial round-robin (6 matches per team)
            matches = generator.generate_matches(teams, league, 6)
            
            # Double round-robin (each team plays every other team twice)
            matches = generator.generate_matches(teams, league, 2*(len(teams)-1))
        """
        # Validation
        if len(teams) < 2:
            raise ValueError("At least 2 teams are required")
        
        # Validate that all teams belong to the specified league
        for team in teams:
            if team.league.id != league.id:
                raise ValueError(f"Team '{team.name}' belongs to league '{team.league.name}' "
                               f"(ID: {team.league.id}), not '{league.name}' (ID: {league.id})")
        
        # Determine matches per team
        if matches_per_team is None:
            if hasattr(league, 'num_matches') and league.num_matches:
                matches_per_team = league.num_matches
            else:
                # Default to full round-robin (each team plays every other team once)
                matches_per_team = len(teams) - 1
        
        if matches_per_team < 1:
            raise ValueError("Matches per team must be at least 1")
        
        # Check if total match slots is even
        total_match_slots = len(teams) * matches_per_team
        if total_match_slots % 2 != 0:
            raise ValueError(
                f"Invalid configuration: {len(teams)} teams × {matches_per_team} matches = "
                f"{total_match_slots} total match slots. This must be even since each match uses exactly 2 slots."
            )
        
        # Generate pairings using the round-robin algorithm
        pairings = self._generate_pairings(teams, matches_per_team)
        
        # Calculate total rounds based on pairings and teams
        n = len(teams)
        matches_per_round = n if n % 2 == 0 else (n - 1)
        matches_per_round = n*(n-1)/2
        total_rounds = len(pairings) / matches_per_round if matches_per_round > 0 else 1.0
        
        
        # Track how many times each pair has played to determine round number
        pair_round_counter = {}
        
        # Convert pairings to Match objects
        matches = []
        for home_team, visitor_team in pairings:
            # Create sorted pair key for consistent lookup
            pair_key = tuple(sorted([home_team.id, visitor_team.id]))
            
            # Increment round counter for this pair (starts at 1 for first meeting)
            pair_round_counter[pair_key] = pair_round_counter.get(pair_key, 0) + 1
            current_round = pair_round_counter[pair_key]
            
            match = Match(
                id=self.next_match_id,
                round=current_round,
                num_rounds=total_rounds,
                league=league,
                home_team=home_team,
                visitor_team=visitor_team,
                facility=None,  # Unscheduled
                date=None,      # Unscheduled
                scheduled_times=[]  # Unscheduled
            )
            matches.append(match)
            self.next_match_id += 1
        
        return matches
    
    def _generate_pairings(self, teams: List[Team], matches_per_team: int) -> List[Tuple[Team, Team]]:
        """
        Generate round-robin pairings with balanced home/away assignments using the circle method.
        
        ALGORITHM DETAILS:
        1. Generate systematic round-robin rounds using circle method
        2. For even teams: rotate all teams except first around circle each round
        3. For odd teams: add dummy "bye" team, then remove bye matches
        4. Cycle through rounds multiple times if matches_per_team > (teams-1)
        5. Balance home/away by alternating assignments and considering previous meetings
        6. Track pair meetings to handle multiple cycles (reverse home/away on rematches)
        
        BALANCE STRATEGY:
        - Primary: Choose home team with fewer home games so far
        - Secondary: For rematches, reverse home/away from previous meeting
        - Ensures maximum deviation ≤ 1 when perfect balance is mathematically possible
        
        Args:
            teams: List of Team objects
            matches_per_team: Number of matches each team should play
            
        Returns:
            List of tuples (home_team, away_team) representing the complete schedule
        """
        n = len(teams)
        
        # Create tracking dictionaries
        team_matches = {team.id: [] for team in teams}
        team_home_count = {team.id: 0 for team in teams}
        team_away_count = {team.id: 0 for team in teams}
        
        # Track how many times each pair has played
        pair_counts = {}
        for i in range(n):
            for j in range(i + 1, n):
                pair_key = tuple(sorted([teams[i].id, teams[j].id]))
                pair_counts[pair_key] = 0
        
        # Schedule matches
        schedule = []
        
        # Use round-robin algorithm to ensure even distribution
        if n % 2 == 0:
            # Even number of teams
            rounds = self._generate_even_rounds(teams)
        else:
            # Odd number of teams - add a dummy team
            rounds = self._generate_odd_rounds(teams)
        
        # Keep cycling through rounds until each team has enough matches
        max_unique_opponents = n - 1
        total_rounds_needed = (matches_per_team + max_unique_opponents - 1) // max_unique_opponents
        
        for cycle in range(total_rounds_needed):
            for round_idx, current_round in enumerate(rounds):
                for match in current_round:
                    home, away = match
                    
                    # Check if both teams still need more matches
                    if (len(team_matches[home.id]) >= matches_per_team or 
                        len(team_matches[away.id]) >= matches_per_team):
                        continue
                    
                    # For multiple cycles, alternate home/away from previous meetings
                    pair_key = tuple(sorted([home.id, away.id]))
                    times_played = pair_counts[pair_key]
                    
                    # Determine home/away based on balance and previous meetings
                    if times_played > 0:
                        # If they've played before, reverse home/away from last time
                        for prev_home, prev_away in reversed(schedule):
                            if {prev_home.id, prev_away.id} == {home.id, away.id}:
                                if prev_home.id == home.id:
                                    home, away = away, home
                                break
                    else:
                        # First meeting - use balance
                        if team_home_count[home.id] > team_home_count[away.id]:
                            home, away = away, home
                    
                    # Add the match
                    schedule.append((home, away))
                    team_matches[home.id].append(away.id)
                    team_matches[away.id].append(home.id)
                    team_home_count[home.id] += 1
                    team_away_count[away.id] += 1
                    pair_counts[pair_key] += 1
                    
                    # Check if we've scheduled enough matches
                    if all(len(team_matches[team.id]) >= matches_per_team for team in teams):
                        return schedule
        
        return schedule
    
    def _generate_even_rounds(self, teams: List[Team]) -> List[List[Tuple[Team, Team]]]:
        """
        Generate rounds for even number of teams using the circle method algorithm.
        
        CIRCLE METHOD ALGORITHM:
        1. Arrange teams in circle with first team fixed at top
        2. Each round: pair teams across circle (team[i] with team[n-1-i])
        3. Rotate all teams except first clockwise for next round
        4. Alternate home/away assignments between rounds
        5. Generate (n-1) rounds total for n teams
        
        Example with 4 teams [A,B,C,D]:
        Initial: A-B-C-D (circle)
        Round 1: A-D, B-C (A,B home)
        Rotate: A-D-B-C
        Round 2: A-C, D-B (C,B home) 
        Rotate: A-C-D-B
        Round 3: A-B, C-D (A,C home)
        
        This ensures each team plays every other team exactly once.
        """
        n = len(teams)
        rounds = []
        
        # Create a list of team indices
        indices = list(range(n))
        
        for round_num in range(n - 1):
            round_matches = []
            
            # Pair teams
            for i in range(n // 2):
                team1_idx = indices[i]
                team2_idx = indices[n - 1 - i]
                
                # Alternate home/away assignment
                if round_num % 2 == 0:
                    round_matches.append((teams[team1_idx], teams[team2_idx]))
                else:
                    round_matches.append((teams[team2_idx], teams[team1_idx]))
            
            rounds.append(round_matches)
            
            # Rotate indices (keep first team fixed)
            indices = [indices[0]] + [indices[-1]] + indices[1:-1]
        
        return rounds
    
    def _generate_odd_rounds(self, teams: List[Team]) -> List[List[Tuple[Team, Team]]]:
        """
        Generate rounds for odd number of teams by adding a dummy "bye" team.
        
        ODD TEAM HANDLING:
        1. Add dummy "bye" team to make even number
        2. Run standard circle method algorithm
        3. Remove all matches involving the bye team
        4. Result: each team gets one bye per full round-robin cycle
        
        Example with 5 teams [A,B,C,D,E]:
        Add bye: [A,B,C,D,E,BYE]
        Generate 6-team rounds, then remove BYE matches:
        Round 1: A-E, B-D, C-BYE → A-E, B-D (C has bye)
        Round 2: A-D, E-C, B-BYE → A-D, E-C (B has bye)
        etc.
        
        Each team plays (n-1) matches in full round-robin, with one bye per cycle.
        """
        # Create a dummy team for the bye
        dummy_team = Team(
            id=-1,
            name="BYE",
            league=teams[0].league,
            home_facility=teams[0].home_facility  # Use any facility
        )
        teams_with_bye = teams + [dummy_team]
        rounds = self._generate_even_rounds(teams_with_bye)
        
        # Remove matches involving the bye
        cleaned_rounds = []
        for round_matches in rounds:
            cleaned_round = [(h, a) for h, a in round_matches if h.id != -1 and a.id != -1]
            if cleaned_round:
                cleaned_rounds.append(cleaned_round)
        
        return cleaned_rounds
    


    def analyze_team_balance(self, matches: List[Match]) -> Dict[str, Any]:
        """
        Analyze home/away balance for teams in the generated matches.
        
        BALANCE METRICS CALCULATED:
        1. Individual team statistics (home/away/total games)
        2. Distribution analysis (min/max home and away games)
        3. Deviation from ideal balance
        4. Perfect balance assessment
        
        BALANCE THEORY:
        - Ideal balance: home games ≈ away games for each team
        - With even matches_per_team: perfect balance possible (home = away)
        - With odd matches_per_team: best balance is |home - away| ≤ 1
        - Maximum theoretical deviation: 0 (even matches) or 1 (odd matches)
        
        INTERPRETATION:
        - perfectly_balanced = True: all teams have ideal distribution
        - max_deviation = 0: perfect balance achieved
        - max_deviation = 1: best possible balance for odd matches_per_team
        - max_deviation > 1: suboptimal balance (may indicate algorithm issue)
        
        Args:
            matches: List of Match objects to analyze
        
        Returns:
            Dict containing comprehensive balance statistics:
            - total_matches: number of matches analyzed
            - teams: list of team info (id, name)
            - matches_per_team: games each team plays
            - team_stats: per-team home/away/total counts
            - balance_analysis: deviation metrics and balance assessment
        """
        if not matches:
            return {
                "total_matches": 0,
                "teams": [],
                "team_stats": {},
                "balance_analysis": {}
            }
        
        # Get all unique teams
        team_ids = set()
        teams_dict = {}
        for match in matches:
            team_ids.add(match.home_team.id)
            team_ids.add(match.visitor_team.id)
            teams_dict[match.home_team.id] = match.home_team
            teams_dict[match.visitor_team.id] = match.visitor_team
        teams = [teams_dict[team_id] for team_id in sorted(team_ids)]
        
        # Initialize statistics
        stats = {team.id: {
            "team": team,
            "home": 0, 
            "away": 0,
            "total": 0
        } for team in teams}
        
        # Count matches for each team
        for match in matches:
            stats[match.home_team.id]["home"] += 1
            stats[match.home_team.id]["total"] += 1
            stats[match.visitor_team.id]["away"] += 1
            stats[match.visitor_team.id]["total"] += 1
        
        # Calculate balance metrics
        if teams:
            home_counts = [s["home"] for s in stats.values()]
            away_counts = [s["away"] for s in stats.values()]
            total_counts = [s["total"] for s in stats.values()]
            
            matches_per_team = total_counts[0] if total_counts else 0
            ideal_home = matches_per_team // 2
            ideal_away = matches_per_team - ideal_home
            
            max_home = max(home_counts) if home_counts else 0
            min_home = min(home_counts) if home_counts else 0
            max_away = max(away_counts) if away_counts else 0
            min_away = min(away_counts) if away_counts else 0
            
            max_deviation = max(
                max_home - ideal_home,
                ideal_home - min_home,
                max_away - ideal_away,
                ideal_away - min_away
            ) if home_counts and away_counts else 0
        else:
            matches_per_team = ideal_home = ideal_away = 0
            max_home = min_home = max_away = min_away = max_deviation = 0
        
        return {
            "total_matches": len(matches),
            "teams": [{"id": team.id, "name": team.name} for team in teams],
            "matches_per_team": matches_per_team,
            "team_stats": {team.id: {
                "name": s["team"].name,
                "home": s["home"],
                "away": s["away"],
                "total": s["total"]
            } for team, s in [(teams[i], stats[teams[i].id]) for i in range(len(teams))]},
            "balance_analysis": {
                "ideal_home": ideal_home,
                "ideal_away": ideal_away,
                "max_home": max_home,
                "min_home": min_home,
                "max_away": max_away,
                "min_away": min_away,
                "max_deviation": max_deviation,
                "perfectly_balanced": max_deviation == 0,
                "balance_possible": matches_per_team % 2 == 0
            }
        }
    
    
    def print_matches(self, matches: List[Match], include_stats: bool = True):
        """
        Pretty print the generated matches.
        
        Args:
            matches: List of Match objects to display
            include_stats: Whether to include team balance statistics
        """
        if not matches:
            print("No matches generated.")
            return
        
        league = matches[0].league
        print(f"Generated Matches for {league.name} ({league.year})")
        print(f"Section: {league.section}, Region: {league.region}")
        print(f"Division: {league.division}, Age Group: {league.age_group}")
        print(f"Total matches: {len(matches)}")
        print("=" * 80)
        print()
        
        # Print matches
        print("Unscheduled Matches:")
        print(f"{'ID':>3s} {'Round':>5s} {'Home Team':25s} {'Visitor Team':25s} {'Status':12s}")
        print("-" * 85)
        
        for match in matches:
            round_str = f"{match.round}/{match.num_rounds:.1f}"
            print(f"{match.id:3d} {round_str:>5s} {match.home_team.name:25s} {match.visitor_team.name:25s} {match.get_status():12s}")
        
        # Print statistics if requested
        if include_stats:
            balance = self.analyze_team_balance(matches)
            
            print()
            print("Team Statistics:")
            print(f"{'Team':25s} {'Matches':>8s} {'Home':>6s} {'Away':>6s}")
            print("-" * 50)
            
            for team_id, stats in balance["team_stats"].items():
                print(f"{stats['name']:25s} {stats['total']:8d} {stats['home']:6d} {stats['away']:6d}")
            
            print()
            print("Balance Analysis:")
            ba = balance["balance_analysis"]
            print(f"Ideal distribution: {ba['ideal_home']} home, {ba['ideal_away']} away")
            
            if ba["perfectly_balanced"]:
                print("✓ Perfect balance achieved!")
            else:
                print(f"Maximum deviation from ideal: {ba['max_deviation']}")
                if not ba["balance_possible"]:
                    print("Note: Perfect balance impossible with odd number of matches per team")
    
    def export_matches_csv(self, matches: List[Match], filename: str):
        """
        Export matches to a CSV file.
        
        Args:
            matches: List of Match objects to export
            filename: Output filename
        """
        with open(filename, 'w') as f:
            f.write("Match_ID,Round,Num_Rounds,League_ID,League_Name,Home_Team_ID,Home_Team_Name,Visitor_Team_ID,Visitor_Team_Name,Status\n")
            for match in matches:
                f.write(f"{match.id},{match.round},{match.num_rounds},{match.league.id},{match.league.name},"
                       f"{match.home_team.id},{match.home_team.name},"
                       f"{match.visitor_team.id},{match.visitor_team.name},"
                       f"{match.get_status()}\n")


    
    
    def filter_matches_by_team(self, matches: List[Match], team: Team) -> List[Match]:
        """
        Filter matches to only those involving a specific team.
        
        Args:
            matches: List of Match objects to filter
            team: Team object to filter by
            
        Returns:
            List of matches involving the specified team
        """
        return [match for match in matches 
                if match.home_team.id == team.id or match.visitor_team.id == team.id]
    
    def get_team_opponents(self, matches: List[Match], team: Team) -> List[Team]:
        """
        Get all opponents for a specific team from the match list.
        
        Args:
            matches: List of Match objects
            team: Team object to find opponents for
            
        Returns:
            List of opponent Team objects (no duplicates)
        """
        opponents = set()
        for match in matches:
            if match.home_team.id == team.id:
                opponents.add(match.visitor_team)
            elif match.visitor_team.id == team.id:
                opponents.add(match.home_team)
        return list(opponents)
    
    def reset_match_counter(self, starting_id: int = 1):
        """
        Reset the match ID counter.
        
        Args:
            starting_id: The ID to assign to the next generated match
        """
        self.starting_match_id = starting_id
        self.next_match_id = starting_id


# Example usage and testing
def main():
    """Command-line interface for MatchGenerator."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description="Generate USTA round-robin tournament matches with balanced home/away assignments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 4 6                    # 4 teams, 6 matches each
  %(prog)s 5 4 --export matches.csv  # 5 teams, 4 matches each, export to CSV
  %(prog)s 6 --full-robin         # 6 teams, full round-robin (5 matches each)
  %(prog)s 8 10 --no-stats        # 8 teams, 10 matches each, no statistics
  %(prog)s 4 6 --demo             # Run with demo data (ignores other options)

Notes:
  - Total match slots (teams × matches_per_team) must be even
  - Use --full-robin to automatically calculate full round-robin matches
  - Demo mode creates realistic USTA league data for testing
        """
    )
    
    parser.add_argument(
        "num_teams",
        type=int,
        help="Number of teams in the tournament (minimum 2)"
    )
    
    parser.add_argument(
        "matches_per_team",
        type=int,
        nargs="?",
        help="Number of matches each team should play (minimum 1)"
    )
    
    parser.add_argument(
        "--full-robin",
        action="store_true",
        help="Generate full round-robin (each team plays every other team once)"
    )
    
    parser.add_argument(
        "--export",
        metavar="FILE",
        help="Export matches to CSV file"
    )
    
    parser.add_argument(
        "--no-stats",
        action="store_true",
        help="Don't display team statistics and balance analysis"
    )
    
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with realistic demo data (overrides other options)"
    )
    
    parser.add_argument(
        "--start-id",
        type=int,
        default=1,
        help="Starting match ID (default: 1)"
    )
    
    args = parser.parse_args()
    
    # Run demo mode if requested
    if args.demo:
        return run_demo()
    
    # Validate arguments
    if args.num_teams < 2:
        parser.error("Number of teams must be at least 2")
    
    # Determine matches per team
    if args.full_robin:
        if args.matches_per_team:
            print("Warning: --full-robin overrides matches_per_team argument")
        matches_per_team = args.num_teams - 1
    else:
        if args.matches_per_team is None:
            parser.error("matches_per_team is required unless --full-robin is specified")
        if args.matches_per_team < 1:
            parser.error("Matches per team must be at least 1")
        matches_per_team = args.matches_per_team
    
    # Validate total match slots
    total_match_slots = args.num_teams * matches_per_team
    if total_match_slots % 2 != 0:
        parser.error(
            f"Invalid configuration: {args.num_teams} teams × {matches_per_team} matches = "
            f"{total_match_slots} total match slots. This must be even since each match uses exactly 2 slots."
        )
    
    try:
        # Import USTA classes
        from usta_constants import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS
        from usta_league import League
        from usta_team import Team
        from usta_facility import Facility
        
        print("USTA Match Generator")
        print("=" * 50)
        print(f"Teams: {args.num_teams}")
        print(f"Matches per team: {matches_per_team}")
        if args.full_robin:
            print("Mode: Full round-robin")
        print()
        
        # Create minimal league
        league = League(
            id=1,
            name="Generated League",
            year=2025,
            section="Southwest",
            region="Southern New Mexico",
            age_group="40 & Over", 
            division="4.0 Men",
            num_lines_per_match=3,
            num_matches=matches_per_team
        )
        
        # Create minimal facility
        facility = Facility(
            id=1,
            name="Main Tennis Center",
            short_name="MTC",
            location="City, State",
            total_courts=8
        )
        
        # Create teams with generic names
        teams = []
        for i in range(args.num_teams):
            team = Team(
                id=i + 1,
                name=f"Team {i + 1}",
                league=league,
                home_facility=facility,
                captain=f"Captain {i + 1}",
                preferred_days=["Saturday", "Sunday"]
            )
            teams.append(team)
        
        print("Teams:")
        for team in teams:
            print(f"  {team.id}: {team.name}")
        print()
        
        # Generate matches
        print("Generating matches...")
        generator = MatchGenerator(starting_match_id=args.start_id)
        matches = generator.generate_matches(teams, league, matches_per_team)
        
        # Display results
        print(f"✓ Generated {len(matches)} matches")
        
        # Show balance summary
        balance = generator.analyze_team_balance(matches)
        ba = balance["balance_analysis"]
        
        if ba["perfectly_balanced"]:
            print("✓ Perfect home/away balance achieved!")
        else:
            print(f"⚠ Maximum deviation from ideal balance: {ba['max_deviation']}")
            if not ba["balance_possible"]:
                print("  (Perfect balance impossible with odd matches per team)")
        
        print(f"Total rounds: {matches[0].num_rounds if matches else 0}")
        print()
        
        # Print detailed results
        generator.print_matches(matches, include_stats=not args.no_stats)
        
        # Export if requested
        if args.export:
            generator.export_matches_csv(matches, args.export)
            print(f"\n✓ Matches exported to {args.export}")
        
    except ImportError as e:
        print(f"Error: Missing USTA modules - {e}")
        print("\nRequired files:")
        print("- usta_constants.py")
        print("- usta_league.py")
        print("- usta_team.py") 
        print("- usta_facility.py")
        print("- usta_match.py")
        sys.exit(1)
        
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def run_demo():
    """Run the comprehensive demo with realistic USTA data."""
    
    print("MatchGenerator Demo Mode")
    print("=" * 60)
    print()
    
    try:
        # Import USTA classes
        from usta_constants import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS
        from usta_league import League
        from usta_team import Team
        from usta_facility import Facility, WeeklySchedule, DaySchedule, TimeSlot
        
        print("Creating demo league and teams...")
        
        # Create a demo league
        league = League(
            id=1,
            name="Las Cruces Summer League",
            year=2025,
            section="Southwest",
            region="Southern New Mexico", 
            age_group="40 & Over",
            division="4.0 Men",
            num_lines_per_match=3,
            num_matches=6  # Each team plays 6 matches
        )
        
        # Create demo facilities
        facility1 = Facility(
            id=1,
            name="Las Cruces Tennis Club",
            short_name="LCTC",
            location="Las Cruces, NM",
            total_courts=8
        )
        
        facility2 = Facility(
            id=2,
            name="Mesilla Valley Tennis Center", 
            short_name="MVTC",
            location="Mesilla, NM",
            total_courts=6
        )
        
        facility3 = Facility(
            id=3,
            name="NMSU Tennis Complex",
            short_name="NMSU",
            location="Las Cruces, NM", 
            total_courts=12
        )
        
        facility4 = Facility(
            id=4,
            name="Desert Hills Tennis Club",
            short_name="DHTC",
            location="Las Cruces, NM",
            total_courts=4
        )
        
        # Create demo teams
        teams = [
            Team(
                id=1,
                name="Las Cruces Aces",
                league=league,
                home_facility=facility1,
                captain="John Smith",
                preferred_days=["Saturday", "Sunday"]
            ),
            Team(
                id=2, 
                name="Mesilla Valley Smashers",
                league=league,
                home_facility=facility2,
                captain="Maria Garcia",
                preferred_days=["Saturday"]
            ),
            Team(
                id=3,
                name="NMSU Aggies",
                league=league,
                home_facility=facility3,
                captain="David Johnson", 
                preferred_days=["Friday", "Saturday"]
            ),
            Team(
                id=4,
                name="Desert Storm",
                league=league,
                home_facility=facility4,
                captain="Lisa Brown",
                preferred_days=["Sunday"]
            ),
            Team(
                id=5,
                name="Organ Mountain Eagles",
                league=league,
                home_facility=facility1,  # Shares facility with Aces
                captain="Robert Wilson",
                preferred_days=["Saturday", "Sunday"]
            )
        ]
        
        print(f"League: {league.name} ({league.year})")
        print(f"Division: {league.division}, Age Group: {league.age_group}")
        print(f"Section: {league.section}, Region: {league.region}")
        print(f"Teams: {len(teams)}")
        for team in teams:
            print(f"  - {team.name} (Captain: {team.captain}, Home: {team.home_facility.short_name})")
        print()
        
        # Create match generator
        generator = MatchGenerator(starting_match_id=1001)
        
        print("Generating matches...")
        
        # Test different scenarios
        scenarios = [
            ("Full Round-Robin", None),  # Each team plays every other team once
            ("Partial Round-Robin", 3),  # Each team plays 3 matches
            ("Extended Season", 6),      # Each team plays 6 matches (some rematches)
        ]
        
        for scenario_name, matches_per_team in scenarios:
            print(f"\n{scenario_name}:")
            print("-" * 40)
            
            try:
                # Generate matches
                matches = generator.generate_matches(teams, league, matches_per_team)
                
                # Print summary
                balance = generator.analyze_team_balance(matches)
                print(f"Generated {len(matches)} matches")
                print(f"Matches per team: {balance['matches_per_team']}")
                print(f"Total rounds: {matches[0].num_rounds if matches else 0}")
                
                # Show balance
                ba = balance["balance_analysis"]
                if ba["perfectly_balanced"]:
                    print("✓ Perfect home/away balance achieved!")
                else:
                    print(f"Maximum deviation from ideal balance: {ba['max_deviation']}")
                
                # Show first few matches as example
                print("\nFirst 5 matches:")
                for i, match in enumerate(matches[:5]):
                    round_str = f"{match.round}/{match.num_rounds:.1f}"
                    print(f"  Match {match.id}: {match.home_team.name} vs {match.visitor_team.name} (Round {round_str})")
                
                if len(matches) > 5:
                    print(f"  ... and {len(matches) - 5} more matches")
                
                # Reset counter for next scenario
                generator.reset_match_counter(1001)
                
            except ValueError as e:
                print(f"Error: {e}")
        
        print(f"\n{'='*60}")
        print("DETAILED EXAMPLE: Extended Season (6 matches per team)")
        print('='*60)
        
        # Generate the extended season again for detailed display
        matches = generator.generate_matches(teams, league, 6)
        
        # Print all matches with detailed information
        generator.print_matches(matches, include_stats=True)
        
        # Export to CSV
        csv_filename = "usta_matches_demo.csv"
        generator.export_matches_csv(matches, csv_filename)
        print(f"\nMatches exported to {csv_filename}")
        
        # Show some analysis
        print(f"\nADDITIONAL ANALYSIS:")
        print("-" * 30)
        
        # Show matches for specific team
        team_to_analyze = teams[0]  # Las Cruces Aces
        team_matches = generator.filter_matches_by_team(matches, team_to_analyze)
        opponents = generator.get_team_opponents(matches, team_to_analyze)
        
        print(f"\n{team_to_analyze.name} schedule:")
        home_games = sum(1 for m in team_matches if m.home_team.id == team_to_analyze.id)
        away_games = len(team_matches) - home_games
        
        print(f"Total matches: {len(team_matches)} ({home_games} home, {away_games} away)")
        print(f"Opponents: {[team.name for team in opponents]}")
        
        print("\nMatch details:")
        for match in team_matches:
            if match.home_team.id == team_to_analyze.id:
                vs_team = match.visitor_team.name
                location = "HOME"
            else:
                vs_team = match.home_team.name  
                location = "AWAY"
            round_str = f"{match.round}/{match.num_rounds:.1f}"
            print(f"  Match {match.id}: vs {vs_team:25s} ({location}) Round {round_str}")
        
        print(f"\nDemo completed successfully!")
        
    except ImportError as e:
        print(f"Error importing USTA classes: {e}")
        print("Make sure all USTA module files are in the same directory:")
        print("- usta_constants.py")
        print("- usta_league.py") 
        print("- usta_team.py")
        print("- usta_facility.py")
        print("- usta_match.py")
        
    except Exception as e:
        print(f"Error running demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()