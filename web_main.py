from flask import render_template, request, redirect, url_for, flash
from web_database import get_db, init_db
from typing import Optional, Type, Dict, Any

def register_routes(app):
    """Register main/core routes"""
    
    @app.route('/')
    def index():
        """Home page with database connection"""
        from web_database import db_config
        if db_config['backend_class'] is None:
            return render_template('connect.html')
        
        # If connected, redirect to dashboard
        return redirect(url_for('dashboard'))

    @app.route('/dashboard')
    def dashboard():
        """Dashboard page - main overview when connected to database"""
        from web_database import db_config
        if db_config['backend_class'] is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))
        
        connection_info = str(db_config['connection_params'])
        return render_template('dashboard.html', db_path=connection_info)

    @app.route('/connect', methods=['POST'])
    def connect_db():
        """Connect to database"""
        db_path = request.form.get('db_path', '').strip()
        backend_type = request.form.get('backend_type', 'sqlite').strip()
        
        if not db_path:
            flash('Please provide a database path', 'error')
            return redirect(url_for('index'))
        
        try:
            if backend_type.lower() == 'sqlite':
                from sqlite_tennis_db import SQLiteTennisDB
                backend_class = SQLiteTennisDB
                connection_params = {'db_path': db_path}
            else:
                flash(f'Unsupported backend type: {backend_type}', 'error')
                return redirect(url_for('index'))
            
            if init_db(backend_class, **connection_params):
                flash(f'Successfully connected to {db_path}', 'success')
                return redirect(url_for('dashboard'))  # Redirect to dashboard after successful connection
            else:
                flash(f'Failed to connect to {db_path}', 'error')
        
        except ImportError as e:
            flash(f'Database backend not available: {e}', 'error')
        except Exception as e:
            flash(f'Error connecting to database: {e}', 'error')
        
        return redirect(url_for('index'))

    @app.route('/disconnect')
    def disconnect():
        """Disconnect from database"""
        from web_database import db_config, close_db
        close_db(None)
        db_config['backend_class'] = None
        db_config['connection_params'] = {}
        flash('Disconnected from database', 'info')
        return redirect(url_for('index'))

    @app.route('/stats')
    def stats():
        """Database statistics page"""
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('dashboard'))
        
        try:
            from web_database import db_config
            stats_data = {
                'facilities_count': len(db.list_facilities()),
                'leagues_count': len(db.list_leagues()),
                'teams_count': len(db.list_teams()),
                'matches_count': len(db.list_matches()),
                'db_path': str(db_config['connection_params'])
            }
            
            # League breakdown
            leagues_list = db.list_leagues()
            league_stats = []
            for league in leagues_list:
                try:
                    teams_in_league = len(db.list_teams(league))
                    matches_in_league = len(db.list_matches(league))
                    league_stats.append({
                        'league': league,
                        'teams_count': teams_in_league,
                        'matches_count': matches_in_league
                    })
                except Exception as e:
                    print(f"Warning: Could not get stats for league {league.id}: {e}")
            
            stats_data['league_breakdown'] = league_stats
            
            return render_template('stats.html', stats=stats_data)
        except Exception as e:
            flash(f'Error loading statistics: {e}', 'error')
            return redirect(url_for('dashboard'))

    @app.route('/constants')
    def constants():
        """View USTA constants"""
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('dashboard'))
        
        try:
            from usta_constants import get_usta_constants
            constants_data = get_usta_constants()
            return render_template('constants.html', constants=constants_data)
        except Exception as e:
            flash(f'Error loading constants: {e}', 'error')
            return redirect(url_for('dashboard'))