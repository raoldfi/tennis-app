#!/usr/bin/env python3
"""
Tennis Web App Starter Script

This script demonstrates how to start the tennis web app with different database backends
using the new interface-based architecture.

Usage:
    python start_tennis_app.py --backend sqlite --db-path tennis.db
    python start_tennis_app.py --backend sqlite --db-path /path/to/tennis.db --port 8080
    python start_tennis_app.py --backend postgresql --host localhost --database tennis --user tennis_user
"""

import argparse
import sys
import os
from typing import Type, Dict, Any

# Import the updated web app
from web_app import app, create_app_with_backend, TennisDBInterface

def get_sqlite_backend():
    """Import and return SQLite backend class"""
    try:
        from sqlite_tennis_db import SQLiteTennisDB
        return SQLiteTennisDB
    except ImportError as e:
        print(f"Error: SQLite backend not available: {e}")
        sys.exit(1)

def get_postgresql_backend():
    """Import and return PostgreSQL backend class (when implemented)"""
    try:
        # This would be implemented in the future
        from postgresql_tennis_db import PostgreSQLTennisDB
        return PostgreSQLTennisDB
    except ImportError as e:
        print(f"Error: PostgreSQL backend not available: {e}")
        print("Note: PostgreSQL backend is not yet implemented.")
        sys.exit(1)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Start the Tennis Database Web Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start with SQLite database
  python start_tennis_app.py --backend sqlite --db-path tennis.db
  
  # Start with SQLite on custom port
  python start_tennis_app.py --backend sqlite --db-path tennis.db --port 8080
  
  # Start with PostgreSQL (when implemented)
  python start_tennis_app.py --backend postgresql --host localhost --database tennis --user tennis_user
  
  # Start without pre-configured database (use web interface to connect)
  python start_tennis_app.py
        """
    )
    
    parser.add_argument(
        '--backend', 
        choices=['sqlite', 'postgresql'], 
        help='Database backend to use'
    )
    
    parser.add_argument(
        '--host', 
        default='0.0.0.0', 
        help='Host to bind the web server to (default: 0.0.0.0)'
    )
    
    parser.add_argument(
        '--port', 
        type=int, 
        default=5000, 
        help='Port to bind the web server to (default: 5000)'
    )
    
    parser.add_argument(
        '--debug', 
        action='store_true', 
        help='Enable debug mode'
    )
    
    # SQLite-specific arguments
    parser.add_argument(
        '--db-path', 
        help='Path to SQLite database file (for sqlite backend)'
    )
    
    # PostgreSQL-specific arguments
    parser.add_argument(
        '--db-host', 
        default='localhost', 
        help='PostgreSQL host (default: localhost)'
    )
    
    parser.add_argument(
        '--db-port', 
        type=int, 
        default=5432, 
        help='PostgreSQL port (default: 5432)'
    )
    
    parser.add_argument(
        '--database', 
        help='PostgreSQL database name'
    )
    
    parser.add_argument(
        '--user', 
        help='PostgreSQL username'
    )
    
    parser.add_argument(
        '--password', 
        help='PostgreSQL password'
    )
    
    return parser.parse_args()

def validate_backend_args(args):
    """Validate that required arguments are provided for the selected backend"""
    if args.backend == 'sqlite':
        if not args.db_path:
            print("Error: --db-path is required for SQLite backend")
            sys.exit(1)
        
        # Check if directory exists for the database file
        db_dir = os.path.dirname(os.path.abspath(args.db_path))
        if not os.path.exists(db_dir):
            print(f"Error: Directory does not exist: {db_dir}")
            sys.exit(1)
    
    elif args.backend == 'postgresql':
        required_args = ['database', 'user']
        missing_args = [arg for arg in required_args if not getattr(args, arg)]
        if missing_args:
            print(f"Error: The following arguments are required for PostgreSQL backend: {', '.join('--' + arg for arg in missing_args)}")
            sys.exit(1)

def get_backend_config(args) -> tuple[Type[TennisDBInterface], Dict[str, Any]]:
    """Get backend class and connection parameters based on arguments"""
    if args.backend == 'sqlite':
        backend_class = get_sqlite_backend()
        connection_params = {'db_path': args.db_path}
        
    elif args.backend == 'postgresql':
        backend_class = get_postgresql_backend()
        connection_params = {
            'host': args.db_host,
            'port': args.db_port,
            'database': args.database,
            'user': args.user,
            'password': args.password
        }
    
    else:
        raise ValueError(f"Unsupported backend: {args.backend}")
    
    return backend_class, connection_params

def print_startup_info(args, backend_class=None, connection_params=None):
    """Print startup information"""
    print("=" * 60)
    print("🎾 Tennis Database Web Application")
    print("=" * 60)
    
    if args.backend:
        print(f"Backend: {args.backend.title()}")
        if args.backend == 'sqlite':
            print(f"Database File: {args.db_path}")
        elif args.backend == 'postgresql':
            print(f"Database: {connection_params['user']}@{connection_params['host']}:{connection_params['port']}/{connection_params['database']}")
    else:
        print("Backend: Not configured (use web interface to connect)")
    
    print(f"Web Server: http://{args.host}:{args.port}")
    print(f"Debug Mode: {'Enabled' if args.debug else 'Disabled'}")
    print("=" * 60)
    
    if args.backend:
        print(f"✅ Pre-configured with {args.backend.title()} backend")
        print("   You can start using the application immediately!")
    else:
        print("⚠️  No database backend configured")
        print("   Visit the web interface to connect to a database")
    
    print("\n🚀 Starting web server...")

def main():
    """Main function"""
    args = parse_arguments()
    
    # If backend is specified, validate arguments and configure the app
    if args.backend:
        validate_backend_args(args)
        backend_class, connection_params = get_backend_config(args)
        
        print_startup_info(args, backend_class, connection_params)
        
        try:
            # Initialize the app with the specified backend
            create_app_with_backend(backend_class, **connection_params)
            print("✅ Database connection established successfully!")
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            print("\nTroubleshooting:")
            if args.backend == 'sqlite':
                print(f"- Check that the directory exists: {os.path.dirname(os.path.abspath(args.db_path))}")
                print(f"- Check file permissions for: {args.db_path}")
            elif args.backend == 'postgresql':
                print("- Verify PostgreSQL server is running")
                print("- Check connection parameters (host, port, database, user, password)")
                print("- Ensure the database and user exist")
            sys.exit(1)
    else:
        print_startup_info(args)
        print("📝 You can configure the database through the web interface")
    
    # Start the Flask web server
    try:
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
