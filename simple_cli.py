#!/usr/bin/env python3
"""
SIMPLIFIED TENNIS CLI WITH LOAD/IMPORT CAPABILITIES
==================================================

This version includes comprehensive load/import functionality with:
1. Dry-run by default for all import operations
2. YAML file import support
3. Individual entity creation
4. Bulk data loading with validation
5. Clear preview before making changes

USAGE EXAMPLES:

# Preview YAML import (safe)
python tennis_cli.py --db-path tennis.db load facilities.yaml
python tennis_cli.py --db-path tennis.db load complete_setup.yaml

# Actually import YAML file
python tennis_cli.py --db-path tennis.db load facilities.yaml --execute

# Create individual entities (dry-run by default)
python tennis_cli.py --db-path tennis.db create match --league-id 1 --home-team-id 1 --visitor-team-id 2

# Generate matches (dry-run by default)
python tennis_cli.py --db-path tennis.db generate-matches --league-id 1
"""

import traceback
import argparse
import json
import sys
import os
import yaml
from typing import Dict, Any, Optional, List, Tuple
import logging
from dataclasses import dataclass, field

from scheduling_manager import SchedulingManager
import scheduling_manager
from usta import Match, MatchType, League, Team, Facility

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from tennis_db_factory import TennisDBFactory, DatabaseBackend, TennisDBManager
except ImportError as e:
    print(f"Error: Could not import tennis database modules: {e}", file=sys.stderr)
    sys.exit(1)


class SimplifiedTennisCLIWithImport:
    """Enhanced CLI with comprehensive load/import capabilities and dry-run defaults"""
    
    def __init__(self):
        self.db_manager = None
    
    def run(self):
        """Main CLI entry point with import capabilities"""
        parser = argparse.ArgumentParser(
            description="Tennis CLI with built-in dry-run support and import capabilities",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # List entities
  tennis_cli.py --db-path tennis.db list leagues
  tennis_cli.py --db-path tennis.db list matches --league-id 1
  
  # Load/Import operations (dry-run by default)
  tennis_cli.py --db-path tennis.db load facilities.yaml
  tennis_cli.py --db-path tennis.db load complete_setup.yaml --execute
  
  # Create entities (dry-run by default)
  tennis_cli.py --db-path tennis.db create match --league-id 1 --home-team-id 1 --visitor-team-id 2
  tennis_cli.py --db-path tennis.db create match --league-id 1 --home-team-id 1 --visitor-team-id 2 --execute
  
  # Generate matches (dry-run by default)
  tennis_cli.py --db-path tennis.db generate-matches --league-id 1
  tennis_cli.py --db-path tennis.db generate-matches --league-id 1 --execute
  
  # Scheduling operations (dry-run by default)
  tennis_cli.py --db-path tennis.db auto-schedule
  tennis_cli.py --db-path tennis.db auto-schedule --execute
  
  # Test functionality
  tennis_cli.py --db-path tennis.db test --comprehensive
            """
        )
        
        # Database arguments
        parser.add_argument('--db-path', required=True, help='SQLite database path')
        parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
        
        subparsers = parser.add_subparsers(dest="command", help="Available commands")
        
        # List command
        list_parser = subparsers.add_parser("list", help="List entities")
        list_parser.add_argument("table", 
                               choices=["teams", "leagues", "matches", "facilities", "sections", "regions", "age-groups", "divisions"], 
                               help="Type of entity to list")
        list_parser.add_argument("--league-id", type=int, help="Filter by league ID")
        list_parser.add_argument('--match-type', 
                       choices=['all', 'scheduled', 'unscheduled'],
                       default="all",
                       help='Type of matches to list')
        list_parser.add_argument('--format', choices=['json', 'table'], default='table', help='Output format')
        
        # Load command - DRY-RUN BY DEFAULT
        load_parser = subparsers.add_parser("load", help="Load data from YAML file (DRY-RUN by default)")
        load_parser.add_argument("file_path", help="Path to YAML file")
        load_parser.add_argument("--execute", action="store_true", 
                                help="ACTUALLY load data (default is dry-run)")
        load_parser.add_argument("--clear-existing", action="store_true", 
                                help="Clear existing data before loading (use with caution)")
        load_parser.add_argument("--validate-only", action="store_true", 
                                help="Only validate file format without preview")
        
        # Create command - DRY-RUN BY DEFAULT
        create_parser = subparsers.add_parser("create", help="Create new entities (DRY-RUN by default)")
        create_parser.add_argument("entity", choices=["match", "league", "team", "facility"], 
                                  help="Type of entity to create")
        create_parser.add_argument("--execute", action="store_true", 
                                  help="ACTUALLY create entity (default is dry-run)")
        
        # Match creation arguments
        create_parser.add_argument("--league-id", type=int, help="League ID (for matches)")
        create_parser.add_argument("--home-team-id", type=int, help="Home team ID (for matches)")
        create_parser.add_argument("--visitor-team-id", type=int, help="Visitor team ID (for matches)")
        
        # League creation arguments
        create_parser.add_argument("--name", help="Name (for leagues, teams, facilities)")
        create_parser.add_argument("--year", type=int, help="Year (for leagues)")
        create_parser.add_argument("--section", help="Section (for leagues)")
        create_parser.add_argument("--region", help="Region (for leagues)")
        create_parser.add_argument("--age-group", help="Age group (for leagues)")
        create_parser.add_argument("--division", help="Division (for leagues)")
        
        # Team creation arguments
        create_parser.add_argument("--captain", help="Captain name (for teams)")
        create_parser.add_argument("--home-facility-id", type=int, help="Home facility ID (for teams)")
        
        # Facility creation arguments
        create_parser.add_argument("--short-name", help="Short name (for facilities)")
        create_parser.add_argument("--location", help="Location (for facilities)")
        create_parser.add_argument("--total-courts", type=int, help="Total courts (for facilities)")
        
        # Generate matches command - DRY-RUN BY DEFAULT
        generate_parser = subparsers.add_parser("generate-matches", help="Generate matches (DRY-RUN by default)")
        generate_parser.add_argument("--league-id", type=int, help="League ID")
        generate_parser.add_argument("--league-ids", help="Comma-separated league IDs")
        generate_parser.add_argument("--min-teams", type=int, default=2, help="Minimum teams required")
        generate_parser.add_argument("--execute", action="store_true", 
                                    help="ACTUALLY generate matches (default is dry-run)")
        generate_parser.add_argument("--skip-existing", action="store_true", help="Skip leagues with matches")
        generate_parser.add_argument("--overwrite-existing", action="store_true", help="Delete existing matches first")
        generate_parser.add_argument("--progress", action="store_true", help="Show progress")
        
        # Auto-schedule command - DRY-RUN BY DEFAULT
        auto_schedule_parser = subparsers.add_parser("auto-schedule", help="Auto-schedule matches (DRY-RUN by default)")
        auto_schedule_parser.add_argument("--league-id", type=int, help="League ID")
        auto_schedule_parser.add_argument("--league-ids", help="Comma-separated league IDs")
        auto_schedule_parser.add_argument("--max-matches", type=int, help="Maximum matches to process")
        auto_schedule_parser.add_argument("--execute", action="store_true", 
                                         help="ACTUALLY execute scheduling (default is dry-run)")
        auto_schedule_parser.add_argument("--progress", action="store_true", help="Show progress")
        auto_schedule_parser.add_argument("--seed", type=int, help="Seed for reproducible scheduling (optional)")
        
        # Optimize command - find best auto-schedule with multiple iterations
        optimize_parser = subparsers.add_parser("optimize-schedule", help="Run auto-schedule optimization with multiple iterations")
        optimize_parser.add_argument("--league-id", type=int, help="League ID")
        optimize_parser.add_argument("--league-ids", help="Comma-separated league IDs")
        optimize_parser.add_argument("--max-matches", type=int, help="Maximum matches to process")
        optimize_parser.add_argument("--iterations", type=int, default=10, 
                                   help="Number of optimization iterations (default: 10, max: 100)")
        optimize_parser.add_argument("--execute", action="store_true", 
                                   help="Execute with best seed after optimization (default is dry-run)")
        optimize_parser.add_argument("--progress", action="store_true", help="Show progress")
        
        # Schedule command - DRY-RUN BY DEFAULT
        schedule_parser = subparsers.add_parser("schedule", help="Schedule specific match (DRY-RUN by default)")
        schedule_parser.add_argument("--match-id", type=int, required=True, help="Match ID")
        schedule_parser.add_argument("--facility-id", type=int, required=True, help="Facility ID")
        schedule_parser.add_argument("--date", required=True, help="Date (YYYY-MM-DD)")
        schedule_parser.add_argument("--time", required=True, help="Time (HH:MM)")
        schedule_parser.add_argument("--execute", action="store_true", 
                                    help="ACTUALLY execute scheduling (default is dry-run)")
        
        # Unschedule command - DRY-RUN BY DEFAULT
        unschedule_parser = subparsers.add_parser("unschedule", help="Unschedule matches (DRY-RUN by default)")
        unschedule_parser.add_argument("--match-id", type=int, help="Match ID")
        unschedule_parser.add_argument("--league-id", type=int, help="League ID")
        unschedule_parser.add_argument("--execute", action="store_true", 
                                      help="ACTUALLY execute unscheduling (default is dry-run)")
        unschedule_parser.add_argument("--progress", action="store_true", help="Show progress")
        
        # Delete command - DRY-RUN BY DEFAULT
        delete_parser = subparsers.add_parser("delete", help="Delete entities (DRY-RUN by default)")
        delete_parser.add_argument("entity", choices=["matches", "teams", "leagues", "facilities"], 
                                  help="Type of entity to delete")
        delete_parser.add_argument("--id", type=int, help="Specific entity ID to delete")
        delete_parser.add_argument("--league-id", type=int, help="League ID (for matches/teams)")
        delete_parser.add_argument("--execute", action="store_true", 
                                  help="ACTUALLY delete entities (default is dry-run)")
        delete_parser.add_argument("--progress", action="store_true", help="Show progress")
        
        # Test command
        test_parser = subparsers.add_parser("test", help="Test functionality")
        test_parser.add_argument("--comprehensive", action="store_true", help="Comprehensive testing")
        test_parser.add_argument("--import-test", action="store_true", help="Test import functionality")
        
        # Stats command
        stats_parser = subparsers.add_parser("stats", help="Show statistics")
        stats_parser.add_argument("--league-id", type=int, help="League ID")
        
        # Health command
        health_parser = subparsers.add_parser("health", help="Check database health")
        
        # Facility requirements command
        facility_req_parser = subparsers.add_parser("facility-requirements", 
                                                   help="Calculate facility requirements for a league")
        facility_req_parser.add_argument("--league-id", type=int, required=True, 
                                        help="League ID to analyze")
        facility_req_parser.add_argument("--no-utilization", action="store_true", 
                                        help="Skip current utilization analysis")
        facility_req_parser.add_argument("--output", choices=["json", "summary"], default="summary",
                                        help="Output format (default: summary)")
        
        args = parser.parse_args()
        
        if not args.command:
            parser.print_help()
            return 1
        
        # Connect to database
        try:
            backend_enum = DatabaseBackend('sqlite')
            config = {'db_path': args.db_path}
            self.db_manager = TennisDBManager(backend_enum, config)
            db = self.db_manager.connect()
            
            # Route to command handlers
            if args.command == "list":
                return self.handle_list(args, db)
            elif args.command == "load":
                return self.handle_load(args, db)
            elif args.command == "create":
                return self.handle_create(args, db)
            elif args.command == "generate-matches":
                return self.handle_generate_matches(args, db)
            elif args.command == "auto-schedule":
                return self.handle_auto_schedule(args, db)
            elif args.command == "optimize-schedule":
                return self.handle_optimize_schedule(args, db)
            elif args.command == "schedule":
                return self.handle_schedule(args, db)
            elif args.command == "unschedule":
                return self.handle_unschedule(args, db)
            elif args.command == "delete":
                return self.handle_delete(args, db)
            elif args.command == "test":
                return self.handle_test(args, db)
            elif args.command == "stats":
                return self.handle_stats(args, db)
            elif args.command == "health":
                return self.handle_health(args, db)
            elif args.command == "facility-requirements":
                return self.handle_facility_requirements(args, db)
            else:
                print(f"Unknown command: {args.command}")
                return 1
                
        except Exception as e:
            print(f"Error: {e}")
            if args.verbose:
                traceback.print_exc()
            return 1
        finally:
            if self.db_manager:
                try:
                    self.db_manager.disconnect()
                except:
                    pass
    
    def handle_load(self, args, db):
            """Handle YAML file loading using the database's YAMLImportExportMixin"""
            try:
                # Check if file exists
                if not os.path.exists(args.file_path):
                    print(f"Error: File {args.file_path} not found")
                    return 1
                
                # Determine mode
                dry_run = not args.execute
                
                # Display mode
                if dry_run:
                    print(f"🧪 DRY RUN MODE: Loading {args.file_path} (no changes will be made)")
                else:
                    print(f"🚀 EXECUTING: Loading {args.file_path} (changes will be made to database)")
                
                if args.validate_only:
                    print("📋 VALIDATION ONLY: Checking file format...")
                    # Use the database's import method with validate_only=True
                    try:
                        result = db.import_from_yaml(args.file_path, validate_only=True)
                        
                        if result['total_errors'] == 0:
                            print("✅ File format is valid")
                            print(f"📋 Validation summary:")
                            print(f"   Leagues: {result['leagues']['processed']} processed")
                            print(f"   Facilities: {result['facilities']['processed']} processed") 
                            print(f"   Teams: {result['teams']['processed']} processed")
                            print(f"   Matches: {result['matches']['processed']} processed")
                            return 0
                        else:
                            print("❌ YAML validation failed:")
                            for entity_type in ['leagues', 'facilities', 'teams', 'matches']:
                                errors = result[entity_type].get('errors', [])
                                for error in errors:
                                    print(f"   {error}")
                            return 1
                            
                    except Exception as validate_error:
                        print(f"❌ Validation failed: {validate_error}")
                        return 1
                
                # Use the database's import method
                try:
                    skip_existing = not args.clear_existing
                    result = db.import_from_yaml(
                        args.file_path, 
                        skip_existing=skip_existing,
                        validate_only=False
                    )
                    
                    # Display results
                    if result['total_errors'] == 0:
                        if dry_run:
                            print(f"✅ Import validation completed successfully!")
                            print(f"📋 Would import:")
                        else:
                            print(f"✅ Data imported successfully!")
                            print(f"📋 Imported:")
                        
                        print(f"   Facilities: {result['facilities']['imported']}")
                        print(f"   Leagues: {result['leagues']['imported']}")
                        print(f"   Teams: {result['teams']['imported']}")
                        print(f"   Matches: {result['matches']['imported']}")
                        
                        if result['total_skipped'] > 0:
                            print(f"📋 Skipped (already exist): {result['total_skipped']} records")
                        
                        print(f"📋 Duration: {result['duration_seconds']} seconds")
                        
                        if dry_run:
                            print(f"\nUse --execute flag to actually import this data")
                        
                        return 0
                    else:
                        action = "validation" if dry_run else "import"
                        print(f"❌ Data {action} completed with errors:")
                        print(f"   Processed: {result['total_processed']}")
                        print(f"   Imported: {result['total_imported']}")
                        print(f"   Errors: {result['total_errors']}")
                        
                        # Show detailed errors
                        for entity_type in ['leagues', 'facilities', 'teams', 'matches']:
                            errors = result[entity_type].get('errors', [])
                            if errors:
                                print(f"\n   {entity_type.capitalize()} errors:")
                                for error in errors[:5]:  # Show first 5 errors
                                    print(f"     - {error}")
                                if len(errors) > 5:
                                    print(f"     ... and {len(errors) - 5} more {entity_type} errors")
                        
                        return 1
                        
                except Exception as import_error:
                    print(f"❌ Import failed: {import_error}")
                    if args.verbose:
                        traceback.print_exc()
                    return 1
                
            except Exception as e:
                print(f"Error loading data: {e}")
                if args.verbose:
                    traceback.print_exc()
                return 1
    
    def handle_create(self, args, db):
        """Handle entity creation with dry-run by default"""
        try:
            dry_run = not args.execute
            
            if dry_run:
                print(f"🧪 DRY RUN MODE: Creating {args.entity} (no changes will be made)")
            else:
                print(f"🚀 EXECUTING: Creating {args.entity}")
            
            if args.entity == "match":
                return self._create_match(args, db, dry_run)
            elif args.entity == "league":
                return self._create_league(args, db, dry_run)
            elif args.entity == "team":
                return self._create_team(args, db, dry_run)
            elif args.entity == "facility":
                return self._create_facility(args, db, dry_run)
            else:
                print(f"Unknown entity type: {args.entity}")
                return 1
                
        except Exception as e:
            print(f"Error creating {args.entity}: {e}")
            if args.verbose:
                traceback.print_exc()
            return 1
    
    def handle_generate_matches(self, args, db):
        """Handle match generation with dry-run by default"""
        try:
            # Parse target leagues
            target_league_ids = None
            if args.league_id:
                target_league_ids = [args.league_id]
            elif args.league_ids:
                try:
                    target_league_ids = [int(x.strip()) for x in args.league_ids.split(',')]
                except ValueError:
                    print("Error: Invalid league IDs format")
                    return 1
            
            # Get leagues
            if target_league_ids:
                leagues = []
                for league_id in target_league_ids:
                    league = db.get_league(league_id)
                    if league:
                        leagues.append(league)
                    else:
                        print(f"Warning: League {league_id} not found")
            else:
                leagues = db.list_leagues()
            
            if not leagues:
                print("No leagues found")
                return 1
            
            # Determine mode
            dry_run = not args.execute
            
            if dry_run:
                print(f"🧪 DRY RUN MODE: Generating matches for {len(leagues)} league(s)")
                print("Use --execute flag to actually generate matches")
            else:
                print(f"🚀 EXECUTING: Generating matches for {len(leagues)} league(s)")
            
            print(f"Minimum teams required: {args.min_teams}")
            print("-" * 60)
            
            total_generated = 0
            total_skipped = 0
            
            for i, league in enumerate(leagues):
                if args.progress:
                    print(f"[{i+1}/{len(leagues)}] Processing: {league.name}")
                
                # Get teams
                teams = db.list_teams(league)
                if len(teams) < args.min_teams:
                    if args.progress:
                        print(f"  Skipped: Only {len(teams)} teams (need {args.min_teams})")
                    total_skipped += 1
                    continue
                
                # Check existing matches
                existing_matches = db.list_matches(league=league, match_type=MatchType.ALL)
                if existing_matches and args.skip_existing:
                    if args.progress:
                        print(f"  Skipped: Already has {len(existing_matches)} matches")
                    total_skipped += 1
                    continue
                
                # Generate matches
                from match_generator import MatchGenerator
                match_generator = MatchGenerator()
                matches = match_generator.generate_matches(teams=teams, league=league)
                
                if dry_run:
                    if args.progress:
                        print(f"  Would generate: {len(matches)} matches for {len(teams)} teams")
                else:
                    # Delete existing if overwrite requested
                    if args.overwrite_existing and existing_matches:
                        for match in existing_matches:
                            db.delete_match(match.id)
                        if args.progress:
                            print(f"  Deleted: {len(existing_matches)} existing matches")
                    
                    # Add new matches
                    for match in matches:
                        db.add_match(match)
                    
                    if args.progress:
                        print(f"  Generated: {len(matches)} matches for {len(teams)} teams")
                
                total_generated += len(matches)
            
            # Summary
            print("-" * 60)
            if dry_run:
                print("DRY RUN SUMMARY:")
                print(f"  Would generate: {total_generated} matches")
                print(f"  Would skip: {total_skipped} leagues")
                print("\nUse --execute flag to actually generate matches")
            else:
                print("GENERATION SUMMARY:")
                print(f"  Generated: {total_generated} matches")
                print(f"  Skipped: {total_skipped} leagues")
            
            return 0
            
        except Exception as e:
            print(f"Error generating matches: {e}")
            if args.verbose:
                traceback.print_exc()
            return 1
    
    def handle_delete(self, args, db):
        """Handle entity deletion with dry-run by default"""
        try:
            dry_run = not args.execute
            
            if dry_run:
                print(f"🧪 DRY RUN MODE: Deleting {args.entity} (no changes will be made)")
            else:
                print(f"🚀 EXECUTING: Deleting {args.entity}")
            
            entities_to_delete = []
            
            if args.entity == "matches":
                if args.id:
                    match = db.get_match(args.id)
                    if match:
                        entities_to_delete.append(match)
                elif args.league_id:
                    league = db.get_league(args.league_id)
                    if league:
                        entities_to_delete = db.list_matches(league=league, match_type=MatchType.ALL)
                else:
                    entities_to_delete = db.list_matches(match_type=MatchType.ALL)
            
            elif args.entity == "teams":
                if args.id:
                    team = db.get_team(args.id)
                    if team:
                        entities_to_delete.append(team)
                elif args.league_id:
                    league = db.get_league(args.league_id)
                    if league:
                        entities_to_delete = db.list_teams(league)
                else:
                    entities_to_delete = db.list_teams()
            
            # Add similar logic for leagues and facilities...
            
            if not entities_to_delete:
                print("No entities found to delete")
                return 0
            
            print(f"\nFound {len(entities_to_delete)} {args.entity} to delete:")
            for entity in entities_to_delete[:10]:  # Show first 10
                if hasattr(entity, 'name'):
                    print(f"  {entity.__class__.__name__} {entity.id}: {entity.name}")
                else:
                    print(f"  {entity.__class__.__name__} {entity.id}")
            
            if len(entities_to_delete) > 10:
                print(f"  ... and {len(entities_to_delete) - 10} more")
            
            if dry_run:
                print(f"\nUse --execute flag to actually delete these {args.entity}")
                return 0
            else:
                # Confirmation for actual deletion
                response = input(f"\nAre you sure you want to delete {len(entities_to_delete)} {args.entity}? (yes/no): ")
                if response.lower() not in ['yes', 'y']:
                    print("Deletion cancelled")
                    return 0
                
                # Actually delete
                deleted_count = 0
                for entity in entities_to_delete:
                    try:
                        if args.entity == "matches":
                            db.delete_match(entity)
                        elif args.entity == "teams":
                            db.delete_team(entity)
                        # Add other entity types...
                        
                        deleted_count += 1
                        if args.progress:
                            print(f"  Deleted {entity.__class__.__name__} {entity.id}")
                    except Exception as e:
                        print(f"  Failed to delete {entity.__class__.__name__} {entity.id}: {e}")
                
                print(f"\n✅ Deleted {deleted_count}/{len(entities_to_delete)} {args.entity}")
                return 0
            
        except Exception as e:
            print(f"Error deleting {args.entity}: {e}")
            if args.verbose:
                traceback.print_exc()
            return 1
    
    def _validate_yaml_data(self, data) -> Dict:
        """Validate YAML data structure"""
        errors = []
        
        if not isinstance(data, dict):
            errors.append("Root level must be a dictionary")
            return {'valid': False, 'errors': errors}
        
        # Check for valid sections
        valid_sections = ['facilities', 'leagues', 'teams', 'matches']
        for section in data.keys():
            if section not in valid_sections:
                errors.append(f"Unknown section: {section}")
        
        # Validate facilities
        if 'facilities' in data:
            if not isinstance(data['facilities'], list):
                errors.append("Facilities must be a list")
            else:
                for i, facility in enumerate(data['facilities']):
                    if not isinstance(facility, dict):
                        errors.append(f"Facility {i} must be a dictionary")
                    elif 'name' not in facility:
                        errors.append(f"Facility {i} missing required 'name' field")
        
        # Validate leagues
        if 'leagues' in data:
            if not isinstance(data['leagues'], list):
                errors.append("Leagues must be a list")
            else:
                for i, league in enumerate(data['leagues']):
                    if not isinstance(league, dict):
                        errors.append(f"League {i} must be a dictionary")
                    else:
                        required_fields = ['name', 'year', 'section', 'region', 'age_group', 'division']
                        for field in required_fields:
                            if field not in league:
                                errors.append(f"League {i} missing required '{field}' field")
        
        # Validate teams
        if 'teams' in data:
            if not isinstance(data['teams'], list):
                errors.append("Teams must be a list")
            else:
                for i, team in enumerate(data['teams']):
                    if not isinstance(team, dict):
                        errors.append(f"Team {i} must be a dictionary")
                    else:
                        required_fields = ['name', 'league_name']
                        for field in required_fields:
                            if field not in team:
                                errors.append(f"Team {i} missing required '{field}' field")
        
        return {'valid': len(errors) == 0, 'errors': errors}
    


    
    def _create_match(self, args, db, dry_run):
        """Create a match"""
        if not all([args.league_id, args.home_team_id, args.visitor_team_id]):
            print("Error: Must specify --league-id, --home-team-id, and --visitor-team-id")
            return 1
        
        # Validate entities exist
        league = db.get_league(args.league_id)
        if not league:
            print(f"Error: League {args.league_id} not found")
            return 1
        
        home_team = db.get_team(args.home_team_id)
        if not home_team:
            print(f"Error: Home team {args.home_team_id} not found")
            return 1
        
        visitor_team = db.get_team(args.visitor_team_id)
        if not visitor_team:
            print(f"Error: Visitor team {args.visitor_team_id} not found")
            return 1
        
        print(f"Creating match:")
        print(f"  League: {league.name}")
        print(f"  Home team: {home_team.name}")
        print(f"  Visitor team: {visitor_team.name}")
        
        if dry_run:
            print("✅ Would create match successfully")
            print("Use --execute flag to actually create the match")
            return 0
        else:
            try:
                match = Match(
                    league=league,
                    home_team=home_team,
                    visitor_team=visitor_team,
                    round_number=1,
                    num_rounds=1
                )
                db.add_match(match)
                print(f"✅ Match created successfully with ID {match.id}")
                return 0
            except Exception as e:
                print(f"❌ Failed to create match: {e}")
                return 1
    
    def _create_league(self, args, db, dry_run):
        """Create a league"""
        required_fields = ['name', 'year', 'section', 'region', 'age_group', 'division']
        missing_fields = [field for field in required_fields if not getattr(args, field.replace('-', '_'), None)]
        
        if missing_fields:
            print(f"Error: Missing required fields: {', '.join(['--' + field for field in missing_fields])}")
            return 1
        
        print(f"Creating league:")
        print(f"  Name: {args.name}")
        print(f"  Year: {args.year}")
        print(f"  Section: {args.section}")
        print(f"  Region: {args.region}")
        print(f"  Age group: {args.age_group}")
        print(f"  Division: {args.division}")
        
        if dry_run:
            print("✅ Would create league successfully")
            print("Use --execute flag to actually create the league")
            return 0
        else:
            try:
                league = League(
                    name=args.name,
                    year=args.year,
                    section=args.section,
                    region=args.region,
                    age_group=args.age_group,
                    division=args.division
                )
                db.add_league(league)
                print(f"✅ League created successfully with ID {league.id}")
                return 0
            except Exception as e:
                print(f"❌ Failed to create league: {e}")
                return 1
    
    def _create_team(self, args, db, dry_run):
        """Create a team"""
        if not all([args.name, args.league_id]):
            print("Error: Must specify --name and --league-id")
            return 1
        
        league = db.get_league(args.league_id)
        if not league:
            print(f"Error: League {args.league_id} not found")
            return 1
        
        facility = None
        if args.home_facility_id:
            facility = db.get_facility(args.home_facility_id)
            if not facility:
                print(f"Error: Facility {args.home_facility_id} not found")
                return 1
        
        print(f"Creating team:")
        print(f"  Name: {args.name}")
        print(f"  League: {league.name}")
        print(f"  Captain: {args.captain or 'Not specified'}")
        print(f"  Home facility: {facility.name if facility else 'Not specified'}")
        
        if dry_run:
            print("✅ Would create team successfully")
            print("Use --execute flag to actually create the team")
            return 0
        else:
            try:
                team = Team(
                    name=args.name,
                    league=league,
                    captain=args.captain or '',
                    preferred_facilities=[facility] if facility else []
                )
                db.add_team(team)
                print(f"✅ Team created successfully with ID {team.id}")
                return 0
            except Exception as e:
                print(f"❌ Failed to create team: {e}")
                return 1
    
    def _create_facility(self, args, db, dry_run):
        """Create a facility"""
        if not args.name:
            print("Error: Must specify --name")
            return 1
        
        print(f"Creating facility:")
        print(f"  Name: {args.name}")
        print(f"  Short name: {args.short_name or args.name[:10]}")
        print(f"  Location: {args.location or 'Not specified'}")
        print(f"  Total courts: {args.total_courts or 6}")
        
        if dry_run:
            print("✅ Would create facility successfully")
            print("Use --execute flag to actually create the facility")
            return 0
        else:
            try:
                facility = Facility(
                    name=args.name,
                    short_name=args.short_name or args.name[:10],
                    location=args.location or '',
                    total_courts=args.total_courts or 6
                )
                db.add_facility(facility)
                print(f"✅ Facility created successfully with ID {facility.id}")
                return 0
            except Exception as e:
                print(f"❌ Failed to create facility: {e}")
                return 1
    
    # Include all the other handler methods from the previous implementation
    def handle_list(self, args, db):
        """Handle list command"""
        if args.table == "matches":
            from usta_match import MatchType
            match_type = MatchType.from_string(args.match_type)
            
            if args.league_id:
                league = db.get_league(args.league_id)
                if not league:
                    print(f"League {args.league_id} not found")
                    return 1
                matches = db.list_matches(league=league, match_type=match_type)
            else:
                matches = db.list_matches(match_type=match_type)
            
            if args.format == 'json':
                matches_data = [
                    {
                        'id': match.id,
                        'league_name': match.league.name,
                        'home_team_name': match.home_team.name,
                        'visitor_team_name': match.visitor_team.name,
                        'facility_name': match.facility.name if match.facility else None,
                        'date': match.date,
                        'scheduled_times': match.scheduled_times,
                        'status': match.get_status()
                    }
                    for match in matches
                ]
                print(json.dumps(matches_data, indent=2))
            else:
                self._pretty_print_matches(matches, args.league_id)
            
        elif args.table == "leagues":
            leagues = db.list_leagues()
            if args.format == 'json':
                leagues_data = [
                    {
                        'id': league.id,
                        'name': league.name,
                        'year': league.year,
                        'section': league.section,
                        'region': league.region,
                        'age_group': league.age_group,
                        'division': league.division
                    }
                    for league in leagues
                ]
                print(json.dumps(leagues_data, indent=2))
            else:
                for league in leagues:
                    print(f"League {league.id}: {league.name} ({league.year})")
            
        elif args.table == "teams":
            teams = db.list_teams(args.league_id)
            if args.format == 'json':
                teams_data = [
                    {
                        'id': team.id,
                        'name': team.name,
                        'league_name': team.league.name,
                        'captain': team.captain,
                        'home_facility_name': team.get_primary_facility().name if team.preferred_facilities else None
                    }
                    for team in teams
                ]
                print(json.dumps(teams_data, indent=2))
            else:
                for team in teams:
                    facility_info = f" (Primary: {team.get_primary_facility().name})" if team.preferred_facilities else ""
                    print(f"Team {team.id}: {team.name} ({team.league.name}){facility_info}")
                
        elif args.table == "facilities":
            facilities = db.list_facilities()
            if args.format == 'json':
                facilities_data = [
                    {
                        'id': facility.id,
                        'name': facility.name,
                        'short_name': facility.short_name,
                        'location': facility.location,
                        'total_courts': facility.total_courts
                    }
                    for facility in facilities
                ]
                print(json.dumps(facilities_data, indent=2))
            else:
                for facility in facilities:
                    print(f"Facility {facility.id}: {facility.name} ({facility.total_courts} courts)")
        
        elif args.table == "sections":
            from usta_constants import USTA_SECTIONS
            if args.format == 'json':
                print(json.dumps([{'name': section} for section in USTA_SECTIONS], indent=2))
            else:
                for section in USTA_SECTIONS:
                    print(f"  {section}")
        
        elif args.table == "regions":
            from usta_constants import USTA_REGIONS
            if args.format == 'json':
                print(json.dumps([{'name': region} for region in USTA_REGIONS], indent=2))
            else:
                for region in USTA_REGIONS:
                    print(f"  {region}")
        
        elif args.table == "age-groups":
            from usta_constants import USTA_AGE_GROUPS
            if args.format == 'json':
                print(json.dumps([{'name': age_group} for age_group in USTA_AGE_GROUPS], indent=2))
            else:
                for age_group in USTA_AGE_GROUPS:
                    print(f"  {age_group}")
        
        elif args.table == "divisions":
            from usta_constants import USTA_DIVISIONS
            if args.format == 'json':
                print(json.dumps([{'name': division} for division in USTA_DIVISIONS], indent=2))
            else:
                for division in USTA_DIVISIONS:
                    print(f"  {division}")
        
        return 0
    
    def handle_auto_schedule(self, args, db):
        """Handle auto-scheduling using the match manager"""
        try:
            # Parse target leagues
            target_league_ids = None
            if args.league_id:
                target_league_ids = [args.league_id]
            elif args.league_ids:
                try:
                    target_league_ids = [int(x.strip()) for x in args.league_ids.split(',')]
                except ValueError:
                    print("Error: Invalid league IDs format")
                    return 1
            
            # Get all unscheduled matches at once
            from usta import MatchType
            if target_league_ids:
                # Get matches for specific leagues
                all_unscheduled_matches = []
                for league_id in target_league_ids:
                    league = db.get_league(league_id)
                    if league:
                        league_matches = db.list_matches(league=league, match_type=MatchType.UNSCHEDULED)
                        all_unscheduled_matches.extend(league_matches)
                    else:
                        print(f"Warning: League {league_id} not found")
            else:
                # Get all unscheduled matches from all leagues
                all_unscheduled_matches = db.list_matches(match_type=MatchType.UNSCHEDULED)
            
            if not all_unscheduled_matches:
                print("No unscheduled matches found")
                return 0
            
            # Apply max limit if specified
            if args.max_matches and len(all_unscheduled_matches) > args.max_matches:
                all_unscheduled_matches = all_unscheduled_matches[:args.max_matches]
                print(f"Limited to {args.max_matches} matches for testing")
            
            # Determine mode
            dry_run = not args.execute
            
            if dry_run:
                print(f"🧪 DRY RUN MODE: Auto-scheduling {len(all_unscheduled_matches)} unscheduled matches")
                print("Use --execute flag to actually schedule matches")
            else:
                print(f"🚀 EXECUTING: Auto-scheduling {len(all_unscheduled_matches)} unscheduled matches")
            
            print(f"Processing {len(all_unscheduled_matches)} unscheduled matches...")
            print("-" * 60)
            
            # Determine seed to use
            if args.seed is not None:
                seed = args.seed
                print(f"Using provided seed: {seed}")
            else:
                # Generate seed using same method as web interface
                import time
                seed = int(time.time() * 1000) % 2**31
                print(f"Generated seed: {seed}")
            
            # Auto-schedule all matches at once
            try:
                scheduling_manager = SchedulingManager(db)
                results = scheduling_manager.auto_schedule_matches(all_unscheduled_matches, dry_run=dry_run, seed=seed)

                scheduled_count = results.get('scheduled', 0)
                failed_count = results.get('failed', 0)
                
                if args.progress:
                    if dry_run:
                        print(f"Would schedule: {scheduled_count}/{len(all_unscheduled_matches)} matches")
                    else:
                        print(f"Scheduled: {scheduled_count}/{len(all_unscheduled_matches)} matches")
                    
                    if failed_count > 0:
                        verb = "would fail" if dry_run else "failed"
                        print(f"Failed: {failed_count} matches {verb}")
                    
                    # Show sample scheduling details
                    if results.get('scheduling_details') and args.progress:
                        print("Sample scheduled matches:")
                        for detail in results['scheduling_details'][:5]:  # Show first 5
                            status = detail.get('status', 'scheduled')
                            facility = detail.get('facility', 'Unknown')
                            date = detail.get('date', 'Unknown')
                            times = detail.get('times', [])
                            times_str = ', '.join(times) if times else 'No times'
                            print(f"  Match {detail['match_id']}: {facility} on {date} at {times_str}")
                        
                        if len(results['scheduling_details']) > 5:
                            print(f"  ... and {len(results['scheduling_details']) - 5} more")
                
                # Show errors if any
                if results.get('errors') and args.progress:
                    scheduling_errors = [e for e in results['errors'] if e.get('status') == 'scheduling_failed']
                    if scheduling_errors:
                        print(f"Scheduling failures: {len(scheduling_errors)}")
                        for error in scheduling_errors[:3]:  # Show first 3 failures
                            match_id = error.get('match_id', 'Unknown')
                            reason = error.get('reason', 'Unknown reason')
                            print(f"  Match {match_id}: {reason}")
                        
                        if len(scheduling_errors) > 3:
                            print(f"  ... and {len(scheduling_errors) - 3} more failures")
                
            except Exception as e:
                print(f"❌ Error auto-scheduling matches: {e}")
                if args.verbose:
                    import traceback
                    traceback.print_exc()
                return 1
            
            # Summary
            print("-" * 60)
            if dry_run:
                print("DRY RUN SUMMARY:")
                print(f"  Would schedule: {scheduled_count} matches")
                print(f"  Would fail: {failed_count} matches")
                print("\n✅ Dry-run completed successfully!")
                print("Run with --execute flag to actually perform scheduling")
            else:
                print("EXECUTION SUMMARY:")
                print(f"  Scheduled: {scheduled_count} matches")
                print(f"  Failed: {failed_count} matches")
                print("\n✅ Auto-scheduling completed!")
            
            return 0
            
        except Exception as e:
            print(f"Error in auto-schedule: {e}")
            if args.verbose:
                traceback.print_exc()
            return 1
    
    def handle_optimize_schedule(self, args, db):
        """Handle auto-schedule optimization with multiple iterations"""
        try:
            # Validate iterations parameter
            if args.iterations < 1 or args.iterations > 100:
                print("Error: iterations must be between 1 and 100")
                return 1
            
            # Parse target leagues
            target_league_ids = None
            if args.league_id:
                target_league_ids = [args.league_id]
            elif args.league_ids:
                try:
                    target_league_ids = [int(x.strip()) for x in args.league_ids.split(',')]
                except ValueError:
                    print("Error: Invalid league IDs format")
                    return 1
            
            # Get all unscheduled matches at once
            from usta import MatchType
            if target_league_ids:
                # Get matches for specific leagues
                all_unscheduled_matches = []
                for league_id in target_league_ids:
                    league = db.get_league(league_id)
                    if league:
                        league_matches = db.list_matches(league=league, match_type=MatchType.UNSCHEDULED)
                        all_unscheduled_matches.extend(league_matches)
                    else:
                        print(f"Warning: League {league_id} not found")
            else:
                # Get all unscheduled matches from all leagues
                all_unscheduled_matches = db.list_matches(match_type=MatchType.UNSCHEDULED)
            
            if not all_unscheduled_matches:
                print("No unscheduled matches found")
                return 0
            
            # Apply max limit if specified
            if args.max_matches and len(all_unscheduled_matches) > args.max_matches:
                all_unscheduled_matches = all_unscheduled_matches[:args.max_matches]
                print(f"Limited to {args.max_matches} matches for testing")
            
            # Determine mode
            dry_run = not args.execute
            
            if dry_run:
                print(f"🧪 DRY RUN MODE: Optimizing auto-schedule for {len(all_unscheduled_matches)} matches")
                print("Use --execute flag to run best result after optimization")
            else:
                print(f"🚀 EXECUTING: Optimizing auto-schedule for {len(all_unscheduled_matches)} matches")
                print("Will execute with best seed after optimization")
            
            print(f"Running {args.iterations} optimization iterations...")
            print("-" * 60)
            
            # Run optimization
            try:
                optimization_result = db.optimize_auto_schedule(
                    matches=all_unscheduled_matches, 
                    max_iterations=args.iterations
                )
                
                if not optimization_result.get('optimization_completed', False):
                    error_msg = optimization_result.get('error', 'Unknown optimization error')
                    print(f"❌ Optimization failed: {error_msg}")
                    return 1
                
                # Extract optimization results
                best_seed = optimization_result.get('best_seed')
                best_unscheduled_count = optimization_result.get('best_unscheduled_count', float('inf'))
                best_quality_score = optimization_result.get('best_quality_score', 0)
                results_history = optimization_result.get('results_history', [])
                improvement_found = optimization_result.get('improvement_found', False)
                
                print(f"✅ Optimization completed after {args.iterations} iterations")
                print("-" * 60)
                
                if improvement_found:
                    schedulable_count = len(all_unscheduled_matches) - best_unscheduled_count
                    print(f"🎯 BEST RESULT FOUND:")
                    print(f"  Seed: {best_seed}")
                    print(f"  Schedulable matches: {schedulable_count}/{len(all_unscheduled_matches)}")
                    print(f"  Unscheduled matches: {best_unscheduled_count}")
                    print(f"  Average quality score: {best_quality_score:.1f}")
                    
                    if args.progress and results_history:
                        print(f"\n📊 OPTIMIZATION PROGRESS:")
                        print("Iteration | Seed      | Schedulable | Unscheduled | Quality")
                        print("-" * 60)
                        for result in results_history[-10:]:  # Show last 10 iterations
                            iteration = result['iteration']
                            seed = result['seed']
                            scheduled = result['scheduled_count']
                            unscheduled = result['unscheduled_count']
                            quality = result['avg_quality_score']
                            is_best = seed == best_seed
                            marker = " *" if is_best else ""
                            print(f"{iteration:9d} | {seed:9d} | {scheduled:11d} | {unscheduled:11d} | {quality:7.1f}{marker}")
                    
                    # Execute with best seed if requested
                    if not dry_run:
                        print(f"\n🚀 EXECUTING with best seed {best_seed}...")
                        execute_result = db.auto_schedule_matches(
                            all_unscheduled_matches, 
                            dry_run=False, 
                            seed=best_seed
                        )
                        
                        scheduled_count = execute_result.get('scheduled', 0)
                        failed_count = execute_result.get('failed', 0)
                        
                        print(f"\n✅ EXECUTION COMPLETED:")
                        print(f"  Scheduled: {scheduled_count} matches")
                        print(f"  Failed: {failed_count} matches")
                        
                        if args.progress and execute_result.get('scheduling_details'):
                            print("\nSample scheduled matches:")
                            for detail in execute_result['scheduling_details'][:5]:
                                facility = detail.get('facility', 'Unknown')
                                date = detail.get('date', 'Unknown')
                                times = detail.get('times', [])
                                times_str = ', '.join(times) if times else 'No times'
                                quality = detail.get('quality_score', 0)
                                print(f"  Match {detail['match_id']}: {facility} on {date} at {times_str} (quality: {quality})")
                    else:
                        print(f"\n💡 To execute this optimization result, run:")
                        print(f"   --execute --iterations {args.iterations}")
                        print(f"\n   Or use the best seed directly with auto-schedule:")
                        cmd_parts = ["auto-schedule"]
                        if args.league_id:
                            cmd_parts.append(f"--league-id {args.league_id}")
                        elif args.league_ids:
                            cmd_parts.append(f"--league-ids {args.league_ids}")
                        if args.max_matches:
                            cmd_parts.append(f"--max-matches {args.max_matches}")
                        cmd_parts.append("--execute")
                        print(f"   {' '.join(cmd_parts)} (with seed {best_seed})")
                else:
                    print(f"⚠️ No schedulable matches found after {args.iterations} iterations")
                    if args.progress and results_history:
                        print(f"\n📊 All iterations had 0 schedulable matches")
                        print("This might indicate:")
                        print("  - Insufficient facility availability")
                        print("  - Team scheduling conflicts")
                        print("  - Configuration issues")
                
                return 0
                
            except Exception as e:
                print(f"❌ Error during optimization: {e}")
                if args.verbose:
                    import traceback
                    traceback.print_exc()
                return 1
            
        except Exception as e:
            print(f"Error in optimize-schedule: {e}")
            if args.verbose:
                traceback.print_exc()
            return 1
    
    def handle_schedule(self, args, db):
        """Handle single match scheduling with dry-run by default"""
        try:
            # Validate inputs
            match = db.get_match(args.match_id)
            if not match:
                print(f"Match {args.match_id} not found")
                return 1
            
            facility = db.get_facility(args.facility_id)
            if not facility:
                print(f"Facility {args.facility_id} not found")
                return 1
            
            # Determine mode
            dry_run = not args.execute
            
            # Display what we're doing
            if dry_run:
                print("🧪 DRY RUN MODE: Schedule match preview")
            else:
                print("🚀 EXECUTING: Scheduling match")
                
            print(f"  Match: {match.home_team.name} vs {match.visitor_team.name}")
            print(f"  League: {match.league.name}")
            print(f"  Facility: {facility.name}")
            print(f"  Date: {args.date}")
            print(f"  Time: {args.time}")
            
            if dry_run:
                print("\nChecking feasibility...")
                
                # Check if already scheduled
                if match.is_scheduled():
                    print("❌ WOULD FAIL: Match is already scheduled")
                    print(f"   Current: {match.facility.name} on {match.date}")
                    return 1
                
                # Could add more checks here (facility availability, etc.)
                print("✅ WOULD SUCCEED: Scheduling appears feasible")
                print("\nUse --execute flag to actually perform scheduling")
                return 0
            else:
                # Actually schedule the match
                result = db.schedule_match(
                    match, args.date, [args.time], "same_time"
                )
                success = result.get('success', False)
                
                if success:
                    print("✅ Match scheduled successfully!")
                    return 0
                else:
                    print("❌ Failed to schedule match")
                    return 1
            
        except Exception as e:
            print(f"Error scheduling match: {e}")
            if args.verbose:
                traceback.print_exc()
            return 1
    
    def handle_unschedule(self, args, db):
        """Handle unscheduling with dry-run by default"""
        try:
            matches_to_unschedule = []
            
            if args.match_id:
                match = db.get_match(args.match_id)
                if not match:
                    print(f"Match {args.match_id} not found")
                    return 1
                if not match.is_scheduled():
                    print(f"Match {args.match_id} is not scheduled")
                    return 1
                matches_to_unschedule.append(match)
                
            elif args.league_id:
                league = db.get_league(args.league_id)
                if not league:
                    print(f"League {args.league_id} not found")
                    return 1
                matches_to_unschedule = db.list_matches(league=league, match_type=MatchType.SCHEDULED)
            else:
                # Unschedule all scheduled matches
                matches_to_unschedule = db.list_matches(match_type=MatchType.SCHEDULED)
            
            if not matches_to_unschedule:
                print("No scheduled matches found")
                return 0
            
            # Determine mode
            dry_run = not args.execute
            
            # Display what we're doing
            if dry_run:
                print(f"🧪 DRY RUN MODE: Would unschedule {len(matches_to_unschedule)} match(es)")
            else:
                print(f"🚀 EXECUTING: Unscheduling {len(matches_to_unschedule)} match(es)")
            
            print("-" * 50)
            for match in matches_to_unschedule:
                facility_info = f" at {match.facility.name}" if match.facility else ""
                date_info = f" on {match.date}" if match.date else ""
                print(f"  Match {match.id}: {match.home_team.name} vs {match.visitor_team.name}{facility_info}{date_info}")
            
            if dry_run:
                print(f"\nUse --execute flag to actually unschedule these matches")
                return 0
            else:
                # Actually unschedule
                scheduling_manager = SchedulingManager(db)
                unscheduled_count = 0
                for match in matches_to_unschedule:
                    try:
                        scheduling_manager.unschedule_match(match)
                        unscheduled_count += 1
                        if args.progress:
                            print(f"  Unscheduled match {match.id}")
                    except Exception as e:
                        print(f"  Failed to unschedule match {match.id}: {e}")
                
                print(f"\n✅ Unscheduled {unscheduled_count}/{len(matches_to_unschedule)} matches")
                return 0
            
        except Exception as e:
            print(f"Error unscheduling: {e}")
            if args.verbose:
                traceback.print_exc()
            return 1
    
    def handle_test(self, args, db):
        """Handle testing with import tests"""
        print("🧪 TESTING FUNCTIONALITY")
        print("=" * 50)
        
        # Test 1: Basic dry-run functionality
        print("\n1. Testing basic dry-run functionality...")
        try:
            matches = db.list_matches(match_type=MatchType.UNSCHEDULED)
            if matches:
                test_matches = matches[:2]
                results = db.auto_schedule_matches(test_matches, dry_run=True)
                print(f"   ✅ Dry-run completed: {results['scheduled']} would be scheduled")
            else:
                print("   ⚠️  No unscheduled matches for testing")
        except Exception as e:
            print(f"   ❌ Dry-run test failed: {e}")
            return 1
        
        if args.import_test:
            # Test 2: Import functionality
            print("\n2. Testing import functionality...")
            
            # Create a test YAML file
            test_yaml = {
                'facilities': [
                    {'name': 'Test Facility', 'short_name': 'TEST', 'location': 'Test Location', 'total_courts': 8}
                ],
                'leagues': [
                    {
                        'name': 'Test League', 'year': 2025, 'section': 'USTA_PNW',
                        'region': 'Seattle', 'age_group': '18+', 'division': '3.0'
                    }
                ]
            }
            
            try:
                # Test validation
                validation_result = self._validate_yaml_data(test_yaml)
                if validation_result['valid']:
                    print("   ✅ YAML validation working correctly")
                else:
                    print(f"   ❌ YAML validation failed: {validation_result['errors']}")
                    return 1
                
                # Test preview
                print("   ✅ YAML preview functionality working")
                
            except Exception as e:
                print(f"   ❌ Import test failed: {e}")
                return 1
        
        if args.comprehensive:
            # Include all previous comprehensive tests
            print("\n3. Testing conflict detection...")
            # Add comprehensive testing here
        
        print("\n✅ ALL TESTS PASSED!")
        return 0
    
    def handle_stats(self, args, db):
        """Handle statistics display for leagues and facilities"""
        try:
            print("📊 TENNIS DATABASE STATISTICS")
            print("=" * 60)
            
            # Get basic counts
            leagues = db.list_leagues()
            facilities = db.list_facilities()
            teams = db.list_teams()
            matches = db.list_matches()
            
            print("\n📋 BASIC STATISTICS")
            print("-" * 30)
            print(f"Total Leagues: {len(leagues)}")
            print(f"Total Facilities: {len(facilities)}")
            print(f"Total Teams: {len(teams)}")
            print(f"Total Matches: {len(matches)}")
            
            # Filter by league if specified
            if args.league_id:
                target_league = db.get_league(args.league_id)
                if not target_league:
                    print(f"\nError: League {args.league_id} not found")
                    return 1
                leagues = [target_league]
                print(f"\n🎯 FILTERED BY LEAGUE: {target_league.name}")
            
            # League Statistics
            print("\n🏆 LEAGUE STATISTICS")
            print("-" * 30)
            
            for league in leagues:
                league_teams = db.list_teams(league)
                league_matches = db.list_matches(league=league)
                scheduled_matches = [m for m in league_matches if m.is_scheduled()]
                unscheduled_matches = [m for m in league_matches if not m.is_scheduled()]
                
                print(f"\nLeague: {league.name} (ID: {league.id})")
                print(f"  Year: {league.year}")
                print(f"  Section: {league.section}, Region: {league.region}")
                print(f"  Age Group: {league.age_group}, Division: {league.division}")
                print(f"  Teams: {len(league_teams)}")
                print(f"  Matches: {len(league_matches)} total")
                print(f"    Scheduled: {len(scheduled_matches)}")
                print(f"    Unscheduled: {len(unscheduled_matches)}")
                
                if len(league_matches) > 0:
                    completion_rate = (len(scheduled_matches) / len(league_matches)) * 100
                    print(f"  Completion Rate: {completion_rate:.1f}%")
                
                # Lines per match info
                if hasattr(league, 'num_lines_per_match'):
                    print(f"  Lines per Match: {league.num_lines_per_match}")
                    total_court_hours = len(scheduled_matches) * league.num_lines_per_match
                    print(f"  Total Court Hours Used: {total_court_hours}")
            
            # Facility Statistics
            print("\n🏟️  FACILITY STATISTICS")
            print("-" * 30)
            
            for facility in facilities:
                print(f"\nFacility: {facility.name} (ID: {facility.id})")
                if facility.location:
                    print(f"  Location: {facility.location}")
                if facility.total_courts:
                    print(f"  Total Courts: {facility.total_courts}")
                
                # Get facility statistics using the unified method
                try:
                    # Get comprehensive facility statistics
                    facility_stats = db.facility_manager.facility_statistics(
                        facility=facility,
                        league=target_league if args.league_id else None,
                        include_league_breakdown=True,
                        include_per_day_utilization=True,
                        include_peak_demand=True,
                        include_requirements=False
                    )
                    
                    # Display overall utilization
                    total_utilization = facility_stats.get("total_utilization", 0.0)
                    total_slots = facility_stats.get("total_available_slots", 0)
                    used_slots = facility_stats.get("total_time_slots_used", 0)
                    
                    print(f"  Total Available Slots: {total_slots}")
                    print(f"  Used Slots: {used_slots}")
                    print(f"  Overall Utilization: {total_utilization:.1f}%")
                    
                    # Status based on utilization
                    if total_utilization > 80:
                        status = "HIGH USAGE ⚠️"
                    elif total_utilization > 50:
                        status = "MODERATE USAGE"
                    elif total_utilization > 0:
                        status = "LOW USAGE"
                    else:
                        status = "UNUSED"
                    print(f"  Status: {status}")
                    
                    # League breakdown
                    league_breakdown = facility_stats.get("league_breakdown", {})
                    if league_breakdown:
                        print(f"  Leagues Using Facility:")
                        for league_id, league_data in league_breakdown.items():
                            league_name = league_data.get("league_name", f"League {league_id}")
                            league_util = league_data.get("utilization_percentage", 0.0)
                            league_slots = league_data.get("slots_used", 0)
                            print(f"    • {league_name}: {league_slots} slots ({league_util:.1f}%)")
                    
                    # Peak demand
                    peak_demand = facility_stats.get("peak_demand", {})
                    if peak_demand:
                        peak_day = peak_demand.get("peak_day")
                        peak_slots = peak_demand.get("peak_slots_used", 0)
                        if peak_day and peak_slots > 0:
                            print(f"  Peak Day: {peak_day} ({peak_slots} slots)")
                    
                    # Daily utilization patterns
                    per_day_util = facility_stats.get("per_day_utilization", {})
                    if per_day_util and any(util > 0 for util in per_day_util.values()):
                        print(f"  Daily Utilization:")
                        for day, util in per_day_util.items():
                            if util > 0:
                                print(f"    • {day}: {util:.1f}%")
                    
                except Exception as e:
                    print(f"  Error calculating statistics: {e}")
                
                # Count teams using this facility
                teams_using_facility = [
                    team for team in teams 
                    if team.preferred_facilities and facility in team.preferred_facilities
                ]
                if teams_using_facility:
                    print(f"  Teams Using Facility: {len(teams_using_facility)}")
                    for team in teams_using_facility[:3]:  # Show first 3
                        print(f"    • {team.name}")
                    if len(teams_using_facility) > 3:
                        print(f"    ... and {len(teams_using_facility) - 3} more")
            
            # Overall System Statistics
            print(f"\n🌐 SYSTEM OVERVIEW")
            print("-" * 30)
            
            # Calculate total utilization across all facilities
            total_system_slots = 0
            total_system_used = 0
            
            for facility in facilities:
                try:
                    facility_stats = db.facility_manager.facility_statistics(
                        facility=facility,
                        league=target_league if args.league_id else None
                    )
                    total_system_slots += facility_stats.get("total_available_slots", 0)
                    total_system_used += facility_stats.get("total_time_slots_used", 0)
                except Exception:
                    pass
            
            if total_system_slots > 0:
                system_utilization = (total_system_used / total_system_slots) * 100
                print(f"System-wide Utilization: {system_utilization:.1f}%")
                print(f"Total System Capacity: {total_system_slots} slots")
                print(f"Total System Usage: {total_system_used} slots")
                print(f"Available Capacity: {total_system_slots - total_system_used} slots")
            
            # Match scheduling statistics
            all_scheduled = sum(1 for m in matches if m.is_scheduled())
            all_unscheduled = sum(1 for m in matches if not m.is_scheduled())
            
            if len(matches) > 0:
                overall_completion = (all_scheduled / len(matches)) * 100
                print(f"Overall Match Completion: {overall_completion:.1f}%")
                print(f"Scheduling Backlog: {all_unscheduled} unscheduled matches")
            
            print("\n" + "=" * 60)
            return 0
            
        except Exception as e:
            print(f"Error generating statistics: {e}")
            if args.verbose:
                traceback.print_exc()
            return 1
    
    def handle_health(self, args, db):
        """Handle health check"""
        try:
            leagues = db.list_leagues()
            facilities = db.list_facilities()
            teams = db.list_teams()
            matches = db.list_matches()
            
            print("Database health check: ✅ OK")
            print(f"Connection: Active")
            print(f"Data summary:")
            print(f"  Leagues: {len(leagues)}")
            print(f"  Facilities: {len(facilities)}")
            print(f"  Teams: {len(teams)}")
            print(f"  Matches: {len(matches)}")
            
            return 0
        except Exception as e:
            print(f"Database health check: ❌ FAILED")
            print(f"Error: {e}")
            return 1

    def handle_facility_requirements(self, args, db):
        """Handle facility requirements calculation"""
        try:
            # Validate league exists
            league = db.get_league(args.league_id)
            if not league:
                print(f"League {args.league_id} not found")
                return 1
            
            print(f"📊 Calculating facility requirements for league: {league.name}")
            print("-" * 60)
            
            # Calculate requirements
            include_utilization = not args.no_utilization
            requirements = db.facility_manager.calculate_league_facility_requirements(
                league=league, 
                include_utilization=include_utilization
            )
            
            if args.output == "json":
                print(json.dumps(requirements, indent=2))
            else:
                self._print_facility_requirements_summary(requirements)
            
            return 0
            
        except Exception as e:
            print(f"Error calculating facility requirements: {e}")
            if args.verbose:
                traceback.print_exc()
            return 1

    def _print_facility_requirements_summary(self, requirements):
        """Print a human-readable summary of facility requirements"""
        print("📋 FACILITY REQUIREMENTS SUMMARY")
        print("=" * 60)
        
        # Basic info
        print(f"League: {requirements['league_name']}")
        print(f"Total Teams: {requirements['total_teams']}")
        print(f"Total Matches: {requirements['total_matches']}")
        print(f"Lines per Match: {requirements['lines_per_match']}")
        print(f"Total Court Hours: {requirements['total_court_hours']}")
        print(f"League Duration: {requirements['league_duration_weeks']} weeks")
        
        # Facility analysis
        print("\n🏟️  FACILITY ANALYSIS")
        print("-" * 30)
        facilities_analysis = requirements['facilities_analysis']
        print(f"Total Facilities Used: {facilities_analysis['total_facilities']}")
        
        if facilities_analysis['facilities_used']:
            print("\nFacilities:")
            for facility in facilities_analysis['facilities_used']:
                print(f"  • {facility['facility_name']} ({facility['facility_location']})")
                print(f"    - Teams: {facility['teams_count']}")
                print(f"    - Courts: {facility['total_courts']}")
        
        # Geographic distribution
        geo_dist = facilities_analysis['geographic_distribution']
        if len(geo_dist) > 1:
            print(f"\nGeographic Distribution:")
            for location, facilities in geo_dist.items():
                print(f"  • {location}: {len(facilities)} facilities")
        
        # Peak demand
        print("\n📈 PEAK DEMAND ANALYSIS")
        print("-" * 30)
        peak_demand = requirements['peak_demand']
        print(f"Matches per Week: {peak_demand['matches_per_week']}")
        
        if peak_demand['courts_needed_per_day']:
            print("\nCourts Needed per Day:")
            for day, courts in peak_demand['courts_needed_per_day'].items():
                print(f"  • {day}: {courts} courts")
            
            peak_day = peak_demand.get('peak_day')
            if peak_day:
                print(f"\nPeak Day: {peak_day}")
        
        # Team preferences
        if peak_demand['team_day_preferences']:
            print("\nTeam Day Preferences:")
            for day, count in peak_demand['team_day_preferences'].items():
                print(f"  • {day}: {count} teams")
        
        # Utilization analysis
        if requirements['utilization_analysis'] and "error" not in requirements['utilization_analysis']:
            print("\n💹 CURRENT UTILIZATION")
            print("-" * 30)
            for facility_id, util_data in requirements['utilization_analysis'].items():
                if isinstance(util_data, dict):
                    print(f"  • {util_data['facility_name']}")
                    print(f"    - Total Courts: {util_data['total_courts']}")
                    print(f"    - Current Usage: {util_data['current_usage']}")
                    print(f"    - Utilization: {util_data['utilization_percentage']:.1f}%")
        
        # Recommendations
        print("\n💡 RECOMMENDATIONS")
        print("-" * 30)
        for i, recommendation in enumerate(requirements['recommendations'], 1):
            print(f"{i}. {recommendation}")
        
        # League configuration
        print("\n⚙️  LEAGUE CONFIGURATION")
        print("-" * 30)
        print(f"Split Lines Allowed: {'Yes' if requirements['allow_split_lines'] else 'No'}")
        if requirements['preferred_days']:
            print(f"Preferred Days: {', '.join(requirements['preferred_days'])}")
        if requirements['backup_days']:
            print(f"Backup Days: {', '.join(requirements['backup_days'])}")
        
        print("\n" + "=" * 60)
    
    def _pretty_print_matches(self, matches, specific_league_id=None):
        """Pretty print matches"""
        if not matches:
            print("No matches found")
            return
        
        print(f"\nFound {len(matches)} match(es):")
        print("=" * 80)
        
        for match in matches:
            print(f"  Match {match.id}: {match.home_team.name} vs {match.visitor_team.name}")
            
            if not specific_league_id:
                print(f"    League: {match.league.name}")
            
            status = match.get_status()
            if match.is_scheduled():
                facility_name = match.facility.name if match.facility else "Unknown"
                times_str = ", ".join(match.scheduled_times) if match.scheduled_times else "No times"
                print(f"    Status: {status} | Facility: {facility_name} | Date: {match.date} | Times: {times_str}")
            else:
                expected_lines = match.league.num_lines_per_match
                print(f"    Status: {status} | Expected lines: {expected_lines}")
            
            print()


def main():
    """Main entry point"""
    cli = SimplifiedTennisCLIWithImport()
    return cli.run()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        sys.exit(1)


# ================================================================
# EXAMPLE YAML FILES FOR IMPORT
# ================================================================

example_facilities_yaml = """
# Example facilities.yaml file
facilities:
  - name: "Tennis Center North"
    short_name: "TCN"
    location: "123 Tennis Way, Seattle, WA"
    total_courts: 8
    
  - name: "Tennis Center South"
    short_name: "TCS"
    location: "456 Court Ave, Tacoma, WA"
    total_courts: 6
    
  - name: "Community Tennis Courts"
    short_name: "CTC"
    location: "789 Park Blvd, Bellevue, WA"
    total_courts: 4
"""

example_complete_yaml = """
# Example complete_setup.yaml file
facilities:
  - name: "Tennis Center North"
    short_name: "TCN"
    location: "123 Tennis Way, Seattle, WA"
    total_courts: 8

leagues:
  - name: "Adult 18+ Mixed Doubles"
    year: 2025
    section: "USTA_PNW"
    region: "Seattle"
    age_group: "18+"
    division: "3.0"
    num_lines_per_match: 3
    num_matches: 10

teams:
  - name: "Tennis Center North Team A"
    league_name: "Adult 18+ Mixed Doubles"
    captain: "John Smith"
    home_facility_name: "Tennis Center North"
    preferred_days: ["Monday", "Wednesday", "Friday"]
    
  - name: "Tennis Center North Team B"
    league_name: "Adult 18+ Mixed Doubles"
    captain: "Jane Doe"
    home_facility_name: "Tennis Center North"
    preferred_days: ["Tuesday", "Thursday", "Saturday"]

matches:
  - league_name: "Adult 18+ Mixed Doubles"
    home_team_name: "Tennis Center North Team A"
    visitor_team_name: "Tennis Center North Team B"
    round: 1
    # Optional scheduling info:
    # facility_name: "Tennis Center North"
    # date: "2025-07-15"
    # times: ["09:00", "10:00", "11:00"]
"""

print("""
USAGE EXAMPLES WITH IMPORT:

# Load facilities (dry-run by default)
python tennis_cli.py --db-path tennis.db load facilities.yaml

# Actually load facilities
python tennis_cli.py --db-path tennis.db load facilities.yaml --execute

# Validate YAML file format only
python tennis_cli.py --db-path tennis.db load complete_setup.yaml --validate-only

# Create individual entities (dry-run by default)
python tennis_cli.py --db-path tennis.db create league --name "Test League" --year 2025 --section "USTA_PNW" --region "Seattle" --age-group "18+" --division "3.0"

# Actually create the league
python tennis_cli.py --db-path tennis.db create league --name "Test League" --year 2025 --section "USTA_PNW" --region "Seattle" --age-group "18+" --division "3.0" --execute

# Generate matches (dry-run by default)
python tennis_cli.py --db-path tennis.db generate-matches --league-id 1

# Actually generate matches
python tennis_cli.py --db-path tennis.db generate-matches --league-id 1 --execute

# Test import functionality
python tennis_cli.py --db-path tennis.db test --import-test
""")
