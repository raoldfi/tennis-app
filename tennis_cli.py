#!/usr/bin/env python3
"""
Enhanced CLI for tennis scheduling with multi-backend database support.

This CLI provides a unified interface for managing tennis leagues, teams, matches,
and facilities across different database backends (SQLite, PostgreSQL, MongoDB, etc.).

Usage examples:
    # SQLite (default)
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
    
    def create_database_connection(self, args) -> TennisDBManager:
        """Create database connection based on command line arguments"""
        
        # Option 1: Use config file
        if hasattr(args, 'config') and args.config:
            if not os.path.exists(args.config):
                raise FileNotFoundError(f"Configuration file not found: {args.config}")
            
            backend, config = TennisDBConfig.from_file(args.config)
            return TennisDBManager(backend, config)
        
        # Option 2: Use environment variables
        if not hasattr(args, 'backend') or not args.backend:
            try:
                backend, config = TennisDBConfig.from_environment()
                return TennisDBManager(backend, config)
            except Exception:
                # Fall back to SQLite default
                backend = DatabaseBackend.SQLITE
                config = {'db_path': 'tennis.db'}
                return TennisDBManager(backend, config)
        
        # Option 3: Use command line arguments
        backend_str = args.backend.lower()
        
        if backend_str == 'sqlite':
            config = {
                'db_path': getattr(args, 'db_path', 'tennis.db')
            }
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
        """Handle list commands"""
        try:
            if args.table == "sections":
                # These are constants, not in database
                try:
                    from usta import USTA_SECTIONS
                    results = USTA_SECTIONS.copy()
                except ImportError:
                    results = ["Southwest", "Northern", "Southern", "Eastern", "Western"]
                    
            elif args.table == "regions":
                try:
                    from usta import USTA_REGIONS
                    results = USTA_REGIONS.copy()
                except ImportError:
                    results = ["Northern New Mexico", "Southern New Mexico", "Central New Mexico"]
                    
            elif args.table == "age-groups":
                try:
                    from usta import USTA_AGE_GROUPS
                    results = USTA_AGE_GROUPS.copy()
                except ImportError:
                    results = ["18 & Over", "40 & Over", "55 & Over", "65 & Over"]
                    
            elif args.table == "divisions":
                try:
                    from usta import USTA_DIVISIONS
                    results = USTA_DIVISIONS.copy()
                except ImportError:
                    results = ["2.5", "3.0", "3.5", "4.0", "4.5", "5.0"]
                    
            elif args.table == "backends":
                backends = TennisDBFactory.list_backends()
                results = [{"name": b.value, "available": True} for b in backends]
                
            elif args.table == "lines":
                results = db.list_lines(
                    match_id=getattr(args, 'match_id', None),
                    facility_id=getattr(args, 'facility_id', None),
                    date=getattr(args, 'date', None)
                )
                
            elif args.table == "teams":
                results = db.list_teams(league_id=getattr(args, 'league_id', None))
                
            elif args.table == "matches":
                if getattr(args, 'with_lines', False):
                    results = db.list_matches_with_lines(
                        league_id=getattr(args, 'league_id', None), 
                        include_unscheduled=getattr(args, 'include_unscheduled', False)
                    )
                else:
                    results = db.list_matches(
                        league_id=getattr(args, 'league_id', None), 
                        include_unscheduled=getattr(args, 'include_unscheduled', False)
                    )
                    
            elif args.table == "leagues":
                results = db.list_leagues()
                
            elif args.table == "facilities":
                results = db.list_facilities()
                
            else:
                raise ValueError(f"Unknown table: {args.table}")

            # Convert dataclass objects to dicts for JSON serialization
            if args.table in ["teams", "leagues", "matches", "facilities", "lines"]:
                if args.table == "teams":
                    # Flatten team data for better readability
                    enhanced_results = []
                    for team in results:
                        try:
                            team_dict = {
                                'id': team.id,
                                'name': team.name,
                                'league_id': team.league.id,
                                'league_name': team.league.name,
                                'year': team.league.year,
                                'section': team.league.section,
                                'region': team.league.region,
                                'age_group': team.league.age_group,
                                'division': team.league.division,
                                'home_facility_id': team.home_facility_id,
                                'captain': team.captain,
                                'preferred_days': team.preferred_days
                            }
                            enhanced_results.append(team_dict)
                        except Exception as e:
                            print(f"Warning: Could not process team {team.id}: {e}", file=sys.stderr)
                    results = enhanced_results
                    
                elif args.table == "matches" and getattr(args, 'with_lines', False):
                    # Include line information in match output
                    enhanced_results = []
                    for match in results:
                        try:
                            match_dict = match.__dict__.copy() if hasattr(match, '__dict__') else {}
                            match_dict['lines'] = [line.__dict__ if hasattr(line, '__dict__') else line for line in match.lines]
                            match_dict['line_count'] = len(match.lines)
                            match_dict['scheduling_status'] = match.get_line_scheduling_status()
                            enhanced_results.append(match_dict)
                        except Exception as e:
                            print(f"Warning: Could not process match {match.id}: {e}", file=sys.stderr)
                    results = enhanced_results
                    
                else:
                    results = [obj.__dict__ if hasattr(obj, '__dict__') else obj for obj in results]

            # Format output
            if getattr(args, 'format', 'json') == 'json':
                print(json.dumps(results, indent=2, default=str))
            elif args.format == 'table':
                self._print_table(results)
            else:
                print(json.dumps(results, indent=2, default=str))
                
        except Exception as e:
            print(f"Error: Failed to list {args.table}: {e}", file=sys.stderr)
            if getattr(args, 'verbose', False):
                traceback.print_exc()
            sys.exit(1)

    def handle_create_command(self, args, db):
        """Handle create commands"""
        if args.entity == "matches":
            try:
                league = db.get_league(args.league_id)
                if not league:
                    print(f"Error: League with ID {args.league_id} not found", file=sys.stderr)
                    sys.exit(1)

                teams = db.list_teams(league_id=args.league_id)
                if len(teams) < 2:
                    print(f"Error: League '{league.name}' has fewer than 2 teams; cannot generate matches.", file=sys.stderr)
                    sys.exit(1)

                matches = db.bulk_create_matches_with_lines(args.league_id, teams)

                match_results = []
                for m in matches:
                    match_dict = {
                        "match_id": m.id,
                        "league_id": m.league_id,
                        "home_team_id": m.home_team_id,
                        "visitor_team_id": m.visitor_team_id,
                        "lines_created": len(m.lines),
                        "status": "unscheduled"
                    }
                    match_results.append(match_dict)

                print(json.dumps(match_results, indent=2))
                print(f"\nSuccessfully created {len(matches)} matches with lines for league {args.league_id}", file=sys.stderr)

            except Exception as e:
                print(f"Error: Failed to generate matches - {e}", file=sys.stderr)
                if getattr(args, 'verbose', False):
                    traceback.print_exc()
                sys.exit(1)
        
        elif args.entity == "lines":
            try:
                match = db.get_match(args.match_id)
                if not match:
                    print(f"Error: Match with ID {args.match_id} not found", file=sys.stderr)
                    sys.exit(1)
                
                league = db.get_league(match.league_id)
                if not league:
                    print(f"Error: League for match {args.match_id} not found", file=sys.stderr)
                    sys.exit(1)
                
                lines = db.create_lines_for_match(args.match_id, league)
                
                line_results = []
                for line in lines:
                    line_results.append({
                        "line_id": line.id,
                        "match_id": line.match_id,
                        "line_number": line.line_number,
                        "scheduled": line.is_scheduled(),
                        "status": "scheduled" if line.is_scheduled() else "unscheduled"
                    })
                
                print(json.dumps(line_results, indent=2))
                print(f"\nSuccessfully created {len(lines)} lines for match {args.match_id}", file=sys.stderr)
                
            except Exception as e:
                print(f"Error: Failed to create lines - {e}", file=sys.stderr)
                if getattr(args, 'verbose', False):
                    traceback.print_exc()
                sys.exit(1)

    def handle_schedule_command(self, args, db):
        """Handle schedule commands"""
        try:
            if getattr(args, 'split_lines', False):
                # For now, just try same-time scheduling
                # In a full implementation, you'd parse a more complex scheduling plan
                success = db.schedule_match_all_lines_same_time(
                    args.match_id, args.facility_id, args.date, args.time
                )
            else:
                success = db.schedule_match_all_lines_same_time(
                    args.match_id, args.facility_id, args.date, args.time
                )
            
            result = {
                "match_id": args.match_id,
                "facility_id": args.facility_id,
                "date": args.date,
                "time": args.time,
                "success": success,
                "split_lines": getattr(args, 'split_lines', False)
            }
            
            print(json.dumps(result, indent=2))
            
            if success:
                print(f"\n✓ Successfully scheduled match {args.match_id} for {args.date} at {args.time}", file=sys.stderr)
            else:
                print(f"\n✗ Failed to schedule match {args.match_id} - not enough courts available", file=sys.stderr)
                sys.exit(1)
                
        except Exception as e:
            print(f"Error: Failed to schedule match - {e}", file=sys.stderr)
            if getattr(args, 'verbose', False):
                traceback.print_exc()
            sys.exit(1)

    def handle_unschedule_command(self, args, db):
        """Handle unschedule commands"""
        try:
            db.unschedule_match(args.match_id)
            
            result = {
                "match_id": args.match_id,
                "action": "unscheduled",
                "success": True
            }
            
            print(json.dumps(result, indent=2))
            print(f"\n✓ Successfully unscheduled match {args.match_id}", file=sys.stderr)
            
        except Exception as e:
            print(f"Error: Failed to unschedule match - {e}", file=sys.stderr)
            if getattr(args, 'verbose', False):
                traceback.print_exc()
            sys.exit(1)

    def handle_check_availability_command(self, args, db):
        """Handle availability checking"""
        try:
            available = db.check_court_availability(
                args.facility_id, args.date, args.time, args.courts_needed
            )
            available_count = db.get_available_courts_count(
                args.facility_id, args.date, args.time
            )
            
            result = {
                "facility_id": args.facility_id,
                "date": args.date,
                "time": args.time,
                "courts_needed": args.courts_needed,
                "available": available,
                "courts_available": available_count,
                "can_schedule": available
            }
            
            print(json.dumps(result, indent=2))
            
            if available:
                print(f"\n✓ {available_count} courts available (need {args.courts_needed})", file=sys.stderr)
            else:
                print(f"\n✗ Only {available_count} courts available (need {args.courts_needed})", file=sys.stderr)
            
        except Exception as e:
            print(f"Error: Failed to check availability - {e}", file=sys.stderr)
            if getattr(args, 'verbose', False):
                traceback.print_exc()
            sys.exit(1)

    def handle_stats_command(self, args, db):
        """Handle statistics commands"""
        try:
            if args.entity == "league":
                stats = db.get_league_scheduling_status(args.league_id)
                
                # Add calculated percentages
                if stats['total_matches'] > 0:
                    stats['scheduling_percentage'] = round(
                        (stats['scheduled_matches'] / stats['total_matches']) * 100, 1
                    )
                if stats['total_lines'] > 0:
                    stats['line_scheduling_percentage'] = round(
                        (stats['scheduled_lines'] / stats['total_lines']) * 100, 1
                    )
                
                print(json.dumps(stats, indent=2))
                
            elif args.entity == "facility":
                stats = db.get_facility_utilization(
                    args.facility_id, 
                    args.start_date, 
                    args.end_date
                )
                print(json.dumps(stats, indent=2))
                
            else:
                raise ValueError(f"Unknown stats entity: {args.entity}")
                
        except Exception as e:
            print(f"Error: Failed to get statistics - {e}", file=sys.stderr)
            if getattr(args, 'verbose', False):
                traceback.print_exc()
            sys.exit(1)

    def handle_migrate_command(self, args):
        """Handle database migration"""
        try:
            # Source database
            source_manager = self.create_database_connection(args)
            
            # Target database configuration
            if args.target_backend == 'sqlite':
                target_config = {'db_path': args.target_db_path}
            elif args.target_backend == 'postgresql':
                target_config = {
                    'host': args.target_host,
                    'port': args.target_port,
                    'database': args.target_database,
                    'user': args.target_user,
                    'password': args.target_password
                }
            elif args.target_backend == 'mongodb':
                target_config = {
                    'connection_string': args.target_connection_string,
                    'database': args.target_database
                }
            else:
                raise ValueError(f"Unsupported target backend: {args.target_backend}")
            
            target_backend = DatabaseBackend(args.target_backend.upper())
            
            # Perform migration
            print(f"Starting migration from {source_manager.backend.value} to {target_backend.value}...", file=sys.stderr)
            
            dry_run = getattr(args, 'dry_run', False)
            report = source_manager.migrate_to(target_backend, target_config, dry_run=dry_run)
            
            print(json.dumps(report, indent=2))
            
            if report['status'] == 'completed successfully':
                print(f"\n✓ Migration completed successfully!", file=sys.stderr)
            else:
                print(f"\n✗ Migration had issues: {report['status']}", file=sys.stderr)
                if report['errors']:
                    print(f"Errors: {len(report['errors'])}", file=sys.stderr)
            
        except Exception as e:
            print(f"Error: Migration failed - {e}", file=sys.stderr)
            if getattr(args, 'verbose', False):
                traceback.print_exc()
            sys.exit(1)

    def handle_health_command(self, args, db_manager):
        """Handle health check command"""
        try:
            health = db_manager.health_check()
            print(json.dumps(health, indent=2))
            
            if health['connected'] and health['responsive']:
                print(f"\n✓ Database health: OK", file=sys.stderr)
            else:
                print(f"\n✗ Database health: FAILED", file=sys.stderr)
                if health['error']:
                    print(f"Error: {health['error']}", file=sys.stderr)
                sys.exit(1)
                
        except Exception as e:
            print(f"Error: Health check failed - {e}", file=sys.stderr)
            if getattr(args, 'verbose', False):
                traceback.print_exc()
            sys.exit(1)

    def handle_load_command(self, args, db):
        """Handle YAML loading command"""
        try:
            if hasattr(db, 'load_yaml'):
                db.load_yaml(args.table, args.yaml_path)
                
                result = {
                    "action": "load",
                    "table": args.table,
                    "file": args.yaml_path,
                    "success": True
                }
                
                print(json.dumps(result, indent=2))
                print(f"\n✓ Successfully loaded {args.table} from {args.yaml_path}", file=sys.stderr)
            else:
                print(f"Error: Backend does not support YAML loading", file=sys.stderr)
                sys.exit(1)
                
        except Exception as e:
            print(f"Error: Failed to load YAML - {e}", file=sys.stderr)
            if getattr(args, 'verbose', False):
                traceback.print_exc()
            sys.exit(1)

    def handle_init_command(self, args, db):
        """Handle database initialization"""
        try:
            # Try to initialize/create schema
            if hasattr(db, 'initialize_schema'):
                db.initialize_schema()
            elif hasattr(db, '_initialize_schema'):
                db._initialize_schema()
            
            result = {
                "action": "initialize",
                "backend": self.db_manager.backend.value,
                "success": True
            }
            
            print(json.dumps(result, indent=2))
            print(f"\n✓ Database schema initialized successfully", file=sys.stderr)
            
        except Exception as e:
            print(f"Error: Failed to initialize database - {e}", file=sys.stderr)
            if getattr(args, 'verbose', False):
                traceback.print_exc()
            sys.exit(1)

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
                           help='Database backend to use')
        
        # Configuration file
        parser.add_argument('--config', help='Path to configuration file (JSON)')
        
        # SQLite arguments
        parser.add_argument('--db-path', help='Path to SQLite database file')
        
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
        list_parser.add_argument("--include-unscheduled", action="store_true", help="Include unscheduled matches")
        list_parser.add_argument("--with-lines", action="store_true", help="Include line details for matches")

        # Create command
        create_parser = subparsers.add_parser("create", help="Create entities")
        create_parser.add_argument("entity", choices=["matches", "lines"], help="Type of entity to create")
        create_parser.add_argument("--league-id", type=int, help="League ID (for matches)")
        create_parser.add_argument("--match-id", type=int, help="Match ID (for lines)")

        # Schedule command
        schedule_parser = subparsers.add_parser("schedule", help="Schedule matches")
        schedule_parser.add_argument("--match-id", type=int, required=True, help="Match ID to schedule")
        schedule_parser.add_argument("--facility-id", type=int, required=True, help="Facility ID")
        schedule_parser.add_argument("--date", required=True, help="Date (YYYY-MM-DD)")
        schedule_parser.add_argument("--time", required=True, help="Time (HH:MM)")
        schedule_parser.add_argument("--split-lines", action="store_true", help="Allow split-line scheduling")

        # Unschedule command
        unschedule_parser = subparsers.add_parser("unschedule", help="Unschedule matches")
        unschedule_parser.add_argument("--match-id", type=int, required=True, help="Match ID to unschedule")

        # Check availability command
        avail_parser = subparsers.add_parser("check-availability", help="Check court availability")
        avail_parser.add_argument("--facility-id", type=int, required=True, help="Facility ID")
        avail_parser.add_argument("--date", required=True, help="Date (YYYY-MM-DD)")
        avail_parser.add_argument("--time", required=True, help="Time (HH:MM)")
        avail_parser.add_argument("--courts-needed", type=int, default=1, help="Number of courts needed")

        # Stats command
        stats_parser = subparsers.add_parser("stats", help="Get statistics")
        stats_parser.add_argument("entity", choices=["league", "facility"], help="Type of statistics")
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

        # Init command
        init_parser = subparsers.add_parser("init", help="Initialize database schema")

        try:
            args = parser.parse_args()
            
            if not args.command:
                parser.print_help()
                sys.exit(1)
            
            # Create database connection
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


def main():
    """Main entry point"""
    cli = TennisCLI()
    cli.run()


if __name__ == "__main__":
    main()