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
    
    # Check if sqlite_tennis_db.py exists
    if not check_file_exists("sqlite_tennis_db.py"):
        print("\n❌ Cannot proceed. Missing sqlite_tennis_db.py")
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
            "sqlite_tennis_db.py",
            "--db", db_path,
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
            (["python", "sqlite_tennis_db.py", "--db", db_path, "list", "facilities"], "facilities"),
            (["python", "sqlite_tennis_db.py", "--db", db_path, "list", "leagues"], "leagues"), 
            (["python", "sqlite_tennis_db.py", "--db", db_path, "list", "teams"], "teams"),
            (["python", "sqlite_tennis_db.py", "--db", db_path, "list", "matches"], "matches")
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


def create_sample_files():
    """Create sample YAML files if they don't exist"""
    
    print("\n🔧 Creating sample YAML files...")
    
    # Sample facilities.yaml
    facilities_yaml = '''facilities:
  - id: 1
    name: "Tennis Center North"
    location: "123 Tennis Dr, Albuquerque, NM 87110"
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

  - id: 102
    name: "2025 Adult 18+ 3.5 Women"
    year: 2025
    section: "Southwest"
    region: "Northern New Mexico"
    age_group: "18 & Over"
    division: "3.5 Women"
    num_lines_per_match: 3
'''
    
    # Sample teams.yaml
    teams_yaml = '''teams:
  - id: 1001
    name: "Smith - Tennis Center North"
    league_id: 101
    home_facility_id: 1
    captain: "Jane Smith"

  - id: 1002
    name: "Johnson - Westside Club"
    league_id: 101
    home_facility_id: 2
    captain: "Mary Johnson"

  - id: 1003
    name: "Williams - Tennis Center North"
    league_id: 102
    home_facility_id: 1
    captain: "Sarah Williams"

  - id: 1004
    name: "Brown - Westside Club"
    league_id: 102
    home_facility_id: 2
    captain: "Lisa Brown"
'''
    
    # Sample matches.yaml
    matches_yaml = '''matches:
  - id: 2001
    league_id: 101
    home_team_id: 1001
    visitor_team_id: 1002
    facility_id: 1
    date: "2025-03-15"
    time: "10:00"

  - id: 2002
    league_id: 102
    home_team_id: 1003
    visitor_team_id: 1004
    facility_id: 2
    date: "2025-03-22"
    time: "10:00"
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
    
    # Load the data
    success = load_data_files(db_path)
    
    if success:
        print(f"\n🚀 Next steps:")
        print(f"   1. Start the web app: python tennis_web_app.py")
        print(f"   2. Connect to database: {db_path}")
        print(f"   3. Explore your data!")
        sys.exit(0)
    else:
        print(f"\n🔧 Troubleshooting:")
        print(f"   1. Check your YAML file formats")
        print(f"   2. Ensure all required fields are present")
        print(f"   3. Verify data dependencies (facilities → leagues → teams → matches)")
        sys.exit(1)


if __name__ == "__main__":
    main()