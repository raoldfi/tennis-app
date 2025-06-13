#!/usr/bin/env python3
"""
Test Suite for Utils Functions

This module contains all test functions for the utility functions in utils.py.
Tests cover match generation, optimal scheduling dates, and date set operations.
"""

import sys
import traceback
from typing import List

# Import the functions we want to test from utils
try:
    from utils import (
        generate_matches, 
        get_optimal_scheduling_dates,
        get_date_intersection,
        get_multiple_date_intersection,
        get_date_union,
        get_date_difference
    )
    from usta import League, Team, Facility, Match
    from usta_constants import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure utils.py and usta modules are in your Python path")
    sys.exit(1)


def test_date_intersection_functions():
    """Test all date intersection and set operation functions"""
    print("Testing date intersection and set operation functions...")
    
    try:
        # Test data
        dates1 = ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05"]
        dates2 = ["2025-01-03", "2025-01-04", "2025-01-05", "2025-01-06", "2025-01-07"]
        dates3 = ["2025-01-04", "2025-01-05", "2025-01-06", "2025-01-07", "2025-01-08"]
        
        print("\nTest data:")
        print(f"dates1: {dates1}")
        print(f"dates2: {dates2}")
        print(f"dates3: {dates3}")
        
        # Test intersection
        print("\n=== Testing get_date_intersection ===")
        intersection = get_date_intersection(dates1, dates2)
        print(f"Intersection of dates1 and dates2: {intersection}")
        assert intersection == ["2025-01-03", "2025-01-04", "2025-01-05"], f"Expected intersection failed: {intersection}"
        
        # Test intersection with preserve order
        intersection_reverse = get_date_intersection(dates2, dates1, preserve_order=True)
        print(f"Intersection (dates2 order): {intersection_reverse}")
        
        # Test multiple intersection
        print("\n=== Testing get_multiple_date_intersection ===")
        multi_intersection = get_multiple_date_intersection(dates1, dates2, dates3)
        print(f"Intersection of all three lists: {multi_intersection}")
        assert multi_intersection == ["2025-01-04", "2025-01-05"], f"Expected multi-intersection failed: {multi_intersection}"
        
        # Test union
        print("\n=== Testing get_date_union ===")
        union = get_date_union(dates1, dates2)
        print(f"Union of dates1 and dates2: {union}")
        expected_union = ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05", "2025-01-06", "2025-01-07"]
        assert union == expected_union, f"Expected union failed: {union}"
        
        # Test difference
        print("\n=== Testing get_date_difference ===")
        difference = get_date_difference(dates1, dates2)
        print(f"Dates in dates1 but not in dates2: {difference}")
        assert difference == ["2025-01-01", "2025-01-02"], f"Expected difference failed: {difference}"
        
        difference_reverse = get_date_difference(dates2, dates1)
        print(f"Dates in dates2 but not in dates1: {difference_reverse}")
        assert difference_reverse == ["2025-01-06", "2025-01-07"], f"Expected reverse difference failed: {difference_reverse}"
        
        # Test edge cases
        print("\n=== Testing edge cases ===")
        
        # Empty lists
        empty_intersection = get_date_intersection([], dates1)
        print(f"Intersection with empty list: {empty_intersection}")
        assert empty_intersection == [], "Empty intersection failed"
        
        # No intersection
        no_overlap1 = ["2025-01-01", "2025-01-02"]
        no_overlap2 = ["2025-01-03", "2025-01-04"]
        no_intersection = get_date_intersection(no_overlap1, no_overlap2)
        print(f"No intersection case: {no_intersection}")
        assert no_intersection == [], "No intersection case failed"
        
        # Identical lists
        identical_intersection = get_date_intersection(dates1, dates1)
        print(f"Identical lists intersection: {identical_intersection}")
        assert identical_intersection == dates1, "Identical lists intersection failed"
        
        # Test error handling
        print("\n=== Testing error handling ===")
        try:
            get_date_intersection("not a list", dates1)
            assert False, "Should have raised TypeError"
        except TypeError:
            print("✓ Correctly raised TypeError for invalid input type")
        
        try:
            get_date_intersection(["invalid-date"], dates1)
            assert False, "Should have raised ValueError"
        except ValueError:
            print("✓ Correctly raised ValueError for invalid date format")
        
        print("\n✅ All date intersection function tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Date intersection function tests failed: {e}")
        traceback.print_exc()
        return False


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
        
        # Create teams
        home_team = Team(
            id=1,
            name="Home Team",
            league=league,
            home_facility=facility,
            preferred_days=["Saturday"]
        )
        
        visitor_team = Team(
            id=2,
            name="Visitor Team",
            league=league,
            home_facility=facility,
            preferred_days=["Sunday"]
        )
        
        # Create match
        match = Match(
            id=1,
            league=league,
            home_team=home_team,
            visitor_team=visitor_team
        )
        
        # Test the function
        result = get_optimal_scheduling_dates(match, num_dates=10)
        
        print(f"✓ Function executed successfully")
        print(f"✓ Returned {len(result)} dates")
        if result:
            print(f"✓ First date: {result[0]}")
            print(f"✓ Last date: {result[-1]}")
        
        # Test with empty preferences
        league.preferred_days = []
        league.backup_days = []
        home_team.preferred_days = []
        visitor_team.preferred_days = []
        
        result2 = get_optimal_scheduling_dates(match, num_dates=5)
        print(f"✓ Test with empty preferences: {len(result2)} dates")
        
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
            num_matches=6
        )
        
        facility = Facility(id=1, name="Test Facility")
        
        teams = [
            Team(1, "Team A", league, facility),
            Team(2, "Team B", league, facility),
            Team(3, "Team C", league, facility),
            Team(4, "Team D", league, facility)
        ]
        
        matches = generate_matches(teams)
        
        print(f"✓ Generated {len(matches)} matches")
        print(f"✓ Expected approximately {6 * 4 // 2} matches")
        
        # Verify match properties
        for i, match in enumerate(matches[:3]):  # Show first 3 matches
            print(f"  Match {i+1}: {match.home_team.name} vs {match.visitor_team.name} (ID: {match.get_id()})")
        
        # Test home/away balance
        home_counts = {}
        away_counts = {}
        for match in matches:
            home_counts[match.home_team.id] = home_counts.get(match.home_team.id, 0) + 1
            away_counts[match.visitor_team.id] = away_counts.get(match.visitor_team.id, 0) + 1
        
        print(f"✓ Home game distribution: {home_counts}")
        print(f"✓ Away game distribution: {away_counts}")
        
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
        
        facility = Facility(id=1, name="Test Facility")
        
        teams = [
            Team(1, "Team A", league, facility),
            Team(2, "Team B", league, facility),
            Team(3, "Team C", league, facility),
            Team(4, "Team D", league, facility),
            Team(5, "Team E", league, facility)
        ]
        
        matches = generate_matches(teams)
        print(f"✓ Generated {len(matches)} matches for odd number of teams")
        
        # Verify each team gets roughly equal matches
        team_match_counts = {}
        for match in matches:
            team_match_counts[match.home_team.id] = team_match_counts.get(match.home_team.id, 0) + 1
            team_match_counts[match.visitor_team.id] = team_match_counts.get(match.visitor_team.id, 0) + 1
        
        print(f"✓ Team match distribution: {team_match_counts}")
        
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
        return False
    
    # Test 3: Error cases
    print("\n=== Test 3: Error handling ===")
    
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
        
        facility = Facility(id=1, name="Test Facility")
        teams = [Team(1, "Team A", league, facility)]  # Only 1 team
        
        matches = generate_matches(teams)
        print("✗ Should have raised ValueError for insufficient teams")
        return False
        
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
    
    print("\n✅ Generate matches test completed successfully!")
    return True


def test_date_intersection_with_scheduling():
    """Test date intersection functions in a realistic scheduling scenario"""
    print("\nTesting date intersection in scheduling context...")
    
    try:
        # Simulate finding common available dates for multiple teams/facilities
        team_a_preferred = ["2025-06-07", "2025-06-14", "2025-06-21", "2025-06-28"]  # Saturdays
        team_b_preferred = ["2025-06-08", "2025-06-15", "2025-06-22", "2025-06-29"]  # Sundays
        facility_available = ["2025-06-07", "2025-06-08", "2025-06-14", "2025-06-15", "2025-06-21", "2025-06-22"]
        
        print(f"Team A preferred dates (Saturdays): {team_a_preferred}")
        print(f"Team B preferred dates (Sundays): {team_b_preferred}")
        print(f"Facility available dates: {facility_available}")
        
        # Find dates that work for Team A and the facility
        team_a_options = get_date_intersection(team_a_preferred, facility_available)
        print(f"Team A + Facility options: {team_a_options}")
        
        # Find dates that work for Team B and the facility
        team_b_options = get_date_intersection(team_b_preferred, facility_available)
        print(f"Team B + Facility options: {team_b_options}")
        
        # Find dates that work for both teams and facility (if they were playing each other)
        all_team_options = get_multiple_date_intersection(team_a_preferred, team_b_preferred, facility_available)
        print(f"All teams + Facility options: {all_team_options}")
        
        # Find union of all possible dates
        all_possible = get_date_union(team_a_options, team_b_options)
        print(f"All possible scheduling dates: {all_possible}")
        
        # Simulate already booked dates
        already_booked = ["2025-06-07", "2025-06-15"]
        remaining_options = get_date_difference(all_possible, already_booked)
        print(f"Remaining options after bookings: {remaining_options}")
        
        print("✅ Scheduling scenario test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Scheduling scenario test failed: {e}")
        traceback.print_exc()
        return False


def test_edge_cases_and_performance():
    """Test edge cases and performance of date functions"""
    print("\nTesting edge cases and performance...")
    
    try:
        # Test with large date lists
        print("=== Testing with large date lists ===")
        import datetime
        
        # Generate 1000 dates
        start_date = datetime.date(2025, 1, 1)
        large_list1 = []
        large_list2 = []
        
        for i in range(1000):
            date1 = start_date + datetime.timedelta(days=i)
            date2 = start_date + datetime.timedelta(days=i + 500)  # Offset for partial overlap
            large_list1.append(date1.strftime('%Y-%m-%d'))
            large_list2.append(date2.strftime('%Y-%m-%d'))
        
        # Test intersection performance
        import time
        start_time = time.time()
        intersection = get_date_intersection(large_list1, large_list2)
        end_time = time.time()
        
        print(f"✓ Large list intersection: {len(intersection)} dates in {end_time - start_time:.4f} seconds")
        
        # Test with duplicate dates
        print("\n=== Testing with duplicate dates ===")
        dates_with_dupes1 = ["2025-01-01", "2025-01-02", "2025-01-01", "2025-01-03", "2025-01-02"]
        dates_with_dupes2 = ["2025-01-02", "2025-01-03", "2025-01-02", "2025-01-04"]
        
        intersection_dupes = get_date_intersection(dates_with_dupes1, dates_with_dupes2)
        print(f"✓ Intersection with duplicates: {intersection_dupes}")
        
        union_dupes = get_date_union(dates_with_dupes1, dates_with_dupes2, remove_duplicates=True)
        print(f"✓ Union with duplicates removed: {union_dupes}")
        
        union_keep_dupes = get_date_union(dates_with_dupes1, dates_with_dupes2, remove_duplicates=False)
        print(f"✓ Union keeping duplicates: {union_keep_dupes}")
        
        # Test with unsorted dates
        print("\n=== Testing with unsorted dates ===")
        unsorted1 = ["2025-01-03", "2025-01-01", "2025-01-05", "2025-01-02"]
        unsorted2 = ["2025-01-04", "2025-01-02", "2025-01-06", "2025-01-01"]
        
        sorted_intersection = get_date_intersection(unsorted1, unsorted2, sort_result=True)
        print(f"✓ Sorted intersection of unsorted lists: {sorted_intersection}")
        
        print("✅ Edge cases and performance tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Edge cases and performance tests failed: {e}")
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all test functions and report results"""
    print("🎾 Tennis Utils Test Suite")
    print("=" * 50)
    
    test_functions = [
        ("Date Intersection Functions", test_date_intersection_functions),
        ("Get Optimal Scheduling Dates", test_get_optimal_scheduling_dates),
        ("Generate Matches", test_generate_matches),
        ("Date Intersection with Scheduling", test_date_intersection_with_scheduling),
        ("Edge Cases and Performance", test_edge_cases_and_performance),
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
        "intersection", "scheduling", "matches", "scenario", "edge", "all"
    ], default="all", help="Specific test to run (default: all)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        print("Running in verbose mode...")
    
    # Run specific test or all tests
    if args.test == "intersection":
        return 0 if test_date_intersection_functions() else 1
    elif args.test == "scheduling":
        return 0 if test_get_optimal_scheduling_dates() else 1
    elif args.test == "matches":
        return 0 if test_generate_matches() else 1
    elif args.test == "scenario":
        return 0 if test_date_intersection_with_scheduling() else 1
    elif args.test == "edge":
        return 0 if test_edge_cases_and_performance() else 1
    else:
        return run_all_tests()


if __name__ == "__main__":
    sys.exit(main())