#!/usr/bin/env python3
"""
Enhanced CLI for tennis scheduling with multi-backend database support.

This CLI provides a unified interface for managing tennis leagues, teams, matches,
and facilities across different database backends (SQLite, PostgreSQL, MongoDB, etc.).

Updated to reflect the removal of the Line class - scheduling is now handled at the 
Match level with scheduled_times arrays.

ENHANCED: generate-matches command now supports both single league and bulk operations.
ENHANCED: auto-schedule command for automatically scheduling unscheduled matches.

Usage examples:
    # Basic database operations
    # SQLite (default) - will create database if it doesn't exist
    python tennis_cli.py --backend sqlite --db-path tennis.db list leagues
    
    # List all matches across all leagues
    python tennis_cli.py --db-path tennis.db list matches
    
    # List matches for specific league
    python tennis_cli.py --db-path tennis.db list matches --league-id 1
    
    # List teams, facilities, etc.
    python tennis_cli.py --db-path tennis.db list teams
    python tennis_cli.py --db-path tennis.db list facilities
    
    # Generate matches for leagues
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

    # Usage examples for delete-matches (only deletes unscheduled matches):
    # 
    # Delete a specific unscheduled match
    # python tennis_cli.py --db-path tennis.db delete-matches --match-id 123
    # 
    # Delete all unscheduled matches for a specific league
    # python tennis_cli.py --db-path tennis.db delete-matches --league-id 1
    # 
    # Delete all unscheduled matches for multiple leagues
    # python tennis_cli.py --db-path tennis.db delete-matches --league-ids 1,2,3
    # 
    # Delete ALL unscheduled matches from the entire database
    # python tennis_cli.py --db-path tennis.db delete-matches
    # 
    # Delete with progress reporting and skip confirmation
    # python tennis_cli.py --db-path tennis.db delete-matches --progress --confirm
    
    # Auto-schedule unscheduled matches
    # Schedule all unscheduled matches in all leagues
    python tennis_cli.py --db-path tennis.db auto-schedule
    
    # Schedule with progress reporting
    python tennis_cli.py --db-path tennis.db auto-schedule --progress
    
    # Schedule specific league
    python tennis_cli.py --db-path tennis.db auto-schedule --league-id 1
    
    # Schedule multiple leagues
    python tennis_cli.py --db-path tennis.db auto-schedule --league-ids 1,2,3
    
    # Test with limited matches
    python tennis_cli.py --db-path tennis.db auto-schedule --max-matches 5 --progress
    
    # Manual match scheduling
    # Schedule a specific match
    python tennis_cli.py --db-path tennis.db schedule --match-id 1 --facility-id 1 --date 2025-07-15 --times 09:00 12:00 15:00
    
    # Schedule all lines at same time
    python tennis_cli.py --db-path tennis.db schedule --match-id 1 --facility-id 1 --date 2025-07-15 --times 09:00 --same-time
    
    # Unschedule a specific match
    python tennis_cli.py --db-path tennis.db unschedule --match-id 123

    # Unschedule all matches for a league
    python tennis_cli.py --db-path tennis.db unschedule --league-id 1
    
    # Unschedule matches from multiple leagues
    python tennis_cli.py --db-path tennis.db unschedule --league-ids 1,2,3
    
    # Unschedule ALL scheduled matches from entire database
    python tennis_cli.py --db-path tennis.db unschedule
    
    # Unschedule with progress and skip confirmation
    python tennis_cli.py --db-path tennis.db unschedule --league-id 1 --progress --confirm
    
    # Check court availability
    python tennis_cli.py --db-path tennis.db check-availability --facility-id 1 --date 2025-07-15 --time 09:00 --courts-needed 3
    
    # Statistics and reporting
    # Get overall stats
    python tennis_cli.py --db-path tennis.db stats
    
    # Get league-specific stats
    python tennis_cli.py --db-path tennis.db stats --league-id 1
    
    # Get facility usage stats
    python tennis_cli.py --db-path tennis.db stats --facility-id 1 --start-date 2025-01-01 --end-date 2025-12-31
    
    # Data management
# Load data from YAML files
    python tennis_cli.py --db-path tennis.db load all_data.yaml
    python tennis_cli.py --db-path tennis.db load facilities.yaml
    python tennis_cli.py --db-path tennis.db load --clear-existing complete_setup.yaml
    
    # Create individual matches
    python tennis_cli.py --db-path tennis.db create match --league-id 1 --home-team-id 1 --visitor-team-id 2
    
    # Database health and initialization
    python tennis_cli.py --db-path tennis.db health
    python tennis_cli.py --db-path tennis.db init
    
    # Multi-backend support
    # From environment variables
    export TENNIS_DB_BACKEND=postgresql
    export TENNIS_DB_HOST=localhost
    python tennis_cli.py generate-matches --league-ids 1,2,3
    
    # PostgreSQL
    python tennis_cli.py --backend postgresql --host localhost --database tennis --user tennis_user list leagues
    
    # Migration between backends
    python tennis_cli.py --db-path source.db migrate --target-backend postgresql --target-host localhost --target-database tennis
    
    # List available backends
    python tennis_cli.py list backends
"""
import traceback
import argparse
import json
import sys
import os
from typing import Dict, Any, Optional, List
import traceback
import logging

from usta import Match, MatchType, League, Team, Facility

logging.basicConfig(
    level=logging.INFO,
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
        parser.add_argument('--format', choices=['json', 'table'], default='table', help='Output format')

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
        list_parser.add_argument('--match-type', 
                       choices=['all', 'scheduled', 'unscheduled'],
                       default="all",
                       help='Type of matches to list (default: all)')

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

        # Auto-schedule command
        auto_schedule_parser = subparsers.add_parser("auto-schedule", help="Automatically schedule unscheduled matches")
        auto_schedule_parser.add_argument("--league-id", type=int, 
                                        help="League ID (if not specified, processes all leagues)")
        auto_schedule_parser.add_argument("--league-ids", 
                                        help="Comma-separated list of league IDs (alternative to --league-id)")
        auto_schedule_parser.add_argument("--prefer-home-facility", action="store_true", default=True,
                                        help="Prefer home team facilities when scheduling (default: True)")
        auto_schedule_parser.add_argument("--progress", action="store_true", 
                                        help="Show progress during scheduling")
        auto_schedule_parser.add_argument("--max-matches", type=int, 
                                        help="Maximum number of matches to schedule (for testing)")

        # Unschedule command (enhanced with league options)
        unschedule_parser = subparsers.add_parser("unschedule", help="Remove scheduling from matches")
        unschedule_parser.add_argument("--match-id", type=int, help="Unschedule a specific match by ID")
        unschedule_parser.add_argument("--league-id", type=int, help="Unschedule all scheduled matches for a specific league")
        unschedule_parser.add_argument("--league-ids", help="Comma-separated list of league IDs to unschedule matches from")
        unschedule_parser.add_argument("--confirm", action="store_true", 
                                     help="Skip confirmation prompt (for automated scripts)")
        unschedule_parser.add_argument("--progress", action="store_true", 
                                     help="Show progress during unscheduling")

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

        # Delete matches command
        delete_parser = subparsers.add_parser("delete-matches", help="Delete matches from the database")
        delete_parser.add_argument("--match-id", type=int, help="Delete a specific match by ID")
        delete_parser.add_argument("--league-id", type=int, help="Delete all matches for a specific league")
        delete_parser.add_argument("--league-ids", help="Comma-separated list of league IDs to delete matches from")

        delete_parser.add_argument("--confirm", action="store_true", 
                                 help="Skip confirmation prompt (for automated scripts)")

        delete_parser.add_argument("--progress", action="store_true", 
                                 help="Show progress during deletion")
        

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
        # # load_parser.add_argument("table", choices=["facilities", "leagues", "teams", "matches"], 
        #                        help="Type of data to load")
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
            elif args.command == "auto-schedule":
                return self.handle_auto_schedule_command(args, db)
            elif args.command == "unschedule":
                return self.handle_unschedule_command(args, db)
            elif args.command == "check-availability":
                return self.handle_check_availability_command(args, db)
            elif args.command == "stats":
                return self.handle_stats_command(args, db)
            elif args.command == "generate-matches":
                return self.handle_generate_matches_command(args, db)

            elif args.command == "delete-matches":
                self._handle_delete_matches(args, db)
            
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
        logger.debug("Starting handle_list_command: table=%s, league_id=%s, format=%s", 
                    args.table, getattr(args, 'league_id', None), args.format)
        
        try:
            if args.table == "teams":
                logger.debug("Listing teams for league_id: %s", args.league_id)
                teams = db.list_teams(args.league_id)
                logger.debug("Found %d teams", len(teams))
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
                logger.debug("Listing all leagues")
                leagues = db.list_leagues()
                logger.debug("Found %d leagues", len(leagues))
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
                logger.debug("Listing all facilities")
                facilities = db.list_facilities()
                logger.debug("Found %d facilities", len(facilities))
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
                logger.debug("Listing matches with match_type: %s, league_id: %s", 
                           getattr(args, 'match_type', 'unknown'), getattr(args, 'league_id', None))
                
                # Check if MatchType is available
                from usta_match import MatchType
                
                try:
                    logger.debug("MatchType class available: %s", MatchType)
                    logger.debug("MatchType.ALL: %s", MatchType.ALL)
                    logger.debug("args.match_type value: %s (type: %s)", args.match_type, type(args.match_type))
                except NameError as e:
                    logger.error("MatchType not available: %s", e)
                    print(f"Error: MatchType class not available: {e}", file=sys.stderr)
                    return 1
                
                # Convert string to enum
                try:
                    logger.debug("Converting match_type string '%s' to enum", args.match_type)
                    match_type = MatchType.from_string(args.match_type)
                    logger.debug("Successfully converted to MatchType: %s", match_type)
                except ValueError as e:
                    logger.error("Failed to convert match_type: %s", e)
                    print(f"Error: {e}")
                    return 1
                except Exception as e:
                    logger.error("Unexpected error converting match_type: %s", e)
                    print(f"Unexpected error: {e}")
                    return 1

                # Get matches based on filters
                if args.league_id:
                    logger.debug("Getting matches for specific league: %d", args.league_id)
                    # Original behavior: get matches for specific league
                    league = db.get_league(args.league_id)
                    if not league:
                        logger.error("League %d not found", args.league_id)
                        print(f"Error: League {args.league_id} not found", file=sys.stderr)
                        return 1
                    logger.debug("Found league: %s", league.name)
                    matches = db.list_matches(league=league, match_type=match_type)
                    logger.debug("Found %d matches for league %s", len(matches), league.name)
                else:
                    logger.debug("Getting all matches from all leagues")
                    # NEW: Get all matches from all leagues
                    matches = db.list_matches(match_type=match_type)
                    logger.debug("Found %d total matches across all leagues", len(matches))

                # Output matches
                if args.format == 'json':
                    logger.debug("Outputting matches in JSON format")
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
                    logger.debug("Outputting matches in pretty print format")
                    # NEW: Pretty print each match for human readability
                    self._pretty_print_matches(matches, args.league_id)                
                
            elif args.table == "sections":
                logger.debug("Listing USTA sections")
                from usta_constants import USTA_SECTIONS
                sections_data = [{'name': section} for section in USTA_SECTIONS]
                logger.debug("Found %d sections", len(sections_data))
                self._output_data(sections_data, args)
                
            elif args.table == "regions":
                logger.debug("Listing USTA regions")
                from usta_constants import USTA_REGIONS
                regions_data = [{'name': region} for region in USTA_REGIONS]
                logger.debug("Found %d regions", len(regions_data))
                self._output_data(regions_data, args)
                
            elif args.table == "age-groups":
                logger.debug("Listing USTA age groups")
                from usta_constants import USTA_AGE_GROUPS
                age_groups_data = [{'name': age_group} for age_group in USTA_AGE_GROUPS]
                logger.debug("Found %d age groups", len(age_groups_data))
                self._output_data(age_groups_data, args)
                
            elif args.table == "divisions":
                logger.debug("Listing USTA divisions")
                from usta_constants import USTA_DIVISIONS
                divisions_data = [{'name': division} for division in USTA_DIVISIONS]
                logger.debug("Found %d divisions", len(divisions_data))
                self._output_data(divisions_data, args)
                
            elif args.table == "backends":
                logger.debug("Listing available backends")
                available = TennisDBFactory.list_backends()
                logger.debug("Found %d backends", len(available))
                backends_data = [
                    {
                        'name': backend.value,
                        'available': TennisDBFactory.is_backend_available(backend)
                    }
                    for backend in available
                ]
                self._output_data(backends_data, args)
            
            else:
                logger.error("Unknown table type: %s", args.table)
                print(f"Error: Unknown table type '{args.table}'", file=sys.stderr)
                return 1
                
            logger.debug("Successfully completed handle_list_command for table: %s", args.table)
            return 0
            
        except Exception as e:
            logger.exception("Exception in handle_list_command: %s", e)
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

    def handle_auto_schedule_command(self, args, db):
        """Handle automatic scheduling of unscheduled matches"""
        try:
            target_league_ids = None
            
            # Parse league IDs if provided
            if args.league_id:
                target_league_ids = [args.league_id]
            elif args.league_ids:
                try:
                    target_league_ids = [int(x.strip()) for x in args.league_ids.split(',')]
                except ValueError:
                    print("Error: Invalid league IDs format. Use comma-separated integers (e.g., '1,2,3')", file=sys.stderr)
                    return 1
            
            # Get leagues to process
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
            
            print(f"Auto-scheduling unscheduled matches for {len(leagues)} league(s)...")
            print(f"Prefer home facilities: {args.prefer_home_facility}")
            print("-" * 60)
            
            total_processed = 0
            total_scheduled = 0
            total_failed = 0
            
            results = {
                'successful': [],
                'failed': [],
                'no_matches': []
            }
            
            for i, league in enumerate(leagues):
                if args.progress:
                    print(f"[{i+1}/{len(leagues)}] Processing league: {league.name}")
                
                try:
                    # Get unscheduled matches for this league
                    unscheduled_matches = db.list_matches(league=league, match_type=MatchType.UNSCHEDULED)
                    
                    if not unscheduled_matches:
                        results['no_matches'].append({
                            'league_id': league.id,
                            'league_name': league.name
                        })
                        if args.progress:
                            print(f"  No unscheduled matches found")
                        continue
                    
                    # Apply max_matches limit if specified
                    if args.max_matches and len(unscheduled_matches) > args.max_matches:
                        unscheduled_matches = unscheduled_matches[:args.max_matches]
                        if args.progress:
                            print(f"  Limited to {args.max_matches} matches for testing")
                    
                    if args.progress:
                        print(f"  Found {len(unscheduled_matches)} unscheduled matches")
                    
                    # Use the database's auto_schedule_matches method
                    scheduling_result = db.auto_schedule_matches(unscheduled_matches)
                    
                    scheduled_count = scheduling_result.get('scheduled_count', 0)
                    failed_count = scheduling_result.get('failed_count', 0)
                    
                    results['successful'].append({
                        'league_id': league.id,
                        'league_name': league.name,
                        'total_matches': len(unscheduled_matches),
                        'scheduled_count': scheduled_count,
                        'failed_count': failed_count,
                        'details': scheduling_result
                    })
                    
                    total_scheduled += scheduled_count
                    total_failed += failed_count
                    total_processed += 1
                    
                    if args.progress:
                        print(f"  SCHEDULED: {scheduled_count}/{len(unscheduled_matches)} matches")
                        if failed_count > 0:
                            print(f"  FAILED: {failed_count} matches could not be scheduled")
                    
                except Exception as e:
                    error_msg = str(e)
                    results['failed'].append({
                        'league_id': league.id,
                        'league_name': league.name,
                        'error': error_msg
                    })
                    if args.progress:
                        print(f"  ERROR: {error_msg}")
                    continue
            
            # Print summary
            print("-" * 60)
            print("AUTO-SCHEDULING SUMMARY:")
            print(f"  Leagues processed: {total_processed}")
            print(f"  Matches scheduled: {total_scheduled}")
            print(f"  Matches failed: {total_failed}")
            print(f"  Leagues with no unscheduled matches: {len(results['no_matches'])}")
            
            if results['successful']:
                print(f"\nSUCCESSFUL LEAGUES ({len(results['successful'])}):")
                for result in results['successful']:
                    success_rate = (result['scheduled_count'] / result['total_matches'] * 100) if result['total_matches'] > 0 else 0
                    print(f"  {result['league_name']}: {result['scheduled_count']}/{result['total_matches']} matches ({success_rate:.1f}%)")
            
            if results['no_matches']:
                print(f"\nLEAGUES WITH NO UNSCHEDULED MATCHES ({len(results['no_matches'])}):")
                for result in results['no_matches']:
                    print(f"  {result['league_name']}: All matches already scheduled")
            
            if results['failed']:
                print(f"\nFAILED LEAGUES ({len(results['failed'])}):")
                for result in results['failed']:
                    print(f"  {result['league_name']}: {result['error']}")
            
            # Return appropriate exit code
            if total_failed > 0 and total_scheduled == 0:
                return 1  # Complete failure
            elif total_processed == 0:
                print("\nNo leagues were processed", file=sys.stderr)
                return 1
            else:
                return 0  # Success or partial success
            
        except Exception as e:
            print(f"Error in auto-scheduling: {e}", file=sys.stderr)
            if args.verbose:
                traceback.print_exc()
            return 1

    def handle_unschedule_command(self, args, db):
        """Handle match unscheduling commands - enhanced with league support"""
        try:
            matches_to_unschedule = []
            
            if args.match_id:
                # Unschedule specific match
                match = db.get_match(args.match_id)
                if not match:
                    print(f"❌ Match with ID {args.match_id} not found")
                    return 1
                if not match.is_scheduled():
                    print(f"❌ Match {args.match_id} is not scheduled - nothing to unschedule")
                    return 1
                matches_to_unschedule.append(match)
                
            elif args.league_id or args.league_ids:
                # Unschedule scheduled matches from specific league(s)
                league_ids = []
                if args.league_id:
                    league_ids = [args.league_id]
                elif args.league_ids:
                    try:
                        league_ids = [int(lid.strip()) for lid in args.league_ids.split(',')]
                    except ValueError:
                        print("❌ Error: Invalid league IDs format. Use comma-separated integers.")
                        return 1
                
                # Collect scheduled matches from all specified leagues
                for league_id in league_ids:
                    league = db.get_league(league_id)
                    if not league:
                        print(f"❌ Warning: League with ID {league_id} not found")
                        continue
                    
                    # Get scheduled matches for this league
                    league_matches = db.list_matches(league=league, match_type=MatchType.SCHEDULED)

                    if league_matches:
                        matches_to_unschedule.extend(league_matches)
            
            else:
                # No specific match or league specified - unschedule ALL scheduled matches
                print("🔍 No specific match or league specified - finding all scheduled matches...")
                all_matches = db.list_matches(league=None, match_type=MatchType.SCHEDULED)

                if all_matches:
                    matches_to_unschedule.extend(all_matches)
            
            if not matches_to_unschedule:
                print("📭 No scheduled matches found matching the specified criteria")
                return 0
            
            # Display what will be unscheduled
            print(f"\n🎯 Found {len(matches_to_unschedule)} scheduled match(es) to unschedule:")
            print("-" * 60)
            
            unscheduled_count = 0
            
            for match in matches_to_unschedule:
                facility_info = f" at {match.facility.name}" if match.facility else ""
                date_info = f" on {match.date}" if match.date else ""
                times_info = f" at {', '.join(match.scheduled_times)}" if match.scheduled_times else ""
                
                print(f"  Match {match.id}: {match.home_team.name} vs {match.visitor_team.name}")
                print(f"    League: {match.league.name}")
                print(f"    Currently: SCHEDULED{facility_info}{date_info}{times_info}")
            
            print("-" * 60)
            print(f"Summary: {len(matches_to_unschedule)} scheduled matches")
            
            # Confirmation prompt (unless --confirm is used)
            if not args.confirm:
                if args.match_id:
                    confirmation_msg = f"\n⚠️  This will remove scheduling from match {args.match_id}"
                elif args.league_id or args.league_ids:
                    confirmation_msg = f"\n⚠️  This will remove scheduling from {len(matches_to_unschedule)} match(es) in the specified league(s)"
                else:
                    confirmation_msg = f"\n⚠️  This will remove scheduling from ALL {len(matches_to_unschedule)} scheduled matches in the database"
                
                print(confirmation_msg)
                response = input("Are you sure you want to continue? (yes/no): ")
                if response.lower() not in ['yes', 'y']:
                    print("❌ Operation cancelled")
                    return 0
            
            # Unschedule matches
            print(f"\n📅 Unscheduling {len(matches_to_unschedule)} match(es)...")
            
            for i, match in enumerate(matches_to_unschedule, 1):
                try:
                    if args.progress:
                        print(f"  Unscheduling match {match.id} ({i}/{len(matches_to_unschedule)})")
                    
                    # Use the database's unschedule method
                    db.match_manager.unschedule_match(match)
                    unscheduled_count += 1
                    
                except Exception as e:
                    print(f"❌ Error unscheduling match {match.id}: {e}")
            
            # Final summary
            print(f"\n✅ Successfully unscheduled {unscheduled_count}/{len(matches_to_unschedule)} match(es)")
            
            if unscheduled_count != len(matches_to_unschedule):
                failed_count = len(matches_to_unschedule) - unscheduled_count
                print(f"⚠️  {failed_count} match(es) could not be unscheduled")
                return 1
            
            return 0
            
        except Exception as e:
            print(f"❌ Error during match unscheduling: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
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

        from match_generator import MatchGenerator

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
                        existing_matches = db.list_matches(league=league, match_type=MatchType.ALL)
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
                        existing_matches = db.list_matches(league=league)
                        if existing_matches:
                            for match in existing_matches:
                                db.delete_match(match.id)
                            if args.progress:
                                print(f"  DELETED: {len(existing_matches)} existing matches")

                    if args.progress:
                        print(f"  GENERATING MATCHES FOR {len(teams)} TEAMS")
                    
                    # Generate matches using USTA generate_matches method
                    match_generator = MatchGenerator()                    
                    matches = match_generator.generate_matches(teams=teams, league=league)

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
            matches = db.list_matches()
            
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
        """Handle loading data from YAML files using db.import_from_yaml"""
        logger.debug("Starting handle_load_command: file_path=%s", args.file_path)
        try:
            if not os.path.exists(args.file_path):
                logger.error("File not found: %s", args.file_path)
                print(f"Error: File {args.file_path} not found", file=sys.stderr)
                return 1
            
            logger.info("Importing from YAML file: %s", args.file_path)
            
            # Use the database's built-in import function
            success = db.import_from_yaml(args.file_path)
            
            if success:
                print(f"Successfully imported data from {args.file_path}")
                logger.info("Successfully imported data from %s", args.file_path)
            else:
                print(f"Failed to import data from {args.file_path}", file=sys.stderr)
                logger.error("Failed to import data from %s", args.file_path)
                return 1
                
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
            matches = db.list_matches()
            
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

    def _handle_delete_matches(self, args, db):
        """Handle delete-matches command - enhanced to delete all unscheduled matches when no args provided"""    
        try:
            matches_to_delete = []
            
            if args.match_id:
                # Delete specific match
                match = db.get_match(args.match_id)
                if not match:
                    print(f"❌ Match with ID {args.match_id} not found")
                    return
                
                # Only delete if it's unscheduled (unless explicitly allowing scheduled matches)
                if match.is_scheduled():
                    print(f"❌ Match {args.match_id} is scheduled. Only unscheduled matches can be deleted.")
                    print("    Use 'unschedule' command first if you want to remove this match.")
                    return
                
                matches_to_delete.append(match)
                
            elif args.league_id or args.league_ids:
                # Delete matches from specific league(s)
                league_ids = []
                if args.league_id:
                    league_ids = [args.league_id]
                elif args.league_ids:
                    try:
                        league_ids = [int(lid.strip()) for lid in args.league_ids.split(',')]
                    except ValueError:
                        print("❌ Error: Invalid league IDs format. Use comma-separated integers.")
                        return
                
                # Collect matches from all specified leagues
                for league_id in league_ids:
                    league = db.get_league(league_id)
                    if not league:
                        print(f"❌ Warning: League with ID {league_id} not found")
                        continue
                    
                    # Get unscheduled matches for this league
                    league_matches = db.list_matches(league=league, match_type=MatchType.UNSCHEDULED)
                    matches_to_delete.extend(league_matches)
            
            else:
                # No specific match or league specified - delete ALL UNSCHEDULED matches
                print("🔍 No specific match or league specified - finding all unscheduled matches...")
                unscheduled_matches = db.list_matches(match_type=MatchType.UNSCHEDULED)
                matches_to_delete.extend(unscheduled_matches)
            
            if not matches_to_delete:
                print("📭 No matches found matching the specified criteria")
                return
            
            # Display what will be deleted
            print(f"\n🎯 Found {len(matches_to_delete)} match(es) to delete:")
            print("-" * 60)
            
            deleted_count = 0
            scheduled_count = 0
            unscheduled_count = 0
            
            for match in matches_to_delete:
                status = "SCHEDULED" if match.is_scheduled() else "UNSCHEDULED"
                facility_info = f" at {match.facility.name}" if match.facility else ""
                date_info = f" on {match.date}" if match.date else ""
                
                print(f"  Match {match.id}: {match.home_team.name} vs {match.visitor_team.name}")
                print(f"    League: {match.league.name}")
                print(f"    Status: {status}{facility_info}{date_info}")
                
                if match.is_scheduled():
                    scheduled_count += 1
                else:
                    unscheduled_count += 1
            
            print("-" * 60)
            print(f"Summary: {scheduled_count} scheduled, {unscheduled_count} unscheduled")
            
            # Confirmation prompt (unless --confirm is used)
            if not args.confirm:
                if args.match_id:
                    confirmation_msg = f"\n⚠️  This will permanently delete match {args.match_id}"
                elif args.league_id or args.league_ids:
                    if scheduled_count > 0 and unscheduled_count > 0:
                        confirmation_msg = f"\n⚠️  This will permanently delete {len(matches_to_delete)} match(es) from the specified league(s)"
                    elif scheduled_count > 0:
                        confirmation_msg = f"\n⚠️  This will permanently delete {scheduled_count} scheduled match(es) from the specified league(s)"
                    else:
                        confirmation_msg = f"\n⚠️  This will permanently delete {unscheduled_count} unscheduled match(es) from the specified league(s)"
                else:
                    if scheduled_count > 0 and unscheduled_count > 0:
                        confirmation_msg = f"\n⚠️  This will permanently delete ALL {len(matches_to_delete)} matches in the database"
                    elif scheduled_count > 0:
                        confirmation_msg = f"\n⚠️  This will permanently delete ALL {scheduled_count} scheduled matches in the database"
                    else:
                        confirmation_msg = f"\n⚠️  This will permanently delete ALL {unscheduled_count} unscheduled matches in the database"
                
                print(confirmation_msg)
                response = input("Are you sure you want to continue? (yes/no): ")
                if response.lower() not in ['yes', 'y']:
                    print("❌ Operation cancelled")
                    return
            
            # Delete matches
            print(f"\n🗑️  Deleting {len(matches_to_delete)} match(es)...")
            
            for i, match in enumerate(matches_to_delete, 1):
                try:
                    if args.progress:
                        print(f"  Deleting match {match.id} ({i}/{len(matches_to_delete)})")
                    
                    db.delete_match(match)
                    deleted_count += 1
                    
                except Exception as e:
                    print(f"❌ Error deleting match {match.id}: {e}")
            
            # Final summary
            print(f"\n✅ Successfully deleted {deleted_count}/{len(matches_to_delete)} match(es)")
            
            if deleted_count != len(matches_to_delete):
                failed_count = len(matches_to_delete) - deleted_count
                print(f"⚠️  {failed_count} match(es) could not be deleted")
            
        except Exception as e:
            if args.verbose:
                import traceback
                traceback.print_exc()
            else:
                print(f"❌ Error during match deletion: {e}")

def main():
    """Main entry point"""
    cli = TennisCLI()
    return cli.run()


# if __name__ == "__main__":
#     sys.exit(main())


def show_full_error():
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)

# Wrap your main execution in try/except
if __name__ == "__main__":
    try:
        sys.exit(main())
        pass
    except Exception as e:
        print(f"Error: {e}")
        show_full_error()