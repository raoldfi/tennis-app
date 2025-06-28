#!/usr/bin/env python3
"""
Round-Robin Tournament Generator with CLI

Create balanced round-robin tournaments where every team plays a specified
number of matches while balancing home/away games.

Usage:
    python rr-cli.py --teams 5 --matches 6
    python rr-cli.py -t 8 -m 10 --seed 42
    python rr-cli.py --teams 6 --matches 8 --team-names "Arsenal,Chelsea,Liverpool,ManCity,ManUnited,Tottenham"
"""

import itertools
import argparse
import sys
from typing import List, Tuple, Dict, Optional
from collections import defaultdict, Counter
import random
import math


def create_balanced_single_round(teams: List[str], seed: int = None) -> List[Tuple[str, str]]:
    """Create a single round-robin with balanced home games."""
    if seed is not None:
        random.seed(seed)
        random.shuffle(teams)
    
    pairings = list(itertools.combinations(teams, 2))
    home_counts = defaultdict(int)
    matches = []
    
    for team1, team2 in pairings:
        # Give home advantage to team with fewer home games
        if home_counts[team1] <= home_counts[team2]:
            home, away = team1, team2
        else:
            home, away = team2, team1
        
        matches.append((home, away))
        home_counts[home] += 1
    
    return sort_matches_dynamically(matches)





def create_inverse_pairings(pairings: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Return the round with home and away swapped."""
    return [(away, home) for home, away in pairings]


def sort_matches_dynamically(matches: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Sort matches so that teams with fewer current matches are scheduled earlier.
    This helps balance the number of matches per team when truncating rounds.
    """
    match_counts = Counter()
    home_counts = Counter()
    scheduled = []
    remaining = matches[:]

    while remaining:
        # Sort by: total matches + slight preference for teams with fewer home games
        remaining.sort(key=lambda m: match_counts[m[0]] + match_counts[m[1]] + home_counts[m[0]] * 0.1)
        match = remaining.pop(0)
        scheduled.append(match)
        match_counts[match[0]] += 1
        match_counts[match[1]] += 1
        home_counts[match[0]] += 1

    return scheduled


def create_num_matches_per_team(teams: List[str], matches_per_team: int, seed: int = None) -> List[List[Tuple[str, str]]]:
    """
    Create balanced multiple round pairings where each team plays approximately
    the specified number of matches.
    
    Args:
        teams: List of team names
        matches_per_team: Target number of matches per team
        seed: Random seed for reproducible results
        
    Returns:
        List of rounds, where each round is a list of (home, away) tuples
    """
    n = len(teams)

    # Ensure we can create complete matches (each match involves 2 teams)
    if (n % 2 == 1) and (matches_per_team % 2 == 1):
        matches_per_team += 1
        print(f"Adjusted matches per team to {matches_per_team} to ensure balanced scheduling")

    # Calculate total number of matches needed
    total_matches = n * matches_per_team // 2
    matches_per_round = n * (n - 1) // 2
    num_rounds = math.ceil(total_matches / matches_per_round)

    matches_remaining = total_matches
    rounds = []
    inverse_pairings = []

    print(f"Generating {num_rounds} round(s) for {total_matches} total matches...")

    for round_num in range(num_rounds):
        if matches_remaining <= 0:
            break
            
        matches = []
        
        # Alternate between regular and inverse pairings for balance
        if round_num % 2 == 0:
            matches = create_balanced_single_round(teams, seed + round_num if seed else None)
            inverse_pairings = sort_matches_dynamically(create_inverse_pairings(matches))
        else:
            matches = inverse_pairings

        # If we need fewer matches than a full round, select the most balanced subset
        if matches_remaining < len(matches):
            matches = sort_matches_dynamically(matches)
            matches = matches[:matches_remaining]
            
        rounds.append(matches)
        matches_remaining -= len(matches)
        print(f"Round {round_num + 1}: {len(matches)} matches, {matches_remaining} remaining")

    return rounds

def create_num_matches_v2(teams: List[str], matches_per_team: int, seed: int = None) -> List[List[Tuple[str, str]]]:
    """
    Create balanced multiple round pairings where each team plays approximately
    the specified number of matches.
    
    Args:
        teams: List of team names
        matches_per_team: Target number of matches per team
        seed: Random seed for reproducible results
        
    Returns:
        List of rounds, where each round is a list of (home, away) tuples
    """
    n = len(teams)

    # Ensure we can create complete matches (each match involves 2 teams)
    if (n % 2 == 1) and (matches_per_team % 2 == 1):
        matches_per_team += 1
        print(f"Adjusted matches per team to {matches_per_team} to ensure balanced scheduling")

    # Calculate total number of matches needed
    total_matches = n * matches_per_team // 2
    matches_per_round = n * (n - 1) // 2
    num_rounds = math.ceil(total_matches / matches_per_round)

    matches_remaining = total_matches
    rounds = []

    pairing_counts = defaultdict(int)

    permutations = sort_matches_dynamically(itertools.permutations(teams, 2))
    backup = permutations

    match_counts = Counter()
    home_counts = Counter()
    scheduled = []
    remaining = matches[:]

    while remaining:
        # Sort by: total matches + slight preference for teams with fewer home games
        remaining.sort(key=lambda m: match_counts[m[0]] + match_counts[m[1]] + home_counts[m[0]] * 0.1)
        match = remaining.pop(0)
        scheduled.append(match)
        match_counts[match[0]] += 1
        match_counts[match[1]] += 1
        home_counts[match[0]] += 1

    return rounds



def generate_matches(teams: List[str], num_matches: int) -> List[str]:
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

    
    team_list = teams
    
    # Generate all permutations of team pairs
    permutations = list(itertools.permutations(team_list, 2))
    total_usage_counts = defaultdict(str)  # Use team IDs as keys
    first_usage_counts = defaultdict(str)  # Tracks home game counts (use team IDs)
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
            total_usage_counts[pair[0]] + total_usage_counts[pair[1]], 
            first_usage_counts[pair[0]]
        ))
        
        # If we run out of permutations, reset to backup
        if not permutations:
            permutations = backup_permutations.copy()
        
        selected_pair = permutations.pop(0)
        inverse_pair = (selected_pair[1], selected_pair[0])
        
        # Choose home/away based on balance
        # If first team has more home games than second team, swap them
        if first_usage_counts[selected_pair[0]] > first_usage_counts[selected_pair[1]]:
            selected_pair = inverse_pair
        
        # Create hashable keys for pair counting (using team IDs)
        selected_pair_key = (selected_pair[0], selected_pair[1])
        inverse_pair_key = (selected_pair[1], selected_pair[0])
        
        # If this exact pairing has been used more than its inverse, use the inverse
        if pair_counts[selected_pair_key] > pair_counts[inverse_pair_key]:
            selected_pair = inverse_pair
            selected_pair_key = inverse_pair_key
        
        # Add the selected pair
        selected_pairs.append(selected_pair)
        
        # Update usage counts using team IDs as keys
        total_usage_counts[selected_pair[0]] += 1  # Home team total matches
        total_usage_counts[selected_pair[1]] += 1  # Away team total matches
        first_usage_counts[selected_pair[0]] += 1  # Home team home matches
        pair_counts[selected_pair_key] += 1             # This specific pairing count
        
        # Remove the used pair and its inverse from available permutations
        # Compare by team IDs to ensure proper matching
        selected_ids = (selected_pair[0], selected_pair[1])
        inverse_ids = (selected_pair[1], selected_pair[0])
        permutations = [p for p in permutations 
                      if (p[0].id, p[1].id) != selected_ids and (p[0].id, p[1].id) != inverse_ids]
    
    # Generate deterministic starting match ID for this league
    base_match_id = 1
    
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

    
def create_round_robin(teams: List[str], seed: int = None) -> List[Tuple[str, str]]:
    """Create a full round robin"""
    if seed is not None:
        random.seed(seed)
        random.shuffle(teams)
    
    pairings = list(itertools.permututations(teams, 2))
    return sort_matches_dynamically(pairings)


def analyze_balance(rounds: List[List[Tuple[str, str]]]) -> Dict:
    """Analyze the home/away balance of tournament rounds."""
    if not rounds:
        return {}
    
    home_counts = defaultdict(int)
    away_counts = defaultdict(int)
    total_counts = defaultdict(int)
    num_matches = 0

    for matches in rounds:
        for home, away in matches:
            home_counts[home] += 1
            away_counts[away] += 1
            total_counts[home] += 1
            total_counts[away] += 1
            num_matches += 1
    
    all_teams = set(home_counts.keys()) | set(away_counts.keys())
    
    home_games = [home_counts[team] for team in all_teams]
    away_games = [away_counts[team] for team in all_teams]
    total_games = [total_counts[team] for team in all_teams]
    
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
        'total_matches': num_matches,
        'total_teams': len(all_teams),
        'home_games_per_team': dict(home_counts),
        'away_games_per_team': dict(away_counts),
        'total_games_per_team': dict(total_counts),
        'home_game_stats': calculate_stats(home_games),
        'away_game_stats': calculate_stats(away_games),
        'total_game_stats': calculate_stats(total_games),
    }


def print_analysis(teams: List[str], rounds: List[List[Tuple[str, str]]], title: str = "Tournament Analysis"):
    """Print detailed analysis of tournament rounds."""
    analysis = analyze_balance(rounds)
    
    print(f"\n{title}")
    print("=" * len(title))
    print(f"Teams: {len(teams)} ({', '.join(teams)})")
    print(f"Total matches: {analysis['total_matches']}")
    print(f"Complete round-robin matches: {len(teams) * (len(teams) - 1) // 2}")
    
    print(f"\nSchedule:")
    for r, matches in enumerate(rounds, 1):
        print(f"\nRound {r} ({len(matches)} matches):")
        for i, (home, away) in enumerate(matches, 1):
            print(f"  {i:2d}. {home} (home) vs {away} (away)")
    
    print(f"\nTeam Statistics:")
    print(f"{'Team':<15} {'Home':<6} {'Away':<6} {'Total':<6}")
    print(f"{'-'*15} {'-'*6} {'-'*6} {'-'*6}")
    
    for team in sorted(teams):
        home = analysis['home_games_per_team'].get(team, 0)
        away = analysis['away_games_per_team'].get(team, 0)
        total = analysis['total_games_per_team'].get(team, 0)
        print(f"{team:<15} {home:<6} {away:<6} {total:<6}")
    
    print(f"\nBalance Summary:")
    home_stats = analysis['home_game_stats']
    away_stats = analysis['away_game_stats']
    total_stats = analysis['total_game_stats']
    
    print(f"  Home games  - Min: {home_stats['min']}, Max: {home_stats['max']}, "
          f"Range: {home_stats['range']}, Mean: {home_stats['mean']:.1f}")
    print(f"  Away games  - Min: {away_stats['min']}, Max: {away_stats['max']}, "
          f"Range: {away_stats['range']}, Mean: {away_stats['mean']:.1f}")
    print(f"  Total games - Min: {total_stats['min']}, Max: {total_stats['max']}, "
          f"Range: {total_stats['range']}, Mean: {total_stats['mean']:.1f}")


def generate_team_names(num_teams: int) -> List[str]:
    """Generate default team names (Team A, Team B, etc.)."""
    return [f"Team {chr(65 + i)}" for i in range(num_teams)]


def parse_team_names(team_names_str: str) -> List[str]:
    """Parse comma-separated team names from string."""
    teams = [name.strip() for name in team_names_str.split(',')]
    teams = [name for name in teams if name]  # Remove empty strings
    return teams


def validate_inputs(num_teams: int, matches_per_team: int) -> bool:
    """Validate input parameters."""
    if num_teams < 2:
        print("Error: Need at least 2 teams for a tournament")
        return False
    
    if num_teams > 26:
        print("Error: Maximum 26 teams supported with default naming")
        return False
    
    if matches_per_team < 1:
        print("Error: Each team must play at least 1 match")
        return False
    
    max_possible_matches = num_teams - 1
    if matches_per_team > max_possible_matches:
        print(f"Error: Each team can play at most {max_possible_matches} matches "
              f"(against every other team once)")
        return False
    
    return True


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Generate balanced round-robin tournaments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --teams 5 --matches 6
  %(prog)s -t 8 -m 10 --seed 42
  %(prog)s -t 4 -m 3 --team-names "Arsenal,Chelsea,Liverpool,ManCity"
  %(prog)s --teams 6 --matches 5 --output tournament.txt
        """
    )
    
    parser.add_argument('-t', '--teams', type=int, required=True,
                        help='Number of teams (2-26)')
    
    parser.add_argument('-m', '--matches', type=int, required=True,
                        help='Target number of matches per team')
    
    parser.add_argument('--team-names', type=str,
                        help='Comma-separated list of team names (e.g., "Team1,Team2,Team3")')
    
    parser.add_argument('--seed', type=int,
                        help='Random seed for reproducible results')
    
    parser.add_argument('--output', '-o', type=str,
                        help='Output file to save results (optional)')
    
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress detailed output, show only summary')

    args = parser.parse_args()
    
    # Validate inputs
    if not validate_inputs(args.teams, args.matches):
        sys.exit(1)
    
    # Generate or parse team names
    if args.team_names:
        teams = parse_team_names(args.team_names)
        if len(teams) != args.teams:
            print(f"Error: Provided {len(teams)} team names but specified {args.teams} teams")
            sys.exit(1)
    else:
        teams = generate_team_names(args.teams)
    
    # Generate tournament
    print(f"Generating tournament for {args.teams} teams, {args.matches} matches per team...")
    if args.seed:
        print(f"Using random seed: {args.seed}")
    
    rounds = create_num_matches_per_team(teams, args.matches, args.seed)
    
    # Print results
    if not args.quiet:
        print_analysis(teams, rounds, "Tournament Results")
    else:
        analysis = analyze_balance(rounds)
        total_stats = analysis['total_game_stats']
        print(f"\nSummary: {analysis['total_matches']} matches, "
              f"{total_stats['min']}-{total_stats['max']} games per team "
              f"(mean: {total_stats['mean']:.1f})")
    
    # Save to file if requested
    if args.output:
        try:
            with open(args.output, 'w') as f:
                # Redirect print to file
                import sys
                old_stdout = sys.stdout
                sys.stdout = f
                print_analysis(teams, rounds, "Tournament Results")
                sys.stdout = old_stdout
            print(f"\nResults saved to {args.output}")
        except Exception as e:
            print(f"Error saving to file: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()