from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, g
from sqlite_tennis_db import SQLiteTennisDB
from usta import League, Team, Match, Facility, WeeklySchedule, DaySchedule, TimeSlot
import os
import json
from datetime import datetime
import threading

app = Flask(__name__)
app.secret_key = 'tennis_db_secret_key_change_in_production'

# Global database path (not the connection itself)
db_path = None

def get_db():
    """Get database connection for current thread"""
    if not hasattr(g, 'db') or g.db is None:
        if db_path is None:
            return None
        try:
            g.db = SQLiteTennisDB(db_path)
        except Exception as e:
            print(f"Error creating database connection: {e}")
            return None
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Close database connection at end of request"""
    db = getattr(g, 'db', None)
    if db is not None:
        # Close the connection if the database class has a close method
        if hasattr(db, 'conn') and db.conn:
            try:
                db.conn.close()
            except:
                pass
        g.db = None

def init_db(path):
    """Initialize database path (not connection)"""
    global db_path
    try:
        # Test the connection first
        test_db = SQLiteTennisDB(path)
        if hasattr(test_db, 'conn') and test_db.conn:
            test_db.conn.close()
        
        db_path = path
        return True
    except Exception as e:
        print(f"Error testing database: {e}")
        return False

@app.route('/')
def index():
    """Home page with database connection"""
    if db_path is None:
        return render_template('connect.html')
    return render_template('dashboard.html', db_path=db_path)

@app.route('/connect', methods=['POST'])
def connect_db():
    """Connect to database"""
    path = request.form.get('db_path', '').strip()
    if not path:
        flash('Please provide a database path', 'error')
        return redirect(url_for('index'))
    
    if init_db(path):
        flash(f'Successfully connected to {path}', 'success')
    else:
        flash(f'Failed to connect to {path}', 'error')
    
    return redirect(url_for('index'))

@app.route('/disconnect')
def disconnect():
    """Disconnect from database"""
    global db_path
    # Close any existing connection in current thread
    close_db(None)
    db_path = None
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
            
            if not name:
                flash('Facility name is required', 'error')
                return render_template('add_facility.html')
            
            # Create facility with basic info
            facility = Facility(id=facility_id, name=name, location=location)
            
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

# ==================== LEAGUE ROUTES ====================

@app.route('/leagues')
def leagues():
    """View all leagues"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
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
                                     sections=db.list_sections(),
                                     regions=db.list_regions(),
                                     age_groups=db.list_age_groups(),
                                     divisions=db.list_divisions())
            
            # Validate number of matches
            if num_matches < 1 or num_matches > 50:
                flash('Number of matches must be between 1 and 50', 'error')
                return render_template('add_league.html', 
                                     sections=db.list_sections(),
                                     regions=db.list_regions(),
                                     age_groups=db.list_age_groups(),
                                     divisions=db.list_divisions())
            
            # Validate day selections (no overlap)
            overlapping_days = set(preferred_days) & set(backup_days)
            if overlapping_days:
                flash(f'Days cannot be both preferred and backup: {", ".join(sorted(overlapping_days))}', 'error')
                return render_template('add_league.html', 
                                     sections=db.list_sections(),
                                     regions=db.list_regions(),
                                     age_groups=db.list_age_groups(),
                                     divisions=db.list_divisions())
            
            # Validate dates if both are provided
            if start_date and end_date:
                from datetime import datetime
                try:
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    if end_dt <= start_dt:
                        flash('End date must be after start date', 'error')
                        return render_template('add_league.html', 
                                             sections=db.list_sections(),
                                             regions=db.list_regions(),
                                             age_groups=db.list_age_groups(),
                                             divisions=db.list_divisions())
                except ValueError:
                    flash('Invalid date format. Please use the date picker.', 'error')
                    return render_template('add_league.html', 
                                         sections=db.list_sections(),
                                         regions=db.list_regions(),
                                         age_groups=db.list_age_groups(),
                                         divisions=db.list_divisions())
            
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
                             sections=db.list_sections(),
                             regions=db.list_regions(),
                             age_groups=db.list_age_groups(),
                             divisions=db.list_divisions())
    
    # GET request - show the form
    try:
        return render_template('add_league.html', 
                             sections=db.list_sections(),
                             regions=db.list_regions(),
                             age_groups=db.list_age_groups(),
                             divisions=db.list_divisions())
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
        
        return render_template('teams.html', 
                             teams=teams_list, 
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

# ==================== MATCH ROUTES ====================

@app.route('/matches')
def matches():
    """View matches with optional league filter"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    league_id = request.args.get('league_id', type=int)
    
    try:
        matches_list = db.list_matches(league_id=league_id)
        leagues_list = db.list_leagues()  # For filter dropdown
        
        # Get selected league info if filtering
        selected_league = None
        if league_id:
            selected_league = db.get_league(league_id)
        
        # Enhance matches with team and facility names
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
                'facility_name': 'Unknown'
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
            
            enhanced_matches.append(enhanced_match)
        
        return render_template('matches.html', 
                             matches=enhanced_matches, 
                             leagues=leagues_list,
                             selected_league=selected_league)
    except Exception as e:
        flash(f'Error loading matches: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/matches/add', methods=['GET', 'POST'])
def add_match():
    """Add a new match"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            match_id = int(request.form.get('id'))
            league_id = int(request.form.get('league_id'))
            home_team_id = int(request.form.get('home_team_id'))
            visitor_team_id = int(request.form.get('visitor_team_id'))
            facility_id = int(request.form.get('facility_id'))
            date = request.form.get('date', '').strip()
            time = request.form.get('time', '').strip()
            
            if not all([date, time]):
                flash('Date and time are required', 'error')
                return render_template('add_match.html', 
                                     leagues=db.list_leagues(),
                                     facilities=db.list_facilities())
            
            if home_team_id == visitor_team_id:
                flash('Home team and visitor team cannot be the same', 'error')
                return render_template('add_match.html', 
                                     leagues=db.list_leagues(),
                                     facilities=db.list_facilities())
            
            match = Match(
                id=match_id,
                league_id=league_id,
                home_team_id=home_team_id,
                visitor_team_id=visitor_team_id,
                facility_id=facility_id,
                date=date,
                time=time
            )
            db.add_match(match)
            
            flash(f'Successfully added match: ID {match_id}', 'success')
            return redirect(url_for('matches'))
            
        except ValueError as e:
            if 'already exists' in str(e):
                flash(f'Match with ID {match_id} already exists', 'error')
            else:
                flash(f'Invalid data: {e}', 'error')
        except Exception as e:
            flash(f'Error adding match: {e}', 'error')
        
        return render_template('add_match.html', 
                             leagues=db.list_leagues(),
                             facilities=db.list_facilities())
    
    # GET request - show the form
    try:
        return render_template('add_match.html', 
                             leagues=db.list_leagues(),
                             facilities=db.list_facilities())
    except Exception as e:
        flash(f'Error loading form data: {e}', 'error')
        return redirect(url_for('matches'))

# ==================== CALCULATE PAIRINGS ROUTES ====================


@app.route('/calculate-pairings', methods=['GET', 'POST'])
def calculate_pairings():
    """Calculate pairings form and results handler"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        leagues_list = db.list_leagues()
        
        if request.method == 'POST':
            # Handle form submission
            league_id = request.form.get('league_id', type=int)
            if not league_id:
                flash('Please select a league', 'error')
                return render_template('calculate_pairings.html', 
                                     leagues=leagues_list, 
                                     show_results=False)
            
            # Redirect to GET route with league_id to avoid form resubmission
            return redirect(url_for('calculate_pairings_results', league_id=league_id))
        
        # GET request - show the form
        return render_template('calculate_pairings.html', 
                             leagues=leagues_list, 
                             show_results=False)
        
    except Exception as e:
        flash(f'Error loading leagues: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/calculate-pairings-form')
def calculate_pairings_form():
    """Simple form-only version for navigation compatibility"""
    return redirect(url_for('calculate_pairings'))

@app.route('/calculate-pairings/<int:league_id>')
def calculate_pairings_results(league_id):
    """Calculate and display pairings for a specific league"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        # Get league information
        league = db.get_league(league_id)
        if not league:
            flash(f'League with ID {league_id} not found', 'error')
            return redirect(url_for('calculate_pairings'))
        
        # Get teams in the league
        teams = db.list_teams(league_id=league_id)
        if len(teams) < 2:
            flash(f'League "{league.name}" has only {len(teams)} team(s). Need at least 2 teams to generate pairings.', 'error')
            return redirect(url_for('teams', league_id=league_id))
        
        # ✅ Use League's calculate_pairings method directly
        pairings = league.calculate_pairings(teams)
        
        # Calculate statistics
        match_count_by_team = {}
        home_count_by_team = {}
        away_count_by_team = {}
        
        # Initialize counters
        for team in teams:
            match_count_by_team[team.id] = 0
            home_count_by_team[team.id] = 0
            away_count_by_team[team.id] = 0
        
        # Count matches
        for home_team, visitor_team in pairings:
            match_count_by_team[home_team.id] += 1
            match_count_by_team[visitor_team.id] += 1
            home_count_by_team[home_team.id] += 1
            away_count_by_team[visitor_team.id] += 1
        
        # Prepare team statistics
        team_stats = []
        for team in teams:
            stats = {
                'team': team,
                'total_matches': match_count_by_team[team.id],
                'home_matches': home_count_by_team[team.id],
                'away_matches': away_count_by_team[team.id],
                'matches_expected': league.num_matches
            }
            team_stats.append(stats)
        
        # Prepare pairing details with proper structure
        pairing_details = []
        for i, (home_team, visitor_team) in enumerate(pairings, 1):
            pairing_details.append({
                'match_number': i,
                'home_team': home_team,
                'visitor_team': visitor_team
            })
        
        # Enhanced balance analysis
        balance_analysis = {
            'teams_with_wrong_count': [],
            'imbalanced_teams': [],
            'max_imbalance': 0,
            'total_matches': len(pairings),
            'expected_per_team': league.num_matches
        }
        
        # Check for teams with wrong match count
        for team in teams:
            actual_count = match_count_by_team[team.id]
            if actual_count != league.num_matches:
                balance_analysis['teams_with_wrong_count'].append({
                    'team': team,
                    'actual': actual_count,
                    'expected': league.num_matches
                })
        
        # Check home/away balance
        for team in teams:
            home = home_count_by_team[team.id]
            away = away_count_by_team[team.id]
            imbalance = abs(home - away)
            
            if imbalance > balance_analysis['max_imbalance']:
                balance_analysis['max_imbalance'] = imbalance
            
            if imbalance > 1:  # More than 1 match difference is noteworthy
                balance_analysis['imbalanced_teams'].append({
                    'team': team,
                    'home_matches': home,
                    'away_matches': away,
                    'imbalance': imbalance
                })
        
        # Get all leagues for the form dropdown
        leagues_list = db.list_leagues()
        
        # Return unified template with results
        return render_template('calculate_pairings.html',
                             leagues=leagues_list,
                             selected_league=league,
                             teams=teams,
                             pairings=pairing_details,
                             team_stats=team_stats,
                             balance_analysis=balance_analysis,
                             show_results=True)
        
    except ValueError as e:
        flash(f'Error calculating pairings: {e}', 'error')
        return redirect(url_for('teams', league_id=league_id))
    except Exception as e:
        flash(f'Unexpected error: {e}', 'error')
        return redirect(url_for('calculate_pairings'))

@app.route('/api/calculate-pairings/<int:league_id>')
def api_calculate_pairings(league_id):
    """API endpoint to calculate pairings and return JSON"""
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
        
        # ✅ Use League's calculate_pairings method directly
        pairings = league.calculate_pairings(teams)
        
        # Format results
        results = {
            'league': {
                'id': league.id,
                'name': league.name,
                'num_matches': league.num_matches,
                'num_lines_per_match': league.num_lines_per_match
            },
            'teams_count': len(teams),
            'total_matches': len(pairings),
            'pairings': [
                {
                    'match_number': i + 1,
                    'home_team_id': home_team.id,
                    'home_team_name': home_team.name,
                    'visitor_team_id': visitor_team.id,
                    'visitor_team_name': visitor_team.name
                }
                for i, (home_team, visitor_team) in enumerate(pairings)
            ]
        }
        
        return jsonify(results)
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal server error: {e}'}), 500

# ==================== OTHER ROUTES ====================

@app.route('/constants')
def constants():
    """View USTA constants"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        constants_data = {
            'sections': db.list_sections(),
            'regions': db.list_regions(),
            'age_groups': db.list_age_groups(),
            'divisions': db.list_divisions()
        }
        return render_template('constants.html', constants=constants_data)
    except Exception as e:
        flash(f'Error loading constants: {e}', 'error')
        return redirect(url_for('index'))

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
            'db_path': db_path
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

if __name__ == '__main__':
    # Print all registered routes for debugging
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.endpoint}: {rule.rule}")
    
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)