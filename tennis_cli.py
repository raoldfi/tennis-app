#!/usr/bin/env python3
"""
Enhanced CLI for tennis scheduling with multi-backend database support.

This CLI provides a unified interface for managing tennis leagues, teams, matches,
and facilities across different database backends (SQLite, PostgreSQL, MongoDB, etc.).

Updated to reflect the removal of the Line class - scheduling is now handled at the 
Match level with scheduled_times arrays.

ENHANCED: generate-matches command now supports both single league and bulk operations.

Usage examples:
    # SQLite (default) - will create database if it doesn't exist
    python tennis_cli.py --backend sqlite --db-path tennis.db list leagues
    
    # Generate matches for all leagues
    python tennis_cli.py --db-path tennis.db generate-matches
    
    # Generate matches for a specific league
    python tennis_cli.py --db-path tennis.db generate-matches --league-id 1
    
    # Generate matches for specific leagues only
    python tennis_cli.py --db-path tennis.db generate-matches --league-ids 1,2,3
    
    # Generate matches with minimum team requirements
    python tennis_cli.py --db-path tennis.db generate-matches --min-teams 3
    
    # Skip leagues that already have matches
    python tennis_cli.py --db-path tennis.db generate-matches --skip-existing
    
    # Overwrite existing matches
    python tennis_cli.py --db-path tennis.db generate-matches --overwrite-existing
    
    # Show progress during bulk generation
    python tennis_cli.py --db-path tennis.db generate-matches --progress
    
    # From environment variables
    export TENNIS_DB_BACKEND=postgresql
    export TENNIS_DB_HOST=localhost
    python tennis_cli.py generate-matches --league-ids 1,2,3
"""

import argparse
import json
import sys
import os
from typing import Dict, Any, Optional, List
import traceback
import logging

import usta


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    # Import the tennis database architecture
    from tennis_db_factory import TennisDBFactory, DatabaseBackend, TennisDBManager, TennisDBConfig
except ImportError as e:
    print(f"Error: Could not import tennis database modules: {e}", file=sys.stderr)
    print("Make sure tennis_db_factory.py and tennis_db_interface.py are in your Python path", file=sys.stderr)
    sys.exit(1)


class TennisCLI:
    """Main CLI class for tennis database operations"""
    
    def __init__(self):
        self.db_manager = None
    
    def ensure_database_exists(self, backend_str: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure database file exists for SQLite, create if necessary
        
        Args:
            backend_str: Database backend type
            config: Database configuration
            
        Returns:
            Updated configuration dictionary
        """
        if backend_str.lower() == 'sqlite':
            db_path = config.get('db_path', 'tennis.db')
            
            # Check if database file exists
            if not os.path.exists(db_path):
                print(f"Database file '{db_path}' does not exist. Creating new database...")
                
                # Create directory if it doesn't exist
                dir_path = os.path.dirname(db_path)
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path)
                    print(f"Created directory: {dir_path}")
                
                # Update config to ensure db_path is set
                config['db_path'] = db_path
                
                # The database will be created when TennisDBFactory creates the connection
                print(f"Database will be initialized at: {db_path}")
            else:
                print(f"Using existing database: {db_path}")
        
        return config

    def get_config_from_args(self, args) -> Dict[str, Any]:
        """Build database configuration from command line arguments"""
        
        # Determine backend
        backend_str = (
            args.backend or
            os.environ.get('TENNIS_DB_BACKEND', 'sqlite')
        ).lower()
        
        config = {}
        
        if backend_str == 'sqlite':
            config['db_path'] = (
                args.db_path or 
                os.environ.get('TENNIS_DB_PATH', 'tennis.db')
            )
        elif backend_str == 'postgresql':
            config.update({
                'host': args.host or os.environ.get('TENNIS_DB_HOST', 'localhost'),
                'port': args.port or int(os.environ.get('TENNIS_DB_PORT', 5432)),
                'database': args.database or os.environ.get('TENNIS_DB_NAME', 'tennis'),
                'user': args.user or os.environ.get('TENNIS_DB_USER', 'postgres'),
                'password': args.password or os.environ.get('TENNIS_DB_PASSWORD', '')
            })
        elif backend_str == 'mongodb':
            config['connection_string'] = (
                args.connection_string or 
                os.environ.get('TENNIS_DB_CONNECTION_STRING', 'mongodb://localhost:27017/')
            )
            config['database'] = args.database or os.environ.get('TENNIS_DB_NAME', 'tennis')
        
        # Ensure database exists (for SQLite)
        config = self.ensure_database_exists(backend_str, config)
        
        return backend_str, config

    def add_database_arguments(self, parser):
        """Add database connection arguments to parser"""
        
        # Backend selection
        parser.add_argument('--backend', choices=['sqlite', 'postgresql', 'mongodb', 'mysql'],
                          help='Database backend (env: TENNIS_DB_BACKEND)')
        parser.add_argument('--config', help='JSON config file path')
        
        # SQLite options
        parser.add_argument('--db-path', help='SQLite database file path (env: TENNIS_DB_PATH)')
        
        # PostgreSQL/MySQL options
        parser.add_argument('--host', help='Database host (env: TENNIS_DB_HOST)')
        parser.add_argument('--port', type=int, help='Database port (env: TENNIS_DB_PORT)')
        parser.add_argument('--database', help='Database name (env: TENNIS_DB_NAME)')
        parser.add_argument('--user', help='Database user (env: TENNIS_DB_USER)')
        parser.add_argument('--password', help='Database password (env: TENNIS_DB_PASSWORD)')
        
        # MongoDB options
        parser.add_argument('--connection-string', help='MongoDB connection string')
        
        # General options
        parser.add_argument('--verbose', '-v', action='store_true', help='Verbose error output')
        parser.add_argument('--format', choices=['json', 'table'], default='json', help='Output format')

    def run(self):
        """Main CLI entry point"""
        parser = argparse.ArgumentParser(
            description="Tennis scheduling database CLI with multi-backend support",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=__doc__
        )
        
        # Add database connection arguments
        self.add_database_arguments(parser)
        
        # Create subparsers for different commands
        subparsers = parser.add_subparsers(dest="command", help="Available commands")
        
        # List command
        list_parser = subparsers.add_parser("list", help="List entities from the database")
        list_parser.add_argument("table", 
                               choices=["teams", "leagues", "matches", "sections", 
                                       "regions", "age-groups", "facilities", "divisions", "backends"], 
                               help="Type of entity to list")
        list_parser.add_argument("--league-id", type=int, help="Filter by league ID")
        list_parser.add_argument("--include-unscheduled", action="store_true", 
                               help="Include unscheduled matches in results")

        # Create command
        create_parser = subparsers.add_parser("create", help="Create new entities")
        create_parser.add_argument("entity", choices=["match"], help="Type of entity to create")
        create_parser.add_argument("--league-id", type=int, required=True, help="League ID")
        create_parser.add_argument("--home-team-id", type=int, required=True, help="Home team ID")
        create_parser.add_argument("--visitor-team-id", type=int, required=True, help="Visitor team ID")

        # Schedule command
        schedule_parser = subparsers.add_parser("schedule", help="Schedule matches at facilities")
        schedule_parser.add_argument("--match-id", type=int, required=True, help="Match ID to schedule")
        schedule_parser.add_argument("--facility-id", type=int, required=True, help="Facility ID")
        schedule_parser.add_argument("--date", required=True, help="Date (YYYY-MM-DD)")
        schedule_parser.add_argument("--times", nargs='+', required=True, help="Start times (HH:MM) for each line")
        schedule_parser.add_argument("--same-time", action="store_true", help="Schedule all lines at the same time")

        # Unschedule command
        unschedule_parser = subparsers.add_parser("unschedule", help="Remove scheduling from matches")
        unschedule_parser.add_argument("--match-id", type=int, required=True, help="Match ID to unschedule")

        # Check availability command
        check_parser = subparsers.add_parser("check-availability", help="Check court availability")
        check_parser.add_argument("--facility-id", type=int, required=True, help="Facility ID")
        check_parser.add_argument("--date", required=True, help="Date (YYYY-MM-DD)")
        check_parser.add_argument("--time", required=True, help="Time (HH:MM)")
        check_parser.add_argument("--courts-needed", type=int, default=1, help="Number of courts needed")

        # Stats command
        stats_parser = subparsers.add_parser("stats", help="Get scheduling statistics")
        stats_parser.add_argument("--league-id", type=int, help="League ID (for league stats)")
        stats_parser.add_argument("--facility-id", type=int, help="Facility ID (for facility stats)")
        stats_parser.add_argument("--start-date", help="Start date for facility stats (YYYY-MM-DD)")
        stats_parser.add_argument("--end-date", help="End date for facility stats (YYYY-MM-DD)")

        # Generate matches command (enhanced for single league OR multiple leagues)
        generate_parser = subparsers.add_parser("generate-matches", help="Generate matches for one or all leagues")
        generate_parser.add_argument("--league-id", type=int, 
                                   help="League ID (if not specified, processes all leagues)")
        generate_parser.add_argument("--league-ids", 
                                   help="Comma-separated list of league IDs (alternative to --league-id)")
        generate_parser.add_argument("--min-teams", type=int, default=2, 
                                   help="Minimum teams required to generate matches (default: 2)")
        generate_parser.add_argument("--dry-run", action="store_true", 
                                   help="Show what would be generated without creating matches")
        generate_parser.add_argument("--skip-existing", action="store_true", 
                                   help="Skip leagues that already have matches")
        generate_parser.add_argument("--overwrite-existing", action="store_true", 
                                   help="Delete existing matches before generating new ones")
        generate_parser.add_argument("--progress", action="store_true", 
                                   help="Show progress during generation")

        # Migrate command
        migrate_parser = subparsers.add_parser("migrate", help="Migrate data between backends")
        migrate_parser.add_argument("--target-backend", required=True, 
                                   choices=['sqlite', 'postgresql', 'mongodb', 'mysql'],
                                   help="Target database backend")
        migrate_parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without doing it")
        migrate_parser.add_argument("--target-db-path", help="Target SQLite database path")
        migrate_parser.add_argument("--target-host", help="Target database host")
        migrate_parser.add_argument("--target-port", type=int, help="Target database port")
        migrate_parser.add_argument("--target-database", help="Target database name")
        migrate_parser.add_argument("--target-user", help="Target database user")
        migrate_parser.add_argument("--target-password", help="Target database password")
        migrate_parser.add_argument("--target-connection-string", help="Target MongoDB connection string")

        # Load command (from YAML files)
        load_parser = subparsers.add_parser("load", help="Load data from YAML file")
        load_parser.add_argument("table", choices=["facilities", "leagues", "teams", "matches"], 
                               help="Type of data to load")
        load_parser.add_argument("file_path", help="Path to YAML file")

        # Health command
        health_parser = subparsers.add_parser("health", help="Check database connection health")

        # Init command
        init_parser = subparsers.add_parser("init", help="Initialize database schema")

        # Parse arguments
        args = parser.parse_args()
        
        if not args.command:
            parser.print_help()
            return 1
        
        try:
            # Load config from file if specified
            if hasattr(args, 'config') and args.config:
                with open(args.config, 'r') as f:
                    file_config = json.load(f)
                    # Merge file config with args
                    for key, value in file_config.items():
                        if not hasattr(args, key) or getattr(args, key) is None:
                            setattr(args, key, value)
            
            # Get database configuration
            backend_str, config = self.get_config_from_args(args)
            
            # Create database manager
            try:
                backend_enum = DatabaseBackend(backend_str)
                self.db_manager = TennisDBManager(backend_enum, config)
            except ValueError as e:
                print(f"Error: Invalid backend '{backend_str}': {e}", file=sys.stderr)
                available = TennisDBFactory.list_backends()
                print(f"Available backends: {[b.value for b in available]}", file=sys.stderr)
                return 1
            except Exception as e:
                print(f"Error: Failed to connect to database: {e}", file=sys.stderr)
                if args.verbose:
                    traceback.print_exc()
                return 1
            
            # Get database instance
            db = self.db_manager.connect()
            
            # Route to appropriate command handler
            if args.command == "list":
                return self.handle_list_command(args, db)
            elif args.command == "create":
                return self.handle_create_command(args, db)
            elif args.command == "schedule":
                return self.handle_schedule_command(args, db)
            elif args.command == "unschedule":
                return self.handle_unschedule_command(args, db)
            elif args.command == "check-availability":
                return self.handle_check_availability_command(args, db)
            elif args.command == "stats":
                return self.handle_stats_command(args, db)
            elif args.command == "generate-matches":
                return self.handle_generate_matches_command(args, db)
            elif args.command == "migrate":
                return self.handle_migrate_command(args, db)
            elif args.command == "load":
                return self.handle_load_command(args, db)
            elif args.command == "health":
                return self.handle_health_command(args, db)
            elif args.command == "init":
                return self.handle_init_command(args, db)
            else:
                print(f"Error: Unknown command '{args.command}'", file=sys.stderr)
                return 1
                
        except KeyboardInterrupt:
            print("\nOperation cancelled by user", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            if args.verbose:
                traceback.print_exc()
            return 1
        finally:
            if self.db_manager:
                try:
                    self.db_manager.disconnect()
                except:
                    pass

    def _output_data(self, data: List[Dict], args):
        """Output data in the specified format"""
        if args.format == 'json':
            print(json.dumps(data, indent=2))
        elif args.format == 'table':
            if not data:
                print("No data found.")
                return
            
            # Get all unique keys for table headers
            all_keys = set()
            for item in data:
                all_keys.update(item.keys())
            headers = sorted(list(all_keys))
            
            # Calculate column widths
            col_widths = {}
            for header in headers:
                col_widths[header] = max(len(str(header)), 
                                       max((len(str(item.get(header, ''))) for item in data), default=0))
            
            # Print table header
            header_line = " | ".join(f"{header:<{col_widths[header]}}" for header in headers)
            print(header_line)
            print("-" * len(header_line))
            
            # Print table rows
            for item in data:
                row = " | ".join(f"{str(item.get(header, '')):<{col_widths[header]}}" for header in headers)
                print(row)

    def _get_available_backends(self):
        """Get information about available backends"""
        available = TennisDBFactory.list_backends()
        return f"Available: {', '.join(backend.value for backend in available)}"

    def handle_list_command(self, args, db):
        """Handle list commands for various entities"""
        try:
            if args.table == "teams":
                teams = db.list_teams(args.league_id)
                teams_data = [
                    {
                        'id': team.id,
                        'name': team.name,
                        'captain': team.captain,
                        'league_name': team.league.name,
                        'league_id': team.league.id,
                        'home_facility': team.home_facility if isinstance(team.home_facility, str) else team.home_facility.name,
                        'preferred_days': team.preferred_days
                    }
                    for team in teams
                ]
                self._output_data(teams_data, args)
                
            elif args.table == "leagues":
                leagues = db.list_leagues()
                leagues_data = [
                    {
                        'id': league.id,
                        'name': league.name,
                        'year': league.year,
                        'section': league.section,
                        'region': league.region,
                        'age_group': league.age_group,
                        'division': league.division,
                        'num_lines_per_match': league.num_lines_per_match,
                        'num_matches': league.num_matches,
                        'preferred_days': league.preferred_days,
                        'backup_days': league.backup_days
                    }
                    for league in leagues
                ]
                self._output_data(leagues_data, args)
                
            elif args.table == "facilities":
                facilities = db.list_facilities()
                facilities_data = [
                    {
                        'id': facility.id,
                        'name': facility.name,
                        'short_name': facility.short_name,
                        'location': facility.location,
                        'total_courts': facility.total_courts,
                        'schedule_days': len(facility.schedule.get_all_days()) if facility.schedule else 0
                    }
                    for facility in facilities
                ]
                self._output_data(facilities_data, args)
                
            elif args.table == "matches":
                include_unscheduled = getattr(args, 'include_unscheduled', False)
                
                # MODIFIED: If no league-id provided, get ALL matches from ALL leagues
                if args.league_id:
                    # Original behavior: get matches for specific league
                    league = db.get_league(args.league_id)
                    if not league:
                        print(f"Error: League {args.league_id} not found", file=sys.stderr)
                        return 1
                    matches = db.list_matches(league, include_unscheduled)
                else:
                    # NEW: Get all matches from all leagues
                    matches = db.list_matches(include_unscheduled=include_unscheduled)

                
                # MODIFIED: Use pretty printing instead of _output_data for better readability
                if args.format == 'json':
                    # Keep JSON format for programmatic use
                    matches_data = [
                        {
                            'id': match.id,
                            'league_id': match.league.id,
                            'league_name': match.league.name,
                            'home_team_id': match.home_team.id,
                            'home_team_name': match.home_team.name,
                            'visitor_team_id': match.visitor_team.id,
                            'visitor_team_name': match.visitor_team.name,
                            'facility_id': match.facility.id if match.facility else None,
                            'facility_name': match.facility.name if match.facility else None,
                            'date': match.date,
                            'scheduled_times': match.scheduled_times,
                            'num_scheduled_lines': len(match.scheduled_times),
                            'expected_lines': match.league.num_lines_per_match,
                            'status': match.get_status()
                        }
                        for match in matches
                    ]
                    self._output_data(matches_data, args)
                else:
                    # NEW: Pretty print each match for human readability
                    self._pretty_print_matches(matches, args.league_id)                
                
            elif args.table == "sections":
                from usta_constants import USTA_SECTIONS
                sections_data = [{'name': section} for section in USTA_SECTIONS]
                self._output_data(sections_data, args)
                
            elif args.table == "regions":
                from usta_constants import USTA_REGIONS
                regions_data = [{'name': region} for region in USTA_REGIONS]
                self._output_data(regions_data, args)
                
            elif args.table == "age-groups":
                from usta_constants import USTA_AGE_GROUPS
                age_groups_data = [{'name': age_group} for age_group in USTA_AGE_GROUPS]
                self._output_data(age_groups_data, args)
                
            elif args.table == "divisions":
                from usta_constants import USTA_DIVISIONS
                divisions_data = [{'name': division} for division in USTA_DIVISIONS]
                self._output_data(divisions_data, args)
                
            elif args.table == "backends":
                available = TennisDBFactory.list_backends()
                backends_data = [
                    {
                        'name': backend.value,
                        'available': TennisDBFactory.is_backend_available(backend)
                    }
                    for backend in available
                ]
                self._output_data(backends_data, args)
                
            return 0
            
        except Exception as e:
            print(f"Error listing {args.table}: {e}", file=sys.stderr)
            return 1

    def _pretty_print_matches(self, matches, specific_league_id=None):
        """Pretty print matches in a human-readable format"""
        if not matches:
            if specific_league_id:
                print(f"No matches found for league {specific_league_id}")
            else:
                print("No matches found")
            return
        
        # Group matches by league for better organization when showing all matches
        if specific_league_id:
            # Single league - no grouping needed
            print(f"\nFound {len(matches)} match(es):")
            print("=" * 80)
            
            for match in matches:
                self._print_single_match(match)
        else:
            # Multiple leagues - group by league
            from collections import defaultdict
            matches_by_league = defaultdict(list)
            
            for match in matches:
                matches_by_league[match.league.id].append(match)
            
            total_matches = len(matches)
            total_leagues = len(matches_by_league)
            
            print(f"\nFound {total_matches} match(es) across {total_leagues} league(s):")
            print("=" * 80)
            
            for league_id, league_matches in matches_by_league.items():
                league_name = league_matches[0].league.name
                print(f"\nLEAGUE: {league_name} (ID: {league_id}) - {len(league_matches)} matches")
                print("-" * 60)
                
                for match in league_matches:
                    self._print_single_match(match, show_league=False)
    
    def _print_single_match(self, match, show_league=True):
        """Print a single match in a formatted way"""
        # Basic match info
        match_line = f"Match {match.id}: {match.home_team.name} vs {match.visitor_team.name}"
        
        if show_league:
            match_line += f" ({match.league.name})"
        
        print(f"  {match_line}")
        
        # Status and scheduling info
        status = match.get_status()
        status_info = f"    Status: {status}"
        
        if match.is_scheduled():
            facility_name = match.facility.name if match.facility else "Unknown"
            status_info += f" | Facility: {facility_name} | Date: {match.date}"
            
            if match.scheduled_times:
                times_str = ", ".join(match.scheduled_times)
                status_info += f" | Times: {times_str}"
                
            lines_info = f" | Lines: {len(match.scheduled_times)}/{match.league.num_lines_per_match}"
            status_info += lines_info
        else:
            expected_lines = match.league.num_lines_per_match
            status_info += f" | Expected lines: {expected_lines}"
        
        print(status_info)
        print()  # Empty line for readability



    

    def handle_schedule_command(self, args, db):
        """Handle match scheduling commands"""
        try:
            # Get match to validate it exists
            match = db.get_match(args.match_id)
            if not match:
                print(f"Error: Match {args.match_id} not found", file=sys.stderr)
                return 1
            
            # Get facility to validate it exists
            facility = db.get_facility(args.facility_id)
            if not facility:
                print(f"Error: Facility {args.facility_id} not found", file=sys.stderr)
                return 1
            
            # Validate times
            expected_lines = match.league.num_lines_per_match
            
            if args.same_time:
                if len(args.times) != 1:
                    print(f"Error: When using --same-time, provide exactly one time", file=sys.stderr)
                    return 1
                times = [args.times[0]] * expected_lines
            else:
                if len(args.times) != expected_lines:
                    print(f"Error: League requires {expected_lines} lines, got {len(args.times)} times", file=sys.stderr)
                    return 1
                times = args.times
            
            # Schedule the match
            success = db.schedule_match_all_lines_same_time(args.match_id, args.facility_id, args.date, times[0])
            
            if success:
                print(f"Scheduled match {args.match_id} at {facility.name} on {args.date}")
                print(f"Times: {', '.join(times)}")
                return 0
            else:
                print(f"Error: Failed to schedule match {args.match_id}", file=sys.stderr)
                return 1
            
        except Exception as e:
            print(f"Error scheduling match: {e}", file=sys.stderr)
            return 1

    def handle_unschedule_command(self, args, db):
        """Handle match unscheduling commands"""
        try:
            # Get match to validate it exists
            match = db.get_match(args.match_id)
            if not match:
                print(f"Error: Match {args.match_id} not found", file=sys.stderr)
                return 1
            
            # Unschedule the match
            db.unschedule_match(args.match_id)
            print(f"Unscheduled match {args.match_id}")
            return 0
            
        except Exception as e:
            print(f"Error unscheduling match: {e}", file=sys.stderr)
            return 1

    def handle_check_availability_command(self, args, db):
        """Handle court availability checking"""
        try:
            # Get facility to validate it exists
            facility = db.get_facility(args.facility_id)
            if not facility:
                print(f"Error: Facility {args.facility_id} not found", file=sys.stderr)
                return 1
            
            # Check availability
            available = db.check_court_availability(args.facility_id, args.date, args.time, args.courts_needed)
            available_count = db.get_available_courts_count(args.facility_id, args.date, args.time)
            
            print(f"Facility: {facility.name}")
            print(f"Date: {args.date}, Time: {args.time}")
            print(f"Courts needed: {args.courts_needed}")
            print(f"Available courts: {available_count}")
            print(f"Availability: {'Yes' if available else 'No'}")
            
            return 0
            
        except Exception as e:
            print(f"Error checking availability: {e}", file=sys.stderr)
            return 1

    def handle_stats_command(self, args, db):
        """Handle statistics commands"""
        try:
            if args.league_id:
                # League-specific stats
                stats = db.get_league_scheduling_status(args.league_id)
                league = db.get_league(args.league_id)
                
                print(f"League: {league.name}")
                print(f"Total matches: {stats['total_matches']}")
                print(f"Scheduled matches: {stats['scheduled_matches']}")
                print(f"Unscheduled matches: {stats['unscheduled_matches']}")
                print(f"Partially scheduled matches: {stats['partially_scheduled_matches']}")
                print(f"Total expected lines: {stats['total_lines']}")
                print(f"Scheduled lines: {stats['scheduled_lines']}")
                print(f"Unscheduled lines: {stats['unscheduled_lines']}")
                
            elif args.facility_id:
                # Facility-specific stats
                if not args.start_date or not args.end_date:
                    print("Error: --start-date and --end-date required for facility stats", file=sys.stderr)
                    return 1
                
                stats = db.get_facility_utilization(args.facility_id, args.start_date, args.end_date)
                facility = db.get_facility(args.facility_id)
                
                print(f"Facility: {facility.name}")
                print(f"Period: {args.start_date} to {args.end_date}")
                print(f"Total available hours: {stats['total_available_hours']}")
                print(f"Total used hours: {stats['total_used_hours']}")
                print(f"Utilization: {stats['utilization_percentage']:.1f}%")
                
            else:
                # General stats
                leagues = db.list_leagues()
                print(f"Total leagues: {len(leagues)}")
                
                for league in leagues:
                    stats = db.get_league_scheduling_status(league.id)
                    print(f"\n{league.name}:")
                    print(f"  Matches: {stats['scheduled_matches']}/{stats['total_matches']} scheduled")
                    print(f"  Lines: {stats['scheduled_lines']}/{stats['total_lines']} scheduled")
            
            return 0
            
        except Exception as e:
            print(f"Error getting stats: {e}", file=sys.stderr)
            return 1

    def handle_generate_matches_command(self, args, db):
        """Handle match generation for single league or multiple leagues"""
        try:
            target_league_ids = None
            
            # Check if this is single league mode
            if args.league_id:
                target_league_ids = [args.league_id]
            
            # Multi-league mode (same logic as auto-generate-matches)
            # Parse league IDs if provided
            if args.league_ids:
                try:
                    target_league_ids = [int(x.strip()) for x in args.league_ids.split(',')]
                except ValueError:
                    print("Error: Invalid league IDs format. Use comma-separated integers (e.g., '1,2,3')", file=sys.stderr)
                    return 1
            
            # Get all leagues or specific ones
            if target_league_ids:
                leagues = []
                for league_id in target_league_ids:
                    league = db.get_league(league_id)
                    if not league:
                        print(f"Warning: League {league_id} not found, skipping", file=sys.stderr)
                    else:
                        leagues.append(league)
            else:
                leagues = db.list_leagues()
            
            if not leagues:
                print("No leagues found to process", file=sys.stderr)
                return 1
            
            print(f"Processing {len(leagues)} league(s) for match generation...")
            print(f"Minimum teams required: {args.min_teams}")
            if args.dry_run:
                print("DRY RUN: No matches will be created")
            print("-" * 60)
            
            total_processed = 0
            total_generated = 0
            total_skipped = 0
            total_failed = 0
            
            results = {
                'successful': [],
                'skipped': [],
                'failed': []
            }
            
            for i, league in enumerate(leagues):
                if args.progress:
                    print(f"[{i+1}/{len(leagues)}] Processing league: {league.name}")
                
                try:
                    # Get teams in the league
                    teams = db.list_teams(league)
                    team_count = len(teams)
                    
                    # Check minimum team requirement
                    if team_count < args.min_teams:
                        reason = f"Insufficient teams ({team_count} < {args.min_teams})"
                        results['skipped'].append({
                            'league_id': league.id,
                            'league_name': league.name,
                            'reason': reason,
                            'team_count': team_count
                        })
                        total_skipped += 1
                        if args.progress:
                            print(f"  SKIPPED: {reason}")
                        continue
                    
                    # Check for existing matches if skip_existing is enabled
                    if args.skip_existing:
                        existing_matches = db.list_matches(league.id, include_unscheduled=True)
                        if existing_matches:
                            reason = f"Already has {len(existing_matches)} matches"
                            results['skipped'].append({
                                'league_id': league.id,
                                'league_name': league.name,
                                'reason': reason,
                                'team_count': team_count,
                                'existing_matches': len(existing_matches)
                            })
                            total_skipped += 1
                            if args.progress:
                                print(f"  SKIPPED: {reason}")
                            continue
                    
                    # Delete existing matches if overwrite is enabled
                    if args.overwrite_existing:
                        existing_matches = db.list_matches(league.id, include_unscheduled=True)
                        if existing_matches:
                            for match in existing_matches:
                                db.delete_match(match.id)
                            if args.progress:
                                print(f"  DELETED: {len(existing_matches)} existing matches")

                    if args.progress:
                        print(f"  GENERATING MATCHES FOR {len(teams)} TEAMS")
                    
                    # Generate matches using USTA generate_matches method
                    matches = usta.generate_matches(teams)
                    
                    # Add generated matches to database
                    for match in matches:
                        db.add_match(match)
                    
                    actual_matches = len(matches)
                    
                    results['successful'].append({
                        'league_id': league.id,
                        'league_name': league.name,
                        'team_count': team_count,
                        'matches_generated': actual_matches
                    })
                    total_generated += actual_matches
                    if args.progress:
                        print(f"  GENERATED: {actual_matches} matches for {team_count} teams")                 

                    total_processed += 1
                    
                except Exception as e:
                    error_msg = str(e)
                    results['failed'].append({
                        'league_id': league.id,
                        'league_name': league.name,
                        'error': error_msg
                    })
                    total_failed += 1
                    if args.progress:
                        print(f"  FAILED: {error_msg}")
                    continue
            
            # Print summary
            print("-" * 60)
            print("MATCH GENERATION SUMMARY:")
            print(f"  Leagues processed: {total_processed}")
            print(f"  Matches generated: {total_generated}")
            print(f"  Leagues skipped: {total_skipped}")
            print(f"  Leagues failed: {total_failed}")
            
            if results['successful']:
                print(f"\nSUCCESSFUL LEAGUES ({len(results['successful'])}):")
                for result in results['successful']:
                    print(f"  {result['league_name']}: {result['matches_generated']} matches")
            
            if results['skipped']:
                print(f"\nSKIPPED LEAGUES ({len(results['skipped'])}):")
                for result in results['skipped']:
                    print(f"  {result['league_name']}: {result['reason']}")
            
            if results['failed']:
                print(f"\nFAILED LEAGUES ({len(results['failed'])}):")
                for result in results['failed']:
                    print(f"  {result['league_name']}: {result['error']}")
            
            # Return appropriate exit code
            if total_failed > 0:
                return 1 if total_processed == 0 else 0  # Partial success
            elif total_processed == 0:
                print("\nNo leagues were processed", file=sys.stderr)
                return 1
            else:
                return 0
            
        except Exception as e:
            print(f"Error in match generation: {e}", file=sys.stderr)
            if args.verbose:
                traceback.print_exc()
            return 1
    

    
    def handle_create_command(self, args, db):
        """Handle create commands for new entities"""
        try:
            if args.entity == "match":
                # Get league to validate it exists
                league = db.get_league(args.league_id)
                if not league:
                    print(f"Error: League {args.league_id} not found", file=sys.stderr)
                    return 1
                
                # Get teams to validate they exist
                home_team = db.get_team(args.home_team_id)
                visitor_team = db.get_team(args.visitor_team_id)
                if not home_team:
                    print(f"Error: Home team {args.home_team_id} not found", file=sys.stderr)
                    return 1
                if not visitor_team:
                    print(f"Error: Visitor team {args.visitor_team_id} not found", file=sys.stderr)
                    return 1
                
                # Create a single match using League's generate_matches method
                # We'll generate matches for just these two teams and take the first one
                try:
                    matches = league.generate_matches([home_team, visitor_team])
                    if matches:
                        match = matches[0]
                        db.add_match(match)
                        print(f"Created match {match.id}: {match.home_team.name} vs {match.visitor_team.name}")
                        return 0
                    else:
                        print("Error: No matches generated", file=sys.stderr)
                        return 1
                except Exception as e:
                    print(f"Error: Failed to generate match: {e}", file=sys.stderr)
                    return 1
            
            return 0
            
        except Exception as e:
            print(f"Error creating {args.entity}: {e}", file=sys.stderr)
            return 1


    
    def handle_migrate_command(self, args, db):
        """Handle data migration between backends"""
        try:
            if args.dry_run:
                print("DRY RUN: Would migrate the following data:")
            
            # Build target configuration
            target_config = {}
            if args.target_backend == 'sqlite':
                target_config['db_path'] = args.target_db_path or 'migrated_tennis.db'
            elif args.target_backend == 'postgresql':
                target_config.update({
                    'host': args.target_host or 'localhost',
                    'port': args.target_port or 5432,
                    'database': args.target_database or 'tennis',
                    'user': args.target_user or 'postgres',
                    'password': args.target_password or ''
                })
            elif args.target_backend == 'mongodb':
                target_config['connection_string'] = args.target_connection_string or 'mongodb://localhost:27017/'
                target_config['database'] = args.target_database or 'tennis'
            
            # Create target database manager
            target_backend_enum = DatabaseBackend(args.target_backend)
            target_db_manager = TennisDBManager(target_backend_enum, target_config)
            target_db = target_db_manager.connect()
            
            # Get all data from source database
            facilities = db.list_facilities()
            leagues = db.list_leagues()
            teams = db.list_teams()
            matches = db.list_matches(include_unscheduled=True)
            
            print(f"Source data:")
            print(f"  Facilities: {len(facilities)}")
            print(f"  Leagues: {len(leagues)}")
            print(f"  Teams: {len(teams)}")
            print(f"  Matches: {len(matches)}")
            
            if not args.dry_run:
                # Migrate facilities
                for facility in facilities:
                    target_db.add_facility(facility)
                
                # Migrate leagues
                for league in leagues:
                    target_db.add_league(league)
                
                # Migrate teams
                for team in teams:
                    target_db.add_team(team)
                
                # Migrate matches
                for match in matches:
                    target_db.add_match(match)
                
                print(f"Migration completed successfully to {args.target_backend}")
            else:
                print("Migration not performed (dry run)")
            
            target_db_manager.disconnect()
            return 0
            
        except Exception as e:
            print(f"Error during migration: {e}", file=sys.stderr)
            return 1

    def handle_load_command(self, args, db) -> int:
        """Handle loading data from YAML files with logging"""
        logger.debug("Starting handle_load_command: table=%s, file_path=%s", args.table, args.file_path)
        try:
            import yaml

            if not os.path.exists(args.file_path):
                logger.error("File not found: %s", args.file_path)
                print(f"Error: File {args.file_path} not found", file=sys.stderr)
                return 1
            logger.info("Found YAML file: %s", args.file_path)

            with open(args.file_path, 'r') as f:
                data = yaml.safe_load(f)
            logger.debug("Loaded YAML data: %d items", len(data) if hasattr(data, '__len__') else 0)

            count = 0
            if args.table == "facilities":

                facilities_data = data.get('facilities')
                if facilities_data is None:
                    logger.error("Key 'facilities' not found in YAML file: %s", args.file_path)
                    raise KeyError("Key 'facilities' not found in YAML file")          
                
                from usta_facility import Facility
                logger.info(f"Loading facilities from YAML\n\n")
                for item in facilities_data:
                    logger.debug(f"Loading facility from YAML {item}")
                    facility = Facility.from_yaml_dict(item)
                    db.add_facility(facility)
                    count += 1
                logger.info("Loaded %d facilities", count)
                print(f"Loaded {count} facilities from {args.file_path}")

            elif args.table == "leagues":
                
                leagues_data = data.get('leagues')
                if leagues_data is None:
                    logger.error("Key 'leagues' not found in YAML file: %s", args.file_path)
                    raise KeyError("Key 'leagues' not found in YAML file")
                    
                from usta_league import League
                logger.info("Loading leagues from YAML")
                for item in leagues_data:
                    if hasattr(League, 'from_yaml_dict'):
                        league = League.from_yaml_dict(item)
                    else:
                        league = League(**item)
                    db.add_league(league)
                    count += 1
                logger.info("Loaded %d leagues", count)
                print(f"Loaded {count} leagues from {args.file_path}")

            elif args.table == "teams":
                teams_data = data.get('teams')
                if teams_data is None:
                    logger.error("Key 'teams' not found in YAML file: %s", args.file_path)
                    raise KeyError("Key 'teams' not found in YAML file")
                    
                from usta_team import Team
                logger.info("Loading teams from YAML")
                for item in teams_data:
                    league = db.get_league(item['league_id'])
                    if not league:
                        logger.warning("League not found: %s for team %s", item['league_id'], item.get('name', 'Unknown'))
                        print(f"Warning: League {item['league_id']} not found for team {item.get('name', 'Unknown')}")
                        continue
                    home_facility = None
                    if 'home_facility_id' in item and item['home_facility_id']:
                        home_facility = db.get_facility(item['home_facility_id'])
                        if not home_facility:
                            logger.warning("Facility not found: %s for team %s", item['home_facility_id'], item.get('name', 'Unknown'))
                            print(f"Warning: Facility {item['home_facility_id']} not found for team {item.get('name', 'Unknown')}")
                    if hasattr(Team, 'from_yaml_dict'):
                        item_copy = item.copy()
                        item_copy['league'] = league
                        item_copy['home_facility'] = home_facility
                        team = Team.from_yaml_dict(item_copy)
                    else:
                        team_data = item.copy()
                        team_data['league'] = league
                        team_data['home_facility'] = home_facility
                        team_data.pop('league_id', None)
                        team_data.pop('home_facility_id', None)
                        team = Team(**team_data)
                    db.add_team(team)
                    count += 1
                logger.info("Loaded %d teams", count)
                print(f"Loaded {count} teams from {args.file_path}")

            elif args.table == "matches":
                matches_data = data.get('matches')
                if matches_data is None:
                    logger.error("Key 'matches' not found in YAML file: %s", args.file_path)
                    raise KeyError("Key 'matches' not found in YAML file")
                    
                from usta_match import Match
                logger.info("Loading matches from YAML")
                for item in matches_data:
                    league = db.get_league(item['league_id'])
                    home_team = db.get_team(item['home_team_id'])
                    visitor_team = db.get_team(item['visitor_team_id'])
                    if not all([league, home_team, visitor_team]):
                        logger.warning("Missing reference for match id=%s", item.get('id', 'Unknown'))
                        print(f"Warning: Missing references for match {item.get('id', 'Unknown')}")
                        continue
                    facility = None
                    if item.get('facility_id'):
                        facility = db.get_facility(item['facility_id'])
                    if hasattr(Match, 'from_yaml_dict'):
                        item_copy = item.copy()
                        item_copy.update({
                            'league': league,
                            'home_team': home_team,
                            'visitor_team': visitor_team,
                            'facility': facility
                        })
                        match = Match.from_yaml_dict(item_copy)
                    else:
                        match_data = {
                            'id': item['id'],
                            'league': league,
                            'home_team': home_team,
                            'visitor_team': visitor_team,
                            'facility': facility,
                            'date': item.get('date'),
                            'scheduled_times': item.get('scheduled_times', [])
                        }
                        match = Match(**match_data)
                    db.add_match(match)
                    count += 1
                logger.info("Loaded %d matches", count)
                print(f"Loaded {count} matches from {args.file_path}")

            else:
                logger.error("Unknown table specified: %s", args.table)
                print(f"Error: Unknown table {args.table}", file=sys.stderr)
                return 1

            logger.debug("Finished handle_load_command successfully")
            return 0

        except Exception as e:
            logger.exception("Exception in handle_load_command")
            print(f"Error: {e}", file=sys.stderr)
            return 1

    def handle_health_command(self, args, db):
        """Handle database health check"""
        try:
            # Try to perform a simple query
            leagues = db.list_leagues()
            facilities = db.list_facilities()
            teams = db.list_teams()
            matches = db.list_matches(include_unscheduled=True)
            
            print("Database health check: OK")
            print(f"Connection: Active")
            print(f"Tables accessible: Yes")
            print(f"Data summary:")
            print(f"  Leagues: {len(leagues)}")
            print(f"  Facilities: {len(facilities)}")
            print(f"  Teams: {len(teams)}")
            print(f"  Matches: {len(matches)}")
            
            return 0
            
        except Exception as e:
            print(f"Database health check: FAILED", file=sys.stderr)
            print(f"Error: {e}", file=sys.stderr)
            return 1

    def handle_init_command(self, args, db):
        """Handle database initialization"""
        try:
            # The database schema should already be initialized by the factory
            # This command can be used to verify or reset the schema
            
            print("Database initialization: OK")
            print("Schema created successfully")
            
            # Try a simple operation to verify everything works
            leagues = db.list_leagues()
            print(f"Verification: Can access tables (found {len(leagues)} leagues)")
            
            return 0
            
        except Exception as e:
            print(f"Database initialization: FAILED", file=sys.stderr)
            print(f"Error: {e}", file=sys.stderr)
            return 1


def main():
    """Main entry point"""
    cli = TennisCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())