#!/usr/bin/env python3
"""
Full Round-Robin Tournament Generator

DEFINITION: A "round" = a complete round-robin
- Every team plays every other team exactly once per round
- Round 1: All teams play each other once (with balanced home/away)
- Round 2: All teams play each other again (typically with reversed home/away)
- etc.

For N teams:
- Each round has N*(N-1)/2 matches
- Each team plays (N-1) matches per round
"""

import itertools
import argparse
import sys
from typing import List, Tuple, Dict, Optional
from collections import defaultdict, Counter
import random
import math
from dataclasses import dataclass


@dataclass
class Match:
    """Represents a single match."""
    home_team: str
    away_team: str
    round: int
    match_id: Optional[int] = None
    
    def get_pairing(self) -> Tuple[str, str]:
        """Get the pairing in normalized order (alphabetical)."""
        return tuple(sorted([self.home_team, self.away_team]))
    
    def involves_team(self, team: str) -> bool:
        """Check if this match involves a specific team."""
        return team in (self.home_team, self.away_team)
    
    def __str__(self) -> str:
        return f"Round {self.round}: {self.home_team} vs {self.away_team}"


def create_single_round_robin(teams: List[str], round_num: int, seed: int = None) -> List[Match]:
    """
    Create a single complete round-robin where every team plays every other team once.
    
    Args:
        teams: List of team names
        round_num: Round number for this round-robin
        seed: Random seed for reproducible home/away assignments
        
    Returns:
        List of Match objects for this complete round
    """
    # Create all possible pairings (every team vs every other team)
    all_pairings = list(itertools.combinations(teams, 2))
    
    # Shuffle for randomized home/away assignment
    if seed is not None:
        random.seed(seed)
        random.shuffle(all_pairings)
    
    # Assign home/away with balanced distribution
    home_counts = defaultdict(int)
    matches = []
    match_id_start = (round_num - 1) * len(all_pairings) + 1
    
    for i, (team1, team2) in enumerate(all_pairings):
        # Give home advantage to team with fewer home games
        if home_counts[team1] <= home_counts[team2]:
            home, away = team1, team2
        else:
            home, away = team2, team1
        
        match = Match(
            home_team=home,
            away_team=away,
            round=round_num,
            match_id=match_id_start + i
        )
        matches.append(match)
        home_counts[home] += 1
    
    return matches


def create_inverse_round_robin(original_round: List[Match], new_round_num: int) -> List[Match]:
    """
    Create an inverse round-robin by swapping home/away teams from an existing round.
    
    Args:
        original_round: List of matches from the original round
        new_round_num: Round number for the new inverse round
        
    Returns:
        List of Match objects with home/away swapped
    """
    inverse_matches = []
    match_id_start = (new_round_num - 1) * len(original_round) + 1
    
    for i, original_match in enumerate(original_round):
        inverse_match = Match(
            home_team=original_match.away_team,  # Swap
            away_team=original_match.home_team,  # Swap
            round=new_round_num,
            match_id=match_id_start + i
        )
        inverse_matches.append(inverse_match)
    
    return inverse_matches


def create_multiple_round_robins(teams: List[str], num_rounds: int, seed: int = None) -> List[Match]:
    """
    Create multiple complete round-robin rounds.
    
    Args:
        teams: List of team names
        num_rounds: Number of complete round-robins to create
        seed: Random seed for reproducible results
        
    Returns:
        Flat list of all matches across all rounds
    """
    all_matches = []
    
    print(f"Creating {num_rounds} complete round-robin(s)")
    print(f"Each round: {len(teams)} teams, {len(teams)*(len(teams)-1)//2} matches")
    print(f"Total matches: {num_rounds * len(teams) * (len(teams)-1) // 2}")
    
    for round_num in range(1, num_rounds + 1):
        if round_num % 2 == 1:
            # Odd rounds: Create new round-robin with balanced home/away
            current_seed = seed + round_num if seed else None
            round_matches = create_single_round_robin(teams, round_num, current_seed)
        else:
            # Even rounds: Create inverse of previous round (swap home/away)
            previous_round = [m for m in all_matches if m.round == round_num - 1]
            round_matches = create_inverse_round_robin(previous_round, round_num)
        
        all_matches.extend(round_matches)
        print(f"Round {round_num}: {len(round_matches)} matches")
    
    return all_matches


def create_partial_rounds_for_target_matches(teams: List[str], target_matches_per_team: int, seed: int = None) -> List[Match]:
    """
    Create enough rounds (partial if necessary) to reach target matches per team.
    
    Args:
        teams: List of team names
        target_matches_per_team: Target number of matches each team should play
        seed: Random seed for reproducible results
        
    Returns:
        Flat list of matches, potentially including a partial final round
    """
    n_teams = len(teams)
    matches_per_complete_round = n_teams - 1  # Each team plays every other team once
    matches_per_round_total = n_teams * (n_teams - 1) // 2  # Total matches in a complete round
    
    # Calculate how many complete rounds we need
    complete_rounds_needed = target_matches_per_team // matches_per_complete_round
    remaining_matches_per_team = target_matches_per_team % matches_per_complete_round
    
    print(f"Target: {target_matches_per_team} matches per team")
    print(f"Complete rounds needed: {complete_rounds_needed}")
    print(f"Additional matches per team needed: {remaining_matches_per_team}")
    
    all_matches = []
    
    # Create complete rounds
    if complete_rounds_needed > 0:
        all_matches = create_multiple_round_robins(teams, complete_rounds_needed, seed)
    
    # Create partial round if needed
    if remaining_matches_per_team > 0:
        print(f"Creating partial round {complete_rounds_needed + 1}...")
        
        # Create a full round-robin first
        partial_round_seed = seed + complete_rounds_needed + 1 if seed else None
        full_round = create_single_round_robin(teams, complete_rounds_needed + 1, partial_round_seed)
        
        # Calculate how many total matches we need for the partial round
        total_remaining_matches = (n_teams * remaining_matches_per_team) // 2
        
        # Sort matches to ensure fair distribution when truncating
        sorted_matches = sort_matches_for_balance(full_round)
        
        # Take only the matches we need
        partial_matches = sorted_matches[:total_remaining_matches]
        
        # Update round number and match IDs
        for i, match in enumerate(partial_matches):
            match.round = complete_rounds_needed + 1
            match.match_id = len(all_matches) + i + 1
        
        all_matches.extend(partial_matches)
        print(f"Partial round {complete_rounds_needed + 1}: {len(partial_matches)} matches")
    
    return all_matches


def sort_matches_for_balance(matches: List[Match]) -> List[Match]:
    """
    Sort matches to ensure fair distribution when truncating a round.
    Teams with fewer total matches get priority.
    """
    match_counts = Counter()
    home_counts = Counter()
    scheduled = []
    remaining = matches[:]

    while remaining:
        # Sort by: total matches + slight preference for teams with fewer home games
        remaining.sort(key=lambda m: match_counts[m.home_team] + match_counts[m.away_team] + home_counts[m.home_team] * 0.1)
        match = remaining.pop(0)
        scheduled.append(match)
        match_counts[match.home_team] += 1
        match_counts[match.away_team] += 1
        home_counts[match.home_team] += 1

    return scheduled


# ============ ANALYSIS FUNCTIONS ============

def count_pairings(matches: List[Match]) -> Counter:
    """Count how many times each pairing occurs (order-independent)."""
    return Counter([match.get_pairing() for match in matches])


def get_matches_by_round(matches: List[Match]) -> Dict[int, List[Match]]:
    """Group matches by round number."""
    rounds = defaultdict(list)
    for match in matches:
        rounds[match.round].append(match)
    return dict(rounds)


def analyze_tournament_balance(matches: List[Match]) -> Dict:
    """Comprehensive analysis of tournament balance."""
    # Basic counts
    home_counts = defaultdict(int)
    away_counts = defaultdict(int)
    total_counts = defaultdict(int)
    
    for match in matches:
        home_counts[match.home_team] += 1
        away_counts[match.away_team] += 1
        total_counts[match.home_team] += 1
        total_counts[match.away_team] += 1
    
    # Pairing analysis
    pairing_counts = count_pairings(matches)
    
    # Round analysis
    rounds = get_matches_by_round(matches)
    
    all_teams = set(total_counts.keys())
    
    def calc_stats(values):
        if not values:
            return {}
        return {
            'min': min(values),
            'max': max(values),
            'mean': sum(values) / len(values),
            'range': max(values) - min(values)
        }
    
    return {
        'total_matches': len(matches),
        'total_teams': len(all_teams),
        'total_rounds': len(rounds),
        'matches_per_round': {r: len(round_matches) for r, round_matches in rounds.items()},
        'home_games_per_team': dict(home_counts),
        'away_games_per_team': dict(away_counts),
        'total_games_per_team': dict(total_counts),
        'pairing_counts': dict(pairing_counts),
        'unique_pairings': len(pairing_counts),
        'home_game_stats': calc_stats(list(home_counts.values())),
        'away_game_stats': calc_stats(list(away_counts.values())),
        'total_game_stats': calc_stats(list(total_counts.values())),
        'pairing_balance_stats': calc_stats(list(pairing_counts.values()))
    }


def print_tournament_analysis(matches: List[Match], teams: List[str]):
    """Print comprehensive tournament analysis."""
    analysis = analyze_tournament_balance(matches)
    
    print(f"\nTournament Analysis")
    print("=" * 50)
    print(f"Teams: {len(teams)} ({', '.join(teams)})")
    print(f"Total matches: {analysis['total_matches']}")
    print(f"Total rounds: {analysis['total_rounds']}")
    print(f"Matches per complete round: {len(teams) * (len(teams) - 1) // 2}")
    
    # Round breakdown
    print(f"\nRound breakdown:")
    for round_num, count in sorted(analysis['matches_per_round'].items()):
        expected = len(teams) * (len(teams) - 1) // 2
        if count == expected:
            print(f"  Round {round_num}: {count} matches (complete round)")
        else:
            print(f"  Round {round_num}: {count} matches (partial round)")
    
    # Schedule by round
    rounds = get_matches_by_round(matches)
    print(f"\nDetailed Schedule:")
    for round_num in sorted(rounds.keys()):
        round_matches = rounds[round_num]
        print(f"\nRound {round_num} ({len(round_matches)} matches):")
        for i, match in enumerate(round_matches, 1):
            print(f"  {i:2d}. {match.home_team} (home) vs {match.away_team} (away)")
    
    # Team statistics
    print(f"\nTeam Statistics:")
    print(f"{'Team':<15} {'Home':<6} {'Away':<6} {'Total':<6}")
    print(f"{'-'*15} {'-'*6} {'-'*6} {'-'*6}")
    
    for team in sorted(teams):
        home = analysis['home_games_per_team'].get(team, 0)
        away = analysis['away_games_per_team'].get(team, 0)
        total = analysis['total_games_per_team'].get(team, 0)
        print(f"{team:<15} {home:<6} {away:<6} {total:<6}")
    
    # Pairing analysis
    print(f"\nPairing Frequencies (each team vs each other team):")
    for (team1, team2), count in sorted(analysis['pairing_counts'].items()):
        print(f"  {team1} vs {team2}: {count} time(s)")
    
    # Balance summary
    print(f"\nBalance Summary:")
    home_stats = analysis['home_game_stats']
    total_stats = analysis['total_game_stats']
    pairing_stats = analysis['pairing_balance_stats']
    
    print(f"  Home games  - Range: {home_stats.get('range', 0)}, Mean: {home_stats.get('mean', 0):.1f}")
    print(f"  Total games - Range: {total_stats.get('range', 0)}, Mean: {total_stats.get('mean', 0):.1f}")
    print(f"  Pairings    - Range: {pairing_stats.get('range', 0)}, Mean: {pairing_stats.get('mean', 0):.1f}")
    
    if pairing_stats.get('range', 1) == 0:
        print(f"  ✓ Perfect pairing balance! Every pairing occurs exactly {pairing_stats.get('min', 0)} time(s)")


def generate_team_names(num_teams: int) -> List[str]:
    """Generate default team names (A, B, C, etc.)."""
    return [chr(65 + i) for i in range(num_teams)]


def parse_team_names(team_names_str: str) -> List[str]:
    """Parse comma-separated team names from string."""
    teams = [name.strip() for name in team_names_str.split(',')]
    teams = [name for name in teams if name]  # Remove empty strings
    return teams


# ============ CLI FUNCTIONS ============

def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Generate complete round-robin tournaments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ROUND DEFINITION: A "round" = complete round-robin
Every team plays every other team exactly once per round.

Examples:
  %(prog)s --teams 5 --rounds 2          # 2 complete round-robins
  %(prog)s --teams 4 --matches 5         # 5 matches per team (partial rounds allowed)
  %(prog)s -t 6 --rounds 1 --seed 42     # 1 complete round with seed
  %(prog)s -t 4 --team-names "A,B,C,D"   # Custom team names
        """
    )
    
    parser.add_argument('-t', '--teams', type=int, required=True,
                        help='Number of teams (2-26)')
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--rounds', type=int,
                       help='Number of complete round-robins to create')
    group.add_argument('--matches', type=int,
                       help='Target number of matches per team (partial rounds allowed)')
    
    parser.add_argument('--team-names', type=str,
                        help='Comma-separated list of team names')
    
    parser.add_argument('--seed', type=int,
                        help='Random seed for reproducible results')
    
    parser.add_argument('--output', '-o', type=str,
                        help='Output file to save results')
    
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress detailed output, show only summary')

    args = parser.parse_args()
    
    # Validate inputs
    if args.teams < 2:
        print("Error: Need at least 2 teams")
        sys.exit(1)
    
    if args.teams > 26:
        print("Error: Maximum 26 teams supported with default naming")
        sys.exit(1)
    
    # Generate or parse team names
    if args.team_names:
        teams = parse_team_names(args.team_names)
        if len(teams) != args.teams:
            print(f"Error: Provided {len(teams)} team names but specified {args.teams} teams")
            sys.exit(1)
    else:
        teams = generate_team_names(args.teams)
    
    # Create tournament
    if args.rounds:
        print(f"Generating {args.rounds} complete round-robin(s) for {args.teams} teams...")
        matches = create_multiple_round_robins(teams, args.rounds, args.seed)
    else:
        print(f"Generating tournament for {args.teams} teams, {args.matches} matches per team...")
        matches = create_partial_rounds_for_target_matches(teams, args.matches, args.seed)
    
    # Print results
    if not args.quiet:
        print_tournament_analysis(matches, teams)
    else:
        analysis = analyze_tournament_balance(matches)
        total_stats = analysis['total_game_stats']
        print(f"\nSummary: {analysis['total_matches']} matches, "
              f"{total_stats.get('min', 0)}-{total_stats.get('max', 0)} games per team "
              f"(mean: {total_stats.get('mean', 0):.1f})")
    
    # Save to file if requested
    if args.output:
        try:
            with open(args.output, 'w') as f:
                import sys
                old_stdout = sys.stdout
                sys.stdout = f
                print_tournament_analysis(matches, teams)
                sys.stdout = old_stdout
            print(f"\nResults saved to {args.output}")
        except Exception as e:
            print(f"Error saving to file: {e}")
            sys.exit(1)


def demo():
    """Demonstrate the round-robin generator."""
    print("DEMO: Complete Round-Robin Tournament Generator")
    print("=" * 60)
    
    teams = ["A", "B", "C", "D"]
    
    # Demo 1: Single complete round
    print(f"\nDemo 1: Single complete round")
    matches1 = create_multiple_round_robins(teams, 1, seed=42)
    print_tournament_analysis(matches1, teams)
    
    # Demo 2: Two complete rounds
    print(f"\n" + "="*60)
    print(f"Demo 2: Two complete rounds")
    matches2 = create_multiple_round_robins(teams, 2, seed=42)
    analysis2 = analyze_tournament_balance(matches2)
    print(f"Total: {analysis2['total_matches']} matches across {analysis2['total_rounds']} rounds")
    
    # Demo 3: Target matches per team
    print(f"\n" + "="*60)
    print(f"Demo 3: Target 5 matches per team (partial round needed)")
    matches3 = create_partial_rounds_for_target_matches(teams, 5, seed=42)
    print_tournament_analysis(matches3, teams)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        demo()
    else:
        main()
