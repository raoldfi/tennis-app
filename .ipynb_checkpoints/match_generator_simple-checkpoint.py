"""
Round-Robin Tournament Pairing Generator

This module provides a MatchGenerator class for creating round-robin tournament pairings
with balanced home/away assignments. It supports both full and partial round-robins,
as well as multiple round-robin cycles where teams can play each other more than once.

Algorithm Features:
- Ensures every team plays exactly the specified number of matches
- Balances home and away assignments as evenly as possible
- Supports multiple round-robin cycles (teams can play each other multiple times)
- When teams play multiple times, alternates home/away assignments
- Uses the circle method for systematic pairing generation

Home/Away Balance:
The algorithm attempts to achieve perfect home/away balance, but this is not always possible:

1. Odd Matches Per Team: If matches_per_team is odd, perfect balance is impossible.
   Best case: teams will have either (n+1)/2 home and (n-1)/2 away, or vice versa.

2. Structural Constraints: Even with even matches per team, certain configurations
   may prevent perfect balance due to pairing requirements.

3. Small Tournaments: With 2-3 teams, balance constraints may be impossible to satisfy.

Validation:
- Requires at least 2 teams
- Requires at least 1 match per team
- Total match slots (teams × matches_per_team) must be even, since each match uses 2 slots

Usage Examples:
    generator = MatchGenerator()
    pairings = generator.generate_pairings(['A', 'B', 'C', 'D'], 3)
    generator.print_schedule(pairings)
    balance = generator.analyze_balance(['A', 'B', 'C', 'D'], pairings)
"""


class MatchGenerator:
    """
    A class for generating round-robin tournament pairings with balanced home/away assignments.
    """
    
    def __init__(self):
        """Initialize the MatchGenerator."""
        pass
    
    def generate_pairings(self, teams, matches_per_team):
        """
        Generate round-robin pairings with balanced home/away assignments.
        
        Args:
            teams: List of team names/identifiers
            matches_per_team: Number of matches each team should play
            
        Returns:
            List of tuples (home_team, away_team) representing the schedule
            
        Raises:
            ValueError: If configuration is invalid
        """
        if len(teams) < 2:
            raise ValueError("At least 2 teams are required")
        
        if matches_per_team < 1:
            raise ValueError("Matches per team must be at least 1")
        
        # Check if total match slots is even
        total_match_slots = len(teams) * matches_per_team
        if total_match_slots % 2 != 0:
            raise ValueError(
                f"Invalid configuration: {len(teams)} teams × {matches_per_team} matches = "
                f"{total_match_slots} total match slots. This must be even since each match uses exactly 2 slots."
            )
        
        n = len(teams)
        
        # Create a list to track matches for each team
        team_matches = {team: [] for team in teams}
        team_home_count = {team: 0 for team in teams}
        team_away_count = {team: 0 for team in teams}
        
        # Track how many times each pair has played
        pair_counts = {}
        for i in range(n):
            for j in range(i + 1, n):
                pair_counts[(teams[i], teams[j])] = 0
        
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
                    if (len(team_matches[home]) >= matches_per_team or 
                        len(team_matches[away]) >= matches_per_team):
                        continue
                    
                    # For multiple cycles, alternate home/away from previous meetings
                    pair_key = tuple(sorted([home, away]))
                    times_played = pair_counts[pair_key]
                    
                    # Determine home/away based on balance and previous meetings
                    if times_played > 0:
                        # If they've played before, reverse home/away from last time
                        for prev_home, prev_away in reversed(schedule):
                            if {prev_home, prev_away} == {home, away}:
                                if prev_home == home:
                                    home, away = away, home
                                break
                    else:
                        # First meeting - use balance
                        if team_home_count[home] > team_home_count[away]:
                            home, away = away, home
                    
                    # Add the match
                    schedule.append((home, away))
                    team_matches[home].append(away)
                    team_matches[away].append(home)
                    team_home_count[home] += 1
                    team_away_count[away] += 1
                    pair_counts[pair_key] += 1
                    
                    # Check if we've scheduled enough matches
                    if all(len(team_matches[team]) >= matches_per_team for team in teams):
                        return schedule
        
        return schedule
    
    def _generate_even_rounds(self, teams):
        """Generate rounds for even number of teams using circle method."""
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
    
    def _generate_odd_rounds(self, teams):
        """Generate rounds for odd number of teams by adding a bye."""
        # Add a dummy team for the bye
        teams_with_bye = teams + ["BYE"]
        rounds = self._generate_even_rounds(teams_with_bye)
        
        # Remove matches involving the bye
        cleaned_rounds = []
        for round_matches in rounds:
            cleaned_round = [(h, a) for h, a in round_matches if h != "BYE" and a != "BYE"]
            if cleaned_round:
                cleaned_rounds.append(cleaned_round)
        
        return cleaned_rounds
    
    def print_schedule(self, schedule):
        """Pretty print the schedule."""
        print(f"Total matches: {len(schedule)}\n")
        print("Schedule:")
        for i, (home, away) in enumerate(schedule, 1):
            print(f"Match {i:3d}: {home:15s} (H) vs {away:15s} (A)")
    
    def analyze_balance(self, teams, pairings):
        """
        Analyze home/away balance and return statistics.
        
        Args:
            teams: List of team names
            pairings: List of (home, away) tuples
        
        Returns:
            dict: Statistics about balance including max deviation
        """
        stats = {team: {"home": 0, "away": 0} for team in teams}
        
        for home, away in pairings:
            stats[home]["home"] += 1
            stats[away]["away"] += 1
        
        # Calculate deviations
        max_home = max(s["home"] for s in stats.values())
        min_home = min(s["home"] for s in stats.values())
        max_away = max(s["away"] for s in stats.values())
        min_away = min(s["away"] for s in stats.values())
        
        # Calculate ideal balance
        matches_per_team = stats[teams[0]]["home"] + stats[teams[0]]["away"]
        ideal_home = matches_per_team // 2
        ideal_away = matches_per_team - ideal_home
        
        max_deviation = max(
            max_home - ideal_home,
            ideal_home - min_home,
            max_away - ideal_away,
            ideal_away - min_away
        )
        
        return {
            "matches_per_team": matches_per_team,
            "ideal_home": ideal_home,
            "ideal_away": ideal_away,
            "max_home": max_home,
            "min_home": min_home,
            "max_away": max_away,
            "min_away": min_away,
            "max_deviation": max_deviation,
            "perfectly_balanced": max_deviation == 0,
            "team_stats": stats
        }
    
    def format_schedule(self, teams, pairings, format_type="standard", include_stats=True):
        """
        Format the schedule in different output formats.
        
        Args:
            teams: List of team names
            pairings: List of (home, away) tuples
            format_type: "standard", "csv", or "simple"
            include_stats: Whether to include team statistics (only for standard format)
        
        Returns:
            str: Formatted schedule string
        """
        if format_type == "simple":
            output_lines = []
            for home, away in pairings:
                output_lines.append(f"{home} vs {away}")
            return "\n".join(output_lines)
        
        elif format_type == "csv":
            output_lines = ["Home,Away"]
            for home, away in pairings:
                output_lines.append(f"{home},{away}")
            return "\n".join(output_lines)
        
        else:  # standard format
            output_lines = []
            
            # Header
            output_lines.append(f"Round-Robin Tournament Pairings")
            output_lines.append(f"Teams: {len(teams)}")
            if pairings:
                balance = self.analyze_balance(teams, pairings)
                output_lines.append(f"Matches per team: {balance['matches_per_team']}")
            output_lines.append(f"Total matches: {len(pairings)}")
            output_lines.append("=" * 60)
            output_lines.append("")
            
            # Pairings
            output_lines.append("Pairings to be scheduled:")
            for home, away in pairings:
                output_lines.append(f"{home:20s} (H) vs {away:20s} (A)")
            
            # Statistics
            if include_stats and pairings:
                balance = self.analyze_balance(teams, pairings)
                
                output_lines.append("")
                output_lines.append("Team Statistics:")
                output_lines.append(f"{'Team':20s} {'Matches':>8s} {'Home':>6s} {'Away':>6s}")
                output_lines.append("-" * 50)
                
                for team in teams:
                    s = balance["team_stats"][team]
                    total = s["home"] + s["away"]
                    output_lines.append(
                        f"{team:20s} {total:>8d} {s['home']:>6d} {s['away']:>6d}"
                    )
                
                output_lines.append("")
                output_lines.append("Balance Analysis:")
                output_lines.append(f"Ideal distribution: {balance['ideal_home']} home, {balance['ideal_away']} away")
                
                if balance["perfectly_balanced"]:
                    output_lines.append("✓ Perfect balance achieved!")
                else:
                    output_lines.append(f"Maximum deviation from ideal: {balance['max_deviation']}")
                    if balance["matches_per_team"] % 2 == 1:
                        output_lines.append("Note: Perfect balance impossible with odd number of matches per team")
            
            return "\n".join(output_lines)
    
    def export_schedule(self, teams, pairings, filename, format_type="standard", include_stats=True):
        """
        Export the schedule to a file.
        
        Args:
            teams: List of team names
            pairings: List of (home, away) tuples
            filename: Output filename
            format_type: "standard", "csv", or "simple"
            include_stats: Whether to include team statistics (only for standard format)
        """
        output = self.format_schedule(teams, pairings, format_type, include_stats)
        with open(filename, 'w') as f:
            f.write(output)


def main():
    """Main function with CLI - maintains backward compatibility."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate round-robin tournament pairings with balanced home/away assignments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 6 5                    # 6 teams, 5 matches each (full round-robin)
  %(prog)s 8 3                    # 8 teams, 3 matches each (partial round-robin)
  %(prog)s 5 4 --names A B C D E  # 5 custom team names, 4 matches each
  %(prog)s 4 6 --export pairings.txt  # Export pairings to file
        """
    )
    
    parser.add_argument(
        "num_teams",
        type=int,
        help="Number of teams in the tournament"
    )
    
    parser.add_argument(
        "matches_per_team",
        type=int,
        help="Number of matches each team should play"
    )
    
    parser.add_argument(
        "--names",
        nargs="+",
        help="Custom team names (must match number of teams)"
    )
    
    parser.add_argument(
        "--export",
        metavar="FILE",
        help="Export pairings to a text file"
    )
    
    parser.add_argument(
        "--no-stats",
        action="store_true",
        help="Don't display team statistics"
    )
    
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Output in CSV format"
    )
    
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Simple format: just the pairings, one per line"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.num_teams < 2:
        parser.error("Number of teams must be at least 2")
    
    if args.matches_per_team < 1:
        parser.error("Matches per team must be at least 1")
    
    # Generate team names
    if args.names:
        if len(args.names) != args.num_teams:
            parser.error(f"Number of team names ({len(args.names)}) must match number of teams ({args.num_teams})")
        teams = args.names
    else:
        # Generate default team names
        teams = [f"Team {i+1}" for i in range(args.num_teams)]
    
    # Create generator and generate pairings
    generator = MatchGenerator()
    
    try:
        pairings = generator.generate_pairings(teams, args.matches_per_team)
    except ValueError as e:
        parser.error(str(e))
    
    # Determine format
    if args.simple:
        format_type = "simple"
    elif args.csv:
        format_type = "csv"
    else:
        format_type = "standard"
    
    # Output or export
    if args.export:
        generator.export_schedule(teams, pairings, args.export, format_type, not args.no_stats)
        print(f"Pairings exported to {args.export}")
    else:
        output = generator.format_schedule(teams, pairings, format_type, not args.no_stats)
        print(output)


if __name__ == "__main__":
    main()
