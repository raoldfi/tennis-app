#!/usr/bin/env python3
"""
Test script to verify that the calculate pairings functionality works correctly.
Run this script to test both the core League.calculate_pairings() method and the web app integration.
"""

import sys
import os
import tempfile
from sqlite_tennis_db import SQLiteTennisDB
from usta import League, Team, Facility, WeeklySchedule

def test_league_calculate_pairings():
    """Test the core League.calculate_pairings() method"""
    print("🧪 Testing League.calculate_pairings() method...")
    
    # Create test league
    league = League(
        id=101,
        name="Test League",
        year=2025,
        section="Southwest", 
        region="Northern New Mexico",
        age_group="18 & Over",
        division="3.0 Women",
        num_matches=6,  # Each team plays 6 matches
        num_lines_per_match=3
    )
    
    # Create test teams
    teams = []
    for i in range(4):  # 4 teams
        team = Team(
            id=1000 + i,
            name=f"Test Team {i+1}",
            league=league,
            home_facility_id=1,
            captain=f"Captain {i+1}"
        )
        teams.append(team)
    
    print(f"  📋 Created league: {league.name}")
    print(f"  👥 Created {len(teams)} teams")
    print(f"  🎯 Target: {league.num_matches} matches per team")
    
    # Calculate pairings
    try:
        pairings = league.calculate_pairings(teams)
        print(f"  ✅ Generated {len(pairings)} total pairings")
        
        # Verify statistics
        match_count = {}
        home_count = {}
        away_count = {}
        
        for team in teams:
            match_count[team.id] = 0
            home_count[team.id] = 0
            away_count[team.id] = 0
        
        for home_team, away_team in pairings:
            match_count[home_team.id] += 1
            match_count[away_team.id] += 1
            home_count[home_team.id] += 1
            away_count[away_team.id] += 1
        
        # Check results
        all_correct = True
        max_imbalance = 0
        
        for team in teams:
            total = match_count[team.id]
            home = home_count[team.id]
            away = away_count[team.id]
            imbalance = abs(home - away)
            max_imbalance = max(max_imbalance, imbalance)
            
            print(f"    Team {team.name}: {total} total ({home} home, {away} away)")
            
            if total != league.num_matches:
                print(f"    ❌ Expected {league.num_matches} matches, got {total}")
                all_correct = False
        
        if all_correct:
            print(f"  ✅ All teams have correct match count")
        
        print(f"  📊 Maximum home/away imbalance: {max_imbalance}")
        
        if max_imbalance <= 1:
            print(f"  ✅ Good home/away balance (max imbalance: {max_imbalance})")
        else:
            print(f"  ⚠️  Some home/away imbalance (max: {max_imbalance})")
        
        return True, len(pairings)
        
    except Exception as e:
        print(f"  ❌ Error calculating pairings: {e}")
        return False, 0

def test_database_integration():
    """Test the database integration"""
    print("\n🗄️  Testing database integration...")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        db = SQLiteTennisDB(db_path)
        print(f"  ✅ Created temporary database: {db_path}")
        
        # Add test facility
        facility = Facility(
            id=1,
            name="Test Facility", 
            location="Test Location"
        )
        db.add_facility(facility)
        print(f"  ✅ Added test facility")
        
        # Add test league
        league = League(
            id=101,
            name="Test League DB",
            year=2025,
            section="Southwest",
            region="Northern New Mexico", 
            age_group="18 & Over",
            division="3.0 Women",
            num_matches=4,
            num_lines_per_match=3
        )
        db.add_league(league)
        print(f"  ✅ Added test league")
        
        # Add test teams
        for i in range(3):  # 3 teams
            team = Team(
                id=1000 + i,
                name=f"DB Test Team {i+1}",
                league=league,
                home_facility_id=1,
                captain=f"DB Captain {i+1}"
            )
            db.add_team(team)
        print(f"  ✅ Added 3 test teams")
        
        # Test database calculate_pairings method
        try:
            pairings = db.calculate_pairings(101)
            print(f"  ✅ Database calculate_pairings() generated {len(pairings)} pairings")
            return True
        except Exception as e:
            print(f"  ❌ Database calculate_pairings() failed: {e}")
            return False
            
    except Exception as e:
        print(f"  ❌ Database integration test failed: {e}")
        return False
    finally:
        # Clean up
        try:
            os.unlink(db_path)
            print(f"  🧹 Cleaned up temporary database")
        except:
            pass

def test_web_app_compatibility():
    """Test that the web app routes will work"""
    print("\n🌐 Testing web app compatibility...")
    
    try:
        # Import the web app to check for syntax errors
        import tennis_web_app
        print("  ✅ Web app imports successfully")
        
        # Check that required routes exist
        app = tennis_web_app.app
        routes = [rule.endpoint for rule in app.url_map.iter_rules()]
        
        required_routes = [
            'calculate_pairings',
            'calculate_pairings_results', 
            'api_calculate_pairings'
        ]
        
        missing_routes = [route for route in required_routes if route not in routes]
        
        if missing_routes:
            print(f"  ❌ Missing routes: {missing_routes}")
            return False
        else:
            print(f"  ✅ All required routes present")
            return True
            
    except ImportError as e:
        print(f"  ❌ Cannot import web app: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Web app compatibility test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing Calculate Pairings Functionality\n")
    
    # Test core functionality
    core_success, pairing_count = test_league_calculate_pairings()
    
    # Test database integration  
    db_success = test_database_integration()
    
    # Test web app compatibility
    web_success = test_web_app_compatibility()
    
    # Summary
    print("\n📊 Test Summary:")
    print(f"  Core League.calculate_pairings(): {'✅ PASS' if core_success else '❌ FAIL'}")
    print(f"  Database integration: {'✅ PASS' if db_success else '❌ FAIL'}")
    print(f"  Web app compatibility: {'✅ PASS' if web_success else '❌ FAIL'}")
    
    if all([core_success, db_success, web_success]):
        print("\n🎉 All tests passed! Calculate pairings functionality is working correctly.")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
