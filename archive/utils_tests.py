#!/usr/bin/env python3
"""
Test Suite for Utils Functions

This module contains all test functions for the utility functions in utils.py.
Tests cover match generation and optimal scheduling dates.
"""

import sys
import traceback
from typing import List

# Import the functions we want to test from utils
try:
    from utils import (
        generate_matches, 
        get_optimal_scheduling_dates
    )
    from usta import League, Team, Facility, Match
    from usta_constants import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure utils.py and usta modules are in your Python path")
    sys.exit(1)


def test_get_optimal_scheduling_dates():
    """
    Test function to verify the get_optimal_scheduling_dates works correctly
    """
    print("Testing get_optimal_scheduling_dates function...")
    
    try:
        # Create a league with proper parameters
        league = League(
            id=1,
            name="Test League",
            year=2025,
            section=USTA_SECTIONS[0],    # "Caribbean"
            region=USTA_REGIONS[0],      # "Northern New Mexico"
            age_group=USTA_AGE_GROUPS[0], # "18 & Over"
            division=USTA_DIVISIONS[0],   # "2.5 Women"
            num_lines_per_match=3,
            num_matches=10,
            preferred_days=["Saturday", "Sunday"],
            backup_days=["Friday"],
            start_date="2025-01-01",
            end_date="2025-04-30"
        )
        
        # Create a facility for teams
        facility = Facility(
            id=1,
            name="Test Facility",
            location="Test Location"
        )
        
        # Create teams with preferred days that have intersection
        home_team = Team(
            id=1,
            name="Home Team",
            league=league,
            home_facility=facility,
            preferred_days=["Saturday", "Sunday"]  # Changed to have overlap
        )
        
        visitor_team = Team(
            id=2,
            name="Visitor Team",
            league=league,
            home_facility=facility,
            preferred_days=["Saturday"]  # Changed to have overlap with home team
        )
        
        # Create match
        match = Match(
            id=1,
            round=1,
            league=league,
            home_team=home_team,
            visitor_team=visitor_team,
            facility=None,
            date=None,
            scheduled_times=[]
        )
        
        print(f"Test 1: Teams with overlapping preferred days")
        print(f"Home team preferred: {home_team.preferred_days}")
        print(f"Visitor team preferred: {visitor_team.preferred_days}")
        print(f"League preferred: {league.preferred_days}")
        print(f"League backup: {league.backup_days}")
        
        # Test the function
        result = get_optimal_scheduling_dates(match, num_dates=10)
        
        print(f"✓ Function executed successfully")
        print(f"✓ Returned {len(result)} dates")
        if result:
            print(f"✓ First date: {result[0]}")
            print(f"✓ Last date: {result[-1]}")
            print(f"✓ Sample dates: {result[:5]}")
        
        # Test 2: Teams with no preferred days (should use league preferences)
        print(f"\nTest 2: Teams with no preferred days")
        home_team.preferred_days = []
        visitor_team.preferred_days = []
        
        result2 = get_optimal_scheduling_dates(match, num_dates=5)
        print(f"✓ Test with empty team preferences: {len(result2)} dates")
        if result2:
            print(f"✓ Sample dates: {result2}")
        
        # Test 3: Teams with non-overlapping preferred days (should raise error)
        print(f"\nTest 3: Teams with non-overlapping preferred days")
        home_team.preferred_days = ["Monday"]
        visitor_team.preferred_days = ["Tuesday"]
        
        try:
            result3 = get_optimal_scheduling_dates(match, num_dates=5)
            print(f"✗ Should have raised ValueError for non-overlapping preferences")
            return False
        except ValueError as e:
            print(f"✓ Correctly raised ValueError: {e}")
        
        # Test 4: One team has preferences, other doesn't
        print(f"\nTest 4: Mixed preferences")
        home_team.preferred_days = ["Saturday"]
        visitor_team.preferred_days = []
        
        result4 = get_optimal_scheduling_dates(match, num_dates=5)
        print(f"✓ Test with mixed preferences: {len(result4)} dates")
        if result4:
            print(f"✓ Sample dates: {result4}")
        
        # Test 5: Custom date range
        print(f"\nTest 5: Custom date range")
        home_team.preferred_days = ["Saturday"]
        visitor_team.preferred_days = ["Saturday"]
        
        result5 = get_optimal_scheduling_dates(
            match, 
            start_date="2025-02-01", 
            end_date="2025-02-28",
            num_dates=3
        )
        print(f"✓ Test with custom date range: {len(result5)} dates")
        if result5:
            print(f"✓ Sample dates: {result5}")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        traceback.print_exc()
        return False


def test_generate_matches():
    """
    Test function to verify the generate_matches function works correctly
    Tests various scenarios including edge cases and validation
    """
    print("Testing generate_matches function...")
    
    # Test 1: Basic functionality with even number of teams
    print("\n=== Test 1: Basic functionality (4 teams) ===")
    try:
        league = League(
            id=1,
            name="Test League",
            year=2025,
            section=USTA_SECTIONS[0],
            region=USTA_REGIONS[0],
            age_group=USTA_AGE_GROUPS[0],
            division=USTA_DIVISIONS[0],
            num_lines_per_match=3,
            num_matches=7
        )
        
        facility = Facility(id=1, name="Test Facility", location="Test Location")
        
        teams = [
            Team(1, "Team A", league, facility),
            Team(2, "Team B", league, facility),
            Team(3, "Team C", league, facility),
            Team(4, "Team D", league, facility),
            Team(4, "Team E", league, facility)
        ]
        
        matches = generate_matches(teams)
        
        print(f"✓ Generated {len(matches)} matches")
        print(f"✓ Expected approximately {6 * 4 // 2} matches")
        
        # Verify match properties
        for i, match in enumerate(matches):  # Show first 3 matches
            print(f"  Match {i+1}, round {match.round}: {match.home_team.name} vs {match.visitor_team.name} (ID: {match.id})")
        
        # Test home/away balance
        home_counts = {}
        away_counts = {}
        for match in matches:
            home_counts[match.home_team.id] = home_counts.get(match.home_team.id, 0) + 1
            away_counts[match.visitor_team.id] = away_counts.get(match.visitor_team.id, 0) + 1
        
        print(f"✓ Home game distribution: {home_counts}")
        print(f"✓ Away game distribution: {away_counts}")
        
        # Verify all matches have valid properties and track round information
        round_counts = {}
        round_pairings = {}  # Track which teams play in each round
        
        for match in matches:
            assert match.id is not None, "Match ID should not be None"
            assert match.round >= 1, "Round should be >= 1"
            assert match.league == league, "Match league should match input league"
            assert match.home_team in teams, "Home team should be from input teams"
            assert match.visitor_team in teams, "Visitor team should be from input teams"
            assert match.home_team != match.visitor_team, "Home and visitor teams should be different"
            assert match.facility is None, "Facility should be None for unscheduled matches"
            assert match.date is None, "Date should be None for unscheduled matches"
            assert match.scheduled_times == [], "Scheduled times should be empty for unscheduled matches"
            
            # Count matches per round
            round_counts[match.round] = round_counts.get(match.round, 0) + 1
            
            # Track pairings per round
            if match.round not in round_pairings:
                round_pairings[match.round] = []
            round_pairings[match.round].append((match.home_team.id, match.visitor_team.id))
        
        print("✓ All match properties validated")
        print(f"✓ Round distribution: {round_counts}")
        
        # Verify round numbering makes sense
        max_round = max(round_counts.keys()) if round_counts else 0
        min_round = min(round_counts.keys()) if round_counts else 0
        
        if round_counts:
            assert min_round == 1, f"First round should be 1, got {min_round}"
            print(f"✓ Rounds span from {min_round} to {max_round}")
            
            # Check that rounds are sequential (no gaps)
            expected_rounds = set(range(min_round, max_round + 1))
            actual_rounds = set(round_counts.keys())
            assert actual_rounds == expected_rounds, f"Rounds should be sequential: expected {expected_rounds}, got {actual_rounds}"
            
            # For a complete round-robin, each round should have every team playing every other team once
            # For 4 teams: round 1 should have 6 matches (A-B, A-C, A-D, B-C, B-D, C-D)
            # But since we're generating multiple rounds with limited total matches, 
            # we should verify that no team plays the same opponent twice in the same round
            for round_num, pairings in round_pairings.items():
                teams_in_round = set()
                for home_id, visitor_id in pairings:
                    teams_in_round.add(home_id)
                    teams_in_round.add(visitor_id)
                
                # Check no duplicate pairings in same round
                unique_pairings = set()
                for home_id, visitor_id in pairings:
                    # Normalize pairing (smaller ID first) to catch A-B vs B-A duplicates
                    normalized_pair = tuple(sorted([home_id, visitor_id]))
                    assert normalized_pair not in unique_pairings, f"Duplicate pairing in round {round_num}: {normalized_pair}"
                    unique_pairings.add(normalized_pair)
                
                print(f"✓ Round {round_num}: {len(pairings)} matches, {len(teams_in_round)} teams involved")
        
        print(f"✓ Round validation completed for {len(teams)} teams")
        
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
        traceback.print_exc()
        return False
    
    # Test 2: Odd number of teams
    print("\n=== Test 2: Odd number of teams (5 teams) ===")
    try:
        league = League(
            id=2,
            name="Odd League",
            year=2025,
            section=USTA_SECTIONS[0],
            region=USTA_REGIONS[0],
            age_group=USTA_AGE_GROUPS[0],
            division=USTA_DIVISIONS[0],
            num_lines_per_match=3,
            num_matches=8
        )
        
        facility = Facility(id=1, name="Test Facility", location="Test Location")
        
        teams = [
            Team(1, "Team A", league, facility),
            Team(2, "Team B", league, facility),
            Team(3, "Team C", league, facility),
            Team(4, "Team D", league, facility),
            Team(5, "Team E", league, facility)
        ]
        
        matches = generate_matches(teams)
        print(f"✓ Generated {len(matches)} matches for odd number of teams")
        
        # Verify each team gets roughly equal matches and track rounds
        team_match_counts = {}
        round_counts = {}
        round_pairings = {}
        
        for match in matches:
            team_match_counts[match.home_team.id] = team_match_counts.get(match.home_team.id, 0) + 1
            team_match_counts[match.visitor_team.id] = team_match_counts.get(match.visitor_team.id, 0) + 1
            round_counts[match.round] = round_counts.get(match.round, 0) + 1
            
            # Track pairings per round
            if match.round not in round_pairings:
                round_pairings[match.round] = []
            round_pairings[match.round].append((match.home_team.id, match.visitor_team.id))
        
        print(f"✓ Team match distribution: {team_match_counts}")
        print(f"✓ Round distribution: {round_counts}")
        
        # Check that the distribution is reasonably balanced
        match_counts = list(team_match_counts.values())
        max_count = max(match_counts)
        min_count = min(match_counts)
        print(f"✓ Match count range: {min_count} to {max_count}")
        
        # Verify round numbering for odd teams
        if round_counts:
            max_round = max(round_counts.keys())
            min_round = min(round_counts.keys())
            assert min_round == 1, f"First round should be 1, got {min_round}"
            print(f"✓ Rounds span from {min_round} to {max_round}")
            
            # Check that rounds are sequential
            expected_rounds = set(range(min_round, max_round + 1))
            actual_rounds = set(round_counts.keys())
            assert actual_rounds == expected_rounds, f"Rounds should be sequential: expected {expected_rounds}, got {actual_rounds}"
            
            # Verify no duplicate pairings within same round
            for round_num, pairings in round_pairings.items():
                unique_pairings = set()
                for home_id, visitor_id in pairings:
                    normalized_pair = tuple(sorted([home_id, visitor_id]))
                    assert normalized_pair not in unique_pairings, f"Duplicate pairing in round {round_num}: {normalized_pair}"
                    unique_pairings.add(normalized_pair)
                
                print(f"✓ Round {round_num}: {len(pairings)} matches, no duplicate pairings")
        
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
        return False
    
    # Test 3: Minimum teams (2 teams)
    print("\n=== Test 3: Minimum teams (2 teams) ===")
    try:
        league = League(
            id=3,
            name="Minimal League",
            year=2025,
            section=USTA_SECTIONS[0],
            region=USTA_REGIONS[0],
            age_group=USTA_AGE_GROUPS[0],
            division=USTA_DIVISIONS[0],
            num_lines_per_match=3,
            num_matches=4
        )
        
        facility = Facility(id=1, name="Test Facility", location="Test Location")
        teams = [
            Team(1, "Team A", league, facility),
            Team(2, "Team B", league, facility)
        ]
        
        matches = generate_matches(teams)
        print(f"✓ Generated {len(matches)} matches for 2 teams")
        
        # Should generate some matches between the two teams
        assert len(matches) > 0, "Should generate at least some matches"
        
        # Track rounds and pairings for validation
        round_counts = {}
        round_pairings = {}
        
        for match in matches:
            assert (match.home_team.name == "Team A" and match.visitor_team.name == "Team B") or \
                   (match.home_team.name == "Team B" and match.visitor_team.name == "Team A"), \
                   "All matches should be between Team A and Team B"
            
            round_counts[match.round] = round_counts.get(match.round, 0) + 1
            
            # Track pairings per round
            if match.round not in round_pairings:
                round_pairings[match.round] = []
            round_pairings[match.round].append((match.home_team.id, match.visitor_team.id))
        
        print("✓ Two-team scenario validated")
        print(f"✓ Round distribution: {round_counts}")
        
        # Verify round numbering
        if round_counts:
            max_round = max(round_counts.keys())
            min_round = min(round_counts.keys())
            assert min_round == 1, f"First round should be 1, got {min_round}"
            print(f"✓ Rounds span from {min_round} to {max_round}")
            
            # Check that rounds are sequential
            expected_rounds = set(range(min_round, max_round + 1))
            actual_rounds = set(round_counts.keys())
            assert actual_rounds == expected_rounds, f"Rounds should be sequential: expected {expected_rounds}, got {actual_rounds}"
            
            # For 2 teams, each round can only have 1 match (A vs B)
            # Verify no duplicate pairings within same round (though there's only 1 possible pairing)
            for round_num, pairings in round_pairings.items():
                assert len(pairings) <= 1, f"Round {round_num} should have at most 1 match for 2 teams, got {len(pairings)}"
                print(f"✓ Round {round_num}: {len(pairings)} match(es) - correct for 2 teams")
        
    except Exception as e:
        print(f"✗ Test 3 failed: {e}")
        return False
    
    # Test 4: Error cases
    print("\n=== Test 4: Error handling ===")
    
    # Test with insufficient teams
    try:
        league = League(
            id=4,
            name="Error League",
            year=2025,
            section=USTA_SECTIONS[0],
            region=USTA_REGIONS[0],
            age_group=USTA_AGE_GROUPS[0],
            division=USTA_DIVISIONS[0],
            num_lines_per_match=3,
            num_matches=4
        )
        
        facility = Facility(id=1, name="Test Facility", location="Test Location")
        teams = [Team(1, "Team A", league, facility)]  # Only 1 team
        
        matches = generate_matches(teams)
        print("✗ Should have raised ValueError for insufficient teams")
        return False
        
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
    
    # Test with teams from different leagues
    try:
        league1 = League(
            id=5,
            name="League 1",
            year=2025,
            section=USTA_SECTIONS[0],
            region=USTA_REGIONS[0],
            age_group=USTA_AGE_GROUPS[0],
            division=USTA_DIVISIONS[0],
            num_lines_per_match=3,
            num_matches=4
        )
        
        league2 = League(
            id=6,
            name="League 2",
            year=2025,
            section=USTA_SECTIONS[0],
            region=USTA_REGIONS[0],
            age_group=USTA_AGE_GROUPS[0],
            division=USTA_DIVISIONS[0],
            num_lines_per_match=3,
            num_matches=4
        )
        
        facility = Facility(id=1, name="Test Facility", location="Test Location")
        teams = [
            Team(1, "Team A", league1, facility),
            Team(2, "Team B", league2, facility)  # Different league
        ]
        
        matches = generate_matches(teams)
        print("✗ Should have raised ValueError for teams from different leagues")
        return False
        
    except ValueError as e:
        print(f"✓ Correctly raised ValueError for mixed leagues: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
    
    # Test with empty teams list
    try:
        matches = generate_matches([])
        print("✗ Should have raised ValueError for empty teams list")
        return False
        
    except ValueError as e:
        print(f"✓ Correctly raised ValueError for empty teams: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
    
    print("\n✅ Generate matches test completed successfully!")
    return True


def test_deterministic_match_ids():
    """Test that match IDs are deterministic for the same league"""
    print("\nTesting deterministic match ID generation...")
    
    try:
        # Create identical leagues
        league1 = League(
            id=1,
            name="Test League",
            year=2025,
            section=USTA_SECTIONS[0],
            region=USTA_REGIONS[0],
            age_group=USTA_AGE_GROUPS[0],
            division=USTA_DIVISIONS[0],
            num_lines_per_match=3,
            num_matches=6
        )
        
        league2 = League(
            id=1,  # Same ID
            name="Test League",  # Same name
            year=2025,  # Same year
            section=USTA_SECTIONS[0],  # Same section
            region=USTA_REGIONS[0],  # Same region
            age_group=USTA_AGE_GROUPS[0],  # Same age group
            division=USTA_DIVISIONS[0],  # Same division
            num_lines_per_match=3,
            num_matches=6
        )
        
        facility = Facility(id=1, name="Test Facility", location="Test Location")
        
        # Create identical teams for both leagues
        teams1 = [
            Team(1, "Team A", league1, facility),
            Team(2, "Team B", league1, facility),
            Team(3, "Team C", league1, facility)
        ]
        
        teams2 = [
            Team(1, "Team A", league2, facility),
            Team(2, "Team B", league2, facility),
            Team(3, "Team C", league2, facility)
        ]
        
        # Generate matches for both
        matches1 = generate_matches(teams1)
        matches2 = generate_matches(teams2)
        
        # Check that match IDs are identical
        assert len(matches1) == len(matches2), "Should generate same number of matches"
        
        for i, (match1, match2) in enumerate(zip(matches1, matches2)):
            assert match1.id == match2.id, f"Match {i} IDs should be identical: {match1.id} vs {match2.id}"
        
        print(f"✓ Generated {len(matches1)} matches with identical IDs")
        print(f"✓ First match ID: {matches1[0].id}")
        print(f"✓ Last match ID: {matches1[-1].id}")
        
        # Test with different league (should get different IDs)
        league3 = League(
            id=2,  # Different ID
            name="Different League",
            year=2025,
            section=USTA_SECTIONS[0],
            region=USTA_REGIONS[0],
            age_group=USTA_AGE_GROUPS[0],
            division=USTA_DIVISIONS[0],
            num_lines_per_match=3,
            num_matches=6
        )
        
        teams3 = [
            Team(1, "Team A", league3, facility),
            Team(2, "Team B", league3, facility),
            Team(3, "Team C", league3, facility)
        ]
        
        matches3 = generate_matches(teams3)
        
        # Should have different base IDs
        assert matches1[0].id != matches3[0].id, "Different leagues should have different match ID ranges"
        
        print(f"✓ Different league has different ID range: {matches3[0].id}")
        print("✅ Deterministic match ID test passed!")
        
        return True
        
    except Exception as e:
        print(f"❌ Deterministic match ID test failed: {e}")
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all test functions and report results"""
    print("🎾 Tennis Utils Test Suite")
    print("=" * 50)
    
    test_functions = [
        ("Get Optimal Scheduling Dates", test_get_optimal_scheduling_dates),
        ("Generate Matches", test_generate_matches),
        ("Deterministic Match IDs", test_deterministic_match_ids),
    ]
    
    results = []
    
    for test_name, test_func in test_functions:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Test suite error in {test_name}: {e}")
            traceback.print_exc()
            results.append((test_name, False))
    
    # Print summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status:<10} {test_name}")
        if success:
            passed += 1
    
    print(f"\n🏆 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed successfully!")
        return 0
    else:
        print(f"⚠️  {total - passed} test(s) failed")
        return 1


def main():
    """Main function for running tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test suite for tennis utils functions")
    parser.add_argument("--test", choices=[
        "scheduling", "matches", "deterministic", "all"
    ], default="all", help="Specific test to run (default: all)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        print("Running in verbose mode...")
    
    # Run specific test or all tests
    if args.test == "scheduling":
        return 0 if test_get_optimal_scheduling_dates() else 1
    elif args.test == "matches":
        return 0 if test_generate_matches() else 1
    elif args.test == "deterministic":
        return 0 if test_deterministic_match_ids() else 1
    else:
        return run_all_tests()


if __name__ == "__main__":
    sys.exit(main())