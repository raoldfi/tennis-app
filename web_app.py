#!/usr/bin/env python3
"""
Tennis Web Application - Main Flask Application Entry Point

This is the main Flask web application for the Tennis Database system.
It registers all route modules and configures the application context.

Key Features:
- Modular route registration for different sections (facilities, leagues, teams, matches, etc.)
- Database connection management with multiple backend support
- Application context injection for templates
- Development and production startup configurations

Usage:
    python web_app.py

The application will start on http://localhost:5000 by default.
Use the web interface to connect to a database or pre-configure using
the startup script (start_tennis_app.py) for automated setup.

Author: Tennis App Development Team
"""

from flask import Flask
from typing import Optional, Type, Dict, Any
import web_import_export
import web_main
import web_facilities
import web_leagues
import web_teams
import web_matches
import web_schedule_match
import web_schedule  # Added missing import
from web_database import close_db, db_config, init_db, get_db

app = Flask(__name__)
app.secret_key = 'tennis_db_secret_key_change_in_production'

# Register all routes
web_main.register_routes(app)
web_facilities.register_routes(app)
web_leagues.register_routes(app)
web_teams.register_routes(app)
web_matches.register_routes(app, get_db)  # Pass get_db function
web_schedule.register_routes(app)
web_import_export.register_routes(app)
web_schedule_match.add_scheduling_routes_to_app(app)

# Database cleanup
app.teardown_appcontext(close_db)

from tennis_db_interface import TennisDBInterface

# ==================== APPLICATION CONTEXT ====================

@app.context_processor
def inject_db_path():
    """Inject database path into all templates"""
    if db_config['backend_class'] is not None:
        return {'db_path': str(db_config['connection_params'])}
    return {'db_path': None}

# ==================== STARTUP FUNCTIONS ====================

def create_app_with_sqlite(db_path: str):
    """Create Flask app configured with SQLite backend"""
    from sqlite_tennis_db import SQLiteTennisDB
    
    if init_db(SQLiteTennisDB, db_path=db_path):
        return app
    else:
        raise RuntimeError(f"Failed to initialize database at {db_path}")

def create_app_with_backend(backend_class: Type[TennisDBInterface], **connection_params):
    """Create Flask app configured with specified backend"""
    if init_db(backend_class, **connection_params):
        return app
    else:
        raise RuntimeError(f"Failed to initialize database with {backend_class.__name__}")

if __name__ == '__main__':
    # Print all registered routes for debugging
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.endpoint}: {rule.rule}")
    
    # Default to SQLite if no backend configured
    if db_config['backend_class'] is None:
        print("No database backend configured. Use connect route to configure database.")
    
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)