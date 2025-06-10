#!/usr/bin/env python3
"""
Enhanced CLI for tennis scheduling with multi-backend database support.

This CLI provides a unified interface for managing tennis leagues, teams, matches,
and facilities across different database backends (SQLite, PostgreSQL, MongoDB, etc.).

Usage examples:
    # SQLite (default) - will create database if it doesn't exist
    python tennis_cli.py --backend sqlite --db-path tennis.db list leagues
    
    # PostgreSQL
    python tennis_cli.py --backend postgresql --host localhost --port 5432 \
        --database tennis --user tennis_user --password secret list teams
    
    # MongoDB
    python tennis_cli.py --backend mongodb \
        --connection-string mongodb://localhost:27017/ --database tennis list facilities
    
    # From environment variables
    export TENNIS_DB_BACKEND=postgresql
    export TENNIS_DB_HOST=localhost
    python tennis_cli.py list matches --league-id 1
    
    # From config file
    python tennis_cli.py --config config/production.json generate-matches --league-id 1
    
    # Initialize new database
    python tennis_cli.py --db-path new_tennis.db init

Commands:
    list            List entities (teams, leagues, matches, facilities, lines)
    create          Create entities (matches, lines)
    schedule        Schedule matches at facilities
    unschedule      Remove scheduling from matches
    check-availability  Check court availability at facilities
    stats           Get scheduling statistics
    migrate         Migrate data between backends
    load            Load data from YAML files
    health          Check database connection health
    init            Initialize database schema
"""

import argparse
import json
import sys
import os
from typing import Dict, Any, Optional
import traceback

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
                print(f"Database file '{db_path}' does not exist. Creating new database...", file=sys.stderr)
                
                try:
                    # Create directory if it doesn't exist
                    db_dir = os.path.dirname(db_path)
                    if db_dir and not os.path.exists(db_dir):
                        os.makedirs(db_dir, exist_ok=True)
                        print(f"Created directory: {db_dir}", file=sys.stderr)
                    
                    # Create empty database file by attempting connection
                    import sqlite3
                    conn = sqlite3.connect(db_path)
                    conn.close()
                    
                    print(f"✓ Created new SQLite database: {db_path}", file=sys.stderr)
                    
                    # Auto-initialize schema for new databases
                    self._auto_initialize_schema(backend_str, config)
                    
                except Exception as e:
                    print(f"Error creating database file: {e}", file=sys.stderr)
                    raise
                    
            else:
                # Check if existing database has tables
                try:
                    import sqlite3
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    
                    # Check if main tables exist
                    cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name IN ('teams', 'leagues', 'facilities', 'matches')
                    """)
                    tables = cursor.fetchall()
                    conn.close()
                    
                    if len(tables) == 0:
                        print(f"Database '{db_path}' exists but appears empty. Initializing schema...", file=sys.stderr)
                        self._auto_initialize_schema(backend_str, config)
                    
                except Exception as e:
                    print(f"Warning: Could not check database schema: {e}", file=sys.stderr)
        
        return config
    
    def _auto_initialize_schema(self, backend_str: str, config: Dict[str, Any]) -> None:
        """
        Automatically initialize database schema for new databases
        
        Args:
            backend_str: Database backend type
            config: Database configuration
        """
        try:
            print("Initializing database schema...", file=sys.stderr)
            
            # Create temporary database manager for initialization
            if backend_str.lower() == 'sqlite':
                backend = DatabaseBackend.SQLITE
            elif backend_str.lower() == 'postgresql':
                backend = DatabaseBackend.POSTGRESQL
            elif backend_str.lower() == 'mongodb':
                backend = DatabaseBackend.MONGODB
            elif backend_str.lower() == 'mysql':
                backend = DatabaseBackend.MYSQL
            else:
                print(f"Auto-initialization not supported for backend: {backend_str}", file=sys.stderr)
                return
            
            temp_manager = TennisDBManager(backend, config)
            
            with temp_manager as db:
                if hasattr(db, 'initialize_schema'):
                    db.initialize_schema()
                elif hasattr(db, '_initialize_schema'):
                    db._initialize_schema()
                else:
                    print("Warning: No schema initialization method found", file=sys.stderr)
                    return
            
            print("✓ Database schema initialized successfully", file=sys.stderr)
            
        except Exception as e:
            print(f"Error during auto-initialization: {e}", file=sys.stderr)
            print("You may need to run 'init' command manually", file=sys.stderr)
    
    def create_database_connection(self, args) -> TennisDBManager:
        """Create database connection based on command line arguments"""
        
        # Option 1: Use config file
        if hasattr(args, 'config') and args.config:
            if not os.path.exists(args.config):
                raise FileNotFoundError(f"Configuration file not found: {args.config}")
            
            backend, config = TennisDBConfig.from_file(args.config)
            
            # Ensure database exists for file-based backends
            config = self.ensure_database_exists(backend.value, config)
            
            return TennisDBManager(backend, config)
        
        # Option 2: Use environment variables
        if not hasattr(args, 'backend') or not args.backend:
            try:
                backend, config = TennisDBConfig.from_environment()
                
                # Ensure database exists for file-based backends
                config = self.ensure_database_exists(backend.value, config)
                
                return TennisDBManager(backend, config)
            except Exception:
                # Fall back to SQLite default
                backend_str = 'sqlite'
                config = {'db_path': 'tennis.db'}
                
                # Ensure database exists
                config = self.ensure_database_exists(backend_str, config)
                
                return TennisDBManager(DatabaseBackend.SQLITE, config)
        
        # Option 3: Use command line arguments
        backend_str = args.backend.lower()
        
        if backend_str == 'sqlite':
            config = {
                'db_path': getattr(args, 'db_path', 'tennis.db')
            }
            
            # Ensure database exists
            config = self.ensure_database_exists(backend_str, config)
            
            return TennisDBManager(DatabaseBackend.SQLITE, config)
        
        elif backend_str == 'postgresql':
            config = {
                'host': getattr(args, 'host', 'localhost'),
                'port': getattr(args, 'port', 5432),
                'database': getattr(args, 'database', 'tennis'),
                'user': getattr(args, 'user', 'tennis'),
                'password': getattr(args, 'password', '')
            }
            return TennisDBManager(DatabaseBackend.POSTGRESQL, config)
        
        elif backend_str == 'mongodb':
            config = {
                'connection_string': getattr(args, 'connection_string', 'mongodb://localhost:27017/'),
                'database': getattr(args, 'database', 'tennis')
            }
            return TennisDBManager(DatabaseBackend.MONGODB, config)
        
        elif backend_str == 'mysql':
            config = {
                'host': getattr(args, 'host', 'localhost'),
                'port': getattr(args, 'port', 3306),
                'database': getattr(args, 'database', 'tennis'),
                'user': getattr(args, 'user', 'tennis'),
                'password': getattr(args, 'password', '')
            }
            return TennisDBManager(DatabaseBackend.MYSQL, config)
        
        elif backend_str == 'memory':
            config = {}
            return TennisDBManager(DatabaseBackend.IN_MEMORY, config)
        
        else:
            available = [b.value for b in TennisDBFactory.list_backends()]
            raise ValueError(f"Unsupported backend: {backend_str}. Available: {available}")

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
                        'schedule_days': len(facility.schedule.days)
                    }
                    for facility in facilities
                ]
                self._output_data(facilities_data, args)
                
            elif args.table == "matches":
                include_unscheduled = getattr(args, 'include_unscheduled', False)
                matches = db.list_matches(args.league_id, include_unscheduled)
                matches_data = [
                    {
                        'id': match.id,
                        'league_id': match.league_id,
                        'home_team_id': match.home_team_id,
                        'visitor_team_id': match.visitor_team_id,
                        'facility_id': match.facility_id,
                        'date': match.date,
                        'time': match.time,
                        'status': 'scheduled' if match.facility_id else 'unscheduled'
                    }
                    for match in matches
                ]
                self._output_data(matches_data, args)
                
            elif args.table == "lines":
                lines = db.list_lines(args.match_id, args.facility_id, args.date)
                lines_data = [
                    {
                        'id': line.id,
                        'match_id': line.match_id,
                        'line_number': line.line_number,
                        'facility_id': line.facility_id,
                        'date': line.date,
                        'time': line.time,
                        'court_number': line.court_number,
                        'status': line.get_status()
                    }
                    for line in lines
                ]
                self._output_data(lines_data, args)
                
            elif args.table == "sections":
                from usta import USTA_SECTIONS
                sections_data = [{'name': section} for section in USTA_SECTIONS]
                self._output_data(sections_data, args)
                
            elif args.table == "regions":
                from usta import USTA_REGIONS
                regions_data = [{'name': region} for region in USTA_REGIONS]
                self._output_data(regions_data, args)
                
            elif args.table == "age-groups":
                from usta import USTA_AGE_GROUPS
                age_groups_data = [{'name': age_group} for age_group in USTA_AGE_GROUPS]
                self._output_data(age_groups_data, args)
                
            elif args.table == "divisions":
                from usta import USTA_DIVISIONS
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
                
        except Exception as e:
            print(f"Error: Failed to list {args.table} - {e}", file=sys.stderr)
            if getattr(args, 'verbose', False):
                traceback.print_exc()
            sys.exit(1)

    def handle_init_command(self, args, db):
        """Handle database initialization with enhanced feedback"""
        try:
            print("Initializing database schema...", file=sys.stderr)
            
            # Try to initialize/create schema
            if hasattr(db, 'initialize_schema'):
                db.initialize_schema()
            elif hasattr(db, '_initialize_schema'):
                db._initialize_schema()
            else:
                raise AttributeError("Database does not support schema initialization")
            
            # Verify initialization by checking for key tables
            verification_result = self._verify_database_schema(db)
            
            result = {
                "action": "initialize",
                "backend": self.db_manager.backend.value,
                "success": True,
                "verification": verification_result
            }
            
            print(json.dumps(result, indent=2))
            print(f"\n✓ Database schema initialized successfully", file=sys.stderr)
            
            if verification_result['missing_tables']:
                print(f"⚠ Warning: Some tables may not have been created: {verification_result['missing_tables']}", file=sys.stderr)
            
        except Exception as e:
            print(f"Error: Failed to initialize database - {e}", file=sys.stderr)
            if getattr(args, 'verbose', False):
                traceback.print_exc()
            sys.exit(1)
    
    def _verify_database_schema(self, db) -> Dict[str, Any]:
        """
        Verify that the database schema was properly initialized
        
        Args:
            db: Database instance
            
        Returns:
            Dictionary with verification results
        """
        expected_tables = ['teams', 'leagues', 'facilities', 'matches', 'lines']
        found_tables = []
        missing_tables = []
        
        try:
            # This is backend-specific verification
            if hasattr(db, 'cursor') and db.cursor:
                # SQLite verification
                db.cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                """)
                found_tables = [row[0] for row in db.cursor.fetchall()]
                
            missing_tables = [table for table in expected_tables if table not in found_tables]
            
            return {
                'expected_tables': expected_tables,
                'found_tables': found_tables,
                'missing_tables': missing_tables,
                'initialization_complete': len(missing_tables) == 0
            }
            
        except Exception as e:
            return {
                'expected_tables': expected_tables,
                'found_tables': [],
                'missing_tables': expected_tables,
                'initialization_complete': False,
                'error': str(e)
            }

    def _output_data(self, data, args):
        """Output data in requested format"""
        if getattr(args, 'format', 'json') == 'table':
            self._print_table(data)
        else:
            print(json.dumps(data, indent=2))

    def _print_table(self, data):
        """Print data in table format (simple implementation)"""
        if not data:
            print("No data to display")
            return
        
        if isinstance(data[0], dict):
            # Print headers
            headers = list(data[0].keys())
            print(" | ".join(headers))
            print("-" * (len(" | ".join(headers))))
            
            # Print rows
            for row in data:
                values = [str(row.get(h, '')) for h in headers]
                print(" | ".join(values))
        else:
            for item in data:
                print(item)

    def add_database_arguments(self, parser):
        """Add database connection arguments to parser"""
        
        # Backend selection
        available_backends = ['sqlite', 'postgresql', 'mongodb', 'mysql', 'memory']
        parser.add_argument('--backend', choices=available_backends,
                           help='Database backend to use (default: sqlite)')
        
        # Configuration file
        parser.add_argument('--config', help='Path to configuration file (JSON)')
        
        # SQLite arguments
        parser.add_argument('--db-path', help='Path to SQLite database file (default: tennis.db)')
        
        # PostgreSQL/MySQL arguments
        parser.add_argument('--host', help='Database host')
        parser.add_argument('--port', type=int, help='Database port')
        parser.add_argument('--database', help='Database name')
        parser.add_argument('--user', help='Database user')
        parser.add_argument('--password', help='Database password')
        
        # MongoDB arguments
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
                               choices=["teams", "leagues", "matches", "lines", "sections", 
                                       "regions", "age-groups", "facilities", "divisions", "backends"], 
                               help="Type of entity to list")
        list_parser.add_argument("--league-id", type=int, help="Filter by league ID")
        list_parser.add_argument("--match-id", type=int, help="Filter lines by match ID")
        list_parser.add_argument("--facility-id", type=int, help="Filter lines by facility ID")
        list_parser.add_argument("--date", help="Filter lines by date (YYYY-MM-DD)")
        list_parser.add_argument("--include-unscheduled", action="store_true", 
                               help="Include unscheduled matches in results")

        # Create command
        create_parser = subparsers.add_parser("create", help="Create new entities")
        create_parser.add_argument("entity", choices=["match", "line"], help="Type of entity to create")
        create_parser.add_argument("--league-id", type=int, required=True, help="League ID")
        create_parser.add_argument("--home-team-id", type=int, required=True, help="Home team ID")
        create_parser.add_argument("--visitor-team-id", type=int, required=True, help="Visitor team ID")

        # Schedule command
        schedule_parser = subparsers.add_parser("schedule", help="Schedule matches at facilities")
        schedule_parser.add_argument("--match-id", type=int, required=True, help="Match ID to schedule")
        schedule_parser.add_argument("--facility-id", type=int, required=True, help="Facility ID")
        schedule_parser.add_argument("--date", required=True, help="Date (YYYY-MM-DD)")
        schedule_parser.add_argument("--time", required=True, help="Time (HH:MM)")

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
        load_parser.add_argument("table", choices=["teams", "leagues", "matches", "facilities"], 
                               help="Type of entity to load")
        load_parser.add_argument("--file", "-f", dest="yaml_path", required=True, 
                               help="Path to YAML file")

        # Health command
        health_parser = subparsers.add_parser("health", help="Check database connection health")

        # Init command - enhanced with better help
        init_parser = subparsers.add_parser("init", help="Initialize database schema")
        init_parser.add_argument("--force", action="store_true", 
                               help="Force initialization even if tables already exist")

        try:
            args = parser.parse_args()
            
            if not args.command:
                parser.print_help()
                sys.exit(1)
            
            # Create database connection (with auto-initialization for new databases)
            self.db_manager = self.create_database_connection(args)
            
            # Handle commands that don't need a database connection
            if args.command == "health":
                self.handle_health_command(args, self.db_manager)
                return
            
            if args.command == "migrate":
                self.handle_migrate_command(args)
                return
            
            # Handle commands that need a database connection
            with self.db_manager as db:
                if args.command == "list":
                    self.handle_list_command(args, db)
                elif args.command == "create":
                    self.handle_create_command(args, db)
                elif args.command == "schedule":
                    self.handle_schedule_command(args, db)
                elif args.command == "unschedule":
                    self.handle_unschedule_command(args, db)
                elif args.command == "check-availability":
                    self.handle_check_availability_command(args, db)
                elif args.command == "stats":
                    self.handle_stats_command(args, db)
                elif args.command == "load":
                    self.handle_load_command(args, db)
                elif args.command == "init":
                    self.handle_init_command(args, db)
                else:
                    parser.print_help()
        
        except KeyboardInterrupt:
            print("\nOperation cancelled by user", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            if getattr(args, 'verbose', False) if 'args' in locals() else False:
                traceback.print_exc()
            sys.exit(1)

    # Placeholder methods for commands not fully implemented yet
    def handle_health_command(self, args, db_manager):
        """Handle health check command"""
        try:
            with db_manager as db:
                if db.ping():
                    result = {
                        "status": "healthy",
                        "backend": db_manager.backend.value,
                        "message": "Database connection successful"
                    }
                    print(json.dumps(result, indent=2))
                    print("✓ Database connection is healthy", file=sys.stderr)
                else:
                    result = {
                        "status": "unhealthy",
                        "backend": db_manager.backend.value,
                        "message": "Database ping failed"
                    }
                    print(json.dumps(result, indent=2))
                    print("✗ Database connection failed", file=sys.stderr)
                    sys.exit(1)
        except Exception as e:
            result = {
                "status": "error",
                "backend": db_manager.backend.value if db_manager else "unknown",
                "message": str(e)
            }
            print(json.dumps(result, indent=2))
            print(f"✗ Database health check failed: {e}", file=sys.stderr)
            sys.exit(1)

    def handle_create_command(self, args, db):
        """Handle create command"""
        print(f"Create {args.entity} command not fully implemented yet", file=sys.stderr)

    def handle_schedule_command(self, args, db):
        """Handle schedule command"""
        print("Schedule command not fully implemented yet", file=sys.stderr)

    def handle_unschedule_command(self, args, db):
        """Handle unschedule command"""
        print("Unschedule command not fully implemented yet", file=sys.stderr)

    def handle_check_availability_command(self, args, db):
        """Handle check availability command"""
        print("Check availability command not fully implemented yet", file=sys.stderr)

    def handle_stats_command(self, args, db):
        """Handle stats command"""
        print("Stats command not fully implemented yet", file=sys.stderr)

    def handle_migrate_command(self, args):
        """Handle migrate command"""
        print("Migrate command not fully implemented yet", file=sys.stderr)

    def handle_load_command(self, args, db):
        """Handle load command"""
        try:
            # Validate arguments
            if not hasattr(args, 'table') or not args.table:
                print("Error: Table name is required", file=sys.stderr)
                sys.exit(1)
            
            if not hasattr(args, 'yaml_path') or not args.yaml_path:
                print("Error: YAML file path is required", file=sys.stderr)
                sys.exit(1)
            
            # Check if YAML file exists
            if not os.path.exists(args.yaml_path):
                print(f"Error: YAML file '{args.yaml_path}' not found", file=sys.stderr)
                sys.exit(1)
            
            print(f"Loading {args.table} from {args.yaml_path}...", file=sys.stderr)
            
            # Call the database's load_yaml method
            db.load_yaml(args.table, args.yaml_path)
            
            print(f"✓ Successfully loaded {args.table} from {args.yaml_path}", file=sys.stderr)
            
            # Return success status as JSON
            result = {
                "status": "success",
                "table": args.table,
                "file": args.yaml_path,
                "message": f"Successfully loaded {args.table} data"
            }
            print(json.dumps(result, indent=2))
            
        except FileNotFoundError as e:
            error_result = {
                "status": "error",
                "table": args.table,
                "file": args.yaml_path,
                "error": "file_not_found",
                "message": str(e)
            }
            print(json.dumps(error_result, indent=2))
            print(f"✗ File not found: {e}", file=sys.stderr)
            sys.exit(1)
            
        except ValueError as e:
            error_result = {
                "status": "error", 
                "table": args.table,
                "file": args.yaml_path,
                "error": "validation_error",
                "message": str(e)
            }
            print(json.dumps(error_result, indent=2))
            print(f"✗ Validation error: {e}", file=sys.stderr)
            sys.exit(1)
            
        except Exception as e:
            error_result = {
                "status": "error",
                "table": args.table,
                "file": args.yaml_path,
                "error": "unknown_error", 
                "message": str(e)
            }
            print(json.dumps(error_result, indent=2))
            print(f"✗ Unexpected error: {e}", file=sys.stderr)
            if hasattr(args, 'debug') and args.debug:
                traceback.print_exc(file=sys.stderr)
            sys.exit(1)


def main():
    """Main entry point"""
    cli = TennisCLI()
    cli.run()


if __name__ == "__main__":
    main()