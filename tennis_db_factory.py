"""
Tennis Database Factory and Manager

This module provides factory patterns and management utilities for creating
and managing tennis database connections across multiple backends.

Usage:
    # Create a database instance
    db = TennisDBFactory.create(DatabaseBackend.SQLITE, {'db_path': 'tennis.db'})
    
    # Use database manager with context
    with TennisDBManager(DatabaseBackend.POSTGRESQL, config) as db:
        leagues = db.list_leagues()
    
    # Load configuration from environment
    backend, config = TennisDBConfig.from_environment()
    manager = TennisDBManager(backend, config)
"""

import os
import json
from typing import Union, Dict, Any, List, Tuple
from enum import Enum
from abc import ABC, abstractmethod

# Import the clean interface
from tennis_db_interface import TennisDBInterface


class DatabaseBackend(Enum):
    """Supported database backend types"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql" 
    MYSQL = "mysql"
    MONGODB = "mongodb"
    IN_MEMORY = "memory"


class TennisDBFactory:
    """
    Factory class for creating tennis database instances.
    
    This factory supports multiple backends and handles backend registration,
    configuration validation, and instance creation.
    """
    
    _backends = {}
    _initialized = False
    
    @classmethod
    def _ensure_backends_registered(cls):
        """Ensure all available backends are registered"""
        if cls._initialized:
            return
        
        # Only register SQLite backend by default (no external dependencies)
        cls._register_sqlite_backend()
        cls._initialized = True
    
    @classmethod
    def _register_sqlite_backend(cls):
        """Register SQLite backend (should always be available)"""
        try:
            from backends.sqlite_tennis_db import SQLiteTennisDB
            cls.register_backend(DatabaseBackend.SQLITE, SQLiteTennisDB)
        except ImportError:
            try:
                # Fallback to current directory
                from sqlite_tennis_db import SQLiteTennisDB
                cls.register_backend(DatabaseBackend.SQLITE, SQLiteTennisDB)
            except ImportError:
                pass
    
    @classmethod
    def _register_backend_on_demand(cls, backend_type: DatabaseBackend):
        """Register a backend only when needed"""
        if backend_type in cls._backends:
            return  # Already registered
        
        if backend_type == DatabaseBackend.POSTGRESQL:
            try:
                import psycopg2  # Check if dependency is available
                from backends.postgresql_tennis_db import PostgreSQLTennisDB
                cls.register_backend(DatabaseBackend.POSTGRESQL, PostgreSQLTennisDB)
            except ImportError as e:
                if 'psycopg2' in str(e):
                    raise ImportError(
                        "PostgreSQL backend requires psycopg2. Install it with: pip install psycopg2-binary"
                    )
                else:
                    raise ImportError(f"PostgreSQL backend not available: {e}")
        
        elif backend_type == DatabaseBackend.MONGODB:
            try:
                import pymongo  # Check if dependency is available
                from backends.mongodb_tennis_db import MongoDBTennisDB
                cls.register_backend(DatabaseBackend.MONGODB, MongoDBTennisDB)
            except ImportError as e:
                if 'pymongo' in str(e):
                    raise ImportError(
                        "MongoDB backend requires pymongo. Install it with: pip install pymongo"
                    )
                else:
                    raise ImportError(f"MongoDB backend not available: {e}")
        
        elif backend_type == DatabaseBackend.MYSQL:
            try:
                import mysql.connector  # Check if dependency is available
                from backends.mysql_tennis_db import MySQLTennisDB
                cls.register_backend(DatabaseBackend.MYSQL, MySQLTennisDB)
            except ImportError as e:
                if 'mysql' in str(e):
                    raise ImportError(
                        "MySQL backend requires mysql-connector-python. Install it with: pip install mysql-connector-python"
                    )
                else:
                    raise ImportError(f"MySQL backend not available: {e}")
        
        elif backend_type == DatabaseBackend.IN_MEMORY:
            try:
                from backends.memory_tennis_db import InMemoryTennisDB
                cls.register_backend(DatabaseBackend.IN_MEMORY, InMemoryTennisDB)
            except ImportError:
                # Create a simple in-memory implementation if file doesn't exist
                cls._create_simple_memory_backend()
    
    @classmethod
    def _create_simple_memory_backend(cls):
        """Create a simple in-memory backend if one doesn't exist"""
        from tennis_db_interface import TennisDBInterface
        
        class SimpleInMemoryTennisDB(TennisDBInterface):
            def __init__(self, config):
                self.data = {
                    'teams': {}, 'leagues': {}, 'matches': {}, 
                    'facilities': {}, 'lines': {}
                }
                self._connected = False
            
            def connect(self): 
                self._connected = True
            
            def disconnect(self): 
                self._connected = False
            
            def ping(self): 
                return self._connected
            
            # Implement minimal required methods
            def add_team(self, team): self.data['teams'][team.id] = team
            def get_team(self, team_id): return self.data['teams'].get(team_id)
            def list_teams(self, league_id=None): return list(self.data['teams'].values())
            def update_team(self, team): self.data['teams'][team.id] = team
            def delete_team(self, team_id): self.data['teams'].pop(team_id, None)
            
            def add_league(self, league): self.data['leagues'][league.id] = league
            def get_league(self, league_id): return self.data['leagues'].get(league_id)
            def list_leagues(self): return list(self.data['leagues'].values())
            def update_league(self, league): self.data['leagues'][league.id] = league
            def delete_league(self, league_id): self.data['leagues'].pop(league_id, None)
            
            def add_match(self, match): self.data['matches'][match.id] = match
            def get_match(self, match_id): return self.data['matches'].get(match_id)
            def get_match_with_lines(self, match_id): 
                match = self.data['matches'].get(match_id)
                if match:
                    match.lines = [line for line in self.data['lines'].values() if line.match_id == match_id]
                return match
            def list_matches(self, league_id=None, include_unscheduled=False): 
                return list(self.data['matches'].values())
            def list_matches_with_lines(self, league_id=None, include_unscheduled=False):
                matches = list(self.data['matches'].values())
                for match in matches:
                    match.lines = [line for line in self.data['lines'].values() if line.match_id == match.id]
                return matches
            def delete_match(self, match_id): self.data['matches'].pop(match_id, None)
            
            def add_facility(self, facility): self.data['facilities'][facility.id] = facility
            def get_facility(self, facility_id): return self.data['facilities'].get(facility_id)
            def list_facilities(self): return list(self.data['facilities'].values())
            def update_facility(self, facility): self.data['facilities'][facility.id] = facility
            def delete_facility(self, facility_id): self.data['facilities'].pop(facility_id, None)
            
            def add_line(self, line): self.data['lines'][line.id] = line
            def get_line(self, line_id): return self.data['lines'].get(line_id)
            def list_lines(self, match_id=None, facility_id=None, date=None):
                lines = list(self.data['lines'].values())
                if match_id: lines = [l for l in lines if l.match_id == match_id]
                if facility_id: lines = [l for l in lines if l.facility_id == facility_id]
                if date: lines = [l for l in lines if l.date == date]
                return lines
            def update_line(self, line): self.data['lines'][line.id] = line
            def delete_line(self, line_id): self.data['lines'].pop(line_id, None)
            
            # Scheduling methods (simplified)
            def schedule_match_all_lines_same_time(self, match_id, facility_id, date, time):
                match = self.get_match_with_lines(match_id)
                if match:
                    for line in match.lines:
                        line.facility_id = facility_id
                        line.date = date
                        line.time = time
                        self.update_line(line)
                    match.facility_id = facility_id
                    match.date = date
                    match.time = time
                    self._update_match(match)
                    return True
                return False
            
            def schedule_match_split_lines(self, match_id, date, scheduling_plan): return False
            def unschedule_match(self, match_id):
                match = self.get_match_with_lines(match_id)
                if match:
                    for line in match.lines:
                        line.facility_id = None
                        line.date = None
                        line.time = None
                        self.update_line(line)
                    match.facility_id = None
                    match.date = None
                    match.time = None
                    self._update_match(match)
            
            def check_court_availability(self, facility_id, date, time, courts_needed): return True
            def get_available_courts_count(self, facility_id, date, time): return 10
            def get_league_scheduling_status(self, league_id): 
                return {'total_matches': 0, 'scheduled_matches': 0, 'unscheduled_matches': 0, 
                       'total_lines': 0, 'scheduled_lines': 0, 'unscheduled_lines': 0,
                       'partially_scheduled_matches': 0}
            def get_facility_utilization(self, facility_id, start_date, end_date):
                return {'total_available_hours': 0, 'total_used_hours': 0, 'utilization_percentage': 0}
            def bulk_create_matches_with_lines(self, league_id, teams): return []
            def create_lines_for_match(self, match_id, league): return []
        
        cls.register_backend(DatabaseBackend.IN_MEMORY, SimpleInMemoryTennisDB)
    
    @classmethod
    def register_backend(cls, backend_type: DatabaseBackend, backend_class):
        """
        Register a new backend implementation
        
        Args:
            backend_type: The backend type enum
            backend_class: The implementation class
        """
        if not issubclass(backend_class, TennisDBInterface):
            raise TypeError(f"Backend class must implement TennisDBInterface")
        
        cls._backends[backend_type] = backend_class
        print(f"Registered backend: {backend_type.value}")
    
    @classmethod
    def create(cls, backend: Union[DatabaseBackend, str], config: Dict[str, Any]) -> TennisDBInterface:
        """
        Create a database instance for the specified backend.
        
        Args:
            backend: The database backend type
            config: Backend-specific configuration
            
        Returns:
            TennisDBInterface implementation
            
        Raises:
            ValueError: If backend is not supported or config is invalid
            ImportError: If backend dependencies are not installed
            
        Examples:
            # SQLite (no dependencies required)
            db = TennisDBFactory.create(DatabaseBackend.SQLITE, {
                'db_path': '/path/to/tennis.db'
            })
            
            # PostgreSQL (requires: pip install psycopg2-binary)
            db = TennisDBFactory.create(DatabaseBackend.POSTGRESQL, {
                'host': 'localhost',
                'port': 5432,
                'database': 'tennis',
                'user': 'tennis_user',
                'password': 'secret'
            })
            
            # MongoDB (requires: pip install pymongo)
            db = TennisDBFactory.create(DatabaseBackend.MONGODB, {
                'connection_string': 'mongodb://localhost:27017/',
                'database': 'tennis'
            })
        """
        cls._ensure_backends_registered()
        
        if isinstance(backend, str):
            try:
                backend = DatabaseBackend(backend.lower())
            except ValueError:
                available = [b.value for b in DatabaseBackend]
                raise ValueError(f"Unknown backend: {backend}. Available: {available}")
        
        # Register backend on demand if not already registered
        if backend not in cls._backends:
            try:
                cls._register_backend_on_demand(backend)
            except ImportError as e:
                # Provide helpful error message with installation instructions
                raise ImportError(f"Cannot use {backend.value} backend: {e}")
        
        if backend not in cls._backends:
            registered = [b.value for b in cls.list_backends()]
            raise ValueError(f"Backend {backend.value} not available. Registered backends: {registered}")
        
        # Validate configuration
        cls._validate_config(backend, config)
        
        backend_class = cls._backends[backend]
        return backend_class(config)
    
    @classmethod
    def _validate_config(cls, backend: DatabaseBackend, config: Dict[str, Any]):
        """Validate configuration for specific backend"""
        if backend == DatabaseBackend.SQLITE:
            if 'db_path' not in config:
                raise ValueError("SQLite backend requires 'db_path' in config")
        
        elif backend == DatabaseBackend.POSTGRESQL:
            required = ['host', 'port', 'database', 'user', 'password']
            missing = [key for key in required if key not in config]
            if missing:
                raise ValueError(f"PostgreSQL backend requires: {missing}")
        
        elif backend == DatabaseBackend.MONGODB:
            if 'connection_string' not in config or 'database' not in config:
                raise ValueError("MongoDB backend requires 'connection_string' and 'database' in config")
        
        elif backend == DatabaseBackend.MYSQL:
            required = ['host', 'port', 'database', 'user', 'password']
            missing = [key for key in required if key not in config]
            if missing:
                raise ValueError(f"MySQL backend requires: {missing}")
    
    @classmethod
    def list_backends(cls) -> List[DatabaseBackend]:
        """List all registered backends"""
        cls._ensure_backends_registered()
        return list(cls._backends.keys())
    
    @classmethod
    def backend_info(cls) -> Dict[str, Dict[str, Any]]:
        """Get information about all registered backends"""
        cls._ensure_backends_registered()
        
        info = {}
        for backend_type, backend_class in cls._backends.items():
            info[backend_type.value] = {
                'class': backend_class.__name__,
                'module': backend_class.__module__,
                'description': getattr(backend_class, '__doc__', 'No description'),
            }
        
        return info


class TennisDBManager:
    """
    High-level manager for tennis database operations.
    
    Provides connection management, context managers, caching,
    and additional business logic on top of the basic database interface.
    """
    
    def __init__(self, backend: Union[DatabaseBackend, str], config: Dict[str, Any]):
        """
        Initialize database manager
        
        Args:
            backend: Database backend type
            config: Backend-specific configuration
        """
        self.backend = backend if isinstance(backend, DatabaseBackend) else DatabaseBackend(backend)
        self.config = config.copy()  # Defensive copy
        self.db = None
        self._connected = False
    
    def connect(self) -> TennisDBInterface:
        """
        Get a database connection
        
        Returns:
            Database interface instance
        """
        if not self._connected:
            self.db = TennisDBFactory.create(self.backend, self.config)
            if hasattr(self.db, 'connect'):
                self.db.connect()
            self._connected = True
        
        return self.db
    
    def disconnect(self):
        """Close database connection"""
        if self._connected and self.db:
            if hasattr(self.db, 'disconnect'):
                self.db.disconnect()
            self.db = None
            self._connected = False
    
    def is_connected(self) -> bool:
        """Check if database is connected"""
        if not self._connected or not self.db:
            return False
        
        # Try to ping the database if supported
        if hasattr(self.db, 'ping'):
            try:
                return self.db.ping()
            except:
                return False
        
        return True
    
    def reconnect(self) -> TennisDBInterface:
        """Reconnect to database"""
        self.disconnect()
        return self.connect()
    
    def __enter__(self):
        """Context manager entry"""
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
    
    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()
    
    def migrate_to(self, target_backend: Union[DatabaseBackend, str], 
                   target_config: Dict[str, Any], 
                   dry_run: bool = False) -> Dict[str, Any]:
        """
        Migrate data from current backend to target backend
        
        Args:
            target_backend: Target database backend
            target_config: Target database configuration
            dry_run: If True, only analyze what would be migrated
            
        Returns:
            Migration report with statistics and results
        """
        if isinstance(target_backend, str):
            target_backend = DatabaseBackend(target_backend)
        
        source_db = self.connect()
        
        # Create target database connection
        target_manager = TennisDBManager(target_backend, target_config)
        target_db = target_manager.connect()
        
        migration_report = {
            'source_backend': self.backend.value,
            'target_backend': target_backend.value,
            'dry_run': dry_run,
            'migrated_entities': {},
            'errors': [],
            'warnings': []
        }
        
        try:
            # Migrate leagues first (dependencies)
            leagues = source_db.list_leagues()
            migration_report['migrated_entities']['leagues'] = len(leagues)
            
            if not dry_run:
                for league in leagues:
                    try:
                        target_db.add_league(league)
                    except Exception as e:
                        migration_report['errors'].append(f"Failed to migrate league {league.id}: {e}")
            
            # Migrate facilities
            facilities = source_db.list_facilities()
            migration_report['migrated_entities']['facilities'] = len(facilities)
            
            if not dry_run:
                for facility in facilities:
                    try:
                        target_db.add_facility(facility)
                    except Exception as e:
                        migration_report['errors'].append(f"Failed to migrate facility {facility.id}: {e}")
            
            # Migrate teams
            teams = source_db.list_teams()
            migration_report['migrated_entities']['teams'] = len(teams)
            
            if not dry_run:
                for team in teams:
                    try:
                        target_db.add_team(team)
                    except Exception as e:
                        migration_report['errors'].append(f"Failed to migrate team {team.id}: {e}")
            
            # Migrate matches with lines
            matches = source_db.list_matches_with_lines(include_unscheduled=True)
            migration_report['migrated_entities']['matches'] = len(matches)
            
            total_lines = 0
            if not dry_run:
                for match in matches:
                    try:
                        target_db.add_match(match)
                        total_lines += len(match.lines)
                        
                        # Migrate lines
                        for line in match.lines:
                            target_db.add_line(line)
                            
                    except Exception as e:
                        migration_report['errors'].append(f"Failed to migrate match {match.id}: {e}")
            else:
                total_lines = sum(len(match.lines) for match in matches)
            
            migration_report['migrated_entities']['lines'] = total_lines
            
            if not migration_report['errors']:
                status = "completed successfully"
            else:
                status = f"completed with {len(migration_report['errors'])} errors"
            
            migration_report['status'] = status
            
            print(f"Migration from {self.backend.value} to {target_backend.value} {status}")
            if migration_report['errors']:
                print(f"Errors encountered: {len(migration_report['errors'])}")
            
        except Exception as e:
            migration_report['status'] = 'failed'
            migration_report['errors'].append(f"Migration failed: {e}")
            
        finally:
            target_manager.disconnect()
        
        return migration_report
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on database connection
        
        Returns:
            Health check report
        """
        report = {
            'backend': self.backend.value,
            'connected': False,
            'responsive': False,
            'error': None
        }
        
        try:
            db = self.connect()
            report['connected'] = True
            
            # Test basic functionality
            if hasattr(db, 'ping'):
                report['responsive'] = db.ping()
            else:
                # Try a simple query
                try:
                    db.list_leagues()
                    report['responsive'] = True
                except:
                    report['responsive'] = False
                    
        except Exception as e:
            report['error'] = str(e)
        
        return report


class TennisDBConfig:
    """Configuration management for different environments"""
    
    @staticmethod
    def from_environment() -> Tuple[DatabaseBackend, Dict[str, Any]]:
        """
        Load configuration from environment variables
        
        Environment variables:
            TENNIS_DB_BACKEND: Backend type (sqlite, postgresql, mongodb, etc.)
            
            For SQLite:
                TENNIS_DB_PATH: Path to database file
            
            For PostgreSQL/MySQL:
                TENNIS_DB_HOST: Database host
                TENNIS_DB_PORT: Database port
                TENNIS_DB_NAME: Database name
                TENNIS_DB_USER: Database user
                TENNIS_DB_PASSWORD: Database password
            
            For MongoDB:
                TENNIS_DB_CONNECTION_STRING: MongoDB connection string
                TENNIS_DB_NAME: Database name
        
        Returns:
            Tuple of (backend, config)
        """
        backend_type = os.getenv('TENNIS_DB_BACKEND', 'sqlite').lower()
        
        if backend_type == 'sqlite':
            return DatabaseBackend.SQLITE, {
                'db_path': os.getenv('TENNIS_DB_PATH', 'tennis.db')
            }
        
        elif backend_type == 'postgresql':
            return DatabaseBackend.POSTGRESQL, {
                'host': os.getenv('TENNIS_DB_HOST', 'localhost'),
                'port': int(os.getenv('TENNIS_DB_PORT', '5432')),
                'database': os.getenv('TENNIS_DB_NAME', 'tennis'),
                'user': os.getenv('TENNIS_DB_USER', 'tennis'),
                'password': os.getenv('TENNIS_DB_PASSWORD', '')
            }
        
        elif backend_type == 'mysql':
            return DatabaseBackend.MYSQL, {
                'host': os.getenv('TENNIS_DB_HOST', 'localhost'),
                'port': int(os.getenv('TENNIS_DB_PORT', '3306')),
                'database': os.getenv('TENNIS_DB_NAME', 'tennis'),
                'user': os.getenv('TENNIS_DB_USER', 'tennis'),
                'password': os.getenv('TENNIS_DB_PASSWORD', '')
            }
        
        elif backend_type == 'mongodb':
            return DatabaseBackend.MONGODB, {
                'connection_string': os.getenv('TENNIS_DB_CONNECTION_STRING', 'mongodb://localhost:27017/'),
                'database': os.getenv('TENNIS_DB_NAME', 'tennis')
            }
        
        elif backend_type == 'memory':
            return DatabaseBackend.IN_MEMORY, {}
        
        else:
            raise ValueError(f"Unsupported backend in environment: {backend_type}")
    
    @staticmethod
    def from_file(config_path: str) -> Tuple[DatabaseBackend, Dict[str, Any]]:
        """
        Load configuration from JSON file
        
        Expected format:
        {
            "backend": "postgresql",
            "config": {
                "host": "localhost",
                "port": 5432,
                "database": "tennis",
                "user": "tennis_user",
                "password": "secret"
            }
        }
        
        Args:
            config_path: Path to JSON configuration file
            
        Returns:
            Tuple of (backend, config)
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        
        if 'backend' not in config_data:
            raise ValueError("Configuration file must specify 'backend'")
        
        if 'config' not in config_data:
            raise ValueError("Configuration file must specify 'config'")
        
        backend_type = DatabaseBackend(config_data['backend'].lower())
        backend_config = config_data['config']
        
        # Support environment variable substitution
        backend_config = TennisDBConfig._substitute_env_vars(backend_config)
        
        return backend_type, backend_config
    
    @staticmethod
    def _substitute_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
        """Substitute environment variables in configuration values"""
        result = {}
        
        for key, value in config.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]  # Remove ${ and }
                default_value = ''
                
                # Support ${VAR:default} syntax
                if ':' in env_var:
                    env_var, default_value = env_var.split(':', 1)
                
                result[key] = os.getenv(env_var, default_value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def create_sample_configs(output_dir: str = 'config'):
        """Create sample configuration files"""
        os.makedirs(output_dir, exist_ok=True)
        
        configs = {
            'development.json': {
                'backend': 'sqlite',
                'config': {
                    'db_path': 'tennis_dev.db'
                }
            },
            'testing.json': {
                'backend': 'memory',
                'config': {}
            },
            'production.json': {
                'backend': 'postgresql',
                'config': {
                    'host': 'db.tennis-app.com',
                    'port': 5432,
                    'database': 'tennis_production',
                    'user': 'tennis_app',
                    'password': '${TENNIS_DB_PASSWORD}'
                }
            },
            'analytics.json': {
                'backend': 'mongodb',
                'config': {
                    'connection_string': 'mongodb+srv://analytics:${MONGO_PASSWORD}@cluster.mongodb.net/',
                    'database': 'tennis_analytics'
                }
            }
        }
        
        for filename, config in configs.items():
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"Created sample config: {filepath}")


def main():
    """Example usage and testing"""
    
    print("Tennis Database Factory - Available Backends:")
    print("=" * 50)
    
    # Show available backends
    backends = TennisDBFactory.list_backends()
    print(f"Registered backends: {[b.value for b in backends]}")
    
    # Show backend information
    info = TennisDBFactory.backend_info()
    for backend, details in info.items():
        print(f"\n{backend}:")
        print(f"  Class: {details['class']}")
        print(f"  Module: {details['module']}")
    
    # Example: Create SQLite database
    try:
        print(f"\nTesting SQLite backend...")
        db = TennisDBFactory.create(DatabaseBackend.SQLITE, {'db_path': ':memory:'})
        print(f"✓ SQLite backend created successfully")
    except Exception as e:
        print(f"✗ SQLite backend failed: {e}")
    
    # Example: Database manager
    try:
        print(f"\nTesting database manager...")
        config = {'db_path': ':memory:'}
        with TennisDBManager(DatabaseBackend.SQLITE, config) as db:
            # db is now connected and ready to use
            print(f"✓ Database manager working")
    except Exception as e:
        print(f"✗ Database manager failed: {e}")
    
    # Example: Environment configuration
    try:
        print(f"\nTesting environment configuration...")
        os.environ['TENNIS_DB_BACKEND'] = 'sqlite'
        os.environ['TENNIS_DB_PATH'] = 'test.db'
        backend, config = TennisDBConfig.from_environment()
        print(f"✓ Environment config: {backend.value} with {config}")
    except Exception as e:
        print(f"✗ Environment config failed: {e}")
    
    # Create sample configurations
    print(f"\nCreating sample configuration files...")
    try:
        TennisDBConfig.create_sample_configs('sample_config')
        print(f"✓ Sample configurations created in sample_config/")
    except Exception as e:
        print(f"✗ Failed to create sample configs: {e}")


if __name__ == "__main__":
    main()