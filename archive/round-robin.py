#!/usr/bin/env python3
"""
Single Round with Balanced Home Games

Create one complete round-robin where every team plays every other team exactly once,
while balancing the number of home games each team gets.

For N teams, each team should get approximately (N-1)/2 home games.
"""

import itertools
from typing import List, Tuple, Dict
from collections import defaultdict
import random


def create_balanced_single_round(teams: List[str], seed: int = None) -> List[Tuple[str, str]]:
    """
    Create a single complete round with balanced home games.
    
    Strategy:
    1. Generate all unique pairings using itertools.combinations
    2. For each pairing, decide home/away to balance total home games
    3. Use greedy assignment: give home advantage to team with fewer home games
    
    Args:
        teams: List of team names
        seed: Random seed for deterministic results (optional)
        
    Returns:
        List of (home, away) tuples representing one complete round
        
    Example:
        For 4 teams: ["A", "B", "C", "D"]
        Returns 6 matches where each team gets ~1.5 home games (1 or 2)
    """
    if len(teams) < 2:
        raise ValueError("Need at least 2 teams")
    
    if seed is not None:
        random.seed(seed)
    
    # Get all unique pairings using itertools
    pairings = list(itertools.combinations(teams, 2))
    
    # Track home games for each team
    home_counts = defaultdict(int)
    
    # Process each pairing and assign home/away
    matches = []
    
    for team1, team2 in pairings:
        # Decide home/away based on current home game counts
        team1_home_count = home_counts[team1]
        team2_home_count = home_counts[team2]
        
        if team1_home_count < team2_home_count:
            # team1 has fewer home games, make them home
            home, away = team1, team2
        elif team2_home_count < team1_home_count:
            # team2 has fewer home games, make them home  
            home, away = team2, team1
        else:
            # Tied on home games, choose randomly for deterministic variation
            if random.random() < 0.5:
                home, away = team1, team2
            else:
                home, away = team2, team1
        
        matches.append((home, away))
        home_counts[home] += 1
    
    return matches


def create_perfectly_balanced_single_round(teams: List[str]) -> List[Tuple[str, str]]:
    """
    Create a single round with perfectly balanced home games when possible.
    
    This uses a more sophisticated algorithm that tries to achieve exact balance.
    For N teams:
    - If N is even: each team gets exactly (N-1)/2 home games (not always possible)
    - If N is odd: each team gets exactly (N-1)/2 home games (always possible)
    
    Args:
        teams: List of team names
        
    Returns:
        List of (home, away) tuples with optimal balance
        
    Raises:
        ValueError: If perfect balance is mathematically impossible
    """
    n = len(teams)
    if n < 2:
        raise ValueError("Need at least 2 teams")
    
    # Calculate target home games per team
    target_home_games = (n - 1) // 2
    total_matches = n * (n - 1) // 2
    
    # For even number of teams, perfect balance might not be possible
    if n % 2 == 0:
        # Each team plays (n-1) games, needs (n-1)/2 home games
        # But (n-1) is odd, so perfect split isn't possible
        # Some teams get target_home_games, others get target_home_games + 1
        expected_home_total = n * target_home_games + (n // 2)
        if expected_home_total != total_matches:
            # Adjust target - some teams will get one extra home game
            pass
    
    # Get all pairings
    pairings = list(itertools.combinations(teams, 2))
    
    # Try to solve this as an assignment problem
    # Use backtracking to find a valid assignment
    matches = []
    home_counts = defaultdict(int)
    
    def backtrack(pairing_index: int) -> bool:
        if pairing_index == len(pairings):
            return True  # All pairings assigned successfully
        
        team1, team2 = pairings[pairing_index]
        
        # Try team1 as home
        if home_counts[team1] < target_home_games + 1:  # Allow some flexibility
            matches.append((team1, team2))
            home_counts[team1] += 1
            
            if backtrack(pairing_index + 1):
                return True
            
            # Backtrack
            matches.pop()
            home_counts[team1] -= 1
        
        # Try team2 as home
        if home_counts[team2] < target_home_games + 1:  # Allow some flexibility
            matches.append((team2, team1))
            home_counts[team2] += 1
            
            if backtrack(pairing_index + 1):
                return True
            
            # Backtrack
            matches.pop()
            home_counts[team2] -= 1
        
        return False  # No valid assignment found
    
    if backtrack(0):
        return matches
    else:
        # Fallback to greedy algorithm if perfect balance impossible
        print("Perfect balance not possible, using greedy algorithm")
        return create_balanced_single_round(teams)


def create_optimally_balanced_single_round(teams: List[str]) -> List[Tuple[str, str]]:
    """
    Create the most balanced single round possible using optimization.
    
    This algorithm minimizes the variance in home games across all teams.
    
    Args:
        teams: List of team names
        
    Returns:
        List of (home, away) tuples with optimal balance
    """
    n = len(teams)
    if n < 2:
        raise ValueError("Need at least 2 teams")
    
    pairings = list(itertools.combinations(teams, 2))
    best_matches = None
    best_variance = float('inf')
    
    # Try different random assignments and keep the best one
    for attempt in range(1000):  # Try many random assignments
        matches = []
        home_counts = defaultdict(int)
        
        # Shuffle pairings for variety
        shuffled_pairings = pairings.copy()
        random.shuffle(shuffled_pairings)
        
        for team1, team2 in shuffled_pairings:
            # Assign home based on current counts
            if home_counts[team1] <= home_counts[team2]:
                home, away = team1, team2
            else:
                home, away = team2, team1
            
            matches.append((home, away))
            home_counts[home] += 1
        
        # Calculate variance in home games
        home_game_counts = [home_counts[team] for team in teams]
        mean_home_games = sum(home_game_counts) / len(home_game_counts)
        variance = sum((count - mean_home_games) ** 2 for count in home_game_counts) / len(home_game_counts)
        
        if variance < best_variance:
            best_variance = variance
            best_matches = matches.copy()
    
    return best_matches


def analyze_round_balance(matches: List[Tuple[str, str]]) -> Dict:
    """
    Analyze the home/away balance of a round.
    
    Args:
        matches: List of (home, away) tuples
        
    Returns:
        Dictionary with balance statistics
    """
    if not matches:
        return {}
    
    # Count home and away games
    home_counts = defaultdict(int)
    away_counts = defaultdict(int)
    total_counts = defaultdict(int)
    
    for home, away in matches:
        home_counts[home] += 1
        away_counts[away] += 1
        total_counts[home] += 1
        total_counts[away] += 1
    
    # Get all teams
    all_teams = set(home_counts.keys()) | set(away_counts.keys())
    
    # Calculate statistics
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
        'total_matches': len(matches),
        'total_teams': len(all_teams),
        'home_games_per_team': dict(home_counts),
        'away_games_per_team': dict(away_counts),
        'total_games_per_team': dict(total_counts),
        'home_game_stats': calculate_stats(home_games),
        'away_game_stats': calculate_stats(away_games),
        'total_game_stats': calculate_stats(total_games),
        'is_complete_round': all(total_counts[team] == len(all_teams) - 1 for team in all_teams)
    }


def print_round_analysis(teams: List[str], matches: List[Tuple[str, str]], title: str = "Round Analysis"):
    """
    Print detailed analysis of a round's balance.
    """
    analysis = analyze_round_balance(matches)
    
    print(f"\n{title}")
    print("=" * len(title))
    print(f"Teams: {teams}")
    print(f"Total matches: {analysis['total_matches']}")
    print(f"Expected matches for complete round: {len(teams) * (len(teams) - 1) // 2}")
    print(f"Is complete round: {analysis['is_complete_round']}")
    
    print(f"\nMatches:")
    for i, (home, away) in enumerate(matches, 1):
        print(f"  {i:2d}. {home:10s} (home) vs {away:10s} (away)")
    
    print(f"\nHome/Away Balance:")
    print(f"{'Team':<10} {'Home':<6} {'Away':<6} {'Total':<6}")
    print(f"{'-'*10} {'-'*6} {'-'*6} {'-'*6}")
    
    for team in sorted(teams):
        home = analysis['home_games_per_team'].get(team, 0)
        away = analysis['away_games_per_team'].get(team, 0)
        total = analysis['total_games_per_team'].get(team, 0)
        print(f"{team:<10} {home:<6} {away:<6} {total:<6}")
    
    print(f"\nBalance Statistics:")
    home_stats = analysis['home_game_stats']
    print(f"  Home games - Min: {home_stats['min']}, Max: {home_stats['max']}, "
          f"Range: {home_stats['range']}, Mean: {home_stats['mean']:.1f}")
    
    away_stats = analysis['away_game_stats']
    print(f"  Away games - Min: {away_stats['min']}, Max: {away_stats['max']}, "
          f"Range: {away_stats['range']}, Mean: {away_stats['mean']:.1f}")


def demo_different_algorithms():
    """Demo different balancing algorithms"""
    teams = ["Team A", "Team B", "Team C", "Team D", "Team E"]
    
    print("COMPARISON OF BALANCING ALGORITHMS")
    print("=" * 60)
    
    # Method 1: Simple greedy
    matches1 = create_balanced_single_round(teams, seed=42)
    print_round_analysis(teams, matches1, "Method 1: Greedy Algorithm")
    
    # Method 2: Perfect balance attempt
    matches2 = create_perfectly_balanced_single_round(teams)
    print_round_analysis(teams, matches2, "Method 2: Perfect Balance Algorithm")
    
    # Method 3: Optimized balance
    random.seed(42)
    matches3 = create_optimally_balanced_single_round(teams)
    print_round_analysis(teams, matches3, "Method 3: Optimized Balance Algorithm")


def demo_different_team_sizes():
    """Demo balancing with different numbers of teams"""
    print("\n\nBALANCING WITH DIFFERENT TEAM SIZES")
    print("=" * 60)
    
    for n in [3, 4, 5, 6, 7, 8]:
        teams = [f"Team {chr(65+i)}" for i in range(n)]  # A, B, C, ...
        matches = create_balanced_single_round(teams, seed=42)
        analysis = analyze_round_balance(matches)
        
        home_stats = analysis['home_game_stats']
        print(f"\n{n} teams: Home games range {home_stats['min']}-{home_stats['max']} "
              f"(mean: {home_stats['mean']:.1f})")


def create_multiple_balanced_rounds(teams: List[str], num_rounds: int, 
                                   balance_across_rounds: bool = True) -> List[List[Tuple[str, str]]]:
    """
    Create multiple complete rounds using the balanced single round algorithm.
    
    Args:
        teams: List of team names
        num_rounds: Number of complete rounds to create
        balance_across_rounds: If True, balance home/away across all rounds
                              If False, balance each round independently
    
    Returns:
        List of rounds, where each round is a list of (home, away) tuples
        
    Example:
        teams = ["A", "B", "C", "D"]
        rounds = create_multiple_balanced_rounds(teams, 3, balance_across_rounds=True)
        
        This creates 3 complete rounds where:
        - Each round: every team plays every other team once
        - Across all rounds: home/away games are balanced as much as possible
    """
    if num_rounds < 1:
        raise ValueError("Must create at least 1 round")
    
    if balance_across_rounds:
        return _create_rounds_with_global_balance(teams, num_rounds)
    else:
        return _create_rounds_with_local_balance(teams, num_rounds)


def _create_rounds_with_local_balance(teams: List[str], num_rounds: int) -> List[List[Tuple[str, str]]]:
    """
    Create multiple rounds where each round is individually balanced.
    
    Each round uses create_balanced_single_round independently.
    This can lead to some teams having more total home games across all rounds.
    """
    rounds = []
    
    for round_num in range(num_rounds):
        # Create each round independently with its own balancing
        round_matches = create_balanced_single_round(teams, seed=round_num)
        rounds.append(round_matches)
    
    return rounds


def _create_rounds_with_global_balance(teams: List[str], num_rounds: int) -> List[List[Tuple[str, str]]]:
    """
    Create multiple rounds balancing home/away games across ALL rounds.
    
    This ensures that total home games across all rounds are as balanced as possible.
    """
    # Get base pairings that will be used in each round
    base_pairings = list(itertools.combinations(teams, 2))
    
    # Track cumulative home games across all rounds
    total_home_counts = defaultdict(int)
    rounds = []
    
    for round_num in range(num_rounds):
        round_matches = []
        round_home_counts = defaultdict(int)  # Home games in this round only
        
        for team1, team2 in base_pairings:
            # Decide home/away based on:
            # 1. Total home games across all rounds (primary)
            # 2. Home games in current round (secondary)
            
            team1_total_home = total_home_counts[team1]
            team2_total_home = total_home_counts[team2]
            team1_round_home = round_home_counts[team1]
            team2_round_home = round_home_counts[team2]
            
            # Primary: favor team with fewer total home games
            if team1_total_home < team2_total_home:
                home, away = team1, team2
            elif team2_total_home < team1_total_home:
                home, away = team2, team1
            else:
                # Tied on total home games, use round-level balance
                if team1_round_home <= team2_round_home:
                    home, away = team1, team2
                else:
                    home, away = team2, team1
            
            round_matches.append((home, away))
            round_home_counts[home] += 1
            total_home_counts[home] += 1
        
        rounds.append(round_matches)
    
    return rounds


def create_limited_matches_from_rounds(teams: List[str], total_desired_matches: int,
                                     balance_across_rounds: bool = True) -> List[List[Tuple[str, str]]]:
    """
    Create matches by building complete rounds until we reach the desired total.
    
    This is useful when you want a specific number of matches but still want
    to organize them into complete rounds when possible.
    
    Args:
        teams: List of team names
        total_desired_matches: Total number of matches desired
        balance_across_rounds: Whether to balance home/away across rounds
        
    Returns:
        List of rounds (some may be incomplete if total doesn't divide evenly)
        
    Example:
        teams = ["A", "B", "C", "D"]  # 6 matches per complete round
        matches = create_limited_matches_from_rounds(teams, 10)
        
        Result: 
        - Round 1: 6 matches (complete round)
        - Round 2: 4 matches (partial round, selected optimally)
    """
    n_teams = len(teams)
    matches_per_complete_round = n_teams * (n_teams - 1) // 2
    
    if total_desired_matches <= 0:
        return []
    
    # Calculate how many complete rounds we can fit
    complete_rounds = total_desired_matches // matches_per_complete_round
    remaining_matches = total_desired_matches % matches_per_complete_round
    
    rounds = []
    
    # Create complete rounds
    if complete_rounds > 0:
        complete_round_list = create_multiple_balanced_rounds(
            teams, complete_rounds, balance_across_rounds
        )
        rounds.extend(complete_round_list)
    
    # Handle remaining matches by creating partial round
    if remaining_matches > 0:
        # Track total home games from complete rounds
        total_home_counts = defaultdict(int)
        for round_matches in rounds:
            for home, away in round_matches:
                total_home_counts[home] += 1
        
        # Create partial round with remaining matches
        partial_round = _create_partial_round(teams, remaining_matches, total_home_counts)
        if partial_round:
            rounds.append(partial_round)
    
    return rounds


def _create_partial_round(teams: List[str], num_matches: int, 
                         existing_home_counts: Dict[str, int]) -> List[Tuple[str, str]]:
    """
    Create a partial round with specified number of matches.
    
    Selects matches to balance home games considering existing home game counts.
    """
    # Get all possible pairings
    all_pairings = list(itertools.combinations(teams, 2))
    
    if num_matches >= len(all_pairings):
        # Want all or more matches than possible, create complete round
        return create_balanced_single_round(teams)
    
    # Select best subset of pairings for balance
    selected_matches = []
    working_home_counts = existing_home_counts.copy()
    
    # Sort pairings by how much they help balance home games
    def balance_score(pairing):
        team1, team2 = pairing
        count1 = working_home_counts.get(team1, 0)
        count2 = working_home_counts.get(team2, 0)
        # Prefer pairings with teams that have fewer home games
        return min(count1, count2), -(max(count1, count2))
    
    sorted_pairings = sorted(all_pairings, key=balance_score)
    
    # Select the best pairings
    for i in range(min(num_matches, len(sorted_pairings))):
        team1, team2 = sorted_pairings[i]
        
        # Assign home/away based on current counts
        count1 = working_home_counts.get(team1, 0)
        count2 = working_home_counts.get(team2, 0)
        
        if count1 <= count2:
            home, away = team1, team2
        else:
            home, away = team2, team1
        
        selected_matches.append((home, away))
        working_home_counts[home] = working_home_counts.get(home, 0) + 1
    
    return selected_matches


def analyze_multiple_rounds(rounds: List[List[Tuple[str, str]]]) -> Dict:
    """
    Analyze balance across multiple rounds.
    
    Returns comprehensive statistics about home/away balance.
    """
    if not rounds:
        return {}
    
    # Collect all teams
    all_teams = set()
    for round_matches in rounds:
        for home, away in round_matches:
            all_teams.add(home)
            all_teams.add(away)
    
    teams = sorted(list(all_teams))
    
    # Count games per team across all rounds
    total_home_counts = defaultdict(int)
    total_away_counts = defaultdict(int)
    total_game_counts = defaultdict(int)
    
    # Per-round statistics
    round_stats = []
    
    for round_num, round_matches in enumerate(rounds):
        round_home = defaultdict(int)
        round_away = defaultdict(int)
        round_total = defaultdict(int)
        
        for home, away in round_matches:
            # Round counts
            round_home[home] += 1
            round_away[away] += 1
            round_total[home] += 1
            round_total[away] += 1
            
            # Total counts
            total_home_counts[home] += 1
            total_away_counts[away] += 1
            total_game_counts[home] += 1
            total_game_counts[away] += 1
        
        # Analyze this round
        round_analysis = analyze_round_balance(round_matches)
        round_stats.append({
            'round': round_num + 1,
            'matches': len(round_matches),
            'analysis': round_analysis
        })
    
    # Calculate overall statistics
    total_matches = sum(len(round_matches) for round_matches in rounds)
    
    home_game_values = [total_home_counts[team] for team in teams]
    away_game_values = [total_away_counts[team] for team in teams]
    total_game_values = [total_game_counts[team] for team in teams]
    
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
        'teams': teams,
        'num_rounds': len(rounds),
        'total_matches': total_matches,
        'total_home_counts': dict(total_home_counts),
        'total_away_counts': dict(total_away_counts),
        'total_game_counts': dict(total_game_counts),
        'home_game_stats': calc_stats(home_game_values),
        'away_game_stats': calc_stats(away_game_values),
        'total_game_stats': calc_stats(total_game_values),
        'round_by_round': round_stats
    }


def print_multiple_rounds_analysis(teams: List[str], rounds: List[List[Tuple[str, str]]], 
                                  title: str = "Multiple Rounds Analysis"):
    """
    Print detailed analysis of multiple rounds.
    """
    analysis = analyze_multiple_rounds(rounds)
    
    print(f"\n{title}")
    print("=" * len(title))
    print(f"Teams: {teams}")
    print(f"Number of rounds: {analysis['num_rounds']}")
    print(f"Total matches: {analysis['total_matches']}")
    
    # Print each round
    for round_num, round_matches in enumerate(rounds, 1):
        print(f"\nRound {round_num} ({len(round_matches)} matches):")
        for i, (home, away) in enumerate(round_matches, 1):
            print(f"  {i:2d}. {home:10s} (home) vs {away:10s} (away)")
    
    # Overall balance summary
    print(f"\nOVERALL BALANCE ACROSS ALL ROUNDS:")
    print(f"{'Team':<10} {'Home':<6} {'Away':<6} {'Total':<6}")
    print(f"{'-'*10} {'-'*6} {'-'*6} {'-'*6}")
    
    for team in teams:
        home = analysis['total_home_counts'].get(team, 0)
        away = analysis['total_away_counts'].get(team, 0)
        total = analysis['total_game_counts'].get(team, 0)
        print(f"{team:<10} {home:<6} {away:<6} {total:<6}")
    
    # Balance statistics
    home_stats = analysis['home_game_stats']
    away_stats = analysis['away_game_stats']
    
    print(f"\nBALANCE STATISTICS:")
    print(f"  Home games - Min: {home_stats['min']}, Max: {home_stats['max']}, "
          f"Range: {home_stats['range']}, Mean: {home_stats['mean']:.1f}")
    print(f"  Away games - Min: {away_stats['min']}, Max: {away_stats['max']}, "
          f"Range: {away_stats['range']}, Mean: {away_stats['mean']:.1f}")


def demo_multiple_rounds_creation():
    """Demo creating multiple rounds with different strategies"""
    teams = ["Team A", "Team B", "Team C", "Team D"]
    
    print("MULTIPLE ROUNDS CREATION DEMO")
    print("=" * 60)
    
    # Method 1: Local balance (each round balanced independently)
    print("\nMethod 1: Local Balance (each round independent)")
    rounds_local = create_multiple_balanced_rounds(teams, 3, balance_across_rounds=False)
    print_multiple_rounds_analysis(teams, rounds_local, "Local Balance - 3 Rounds")
    
    # Method 2: Global balance (balance across all rounds)
    print("\nMethod 2: Global Balance (across all rounds)")
    rounds_global = create_multiple_balanced_rounds(teams, 3, balance_across_rounds=True)
    print_multiple_rounds_analysis(teams, rounds_global, "Global Balance - 3 Rounds")
    
    # Method 3: Limited matches
    print("\nMethod 3: Limited Matches (10 matches from 4 teams)")
    rounds_limited = create_limited_matches_from_rounds(teams, 10, balance_across_rounds=True)
    print_multiple_rounds_analysis(teams, rounds_limited, "Limited Matches - 10 total")


def demo_different_scenarios():
    """Demo different team sizes and round counts"""
    print("\n\nDIFFERENT SCENARIOS")
    print("=" * 60)
    
    scenarios = [
        (["A", "B", "C"], 2, "3 teams, 2 rounds"),
        (["A", "B", "C", "D", "E"], 2, "5 teams, 2 rounds"),
        (["A", "B", "C", "D", "E", "F"], 1, "6 teams, 1 round"),
    ]
    
    for teams, num_rounds, description in scenarios:
        print(f"\n{description}:")
        rounds = create_multiple_balanced_rounds(teams, num_rounds, balance_across_rounds=True)
        analysis = analyze_multiple_rounds(rounds)
        
        home_stats = analysis['home_game_stats']
        print(f"  Total matches: {analysis['total_matches']}")
        print(f"  Home games range: {home_stats['min']}-{home_stats['max']} (mean: {home_stats['mean']:.1f})")


if __name__ == "__main__":
    demo_different_algorithms()
    demo_different_team_sizes()
    demo_multiple_rounds_creation()
    demo_different_scenarios()
    
    print("\n" + "="*60)
    print("KEY POINTS FOR MULTIPLE ROUNDS:")
    print("• create_multiple_balanced_rounds() builds on single round algorithm")
    print("• Local balance: each round independent, global balance: across all rounds")
    print("• create_limited_matches_from_rounds() handles partial rounds")
    print("• Global balance gives better overall home/away distribution")
    print("• Can handle any number of rounds and team sizes")