#!/usr/bin/env python3
"""
Tennis Database Population Script

This script populates a tennis database by loading data from YAML files
in the correct dependency order: facilities → leagues → teams → matches

Usage:
    python populate_tennis_db.py [database_path]

If no database path is provided, defaults to 'tennis.db'
"""

import subprocess
import sys
import os
from pathlib import Path
from typing import List, Optional


def run_command(command: List[str]) -> bool:
    """
    Run a command and return True if successful, False otherwise
    
    Args:
        command: List of command parts (e.g., ['python', 'script.py', 'arg'])
        
    Returns:
        bool: True if command succeeded, False otherwise
    """
    try:
        print(f"Running: {' '.join(command)}")
        result = subprocess.run(
            command, 
            check=True, 
            capture_output=True, 
            text=True
        )
        print(f"✅ Success: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        print(f"❌ Error: Command not found: {command[0]}")
        return False


def check_file_exists(file_path: str) -> bool:
    """
    Check if a file exists and print status
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        bool: True if file exists, False otherwise
    """
    if os.path.exists(file_path):
        print(f"✅ Found: {file_path}")
        return True
    else:
        print(f"❌ Missing: {file_path}")
        return False


def initialize_database(db_path: str) -> bool:
    """
    Initialize the database schema
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        bool: True if initialization succeeded, False otherwise
    """
    print(f"\n🔧 Initializing database schema...")
    
    command = [
        sys.executable,  # Use the same Python interpreter
        "tennis_cli.py",
        "--backend", "sqlite",
        "--db-path", db_path,
        "init"
    ]
    
    return run_command(command)


def load_data_files(db_path: str) -> bool:
    """
    Load all data files into the database in the correct order
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        bool: True if all files loaded successfully, False otherwise
    """
    # Define the loading order and file mappings
    load_order = [
        ("facilities", "facilities.yaml"),
        ("leagues", "leagues.yaml"), 
        ("teams", "teams.yaml"),
        ("matches", "matches.yaml")
    ]
    
    print("\n" + "="*60)
    print("TENNIS DATABASE POPULATION")
    print("="*60)
    
    # Check if all required files exist
    print("\n📋 Checking for required YAML files...")
    missing_files = []
    for table_name, file_name in load_order:
        if not check_file_exists(file_name):
            missing_files.append(file_name)
    
    if missing_files:
        print(f"\n❌ Cannot proceed. Missing files: {', '.join(missing_files)}")
        print("\nPlease create the missing YAML files before running this script.")
        return False
    
    # Check if tennis_cli.py exists
    if not check_file_exists("tennis_cli.py"):
        print("\n❌ Cannot proceed. Missing tennis_cli.py")
        return False
    
    # Initialize database schema
    if not initialize_database(db_path):
        print("\n💥 Failed to initialize database. Stopping here.")
        return False
    
    print(f"\n🎾 Loading data into database: {db_path}")
    print("Loading order: facilities → leagues → teams → matches")
    print("-" * 60)
    
    # Load each file in order
    success_count = 0
    for table_name, file_name in load_order:
        print(f"\n📥 Loading {table_name} from {file_name}...")
        
        command = [
            sys.executable,  # Use the same Python interpreter
            "tennis_cli.py",
            "--backend", "sqlite",
            "--db-path", db_path,
            "load",
            table_name,
            "--file", file_name
        ]
        
        if run_command(command):
            success_count += 1
        else:
            print(f"\n💥 Failed to load {table_name}. Stopping here.")
            break
    
    # Summary
    print("\n" + "="*60)
    if success_count == len(load_order):
        print("🎉 SUCCESS: All data loaded successfully!")
        print(f"   Database: {db_path}")
        print(f"   Tables loaded: {success_count}/{len(load_order)}")
        
        # Show quick stats
        print("\n📊 Quick verification...")
        stats_commands = [
            (["python", "tennis_cli.py", "--backend", "sqlite", "--db-path", db_path, "list", "facilities"], "facilities"),
            (["python", "tennis_cli.py", "--backend", "sqlite", "--db-path", db_path, "list", "leagues"], "leagues"), 
            (["python", "tennis_cli.py", "--backend", "sqlite", "--db-path", db_path, "list", "teams"], "teams"),
            (["python", "tennis_cli.py", "--backend", "sqlite", "--db-path", db_path, "list", "matches"], "matches")
        ]
        
        for command, entity_type in stats_commands:
            try:
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                import json
                data = json.loads(result.stdout)
                count = len(data) if isinstance(data, list) else 0
                print(f"   {entity_type.capitalize()}: {count} loaded")
            except:
                print(f"   {entity_type.capitalize()}: Unable to verify")
        
        return True
    else:
        print("❌ FAILURE: Not all data was loaded successfully")
        print(f"   Tables loaded: {success_count}/{len(load_order)}")
        return False


def test_database_connection(db_path: str) -> bool:
    """
    Test the database connection
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        bool: True if connection test succeeded, False otherwise
    """
    print(f"\n🔍 Testing database connection...")
    
    command = [
        sys.executable,
        "tennis_cli.py",
        "--backend", "sqlite",
        "--db-path", db_path,
        "health"
    ]
    
    return run_command(command)


def create_sample_files():
    """Create sample YAML files if they don't exist"""
    
    print("\n🔧 Creating sample YAML files...")
    
    # Sample facilities.yaml
    facilities_yaml = '''facilities:
  - id: 1
    name: "Tennis Center North"
    location: "123 Tennis Dr, Albuquerque, NM 87110"
    total_courts: 12
    schedule:
      Monday:
        start_times:
          - time: "18:00"
            available_courts: 12
      Tuesday:
        start_times:
          - time: "18:00"
            available_courts: 12
      Wednesday:
        start_times:
          - time: "18:00"
            available_courts: 12
      Thursday:
        start_times:
          - time: "18:00"
            available_courts: 12
      Friday:
        start_times: []
      Saturday:
        start_times:
          - time: "10:00"
            available_courts: 8
          - time: "14:00"
            available_courts: 12
      Sunday:
        start_times:
          - time: "10:00"
            available_courts: 8
          - time: "14:00"
            available_courts: 12
    unavailable_dates:
      - "2025-07-04"
      - "2025-12-25"

  - id: 2
    name: "Westside Racquet Club"
    location: "456 Court Ave, Rio Rancho, NM 87124"
    total_courts: 6
    schedule:
      Monday:
        start_times:
          - time: "18:00"
            available_courts: 6
      Tuesday:
        start_times:
          - time: "18:00"
            available_courts: 6
      Wednesday:
        start_times:
          - time: "18:00"
            available_courts: 6
      Thursday:
        start_times:
          - time: "18:00"
            available_courts: 6
      Friday:
        start_times: []
      Saturday:
        start_times:
          - time: "09:00"
            available_courts: 4
          - time: "13:00"
            available_courts: 6
      Sunday:
        start_times:
          - time: "13:00"
            available_courts: 6
    unavailable_dates:
      - "2025-08-20"
      - "2025-08-21"
'''
    
    # Sample leagues.yaml
    leagues_yaml = '''leagues:
  - id: 101
    name: "2025 Adult 18+ 3.0 Women"
    year: 2025
    section: "Southwest"
    region: "Northern New Mexico"
    age_group: "18 & Over"
    division: "3.0 Women"
    num_lines_per_match: 3
    num_matches: 10
    allow_split_lines: false
    preferred_days: ["Saturday", "Sunday"]
    backup_days: []
    start_date: "2025-03-01"
    end_date: "2025-06-30"

  - id: 102
    name: "2025 Adult 18+ 3.5 Women"
    year: 2025
    section: "Southwest"
    region: "Northern New Mexico"
    age_group: "18 & Over"
    division: "3.5 Women"
    num_lines_per_match: 3
    num_matches: 10
    allow_split_lines: false
    preferred_days: ["Saturday", "Sunday"]
    backup_days: []
    start_date: "2025-03-01"
    end_date: "2025-06-30"
'''
    
    # Sample teams.yaml
    teams_yaml = '''teams:
  - id: 1001
    name: "Smith - Tennis Center North"
    league_id: 101
    home_facility_id: 1
    captain: "Jane Smith"
    preferred_days: ["Saturday", "Sunday"]

  - id: 1002
    name: "Johnson - Westside Club"
    league_id: 101
    home_facility_id: 2
    captain: "Mary Johnson"
    preferred_days: ["Saturday", "Sunday"]

  - id: 1003
    name: "Williams - Tennis Center North"
    league_id: 102
    home_facility_id: 1
    captain: "Sarah Williams"
    preferred_days: ["Saturday", "Sunday"]

  - id: 1004
    name: "Brown - Westside Club"
    league_id: 102
    home_facility_id: 2
    captain: "Lisa Brown"
    preferred_days: ["Saturday", "Sunday"]
'''
    
    # Sample matches.yaml (empty since we'll generate matches)
    matches_yaml = '''matches: []
'''
    
    files_to_create = [
        ("facilities.yaml", facilities_yaml),
        ("leagues.yaml", leagues_yaml),
        ("teams.yaml", teams_yaml),
        ("matches.yaml", matches_yaml)
    ]
    
    created_files = []
    for filename, content in files_to_create:
        if not os.path.exists(filename):
            try:
                with open(filename, 'w') as f:
                    f.write(content)
                print(f"✅ Created: {filename}")
                created_files.append(filename)
            except IOError as e:
                print(f"❌ Failed to create {filename}: {e}")
        else:
            print(f"⏭️  Skipped: {filename} (already exists)")
    
    if created_files:
        print(f"\n📝 Created {len(created_files)} sample files. You can now run the population script!")
    
    return len(created_files) > 0


def generate_matches_for_leagues(db_path: str) -> bool:
    """
    Generate matches for all leagues in the database
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        bool: True if matches were generated successfully, False otherwise
    """
    print(f"\n🎲 Generating matches for leagues...")
    
    # First, get list of leagues
    try:
        command = [
            sys.executable,
            "tennis_cli.py",
            "--backend", "sqlite", 
            "--db-path", db_path,
            "list", "leagues"
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        import json
        leagues = json.loads(result.stdout)
        
        if not leagues:
            print("📝 No leagues found. Skipping match generation.")
            return True
        
        # Generate matches for each league
        for league in leagues:
            league_id = league['id']
            league_name = league['name']
            
            print(f"\n🏓 Generating matches for league: {league_name} (ID: {league_id})")
            
            command = [
                sys.executable,
                "tennis_cli.py",
                "--backend", "sqlite",
                "--db-path", db_path,
                "create", "matches",
                "--league-id", str(league_id)
            ]
            
            if not run_command(command):
                print(f"❌ Failed to generate matches for league {league_id}")
                return False
        
        print(f"\n✅ Successfully generated matches for all leagues!")
        return True
        
    except Exception as e:
        print(f"❌ Error generating matches: {e}")
        return False


def main():
    """Main function"""
    
    # Parse command line arguments
    if len(sys.argv) > 2:
        print("Usage: python populate_tennis_db.py [database_path]")
        sys.exit(1)
    
    db_path = sys.argv[1] if len(sys.argv) == 2 else "tennis.db"
    
    print("🎾 Tennis Database Population Script")
    print(f"Target database: {db_path}")
    
    # Check if required YAML files exist
    required_files = ["facilities.yaml", "leagues.yaml", "teams.yaml", "matches.yaml"]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"\n❌ Missing required files: {', '.join(missing_files)}")
        
        response = input("\n🤔 Would you like me to create sample YAML files? (y/n): ")
        if response.lower().startswith('y'):
            if create_sample_files():
                print("\n🎯 Sample files created! You may want to edit them before loading.")
                response = input("Continue with loading sample data? (y/n): ")
                if not response.lower().startswith('y'):
                    print("👋 Exiting. Edit the YAML files as needed, then run this script again.")
                    sys.exit(0)
            else:
                print("❌ Failed to create sample files. Exiting.")
                sys.exit(1)
        else:
            print("👋 Exiting. Please create the required YAML files and run this script again.")
            sys.exit(1)
    
    # Test database connection first
    if not test_database_connection(db_path):
        print("\n❌ Database connection test failed. Please check your setup.")
        sys.exit(1)
    
    # Load the data
    success = load_data_files(db_path)
    
    if success:
        # Generate matches for the leagues
        if generate_matches_for_leagues(db_path):
            print(f"\n🎉 Database population completed successfully!")
        else:
            print(f"\n⚠️  Data loaded but match generation failed.")
        
        print(f"\n🚀 Next steps:")
        print(f"   1. View your data: python tennis_cli.py --db-path {db_path} list <table>")
        print(f"   2. Check league stats: python tennis_cli.py --db-path {db_path} stats league --league-id <id>")
        print(f"   3. Schedule matches: python tennis_cli.py --db-path {db_path} schedule --match-id <id> --facility-id <id> --date YYYY-MM-DD --time HH:MM")
        print(f"   4. Start web app: python tennis_web_app.py")
        sys.exit(0)
    else:
        print(f"\n🔧 Troubleshooting:")
        print(f"   1. Check your YAML file formats")
        print(f"   2. Ensure all required fields are present")
        print(f"   3. Verify data dependencies (facilities → leagues → teams → matches)")
        print(f"   4. Test database: python tennis_cli.py --db-path {db_path} health")
        sys.exit(1)


if __name__ == "__main__":
    main()