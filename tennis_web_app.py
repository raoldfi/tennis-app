from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, g
from tennis_db_interface import TennisDBInterface
from usta import League, Team, Match, Facility, WeeklySchedule, DaySchedule, TimeSlot
import os
import json
from datetime import datetime
import threading
from typing import Optional, Type, Any, Dict



app = Flask(__name__)
app.secret_key = 'tennis_db_secret_key_change_in_production'

# Global database configuration
db_config = {
    'backend_class': None,
    'connection_params': {}
}

def configure_database(backend_class: Type[TennisDBInterface], **connection_params):
    """Configure the database backend and connection parameters"""
    global db_config
    db_config['backend_class'] = backend_class
    db_config['connection_params'] = connection_params

def get_db() -> Optional[TennisDBInterface]:
    """Get database connection for current thread"""
    if not hasattr(g, 'db') or g.db is None:
        if db_config['backend_class'] is None:
            return None
        try:
            # Updated to pass connection_params as config dictionary
            g.db = db_config['backend_class'](db_config['connection_params'])
            g.db.connect()
        except Exception as e:
            print(f"Error creating database connection: {e}")
            return None
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Close database connection at end of request"""
    db = getattr(g, 'db', None)
    if db is not None:
        try:
            db.disconnect()
        except:
            pass
        g.db = None

def init_db(backend_class: Type[TennisDBInterface], **connection_params) -> bool:
    """Initialize database with specified backend and parameters"""
    try:
        # Test the connection first - updated to pass config dictionary
        test_db = backend_class(connection_params)
        test_db.connect()
        if test_db.ping():
            test_db.disconnect()
            configure_database(backend_class, **connection_params)
            return True
        else:
            test_db.disconnect()
            return False
    except Exception as e:
        print(f"Error testing database: {e}")
        return False

@app.route('/')
def index():
    """Home page with database connection"""
    if db_config['backend_class'] is None:
        return render_template('connect.html')
    
    # Get connection info for display
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
    
    # Import the appropriate backend class
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
    global db_config
    # Close any existing connection in current thread
    close_db(None)
    db_config = {'backend_class': None, 'connection_params': {}}
    flash('Disconnected from database', 'info')
    return redirect(url_for('index'))

# ==================== FACILITY ROUTES ====================

@app.route('/facilities')
def facilities():
    """View all facilities"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        facilities_list = db.list_facilities()
        return render_template('facilities.html', facilities=facilities_list)
    except Exception as e:
        flash(f'Error loading facilities: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/facilities/<int:facility_id>')
def view_facility(facility_id):
    """View detailed facility information including schedule"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        facility = db.get_facility(facility_id)
        if not facility:
            flash(f'Facility with ID {facility_id} not found', 'error')
            return redirect(url_for('facilities'))
        
        return render_template('view_facility.html', facility=facility)
        
    except Exception as e:
        flash(f'Error loading facility: {e}', 'error')
        return redirect(url_for('facilities'))

@app.route('/facilities/add', methods=['GET', 'POST'])
def add_facility():
    """Add a new facility with schedule and unavailable dates"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            facility_id = int(request.form.get('id'))
            name = request.form.get('name', '').strip()
            location = request.form.get('location', '').strip()
            total_courts = int(request.form.get('total_courts', 0))
            
            if not name:
                flash('Facility name is required', 'error')
                return render_template('add_facility.html')
            
            # Create facility with basic info
            facility = Facility(
                id=facility_id, 
                name=name, 
                location=location,
                total_courts=total_courts
            )
            
            # Process schedule data from form
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                day_schedule = DaySchedule()
                
                # Get time slots for this day
                time_inputs = request.form.getlist(f'{day.lower()}_times')
                court_inputs = request.form.getlist(f'{day.lower()}_courts')
                
                for time_str, courts_str in zip(time_inputs, court_inputs):
                    if time_str.strip() and courts_str.strip():
                        try:
                            courts = int(courts_str)
                            if courts > 0:
                                time_slot = TimeSlot(time=time_str.strip(), available_courts=courts)
                                day_schedule.start_times.append(time_slot)
                        except ValueError:
                            continue  # Skip invalid entries
                
                facility.schedule.set_day_schedule(day, day_schedule)
            
            # Process unavailable dates
            unavailable_dates_str = request.form.get('unavailable_dates', '').strip()
            if unavailable_dates_str:
                dates = [date.strip() for date in unavailable_dates_str.split('\n') if date.strip()]
                facility.unavailable_dates = dates
            
            db.add_facility(facility)
            
            flash(f'Successfully added facility: {name}', 'success')
            return redirect(url_for('facilities'))
            
        except ValueError as e:
            if 'already exists' in str(e):
                flash(f'Facility with ID {facility_id} already exists', 'error')
            else:
                flash(f'Invalid data: {e}', 'error')
        except Exception as e:
            flash(f'Error adding facility: {e}', 'error')
        
        return render_template('add_facility.html')
    
    # GET request - show the form
    return render_template('add_facility.html')

@app.route('/facilities/<int:facility_id>/edit', methods=['GET', 'POST'])
def edit_facility(facility_id):
    """Edit an existing facility"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        facility = db.get_facility(facility_id)
        if not facility:
            flash(f'Facility with ID {facility_id} not found', 'error')
            return redirect(url_for('facilities'))
    except Exception as e:
        flash(f'Error loading facility: {e}', 'error')
        return redirect(url_for('facilities'))
    
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            location = request.form.get('location', '').strip()
            total_courts = int(request.form.get('total_courts', 0))
            
            if not name:
                flash('Facility name is required', 'error')
                return render_template('edit_facility.html', facility=facility)
            
            # Update facility with basic info
            facility.name = name
            facility.location = location
            facility.total_courts = total_courts
            
            # Process schedule data from form
            facility.schedule = WeeklySchedule()  # Reset schedule
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                day_schedule = DaySchedule()
                
                # Get time slots for this day
                time_inputs = request.form.getlist(f'{day.lower()}_times')
                court_inputs = request.form.getlist(f'{day.lower()}_courts')
                
                for time_str, courts_str in zip(time_inputs, court_inputs):
                    if time_str.strip() and courts_str.strip():
                        try:
                            courts = int(courts_str)
                            if courts > 0:
                                time_slot = TimeSlot(time=time_str.strip(), available_courts=courts)
                                day_schedule.start_times.append(time_slot)
                        except ValueError:
                            continue  # Skip invalid entries
                
                facility.schedule.set_day_schedule(day, day_schedule)
            
            # Process unavailable dates
            unavailable_dates_str = request.form.get('unavailable_dates', '').strip()
            if unavailable_dates_str:
                dates = [date.strip() for date in unavailable_dates_str.split('\n') if date.strip()]
                facility.unavailable_dates = dates
            else:
                facility.unavailable_dates = []
            
            db.update_facility(facility)
            
            flash(f'Successfully updated facility: {name}', 'success')
            return redirect(url_for('facilities'))
            
        except ValueError as e:
            flash(f'Invalid data: {e}', 'error')
        except Exception as e:
            flash(f'Error updating facility: {e}', 'error')
        
        return render_template('edit_facility.html', facility=facility)
    
    # GET request - show the form with existing data
    return render_template('edit_facility.html', facility=facility)

# ==================== LEAGUE ROUTES ====================

@app.route('/leagues', methods=['GET', 'POST'])
def leagues():
    """View all leagues and handle match generation"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    # Handle POST request for match generation
    if request.method == 'POST':
        league_id = request.form.get('league_id', type=int)
        if not league_id:
            flash('Please select a league', 'error')
        else:
            try:
                # Get league and teams
                league = db.get_league(league_id)
                if not league:
                    flash(f'League with ID {league_id} not found', 'error')
                else:
                    teams = db.list_teams(league_id=league_id)
                    if len(teams) < 2:
                        flash(f'League "{league.name}" has only {len(teams)} team(s). Need at least 2 teams to generate matches.', 'error')
                        return redirect(url_for('teams', league_id=league_id))
                    
                    # Generate matches using League.generate_matches()
                    matches = league.generate_matches(teams)
                    
                    # Add/update matches in database
                    created_matches = []
                    updated_matches = []
                    failed_matches = []
                    
                    for match in matches:
                        try:
                            # Check if match already exists
                            existing_match = db.get_match(match.id)
                            
                            if existing_match:
                                # Update existing match with new pairing data
                                db.update_match(match)
                                
                                # Find team names for response
                                home_team = next(team for team in teams if team.id == match.home_team_id)
                                visitor_team = next(team for team in teams if team.id == match.visitor_team_id)
                                
                                updated_matches.append({
                                    'match_id': match.id,
                                    'home_team': home_team.name,
                                    'visitor_team': visitor_team.name,
                                    'facility_id': match.facility_id
                                })
                            else:
                                # Create new match
                                db.add_match(match)
                                
                                # Find team names for response
                                home_team = next(team for team in teams if team.id == match.home_team_id)
                                visitor_team = next(team for team in teams if team.id == match.visitor_team_id)
                                
                                created_matches.append({
                                    'match_id': match.id,
                                    'home_team': home_team.name,
                                    'visitor_team': visitor_team.name,
                                    'facility_id': match.facility_id
                                })
                                
                        except Exception as e:
                            print(f"Warning: Could not create/update match {match.id}: {e}")
                            failed_matches.append({
                                'match_id': match.id,
                                'error': str(e)
                            })
                            continue
                    
                    # Show results
                    total_processed = len(created_matches) + len(updated_matches)
                    if total_processed > 0:
                        if created_matches and updated_matches:
                            flash(f'Successfully generated {len(created_matches)} new matches and updated {len(updated_matches)} existing matches for "{league.name}"!', 'success')
                        elif created_matches:
                            flash(f'Successfully generated {len(created_matches)} matches for "{league.name}"!', 'success')
                        elif updated_matches:
                            flash(f'Successfully updated {len(updated_matches)} existing matches for "{league.name}"!', 'success')
                        
                        if failed_matches:
                            flash(f'Warning: {len(failed_matches)} matches could not be processed due to errors', 'warning')
                    else:
                        flash('No matches were processed. Please check for errors.', 'error')
                        
            except Exception as e:
                flash(f'Error generating matches: {e}', 'error')
    
    # Handle GET request - show leagues
    try:
        leagues_list = db.list_leagues()
        return render_template('leagues.html', leagues=leagues_list)
    except Exception as e:
        flash(f'Error loading leagues: {e}', 'error')
        return redirect(url_for('index'))
        

@app.route('/leagues/add', methods=['GET', 'POST'])
def add_league():
    """Add a new league with enhanced scheduling options"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            league_id = int(request.form.get('id'))
            name = request.form.get('name', '').strip()
            year = int(request.form.get('year'))
            section = request.form.get('section', '').strip()
            region = request.form.get('region', '').strip()
            age_group = request.form.get('age_group', '').strip()
            division = request.form.get('division', '').strip()
            num_lines_per_match = int(request.form.get('num_lines_per_match', 3))
            
            # New fields
            num_matches = int(request.form.get('num_matches', 10))
            allow_split_lines = bool(int(request.form.get('allow_split_lines', 0)))
            
            # Get selected days (may be empty lists)
            preferred_days = request.form.getlist('preferred_days')
            backup_days = request.form.getlist('backup_days')
            
            # Get optional date fields
            start_date = request.form.get('start_date', '').strip() or None
            end_date = request.form.get('end_date', '').strip() or None
            
            if not all([name, section, region, age_group, division]):
                flash('All required fields must be filled', 'error')
                return render_template('add_league.html', 
                                     sections=get_usta_constants()['sections'],
                                     regions=get_usta_constants()['regions'],
                                     age_groups=get_usta_constants()['age_groups'],
                                     divisions=get_usta_constants()['divisions'])
            
            # Validate number of matches
            if num_matches < 1 or num_matches > 50:
                flash('Number of matches must be between 1 and 50', 'error')
                return render_template('add_league.html', 
                                     sections=get_usta_constants()['sections'],
                                     regions=get_usta_constants()['regions'],
                                     age_groups=get_usta_constants()['age_groups'],
                                     divisions=get_usta_constants()['divisions'])
            
            # Validate day selections (no overlap)
            overlapping_days = set(preferred_days) & set(backup_days)
            if overlapping_days:
                flash(f'Days cannot be both preferred and backup: {", ".join(sorted(overlapping_days))}', 'error')
                return render_template('add_league.html', 
                                     sections=get_usta_constants()['sections'],
                                     regions=get_usta_constants()['regions'],
                                     age_groups=get_usta_constants()['age_groups'],
                                     divisions=get_usta_constants()['divisions'])
            
            # Validate dates if both are provided
            if start_date and end_date:
                from datetime import datetime
                try:
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    if end_dt <= start_dt:
                        flash('End date must be after start date', 'error')
                        return render_template('add_league.html', 
                                             sections=get_usta_constants()['sections'],
                                             regions=get_usta_constants()['regions'],
                                             age_groups=get_usta_constants()['age_groups'],
                                             divisions=get_usta_constants()['divisions'])
                except ValueError:
                    flash('Invalid date format. Please use the date picker.', 'error')
                    return render_template('add_league.html', 
                                         sections=get_usta_constants()['sections'],
                                         regions=get_usta_constants()['regions'],
                                         age_groups=get_usta_constants()['age_groups'],
                                         divisions=get_usta_constants()['divisions'])
            
            league = League(
                id=league_id,
                name=name,
                year=year,
                section=section,
                region=region,
                age_group=age_group,
                division=division,
                num_lines_per_match=num_lines_per_match,
                num_matches=num_matches,
                allow_split_lines=allow_split_lines,
                preferred_days=preferred_days,
                backup_days=backup_days,
                start_date=start_date,
                end_date=end_date
            )
            db.add_league(league)
            
            # Create descriptive success message
            split_text = "Lines can be split" if allow_split_lines else "All lines start together"
            days_text = ""
            if preferred_days:
                days_text += f"Preferred days: {', '.join(preferred_days)}"
            if backup_days:
                if days_text:
                    days_text += f"; Backup days: {', '.join(backup_days)}"
                else:
                    days_text += f"Backup days: {', '.join(backup_days)}"
            
            flash(f'Successfully added league: {name} ({num_matches} matches per team, {num_lines_per_match} lines per match, {split_text})', 'success')
            if days_text:
                flash(f'Scheduling: {days_text}', 'info')
            
            return redirect(url_for('leagues'))
            
        except ValueError as e:
            if 'already exists' in str(e):
                flash(f'League with ID {league_id} already exists', 'error')
            else:
                flash(f'Invalid data: {e}', 'error')
        except Exception as e:
            flash(f'Error adding league: {e}', 'error')
        
        return render_template('add_league.html', 
                             sections=get_usta_constants()['sections'],
                             regions=get_usta_constants()['regions'],
                             age_groups=get_usta_constants()['age_groups'],
                             divisions=get_usta_constants()['divisions'])
    
    # GET request - show the form
    try:
        return render_template('add_league.html', 
                             sections=get_usta_constants()['sections'],
                             regions=get_usta_constants()['regions'],
                             age_groups=get_usta_constants()['age_groups'],
                             divisions=get_usta_constants()['divisions'])
    except Exception as e:
        flash(f'Error loading form data: {e}', 'error')
        return redirect(url_for('leagues'))

@app.route('/leagues/<int:league_id>/edit', methods=['GET', 'POST'])
def edit_league(league_id):
    """Edit an existing league"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        league = db.get_league(league_id)
        if not league:
            flash(f'League with ID {league_id} not found', 'error')
            return redirect(url_for('leagues'))
    except Exception as e:
        flash(f'Error loading league: {e}', 'error')
        return redirect(url_for('leagues'))
    
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            year = int(request.form.get('year'))
            section = request.form.get('section', '').strip()
            region = request.form.get('region', '').strip()
            age_group = request.form.get('age_group', '').strip()
            division = request.form.get('division', '').strip()
            num_lines_per_match = int(request.form.get('num_lines_per_match', 3))
            
            # New fields
            num_matches = int(request.form.get('num_matches', 10))
            allow_split_lines = bool(int(request.form.get('allow_split_lines', 0)))
            
            # Get selected days (may be empty lists)
            preferred_days = request.form.getlist('preferred_days')
            backup_days = request.form.getlist('backup_days')
            
            # Get optional date fields
            start_date = request.form.get('start_date', '').strip() or None
            end_date = request.form.get('end_date', '').strip() or None
            
            if not all([name, section, region, age_group, division]):
                flash('All required fields must be filled', 'error')
                return render_template('edit_league.html', 
                                     league=league,
                                     sections=get_usta_constants()['sections'],
                                     regions=get_usta_constants()['regions'],
                                     age_groups=get_usta_constants()['age_groups'],
                                     divisions=get_usta_constants()['divisions'])
            
            # Validate number of matches
            if num_matches < 1 or num_matches > 50:
                flash('Number of matches must be between 1 and 50', 'error')
                return render_template('edit_league.html', 
                                     league=league,
                                     sections=get_usta_constants()['sections'],
                                     regions=get_usta_constants()['regions'],
                                     age_groups=get_usta_constants()['age_groups'],
                                     divisions=get_usta_constants()['divisions'])
            
            # Validate day selections (no overlap)
            overlapping_days = set(preferred_days) & set(backup_days)
            if overlapping_days:
                flash(f'Days cannot be both preferred and backup: {", ".join(sorted(overlapping_days))}', 'error')
                return render_template('edit_league.html', 
                                     league=league,
                                     sections=get_usta_constants()['sections'],
                                     regions=get_usta_constants()['regions'],
                                     age_groups=get_usta_constants()['age_groups'],
                                     divisions=get_usta_constants()['divisions'])
            
            # Validate dates if both are provided
            if start_date and end_date:
                from datetime import datetime
                try:
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    if end_dt <= start_dt:
                        flash('End date must be after start date', 'error')
                        return render_template('edit_league.html', 
                                             league=league,
                                             sections=get_usta_constants()['sections'],
                                             regions=get_usta_constants()['regions'],
                                             age_groups=get_usta_constants()['age_groups'],
                                             divisions=get_usta_constants()['divisions'])
                except ValueError:
                    flash('Invalid date format. Please use the date picker.', 'error')
                    return render_template('edit_league.html', 
                                         league=league,
                                         sections=get_usta_constants()['sections'],
                                         regions=get_usta_constants()['regions'],
                                         age_groups=get_usta_constants()['age_groups'],
                                         divisions=get_usta_constants()['divisions'])
            
            # Update the league object
            league.name = name
            league.year = year
            league.section = section
            league.region = region
            league.age_group = age_group
            league.division = division
            league.num_lines_per_match = num_lines_per_match
            league.num_matches = num_matches
            league.allow_split_lines = allow_split_lines
            league.preferred_days = preferred_days
            league.backup_days = backup_days
            league.start_date = start_date
            league.end_date = end_date
            
            db.update_league(league)
            
            # Create descriptive success message
            split_text = "Lines can be split" if allow_split_lines else "All lines start together"
            days_text = ""
            if preferred_days:
                days_text += f"Preferred days: {', '.join(preferred_days)}"
            if backup_days:
                if days_text:
                    days_text += f"; Backup days: {', '.join(backup_days)}"
                else:
                    days_text += f"Backup days: {', '.join(backup_days)}"
            
            flash(f'Successfully updated league: {name} ({num_matches} matches per team, {num_lines_per_match} lines per match, {split_text})', 'success')
            if days_text:
                flash(f'Scheduling: {days_text}', 'info')
            
            return redirect(url_for('leagues'))
            
        except ValueError as e:
            flash(f'Invalid data: {e}', 'error')
        except Exception as e:
            flash(f'Error updating league: {e}', 'error')
        
        return render_template('edit_league.html', 
                             league=league,
                             sections=get_usta_constants()['sections'],
                             regions=get_usta_constants()['regions'],
                             age_groups=get_usta_constants()['age_groups'],
                             divisions=get_usta_constants()['divisions'])
    
    # GET request - show the form with existing data
    try:
        return render_template('edit_league.html', 
                             league=league,
                             sections=get_usta_constants()['sections'],
                             regions=get_usta_constants()['regions'],
                             age_groups=get_usta_constants()['age_groups'],
                             divisions=get_usta_constants()['divisions'])
    except Exception as e:
        flash(f'Error loading form data: {e}', 'error')
        return redirect(url_for('leagues'))

# ==================== TEAM ROUTES ====================

@app.route('/teams')
def teams():
    """View teams with optional league filter"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    league_id = request.args.get('league_id', type=int)
    
    try:
        teams_list = db.list_teams(league_id=league_id)
        leagues_list = db.list_leagues()  # For filter dropdown
        
        # Get selected league info if filtering
        selected_league = None
        if league_id:
            selected_league = db.get_league(league_id)
        
        # Enhance teams with facility names
        enhanced_teams = []
        for team in teams_list:
            enhanced_team = {
                'team': team,
                'facility_name': 'Unknown Facility'
            }
            
            try:
                facility = db.get_facility(team.home_facility_id)
                if facility:
                    enhanced_team['facility_name'] = facility.name
            except Exception as e:
                print(f"Warning: Could not get facility {team.home_facility_id} for team {team.id}: {e}")
            
            enhanced_teams.append(enhanced_team)
        
        return render_template('teams.html', 
                             teams=enhanced_teams,  # Pass enhanced teams instead of raw teams
                             leagues=leagues_list,
                             selected_league=selected_league)
    except Exception as e:
        flash(f'Error loading teams: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/teams/add', methods=['GET', 'POST'])
def add_team():
    """Add a new team"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            team_id = int(request.form.get('id'))
            name = request.form.get('name', '').strip()
            league_id = int(request.form.get('league_id'))
            home_facility_id = int(request.form.get('home_facility_id'))
            captain = request.form.get('captain', '').strip()
            
            # Get preferred days
            preferred_days = request.form.getlist('preferred_days')
            
            if not all([name, captain]):
                flash('Team name and captain are required', 'error')
                return render_template('add_team.html', 
                                     leagues=db.list_leagues(),
                                     facilities=db.list_facilities())
            
            # Get the league object
            league = db.get_league(league_id)
            if not league:
                flash(f'League with ID {league_id} not found', 'error')
                return render_template('add_team.html', 
                                     leagues=db.list_leagues(),
                                     facilities=db.list_facilities())
            
            team = Team(
                id=team_id,
                name=name,
                league=league,
                home_facility_id=home_facility_id,
                captain=captain,
                preferred_days=preferred_days
            )
            db.add_team(team)
            
            flash(f'Successfully added team: {name}', 'success')
            return redirect(url_for('teams'))
            
        except ValueError as e:
            if 'already exists' in str(e):
                flash(f'Team with ID {team_id} already exists', 'error')
            else:
                flash(f'Invalid data: {e}', 'error')
        except Exception as e:
            flash(f'Error adding team: {e}', 'error')
        
        return render_template('add_team.html', 
                             leagues=db.list_leagues(),
                             facilities=db.list_facilities())
    
    # GET request - show the form
    try:
        return render_template('add_team.html', 
                             leagues=db.list_leagues(),
                             facilities=db.list_facilities())
    except Exception as e:
        flash(f'Error loading form data: {e}', 'error')
        return redirect(url_for('teams'))

@app.route('/teams/<int:team_id>/edit', methods=['GET', 'POST'])
def edit_team(team_id):
    """Edit an existing team"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        team = db.get_team(team_id)
        if not team:
            flash(f'Team with ID {team_id} not found', 'error')
            return redirect(url_for('teams'))
    except Exception as e:
        flash(f'Error loading team: {e}', 'error')
        return redirect(url_for('teams'))
    
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            league_id = int(request.form.get('league_id'))
            home_facility_id = int(request.form.get('home_facility_id'))
            captain = request.form.get('captain', '').strip()
            
            # Get preferred days
            preferred_days = request.form.getlist('preferred_days')
            
            if not all([name, captain]):
                flash('Team name and captain are required', 'error')
                return render_template('edit_team.html', 
                                     team=team,
                                     leagues=db.list_leagues(),
                                     facilities=db.list_facilities())
            
            # Get the league object
            league = db.get_league(league_id)
            if not league:
                flash(f'League with ID {league_id} not found', 'error')
                return render_template('edit_team.html', 
                                     team=team,
                                     leagues=db.list_leagues(),
                                     facilities=db.list_facilities())
            
            # Update the team object
            team.name = name
            team.league = league
            team.home_facility_id = home_facility_id
            team.captain = captain
            team.preferred_days = preferred_days
            
            db.update_team(team)
            
            flash(f'Successfully updated team: {name}', 'success')
            return redirect(url_for('teams'))
            
        except ValueError as e:
            flash(f'Invalid data: {e}', 'error')
        except Exception as e:
            flash(f'Error updating team: {e}', 'error')
        
        return render_template('edit_team.html', 
                             team=team,
                             leagues=db.list_leagues(),
                             facilities=db.list_facilities())
    
    # GET request - show the form with existing data
    try:
        return render_template('edit_team.html', 
                             team=team,
                             leagues=db.list_leagues(),
                             facilities=db.list_facilities())
    except Exception as e:
        flash(f'Error loading form data: {e}', 'error')
        return redirect(url_for('teams'))

@app.route('/teams/<int:team_id>/delete', methods=['DELETE'])
def delete_team_api(team_id):
    db = get_db()
    if db is None:
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        db.delete_team(team_id)
        return jsonify({'success': True, 'message': f'Team {team_id} deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== MATCH ROUTES ====================

@app.route('/matches')
def matches():
    """View matches with optional league filter and unscheduled match support"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    league_id = request.args.get('league_id', type=int)
    show_unscheduled = request.args.get('show_unscheduled', 'true').lower() == 'true'
    
    try:
        matches_list = db.list_matches(league_id=league_id, include_unscheduled=show_unscheduled)
        leagues_list = db.list_leagues()  # For filter dropdown
        facilities_list = db.list_facilities()  # For filter dropdown
        
        # Get selected league info if filtering
        selected_league = None
        if league_id:
            selected_league = db.get_league(league_id)
        
        # Enhance matches with team and facility names, plus status
        enhanced_matches = []
        for match in matches_list:
            enhanced_match = {
                'id': match.id,
                'league_id': match.league_id,
                'home_team_id': match.home_team_id,
                'visitor_team_id': match.visitor_team_id,
                'facility_id': match.facility_id,
                'date': match.date,
                'time': match.time,
                'home_team_name': 'Unknown',
                'visitor_team_name': 'Unknown',
                'facility_name': 'Unknown',
                'league_name': 'Unassigned',
                'status': match.get_status(),
                'is_scheduled': match.is_scheduled(),
                'missing_fields': match.get_missing_fields()
            }
            
            try:
                home_team = db.get_team(match.home_team_id)
                if home_team:
                    enhanced_match['home_team_name'] = home_team.name
            except Exception as e:
                print(f"Warning: Could not get home team {match.home_team_id}: {e}")
            
            try:
                visitor_team = db.get_team(match.visitor_team_id)
                if visitor_team:
                    enhanced_match['visitor_team_name'] = visitor_team.name
            except Exception as e:
                print(f"Warning: Could not get visitor team {match.visitor_team_id}: {e}")
            
            try:
                facility = db.get_facility(match.facility_id)
                if facility:
                    enhanced_match['facility_name'] = facility.name
            except Exception as e:
                print(f"Warning: Could not get facility {match.facility_id}: {e}")
            
            try:
                if match.league_id:
                    league = db.get_league(match.league_id)
                    if league:
                        enhanced_match['league_name'] = league.name
            except Exception as e:
                print(f"Warning: Could not get league {match.league_id}: {e}")
            
            enhanced_matches.append(enhanced_match)
        
        return render_template('matches.html', 
                             matches=enhanced_matches, 
                             leagues=leagues_list,
                             facilities=facilities_list,
                             selected_league=selected_league,
                             show_unscheduled=show_unscheduled)
    except Exception as e:
        flash(f'Error loading matches: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/matches/<int:match_id>/schedule', methods=['POST'])
def schedule_match(match_id):
    """Schedule an existing unscheduled match using auto-scheduling"""
    db = get_db()
    if db is None:
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        # Get the match object
        match = db.get_match(match_id)
        if not match:
            return jsonify({'error': f'Match {match_id} not found'}), 404
        
        # Use the auto-scheduling method with a list containing the single match
        result = db.auto_schedule_matches([match], dry_run=False)
        
        # Check if the match is now scheduled by querying the database
        updated_match = db.get_match(match_id)
        if updated_match and updated_match.is_scheduled():
            return jsonify({
                'success': True,
                'message': f'Match {match_id} has been automatically scheduled',
                'details': result
            })
        else:
            return jsonify({
                'error': 'Could not find suitable scheduling option for this match',
                'details': result
            }), 400
            
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to auto-schedule match: {e}'}), 500


# Fix for tennis_web_app.py - Update the schedule-all route

@app.route('/matches/schedule-all', methods=['POST'])
def schedule_all_matches():
    """Schedule all unscheduled matches, optionally filtered by league"""
    db = get_db()
    if db is None:
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        league_id = request.form.get('league_id', type=int)
        dry_run = request.form.get('dry_run', 'false').lower() == 'true'
        
        if league_id:
            # Get all matches in the specific league
            all_matches = db.list_matches(league_id=league_id, include_unscheduled=True)
            unscheduled_matches = [match for match in all_matches if not match.is_scheduled()]
            scope = f"league {league_id}"
        else:
            # Get all matches across all leagues
            all_matches = db.list_matches(include_unscheduled=True)
            unscheduled_matches = [match for match in all_matches if not match.is_scheduled()]
            scope = "all leagues"
        
        if not unscheduled_matches:
            return jsonify({
                'success': True,
                'message': f'No unscheduled matches found in {scope}',
                'scheduled_count': 0,
                'failed_count': 0,
                'total_count': 0
            })
        
        initial_unscheduled_count = len(unscheduled_matches)
        
        # Use auto-scheduling
        try:
            if league_id:
                # Try league-specific scheduling if the method exists
                result = db.auto_schedule_league_matches(league_id, dry_run=dry_run)
            else:
                # Use general match scheduling
                result = db.auto_schedule_matches(unscheduled_matches, dry_run=dry_run)
        except AttributeError:
            # If auto-scheduling methods don't exist, we can't schedule
            return jsonify({
                'error': 'Auto-scheduling functionality not available in this database backend'
            }), 500
        
        if not dry_run:
            # Re-fetch matches to count how many are now scheduled
            if league_id:
                current_matches = db.list_matches(league_id=league_id, include_unscheduled=True)
            else:
                current_matches = db.list_matches(include_unscheduled=True)
            
            current_unscheduled = [match for match in current_matches if not match.is_scheduled()]
            scheduled_count = initial_unscheduled_count - len(current_unscheduled)
            failed_count = len(current_unscheduled)
        else:
            # For dry run, extract from result if possible
            if isinstance(result, dict):
                scheduled_count = result.get('scheduled_count', 0)
                failed_count = result.get('failed_count', 0)
            else:
                scheduled_count = 0
                failed_count = 0
        
        total_count = initial_unscheduled_count
        
        if dry_run:
            message = f"Dry run completed for {scope}: {scheduled_count} of {total_count} matches could be scheduled"
        else:
            message = f"Scheduled {scheduled_count} of {total_count} matches in {scope}"
            
        if failed_count > 0:
            message += f" ({failed_count} failed)"
        
        return jsonify({
            'success': True,
            'message': message,
            'scheduled_count': scheduled_count,
            'failed_count': failed_count,
            'total_count': total_count,
            'details': result if isinstance(result, dict) else {}
        })
        
    except Exception as e:
        import traceback
        print(f"Error in schedule_all_matches: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Failed to schedule matches: {e}'}), 500


        
@app.route('/matches/<int:match_id>/unschedule', methods=['POST'])
def unschedule_match(match_id):
    """Remove scheduling from a match, making it unscheduled"""
    db = get_db()
    if db is None:
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        db.unschedule_match(match_id)
        
        return jsonify({
            'success': True,
            'message': f'Match {match_id} has been unscheduled'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to unschedule match: {e}'}), 500

@app.route('/matches/delete-all', methods=['POST'])
def delete_all_matches():
    """Delete all matches - useful for regenerating from pairings"""
    db = get_db()
    if db is None:
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        # Get confirmation from request
        confirm = request.form.get('confirm', '').lower() == 'true'
        if not confirm:
            return jsonify({'error': 'Confirmation required'}), 400
        
        # Count existing matches
        existing_matches = db.list_matches()
        match_count = len(existing_matches)
        
        # Delete all matches
        for match in existing_matches:
            db.delete_match(match.id)
        
        return jsonify({
            'success': True,
            'deleted_count': match_count,
            'message': f'Deleted {match_count} matches'
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to delete matches: {e}'}), 500



# ==================== API ROUTES ====================

@app.route('/api/teams/<int:league_id>')
def api_teams_by_league(league_id):
    """API endpoint to get teams by league"""
    db = get_db()
    if db is None:
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        teams_list = db.list_teams(league_id=league_id)
        teams_data = []
        for team in teams_list:
            teams_data.append({
                'id': team.id,
                'name': team.name,
                'captain': team.captain,
                'home_facility_id': team.home_facility_id
            })
        return jsonify(teams_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-matches/<int:league_id>')
def api_generate_matches(league_id):
    """API endpoint to generate matches and return JSON with deterministic ID preservation"""
    db = get_db()
    if db is None:
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        # Get league and teams
        league = db.get_league(league_id)
        if not league:
            return jsonify({'error': f'League with ID {league_id} not found'}), 404
        
        teams = db.list_teams(league_id=league_id)
        if len(teams) < 2:
            return jsonify({'error': f'Need at least 2 teams, found {len(teams)}'}), 400
        
        # Generate matches using League.generate_matches()
        matches = league.generate_matches(teams)
        
        # Process matches with deterministic ID preservation
        created_matches = []
        updated_matches = []
        failed_matches = []
        
        for match in matches:
            try:
                # Check if match already exists with this deterministic ID
                existing_match = db.get_match(match.id)
                
                if existing_match:
                    # Update existing match - preserve deterministic ID
                    db.update_match(match)
                    updated_matches.append({
                        'match_id': match.id,
                        'home_team_id': match.home_team_id,
                        'home_team_name': next(team.name for team in teams if team.id == match.home_team_id),
                        'visitor_team_id': match.visitor_team_id,
                        'visitor_team_name': next(team.name for team in teams if team.id == match.visitor_team_id),
                        'facility_id': match.facility_id,
                        'action': 'updated'
                    })
                else:
                    # Create new match with deterministic ID
                    db.add_match(match)
                    created_matches.append({
                        'match_id': match.id,
                        'home_team_id': match.home_team_id,
                        'home_team_name': next(team.name for team in teams if team.id == match.home_team_id),
                        'visitor_team_id': match.visitor_team_id,
                        'visitor_team_name': next(team.name for team in teams if team.id == match.visitor_team_id),
                        'facility_id': match.facility_id,
                        'action': 'created'
                    })
                    
            except Exception as e:
                failed_matches.append({
                    'match_id': match.id,
                    'error': str(e)
                })
        
        # Format results
        all_matches = created_matches + updated_matches
        
        results = {
            'league': {
                'id': league.id,
                'name': league.name,
                'num_matches': league.num_matches,
                'num_lines_per_match': league.num_lines_per_match
            },
            'teams_count': len(teams),
            'total_matches_processed': len(all_matches),
            'created_count': len(created_matches),
            'updated_count': len(updated_matches),
            'failed_count': len(failed_matches),
            'matches': [
                {
                    'match_id': match['match_id'],
                    'match_number': i + 1,
                    'home_team_id': match['home_team_id'],
                    'home_team_name': match['home_team_name'],
                    'visitor_team_id': match['visitor_team_id'],
                    'visitor_team_name': match['visitor_team_name'],
                    'facility_id': match['facility_id'],
                    'action': match['action']
                }
                for i, match in enumerate(all_matches)
            ],
            'deterministic_ids': True,  # Indicate that IDs are deterministic
            'message': f"Processed {len(all_matches)} matches: {len(created_matches)} created, {len(updated_matches)} updated"
        }
        
        if failed_matches:
            results['failed_matches'] = failed_matches
            results['warning'] = f"{len(failed_matches)} matches failed to process"
        
        return jsonify(results)
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal server error: {e}'}), 500

# ==================== HELPER FUNCTIONS ====================

def get_usta_constants() -> Dict[str, list]:
    """Get USTA constants from the usta module"""
    from usta import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS
    return {
        'sections': USTA_SECTIONS,
        'regions': USTA_REGIONS,
        'age_groups': USTA_AGE_GROUPS,
        'divisions': USTA_DIVISIONS
    }

# ==================== OTHER ROUTES ====================

@app.route('/constants')
def constants():
    """View USTA constants"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        constants_data = get_usta_constants()
        return render_template('constants.html', constants=constants_data)
    except Exception as e:
        flash(f'Error loading constants: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/stats')
def stats():
    """Database statistics page"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
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
                teams_in_league = len(db.list_teams(league_id=league.id))
                matches_in_league = len(db.list_matches(league_id=league.id))
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
        return redirect(url_for('index'))


# Add this route to tennis_web_app.py after the existing matches route

@app.route('/schedule')
def schedule():
    """View matches organized by date in a schedule format"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    league_id = request.args.get('league_id', type=int)
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    try:
        # Get all scheduled matches (only those with dates)
        all_matches = db.list_matches(league_id=league_id, include_unscheduled=False)
        leagues_list = db.list_leagues()  # For filter dropdown
        
        # Filter matches that have dates
        scheduled_matches = [match for match in all_matches if match.date]
        
        # Apply date range filter if provided
        if start_date:
            scheduled_matches = [match for match in scheduled_matches if match.date >= start_date]
        if end_date:
            scheduled_matches = [match for match in scheduled_matches if match.date <= end_date]
        
        # Get selected league info if filtering
        selected_league = None
        if league_id:
            selected_league = db.get_league(league_id)
        
        # Enhance matches with team and facility names
        enhanced_matches = []
        for match in scheduled_matches:
            enhanced_match = {
                'id': match.id,
                'league_id': match.league_id,
                'home_team_id': match.home_team_id,
                'visitor_team_id': match.visitor_team_id,
                'facility_id': match.facility_id,
                'date': match.date,
                'time': match.time,
                'home_team_name': 'Unknown',
                'visitor_team_name': 'Unknown',
                'facility_name': 'Unknown',
                'league_name': 'Unknown',
                'status': match.get_status()
            }
            
            try:
                home_team = db.get_team(match.home_team_id)
                if home_team:
                    enhanced_match['home_team_name'] = home_team.name
            except Exception as e:
                print(f"Warning: Could not get home team {match.home_team_id}: {e}")
            
            try:
                visitor_team = db.get_team(match.visitor_team_id)
                if visitor_team:
                    enhanced_match['visitor_team_name'] = visitor_team.name
            except Exception as e:
                print(f"Warning: Could not get visitor team {match.visitor_team_id}: {e}")
            
            try:
                facility = db.get_facility(match.facility_id)
                if facility:
                    enhanced_match['facility_name'] = facility.name
            except Exception as e:
                print(f"Warning: Could not get facility {match.facility_id}: {e}")
            
            try:
                if match.league_id:
                    league = db.get_league(match.league_id)
                    if league:
                        enhanced_match['league_name'] = league.name
            except Exception as e:
                print(f"Warning: Could not get league {match.league_id}: {e}")
            
            enhanced_matches.append(enhanced_match)
        
        # Group matches by date
        from collections import defaultdict
        from datetime import datetime
        
        matches_by_date = defaultdict(list)
        for match in enhanced_matches:
            matches_by_date[match['date']].append(match)
        
        # Sort matches within each date by time
        for date_key in matches_by_date:
            matches_by_date[date_key].sort(key=lambda x: x['time'] or '00:00')
        
        # Convert to sorted list of (date, day_name, matches) tuples
        schedule_data = []
        for date_str in sorted(matches_by_date.keys()):
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                day_name = date_obj.strftime('%A')  # Full day name
                formatted_date = date_obj.strftime('%B %d, %Y')  # "January 15, 2025"
            except ValueError:
                day_name = 'Unknown'
                formatted_date = date_str
            
            schedule_data.append({
                'date_str': date_str,
                'day_name': day_name,
                'formatted_date': formatted_date,
                'matches': matches_by_date[date_str]
            })
        
        return render_template('schedule.html', 
                             schedule_data=schedule_data,
                             leagues=leagues_list,
                             selected_league=selected_league,
                             start_date=start_date,
                             end_date=end_date,
                             total_matches=len(enhanced_matches))
    
    except Exception as e:
        flash(f'Error loading schedule: {e}', 'error')
        return redirect(url_for('index'))
        

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