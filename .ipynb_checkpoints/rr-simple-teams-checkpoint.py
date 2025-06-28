#!/usr/bin/env python3
"""
Round-Robin Match Generator with CLI - Updated to use USTA classes

Generate balanced round-robin matches where every team plays every other team,
while balancing the number of home games each team gets.

For N teams, each team should get approximately (N-1)/2 home games.
"""

import itertools
import argparse
import sys
from typing import List, Tuple, Dict
from collections import defaultdict, Counter
import random
import math

# Import USTA classes
from usta import League, Team, Match, Facility, MatchType
from usta_constants import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS


class MatchGenerator:
    """
    A class to generate balanced round-robin matches for tennis leagues.
    
    This class handles the creation of unscheduled matches with balanced
    home/away assignments across multiple rounds.
    """
    
    def __init__(self, league: League, teams: List[Team], seed: int = None):
        """
        Initialize the match generator.
        
        Args:
            league: League object that matches belong to
            teams: List of Team objects participating
            seed: Random seed for reproducible results
        """
        self.league = league
        self.teams = teams
        self.seed = seed
        self.matches = []
        
        if len(teams) < 2:
            raise ValueError("Need at least 2 teams to generate matches")

    def create_balanced_single_round_v0(self, teams: List[Team], seed: int = None) -> Tuple[List[Tuple[Team, Team]], Dict[int, int], Dict[int, int]]:
        """Fixed version using team IDs for dictionary keys - now returns counts too"""
        
        if seed is not None:
            random.seed(seed)
            random.shuffle(teams)
        
        pairings = list(itertools.combinations(teams, 2))
        home_counts = defaultdict(int)  # Will use team IDs as keys
        away_counts = defaultdict(int)  # Track away games too
        matches = []
        
        for team1, team2 in pairings:
            # Use team.id as dictionary key instead of team object
            if home_counts[team1.id] <= home_counts[team2.id]:
                home, away = team1, team2
            else:
                home, away = team2, team1
            
            matches.append((home, away))
            home_counts[home.id] += 1  # Use team ID as key
            away_counts[away.id] += 1  # Track away games
        
        return matches, home_counts, away_counts
        
    
    def create_balanced_single_round(self, teams: List[Team] = None, seed: int = None) -> Tuple[List[Tuple[Team, Team]], List[int], List[int]]:
        """
        Create a balanced single round-robin with improved home/away balance.
        
        This algorithm uses a graph coloring approach to ensure better balance.
        For N teams in a complete round-robin, each team should get exactly
        (N-1)/2 home games when N is odd, or as close as possible when N is even.
        
        Args:
            teams: List of Team objects (uses self.teams if None)
            seed: Random seed for shuffling teams (uses self.seed if None)
            
        Returns:
            Tuple of:
            - List of (home_team, away_team) tuples with balanced assignments
            - List of home game counts for each team (indexed by team position in teams list)
            - List of away game counts for each team (indexed by team position in teams list)
        """
        if teams is None:
            teams = self.teams
        
        if seed is None:
            seed = self.seed
            
        n = len(teams)
        
        # Create all possible pairings
        all_pairings = list(itertools.combinations(range(n), 2))
        
        if seed is not None:
            random.seed(seed)
            random.shuffle(all_pairings)
        
        # Initialize home/away counts
        home_counts = [0] * n
        away_counts = [0] * n
        matches = []
        
        # Target home games for each team
        target_home = (n - 1) / 2
        
        # Process each pairing
        for i, j in all_pairings:
            team_i = teams[i]
            team_j = teams[j]
            
            # Calculate current deviations from target
            i_home_deficit = target_home - home_counts[i]
            j_home_deficit = target_home - home_counts[j]
            
            # Assign home team to the one further from target
            if i_home_deficit > j_home_deficit:
                home_idx, away_idx = i, j
                home_team, away_team = team_i, team_j
            elif j_home_deficit > i_home_deficit:
                home_idx, away_idx = j, i
                home_team, away_team = team_j, team_i
            else:
                # Equal deficit - check away counts as tiebreaker
                if away_counts[i] > away_counts[j]:
                    home_idx, away_idx = i, j
                    home_team, away_team = team_i, team_j
                elif away_counts[j] > away_counts[i]:
                    home_idx, away_idx = j, i
                    home_team, away_team = team_j, team_i
                else:
                    # Completely equal - use deterministic choice based on team order
                    if i < j:
                        home_idx, away_idx = i, j
                        home_team, away_team = team_i, team_j
                    else:
                        home_idx, away_idx = j, i
                        home_team, away_team = team_j, team_i
            
            matches.append((home_team, away_team))
            home_counts[home_idx] += 1
            away_counts[away_idx] += 1
        
        return matches, home_counts, away_counts
    
    
    def create_perfectly_balanced_round_robin(self, teams: List[Team]) -> List[Tuple[Team, Team]]:
        """
        Alternative algorithm using circle method for perfect balance.
        
        This creates a perfectly balanced round-robin schedule using the 
        circle/polygon method, which guarantees optimal home/away distribution.
        
        Args:
            teams: List of Team objects
            
        Returns:
            List of (home_team, away_team) tuples
        """
        n = len(teams)
        
        # Handle odd number of teams by adding a "bye"
        if n % 2 == 1:
            teams_to_schedule = teams + [None]  # None represents bye
            n = len(teams_to_schedule)
        else:
            teams_to_schedule = teams[:]
        
        matches = []
        
        # Generate rounds using circle method
        for round_num in range(n - 1):
            # Create pairings for this round
            for i in range(n // 2):
                if i == 0:
                    # First pairing: fixed position vs rotating position
                    team1 = teams_to_schedule[0]
                    team2 = teams_to_schedule[n - 1 - round_num % (n - 1)]
                else:
                    # Other pairings
                    pos1 = i
                    pos2 = n - 1 - i
                    
                    # Adjust for rotation
                    if round_num > 0:
                        pos1 = 1 + (pos1 - 1 + round_num) % (n - 1)
                        pos2 = 1 + (pos2 - 1 + round_num) % (n - 1)
                    
                    team1 = teams_to_schedule[pos1]
                    team2 = teams_to_schedule[pos2]
                
                # Skip bye matchups
                if team1 is None or team2 is None:
                    continue
                
                # Alternate home/away based on round and position
                if (round_num + i) % 2 == 0:
                    matches.append((team1, team2))
                else:
                    matches.append((team2, team1))
        
        return matches
    
    
    # Example usage in your MatchGenerator class:
    def create_balanced_single_round_v2(self, teams: List[Team] = None, seed: int = None) -> List[Tuple[Team, Team]]:
        """
        Create a balanced single round-robin using an optimization approach.
        
        This version uses integer linear programming concepts (simplified) to
        find the best possible home/away assignment.
        """
        if teams is None:
            teams = self.teams
        
        n = len(teams)
        
        # Generate all matchups
        all_matchups = list(itertools.combinations(range(n), 2))
        
        # For small numbers of teams, we can try all possible home/away assignments
        # and pick the most balanced one
        if n <= 6:  # Feasible for brute force
            best_assignment = None
            best_range = float('inf')
            
            # Try different starting configurations
            for attempt in range(min(10, 2**len(all_matchups))):
                matches = []
                home_counts = [0] * n
                
                for i, (team_a_idx, team_b_idx) in enumerate(all_matchups):
                    # Use a pattern based on attempt number
                    if (attempt >> i) & 1:
                        home_idx, away_idx = team_a_idx, team_b_idx
                    else:
                        home_idx, away_idx = team_b_idx, team_a_idx
                    
                    matches.append((teams[home_idx], teams[away_idx]))
                    home_counts[home_idx] += 1
                
                # Calculate range
                current_range = max(home_counts) - min(home_counts)
                
                if current_range < best_range:
                    best_range = current_range
                    best_assignment = matches[:]
                    
                    # Perfect balance found
                    if current_range <= 1:
                        break
            
            return best_assignment if best_assignment else matches
        
        # For larger numbers, use the improved greedy algorithm
        return self.create_balanced_single_round(teams, seed)

    def create_inverse_pairings(self, pairings: List[Tuple[Team, Team]]) -> List[Tuple[Team, Team]]:
        """
        Return the round with home and visitor teams swapped.
        
        Args:
            pairings: List of (home_team, away_team) tuples
            
        Returns:
            List with home and away teams swapped
        """
        matches = []
        for team1, team2 in pairings:
            matches.append((team2, team1))
        return matches

    def sort_matches_dynamically(self, matches: List[Tuple[Team, Team]], home_counts: Dict[int, int] = None) -> List[Tuple[Team, Team]]:
        """
        Sorts matches so that teams with fewer current matches are scheduled earlier.
        This updates team match counts as matches are scheduled.
        
        Args:
            matches: List of (home_team, away_team) tuples
            home_counts: Current home game counts (optional)
            
        Returns:
            Sorted list of matches
        """
        match_counts = Counter()
        if home_counts is None:
            home_counts = Counter()
        else:
            # Convert to Counter if it's a defaultdict
            home_counts = Counter(home_counts)
        
        scheduled = []

        # Start with all matches
        remaining = matches[:]

        while remaining:
            # Sort remaining matches by current match count (least active teams first)
            #remaining.sort(key=lambda m: match_counts[m[0].id] + match_counts[m[1].id] + home_counts[m[0].id])
            #remaining.sort(key=lambda m: match_counts[m[0].id] + match_counts[m[1].id])
            remaining.sort(key=lambda m: (match_counts[m[0].id] + match_counts[m[1].id], 
            home_counts[m[0].id]
        ))

            match = remaining.pop(0)  # Pick the "least played" match
            scheduled.append(match)
            match_counts[match[0].id] += 1
            match_counts[match[1].id] += 1
            home_counts[match[0].id] += 1

        return scheduled

    def generate_team_pairings(self, matches_per_team: int) -> List[List[Tuple[Team, Team]]]:
        """
        Generate balanced multiple round pairings using Team objects.
        
        We do this by creating a balanced round for odd round numbers, we generate a balanced round. 
        The even numbered round is the inverse pairings of the odd. This should guarantee that after 
        two rounds we have all permutations of match pairings.

        To guarantee each of n teams plays k matches, you must calculate how many unique matches are needed. 
        Each match involves 2 teams, so the total number of matches must satisfy:
        
            Total Matches = n*k/2
         
        This formula works regardless of whether n is even or odd, as long as n × k is even 
        (because you can't have half a match).
        
        Args:
            matches_per_team: Number of matches each team should play
            
        Returns:
            List of rounds, where each round is a list of (home_team, away_team) tuples
        """
        n = len(self.teams)

        # As long as one of the number of teams or the matches_per_team is even, we're good
        if (n % 2 == 1) and (matches_per_team % 2 == 1):
            matches_per_team += 1
            print(f"Adjusted matches_per_team to {matches_per_team} to ensure even total")

        # Calculate total number of matches to guarantee each team plays the same
        total_matches = n * matches_per_team // 2

        matches_per_round = n * (n - 1) // 2
        num_rounds = math.ceil(total_matches / matches_per_round)

        matches_remaining = total_matches
        rounds = []
        inverse_pairings = []

        print(f"Generating {total_matches} total matches across {num_rounds} rounds")

        for round_num in range(num_rounds):
            if matches_remaining < 0:
                raise ValueError(f"matches_remaining={matches_remaining}")
            
            matches = []
            home_counts = Counter()
            away_counts = Counter()

            
            # If this is an even round, generate pairings
            if round_num % 2 == 0:
                matches, home_counts, away_counts = self.create_balanced_single_round_v0(self.teams)
                
                inverse_pairings = self.sort_matches_dynamically(
                    self.create_inverse_pairings(matches), home_counts)
            else:
                matches = inverse_pairings

            # Since the matches are sorted to even the number of matches
            # this should result in a fair selection
            if matches_remaining < len(matches):
                # Sort the remaining matches to balance number of matches per team
                matches = self.sort_matches_dynamically(matches, away_counts)
                matches = matches[:matches_remaining]
                
            rounds.append(matches)
            matches_remaining -= len(matches)
            print(f"Round {round_num + 1}: {len(matches)} matches, {matches_remaining} remaining")

        return rounds
        

    def create_matches(self, matches_per_team: int, start_match_id: int = 1) -> List[Match]:
        """
        Generate unscheduled Match objects from team pairings.
        
        Args:
            matches_per_team: Number of matches each team should play
            start_match_id: Starting ID for match numbering
            
        Returns:
            List of unscheduled Match objects
        """
        team_pairings = self.generate_team_pairings(matches_per_team)
        
        matches = []
        match_id = start_match_id
        round_num = 1
        
        for round_pairings in team_pairings:
            for home_team, away_team in round_pairings:
                match = Match(
                    id=match_id,
                    round=round_num,
                    num_rounds=len(team_pairings),
                    league=self.league,
                    home_team=home_team,
                    visitor_team=away_team
                )
                matches.append(match)
                match_id += 1
            round_num += 1
        
        self.matches = matches
        return matches

    def analyze_balance(self) -> Dict:
        """
        Analyze the home/away balance of generated matches.
        
        Returns:
            Dictionary with balance statistics
        """
        if not self.matches:
            return {}
        
        # Count home and away games
        home_counts = defaultdict(int)
        away_counts = defaultdict(int)
        total_counts = defaultdict(int)
        round_counts = defaultdict(int)

        for match in self.matches:
            home_team = match.get_home_team()
            away_team = match.get_visitor_team()
            
            home_counts[home_team.id] += 1
            away_counts[away_team.id] += 1
            total_counts[home_team.id] += 1
            total_counts[away_team.id] += 1
            round_counts[match.round] += 1
        
        # Get all teams
        all_team_ids = set(home_counts.keys()) | set(away_counts.keys())
        
        # Calculate statistics
        home_games = [home_counts[team_id] for team_id in all_team_ids]
        away_games = [away_counts[team_id] for team_id in all_team_ids]
        total_games = [total_counts[team_id] for team_id in all_team_ids]
        
        def calculate_stats(values):
            if not values:
                return {}
            return {
                'min': min(values),
                'max': max(values),
                'mean': sum(values) / len(values),
                'range': max(values) - min(values)
            }
        
        return {
            'total_matches': len(self.matches),
            'total_teams': len(all_team_ids),
            'total_rounds': len(round_counts),
            'matches_per_round': dict(round_counts),
            'home_games_per_team': dict(home_counts),
            'away_games_per_team': dict(away_counts),
            'total_games_per_team': dict(total_counts),
            'home_game_stats': calculate_stats(home_games),
            'away_game_stats': calculate_stats(away_games),
            'total_game_stats': calculate_stats(total_games),
        }

    def print_analysis(self, title: str = "Match Generation Analysis"):
        """
        Print detailed analysis of generated matches.
        
        Args:
            title: Title for the analysis output
        """
        analysis = self.analyze_balance()
        
        if not analysis:
            print("No matches generated yet. Run create_matches() first.")
            return
        
        print(f"\n{title}")
        print("=" * len(title))
        print(f"League: {self.league.name}")
        print(f"Teams: {[team.name for team in self.teams]}")
        print(f"Total matches: {analysis['total_matches']}")
        print(f"Total rounds: {analysis['total_rounds']}")
        print(f"Expected matches for complete round: {len(self.teams) * (len(self.teams) - 1) // 2}")
        
        print(f"\nMatches by Round:")
        for round_num, count in analysis['matches_per_round'].items():
            print(f"  Round {round_num}: {count} matches")
        
        print(f"\nSample Matches:")
        for i, match in enumerate(self.matches[:], 1):
            print(f"  {i:2d}. Match {match.id:2d}: {match.home_team_name:15s} vs {match.visitor_team_name:15s} "
                  f"(Round {match.round}, Status: {match.get_status()})")
        
        # if len(self.matches) > 8:
        #     print(f"  ... and {len(self.matches) - 8} more matches")
        
        print(f"\nHome/Away Balance:")
        print(f"{'Team':<15} {'Home':<6} {'Away':<6} {'Total':<6}")
        print(f"{'-'*15} {'-'*6} {'-'*6} {'-'*6}")
        
        for team in sorted(self.teams, key=lambda t: t.name):
            home = analysis['home_games_per_team'].get(team.id, 0)
            away = analysis['away_games_per_team'].get(team.id, 0)
            total = analysis['total_games_per_team'].get(team.id, 0)
            print(f"{team.name:<15} {home:<6} {away:<6} {total:<6}")
        
        print(f"\nBalance Statistics:")
        home_stats = analysis['home_game_stats']
        print(f"  Home games - Min: {home_stats['min']}, Max: {home_stats['max']}, "
              f"Range: {home_stats['range']}, Mean: {home_stats['mean']:.1f}")
        
        away_stats = analysis['away_game_stats']
        print(f"  Away games - Min: {away_stats['min']}, Max: {away_stats['max']}, "
              f"Range: {away_stats['range']}, Mean: {away_stats['mean']:.1f}")
        
        total_stats = analysis['total_game_stats']
        print(f"  Total games - Min: {total_stats['min']}, Max: {total_stats['max']}, "
              f"Range: {total_stats['range']}, Mean: {total_stats['mean']:.1f}")

    def verify_matches(self) -> bool:
        """
        Verify that all generated matches are properly unscheduled.
        
        Returns:
            True if all matches are unscheduled, False otherwise
        """
        if not self.matches:
            print("No matches to verify")
            return False
        
        all_unscheduled = all(match.is_unscheduled() for match in self.matches)
        print(f"Verification: All {len(self.matches)} matches are unscheduled: {all_unscheduled}")
        
        if not all_unscheduled:
            scheduled_matches = [m for m in self.matches if not m.is_unscheduled()]
            print(f"Warning: {len(scheduled_matches)} matches are scheduled!")
        
        return all_unscheduled


def create_sample_facilities() -> List[Facility]:
    """Create sample facilities for testing (minimal setup since we're not scheduling)."""
    from usta_facility import WeeklySchedule
    
    facilities = []
    
    # Create minimal schedule (empty since we're only creating unscheduled matches)
    schedule = WeeklySchedule()
    
    # Create facilities with basic info only
    facilities.append(Facility(
        id=1,
        name="Valley Ranch Tennis Club",
        location="Las Cruces, NM",
        schedule=schedule,
        total_courts=6
    ))
    
    facilities.append(Facility(
        id=2,
        name="Tennis Center of Albuquerque",
        location="Albuquerque, NM", 
        schedule=schedule,
        total_courts=8
    ))
    
    return facilities


def create_sample_league_and_teams(num_teams: int = 5) -> Tuple[League, List[Team]]:
    """
    Create a sample league and teams for testing.
    
    Args:
        num_teams: Number of teams to create
        
    Returns:
        Tuple of (League, List[Team])
    """
    # Create sample facilities
    facilities = create_sample_facilities()
    
    # Create league
    league = League(
        id=1,
        name="Northern New Mexico 4.0 Men",
        year=2025,
        section="Southwest",
        region="Northern New Mexico",
        age_group="18 & Over",
        division="4.0 Men",
        num_lines_per_match=3,
        preferred_days=["Saturday", "Sunday"]
    )
    
    # Create teams with simple names
    teams = []
    team_names = [chr(65 + i) for i in range(26)]  # A, B, C, D, ..., Z
    
    for i in range(min(num_teams, len(team_names))):
        facility = facilities[i % len(facilities)]
        team = Team(
            id=i + 1,
            name=team_names[i],
            league=league,
            home_facility=facility,
            captain=f"Captain {chr(65 + i)}",
            preferred_days=["Saturday", "Sunday"]
        )
        teams.append(team)
    
    return league, teams


def run_demo(num_teams: int, matches_per_team: int, seed: int = None):
    """
    Run the match generation demo with specified parameters.
    
    Args:
        num_teams: Number of teams to create
        matches_per_team: Number of matches each team should play  
        seed: Random seed for reproducible results
    """
    print(f"\nRUNNING DEMO: {num_teams} teams, {matches_per_team} matches per team")
    print("=" * 60)
    
    try:
        # Create sample league and teams
        league, teams = create_sample_league_and_teams(num_teams)
        
        print(f"Created league: {league.name}")
        print(f"Teams: {[team.name for team in teams]}")
        
        # Create match generator
        generator = MatchGenerator(league, teams, seed)
        
        # Generate matches
        matches = generator.create_matches(matches_per_team)
        
        # Print analysis
        generator.print_analysis(f"Analysis for {num_teams} teams, {matches_per_team} matches per team")
        
        # Verify matches are unscheduled
        print(f"\nVerification:")
        generator.verify_matches()
        
        # Show sample match details
        if matches:
            sample_match = matches[0]
            print(f"\nSample match details:")
            print(f"  ID: {sample_match.get_id()}")
            print(f"  League: {sample_match.get_league().name}")
            print(f"  Home Team: {sample_match.get_home_team().name}")
            print(f"  Visitor Team: {sample_match.get_visitor_team().name}")
            print(f"  Facility: {sample_match.facility}")
            print(f"  Date: {sample_match.date}")
            print(f"  Scheduled Times: {sample_match.get_scheduled_times()}")
            print(f"  Expected Lines: {sample_match.get_expected_lines()}")
            print(f"  Is Scheduled: {sample_match.is_scheduled()}")
            print(f"  Is Unscheduled: {sample_match.is_unscheduled()}")
        
        return generator
        
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Generate balanced round-robin matches for tennis leagues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --teams 4 --matches 6
  %(prog)s --teams 5 --matches 8 --seed 42
  %(prog)s --demo
        """
    )
    
    parser.add_argument(
        '--teams', '-t',
        type=int,
        default=None,
        help='Number of teams (2-10)'
    )
    
    parser.add_argument(
        '--matches', '-m',
        type=int,
        default=None,
        help='Number of matches per team'
    )
    
    parser.add_argument(
        '--seed', '-s',
        type=int,
        default=None,
        help='Random seed for reproducible results'
    )
    
    parser.add_argument(
        '--demo', '-d',
        action='store_true',
        help='Run demo with multiple team sizes'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.demo:
        # Run demo with multiple configurations
        print("ROUND-ROBIN MATCH GENERATOR DEMO")
        print("=" * 60)
        
        configs = [
            (4, 6),
            (5, 8), 
            (6, 10),
            (7, 6)
        ]
        
        for num_teams, matches_per_team in configs:
            run_demo(num_teams, matches_per_team, args.seed)
            print("\n" + "-" * 60)
        
    elif args.teams is not None and args.matches is not None:
        # Validate team count
        if not 2 <= args.teams <= 10:
            print("Error: Number of teams must be between 2 and 10")
            sys.exit(1)
        
        # Validate matches per team
        if args.matches < 1:
            print("Error: Matches per team must be at least 1")
            sys.exit(1)
        
        max_possible = args.teams - 1
        if args.matches > max_possible * 2:
            print(f"Warning: {args.matches} matches per team is very high for {args.teams} teams")
            print(f"Maximum meaningful is {max_possible} (each team plays every other team once)")
        
        # Run single configuration
        run_demo(args.teams, args.matches, args.seed)
        
    else:
        parser.print_help()
        print(f"\nError: Must specify either --demo or both --teams and --matches")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("KEY POINTS FOR USTA ROUND-ROBIN GENERATION:")
    print("• Creates unscheduled Match objects only")
    print("• Works with Team objects instead of strings")
    print("• Generates proper Match objects with league references")
    print("• Scheduling is handled separately by other system components")
    print("• Maintains balance using team IDs for tracking")
    print("• Perfect balance isn't always possible (especially even # teams)")
    print("• Target: each team gets ≈ (N-1)/2 home games")
    print("• For N teams: total matches = N*(N-1)/2, total home games = N*(N-1)/2")


if __name__ == "__main__":
    main()