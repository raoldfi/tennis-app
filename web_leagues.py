"""
Complete Tennis Web App - League Management Routes v2
Enhanced with table view actions: view, edit, delete, and generate_matches
Full implementation with error handling and modern API endpoints
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, make_response
from werkzeug.utils import secure_filename
import yaml
import json
from datetime import datetime, date
import traceback
import tempfile
import os

from usta_league import League
from web_database import get_db
from match_generator import MatchGenerator

def register_routes(app):
    """Register league-related routes with enhanced table actions"""

    # ==================== MAIN LEAGUES PAGE ====================
    
    @app.route('/leagues')
    def leagues():
        """Main leagues page - display all leagues in table format"""
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))
        
        try:
            leagues_list = db.list_leagues()
            
            # Enhance leagues with additional data for table display
            enhanced_leagues = []
            for league in leagues_list:
                # Convert league to dict properly
                if hasattr(league, '__dict__'):
                    enhanced_league = league.__dict__.copy()
                else:
                    enhanced_league = {
                        'id': getattr(league, 'id', None),
                        'name': getattr(league, 'name', ''),
                        'year': getattr(league, 'year', ''),
                        'section': getattr(league, 'section', ''),
                        'region': getattr(league, 'region', ''),
                        'age_group': getattr(league, 'age_group', ''),
                        'division': getattr(league, 'division', '')
                    }
                
                # Add team and match counts
                try:
                    teams = db.list_teams(league)
                    enhanced_league['teams_count'] = len(teams) if teams else 0
                    print(f"League {enhanced_league.get('name')} has {enhanced_league['teams_count']} teams")  # Debug
                except Exception as e:
                    print(f"Error getting teams for league {getattr(league, 'id', 'unknown')}: {e}")
                    enhanced_league['teams_count'] = 0
    
                try:
                    matches = db.list_matches(league=league)
                    enhanced_league['matches_count'] = len(matches) if matches else 0
                    print(f"League {enhanced_league.get('name')} has {enhanced_league['matches_count']} matches")  # Debug
                except Exception as e:
                    print(f"Error getting matches for league {getattr(league, 'id', 'unknown')}: {e}")
                    enhanced_league['matches_count'] = 0
                
                enhanced_leagues.append(enhanced_league)
            
            return render_template('leagues.html', leagues=enhanced_leagues)
        except Exception as e:
            flash(f'Error loading leagues: {e}', 'error')
            return redirect(url_for('index'))

    # ==================== ADD LEAGUE ====================
    
    @app.route('/leagues/add', methods=['GET', 'POST'])
    def add_league():
        """Add a new league"""
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            try:
                # Extract form data
                league_data = {
                    'name': request.form.get('name', '').strip(),
                    'year': request.form.get('year', type=int),
                    'section': request.form.get('section', '').strip(),
                    'region': request.form.get('region', '').strip(),
                    'age_group': request.form.get('age_group', '').strip(),
                    'division': request.form.get('division', '').strip(),
                    'num_matches': request.form.get('num_matches', type=int) or 12,
                    'num_lines_per_match': request.form.get('num_lines_per_match', type=int) or 3,
                    'allow_split_lines': bool(request.form.get('allow_split_lines', type=int)),
                    'start_date': request.form.get('start_date') or None,
                    'end_date': request.form.get('end_date') or None
                }
                
                # Validate required fields
                if not league_data['name']:
                    flash('League name is required', 'error')
                    return render_template('add_league.html')
                
                if not league_data['year'] or league_data['year'] < 2000:
                    flash('Valid year is required', 'error')
                    return render_template('add_league.html')
                
                # Create League object
                league = League(
                    name=league_data['name'],
                    year=league_data['year'],
                    section=league_data['section'],
                    region=league_data['region'],
                    age_group=league_data['age_group'],
                    division=league_data['division']
                )
                
                # Add optional fields
                league.num_matches = league_data['num_matches']
                league.num_lines_per_match = league_data['num_lines_per_match']
                league.allow_split_lines = league_data['allow_split_lines']
                
                # Convert date strings to date objects
                if league_data['start_date']:
                    league.start_date = date.fromisoformat(league_data['start_date'])
                if league_data['end_date']:
                    league.end_date = date.fromisoformat(league_data['end_date'])
                
                # Add to database
                if db.add_league(league):
                    flash(f'League "{league.name}" created successfully', 'success')
                    return redirect(url_for('leagues'))
                else:
                    flash('Failed to create league', 'error')
                    
            except Exception as e:
                flash(f'Error creating league: {str(e)}', 'error')
        
        # Add these lines for GET request:
        return render_template('add_league.html',
                             sections=db.list_sections(),
                             regions=db.list_regions(), 
                             age_groups=db.list_age_groups(),
                             divisions=db.list_divisions(),
                             current_year=datetime.now().year)


    
    # ==================== VIEW LEAGUE ACTION ====================
    

    # Replace the existing view_league function in web_leagues.py with this updated version:
    
    @app.route('/leagues/<int:league_id>')
    @app.route('/leagues/<int:league_id>/view')
    def view_league(league_id):
        """View detailed information about a specific league"""
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))
        
        try:
            # Get the league - try different methods based on your database implementation
            league = None
            try:
                # Try direct get_league method if it exists
                league = db.get_league(league_id)
            except AttributeError:
                # Fallback to list_leagues and find by ID
                leagues_list = db.list_leagues()
                for l in leagues_list:
                    if l.id == league_id:
                        league = l
                        break
            
            if not league:
                flash(f'League {league_id} not found', 'error')
                return redirect(url_for('leagues'))
            
            # Get teams for this league
            teams = db.list_teams(league)
            
            # Enhance teams with facility names
            enhanced_teams = []
            if teams:
                for team in teams:
                    # Handle both Team objects and dictionaries
                    if hasattr(team, '__dict__'):  # It's a Team object
                        team_dict = team.__dict__.copy()
                        
                        # Get facility name and ID if team has a home facility
                        if hasattr(team, 'preferred_facilities') and team.preferred_facilities:
                            try:
                                primary_facility = team.get_primary_facility()
                                team_dict['home_facility_name'] = primary_facility.name
                                team_dict['home_facility_id'] = primary_facility.id
                            except (AttributeError, IndexError):
                                team_dict['home_facility_name'] = None
                                team_dict['home_facility_id'] = None
                        else:
                            team_dict['home_facility_name'] = None
                            team_dict['home_facility_id'] = None
                    else:  # It's already a dictionary
                        team_dict = dict(team) if not isinstance(team, dict) else team.copy()
                        # For dictionary case, we can't call get_primary_facility(), so set to None or use existing value
                        if 'home_facility_name' not in team_dict:
                            team_dict['home_facility_name'] = None
                    
                    # Handle preferred_days as a list
                    if hasattr(team, '__dict__'):  # Team object
                        if hasattr(team, 'preferred_days'):
                            if isinstance(team.preferred_days, str):
                                # If it's a string, try to parse it as JSON or split by comma
                                try:
                                    import json
                                    team_dict['preferred_days'] = json.loads(team.preferred_days)
                                except:
                                    team_dict['preferred_days'] = [day.strip() for day in team.preferred_days.split(',') if day.strip()]
                            else:
                                team_dict['preferred_days'] = team.preferred_days
                        else:
                            team_dict['preferred_days'] = []
                    else:  # Dictionary
                        # For dictionary case, preferred_days might already be in the right format
                        if 'preferred_days' in team_dict:
                            if isinstance(team_dict['preferred_days'], str):
                                try:
                                    import json
                                    team_dict['preferred_days'] = json.loads(team_dict['preferred_days'])
                                except:
                                    team_dict['preferred_days'] = [day.strip() for day in team_dict['preferred_days'].split(',') if day.strip()]
                        else:
                            team_dict['preferred_days'] = []
                    
                    enhanced_teams.append(team_dict)
            
            # Get matches for this league
            matches = db.list_matches(league=league)
            
            # Calculate league statistics
            league_stats = {
                'teams_count': len(teams) if teams else 0,
                'matches_count': len(matches) if matches else 0,
                'scheduled_matches': 0,
                'unscheduled_matches': 0
            }
            
            # Count scheduled vs unscheduled matches
            if matches:
                for match in matches:
                    # Check various possible date fields
                    has_date = False
                    for date_field in ['scheduled_date', 'date', 'match_date']:
                        if hasattr(match, date_field) and getattr(match, date_field):
                            has_date = True
                            break
                    
                    if has_date:
                        league_stats['scheduled_matches'] += 1
                    else:
                        league_stats['unscheduled_matches'] += 1
            
            # Convert league to dict for template if needed
            league_dict = league.__dict__.copy() if hasattr(league, '__dict__') else dict(league)
            
            # Handle preferred_days and backup_days as lists for the league
            for field in ['preferred_days', 'backup_days']:
                if field in league_dict and league_dict[field]:
                    if isinstance(league_dict[field], str):
                        # If it's a string, try to parse it as JSON or split by comma
                        try:
                            import json
                            league_dict[field] = json.loads(league_dict[field])
                        except:
                            league_dict[field] = [day.strip() for day in league_dict[field].split(',') if day.strip()]
                    elif not isinstance(league_dict[field], list):
                        league_dict[field] = []
                else:
                    league_dict[field] = []
            
            return render_template('view_league.html', 
                                 league=league_dict, 
                                 teams=enhanced_teams, 
                                 league_stats=league_stats)
            
        except Exception as e:
            flash(f'Error loading league details: {e}', 'error')
            print(f"Error in view_league: {e}")
            import traceback
            traceback.print_exc()
            return redirect(url_for('leagues'))



    # ==================== EDIT LEAGUE ACTION ====================
    
    @app.route('/leagues/<int:league_id>/edit', methods=['GET', 'POST'])
    def edit_league(league_id):
        """Edit league information"""
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))
        
        try:
            league = db.get_league(league_id)
            if not league:
                flash(f'League {league_id} not found', 'error')
                return redirect(url_for('leagues'))
            
            if request.method == 'POST':
                # Handle form submission for editing league
                try:
                    # Extract form data
                    updated_data = {
                        'name': request.form.get('name', '').strip(),
                        'year': request.form.get('year', type=int),
                        'section': request.form.get('section', '').strip(),
                        'region': request.form.get('region', '').strip(),
                        'age_group': request.form.get('age_group', '').strip(),
                        'division': request.form.get('division', '').strip(),
                        'num_matches': request.form.get('num_matches', type=int),
                        'num_lines_per_match': request.form.get('num_lines_per_match', type=int),
                        'allow_split_lines': bool(request.form.get('allow_split_lines', type=int)),
                        'start_date': request.form.get('start_date') or None,
                        'end_date': request.form.get('end_date') or None,
                        # ADD THESE TWO LINES:
                        'preferred_days': request.form.getlist('preferred_days'),
                        'backup_days': request.form.getlist('backup_days')
}
                    
                    # Validate required fields
                    league.name = updated_data['name']
                    league.year = updated_data['year']
                    league.section = updated_data['section']
                    league.region = updated_data['region']
                    league.age_group = updated_data['age_group']
                    league.division = updated_data['division']
                    league.num_matches = updated_data['num_matches']
                    league.num_lines_per_match = updated_data['num_lines_per_match']
                    league.allow_split_lines = updated_data['allow_split_lines']
                    # Convert date strings to date objects
                    if updated_data['start_date']:
                        league.start_date = date.fromisoformat(updated_data['start_date'])
                    else:
                        league.start_date = None
                    if updated_data['end_date']:
                        league.end_date = date.fromisoformat(updated_data['end_date'])
                    else:
                        league.end_date = None
                    # ADD THESE TWO LINES:
                    league.preferred_days = updated_data['preferred_days']
                    league.backup_days = updated_data['backup_days']
                    
                    # Update league in database
                    success = db.update_league(league)
                    
                    if success:
                        flash(f'League "{league.name}" updated successfully', 'success')
                        return redirect(url_for('view_league', league_id=league_id))
                    else:
                        flash('Failed to update league', 'error')
                        print('Failed to update league', 'error')
                        
                except Exception as e:
                    flash(f'Error updating league: {str(e)}', 'error')
                    print(f'Error updating league: {str(e)}', 'error')

            
            return render_template('edit_league.html', 
                                 league=league,
                                 sections=db.list_sections(),
                                 regions=db.list_regions(),
                                 age_groups=db.list_age_groups(),
                                 divisions=db.list_divisions())
            
        except Exception as e:
            flash(f'Error loading league for editing: {e}', 'error')
            return redirect(url_for('leagues'))

    # ==================== DELETE LEAGUE ACTION ====================
    
    # @app.route('/leagues/<int:league_id>/delete', methods=['POST'])
    # def delete_league(league_id):
    #     """Delete a league and all associated data"""
    #     db = get_db()
    #     if db is None:
    #         flash('No database connection', 'error')
    #         return redirect(url_for('index'))
        
    #     try:
    #         league = db.get_league(league_id)
    #         if not league:
    #             flash(f'League {league_id} not found', 'error')
    #             return redirect(url_for('leagues'))
            
    #         league_name = league.name
            
    #         # Delete league and associated data
    #         success = db.delete_league(league)
            
    #         if success:
    #             flash(f'League "{league_name}" and all associated data deleted successfully', 'success')
    #         else:
    #             flash(f'Failed to delete league "{league_name}"', 'error')
                
    #     except Exception as e:
    #         flash(f'Error deleting league: {str(e)}', 'error')
        
    #     return redirect(url_for('leagues'))

    # ==================== GENERATE MATCHES ROUTES ====================
    
    @app.route('/generate-matches', methods=['GET', 'POST'])
    def generate_matches():
        """Generate matches page - handles both display and form submission"""
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            # Handle form submission
            try:
                league_id = request.form.get('league_id', type=int)
                if not league_id:
                    flash('Please select a league', 'error')
                    return redirect(url_for('generate_matches'))
                
                # Get league
                league = db.get_league(league_id)
                if not league:
                    flash(f'League {league_id} not found', 'error')
                    return redirect(url_for('generate_matches'))
                
                # Get teams for this league
                teams = db.list_teams(league)
                print(f"DEBUG: Found {len(teams)} teams for league {league.name}")
                for i, team in enumerate(teams):
                    print(f"DEBUG: Team {i}: ID={getattr(team, 'id', 'MISSING')}, Name={getattr(team, 'name', 'MISSING')}")

                if len(teams) < 2:
                    flash(f'Need at least 2 teams to generate matches. League "{league.name}" has only {len(teams)} team(s).', 'error')
                    return redirect(url_for('generate_matches'))
                
                # Check for existing matches
                existing_matches = db.list_matches(league=league)
                if existing_matches:
                    flash(f'League "{league.name}" already has {len(existing_matches)} matches. Delete existing matches first if you want to regenerate.', 'warning')
                    return redirect(url_for('generate_matches'))
                
                # Generate matches using the match_generator class
                match_generator = MatchGenerator()
                generated_matches = match_generator.generate_matches(teams=teams, league=league)

                if generated_matches and len(generated_matches) > 0:
                    # Save matches to database
                    try: 
                        for match in generated_matches:
                            db.add_match(match)
                            
                    except Exception as e:
                        flash(f'Failed to save generated matches to database: {str(e)}','error')
                        raise
                    

                    flash(f'Successfully generated {len(generated_matches)} matches for league "{league.name}"', 'success')

                else:
                    flash('No matches were generated', 'error')
                    
            except Exception as e:
                flash(f'Failed to generate matches: {str(e)}', 'error')
                return redirect(url_for('generate_matches'))
        
        # Handle GET request - show the form
        try:
            # leagues_list = db.list_leagues()
            # return render_template('generate_matches.html', leagues=leagues_list)
            return redirect(url_for('leagues'))
        except Exception as e:
            flash(f'Error loading leagues: {e}', 'error')
            return redirect(url_for('index'))

    



    # ==================== AJAX API ENDPOINTS ====================
    
    @app.route('/api/leagues/<int:league_id>')
    def api_get_league(league_id):
        """API endpoint to get league details as JSON"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500
        
        try:
            league = db.get_league(league_id)
            if not league:
                return jsonify({'error': 'League not found'}), 404
            
            # Get additional data
            teams = db.list_teams(league)
            matches = db.list_matches(league=league)
            
            league_data = {
                'id': league.id,
                'name': league.name,
                'year': league.year,
                'section': league.section,
                'region': league.region,
                'age_group': league.age_group,
                'division': league.division,
                'num_matches': getattr(league, 'num_matches', 0),
                'num_lines_per_match': getattr(league, 'num_lines_per_match', 0),
                'allow_split_lines': getattr(league, 'allow_split_lines', False),
                'start_date': getattr(league, 'start_date', None).isoformat() if getattr(league, 'start_date', None) else None,
                'end_date': getattr(league, 'end_date', None).isoformat() if getattr(league, 'end_date', None) else None,
                'teams_count': len(teams) if teams else 0,
                'matches_count': len(matches) if matches else 0,
                'scheduled_matches': len([m for m in (matches or []) if hasattr(m, 'date') and m.date]),
                'unscheduled_matches': len([m for m in (matches or []) if not (hasattr(m, 'date') and m.date)])
            }
            
            return jsonify(league_data)
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500




    # ==================== MODERN API ENDPOINTS ====================


    

    @app.route('/api/leagues/<int:league_id>/generate-matches', methods=['POST'])
    def api_generate_matches(league_id):
        """API endpoint to generate matches for a specific league"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500
        
        try:
            league = db.get_league(league_id)
            if not league:
                return jsonify({'error': 'League not found'}), 404
            
            teams = db.list_teams(league)
            if len(teams) < 2:
                return jsonify({
                    'error': f'Need at least 2 teams to generate matches. League has only {len(teams)} team(s).'
                }), 400
            
            # Check for existing matches
            existing_matches = db.list_matches(league=league)
            if existing_matches:
                return jsonify({
                    'error': f'League already has {len(existing_matches)} matches. Delete existing matches first.'
                }), 400
            
            # Generate matches
            match_generator = MatchGenerator()
            generated_matches = match_generator.generate_matches(teams=teams, league=league)

            if not generated_matches:
                return jsonify({'error': 'No matches were generated'}), 400
            
            # Save matches to database
            saved_count = 0
            for match in generated_matches:
                if db.add_match(match):
                    saved_count += 1
            
            return jsonify({
                'message': f'Successfully generated {saved_count} matches',
                'matches_count': saved_count,
                'league_id': league_id,
                'league_name': league.name
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/leagues', methods=['GET'])
    def api_list_leagues():
        """API endpoint to list all leagues with statistics"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500
        
        try:
            leagues_list = db.list_leagues()
            enhanced_leagues = []
            
            for league in leagues_list:
                # Get team and match counts
                teams = db.list_teams(league=league)
                matches = db.list_matches(league=league)
                
                league_data = {
                    'id': league.id,
                    'name': league.name,
                    'year': league.year,
                    'section': league.section,
                    'region': league.region,
                    'age_group': league.age_group,
                    'division': league.division,
                    'teams_count': len(teams) if teams else 0,
                    'matches_count': len(matches) if matches else 0,
                    'scheduled_matches': len([m for m in (matches or []) if hasattr(m, 'date') and m.date]),
                    'unscheduled_matches': len([m for m in (matches or []) if not (hasattr(m, 'date') and m.date)])
                }
                enhanced_leagues.append(league_data)
            
            return jsonify({
                'leagues': enhanced_leagues,
                'total_count': len(enhanced_leagues)
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500


    
    @app.route('/api/leagues/bulk-generate-matches', methods=['POST'])
    def api_bulk_generate_matches():
        """API endpoint to generate matches for multiple leagues"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500
        
        try:
            # Get all leagues
            leagues_list = db.list_leagues()
            if not leagues_list:
                return jsonify({'error': 'No leagues found'}), 404
            
            # Filter leagues that are ready for match generation
            eligible_leagues = []
            for league in leagues_list:
                teams = db.list_teams(league)
                existing_matches = db.list_matches(league=league)
                
                # League is eligible if it has 2+ teams and no existing matches
                if len(teams) >= 2 and len(existing_matches) == 0:
                    eligible_leagues.append({
                        'league': league,
                        'teams': teams,
                        'teams_count': len(teams)
                    })
            
            if not eligible_leagues:
                return jsonify({
                    'error': 'No leagues are ready for match generation. Leagues need at least 2 teams and no existing matches.'
                }), 400
            
            # Generate matches for each eligible league
            results = []
            success_count = 0
            fail_count = 0
            
            for league_info in eligible_leagues:
                league = league_info['league']
                teams = league_info['teams']
                
                try:
                    # Generate matches using the match_generator class
                    match_generator = MatchGenerator()
                    generated_matches = match_generator.generate_matches(teams=teams, league=league)
                    
                    if not generated_matches:
                        fail_count += 1
                        results.append({
                            'league_id': league.id,
                            'league_name': league.name,
                            'status': 'failed',
                            'error': 'No matches were generated',
                            'matches_count': 0
                        })
                        continue
                    
                    # Save matches to database
                    saved_count = 0
                    for match in generated_matches:
                        if db.add_match(match):
                            saved_count += 1
                    
                    if saved_count > 0:
                        success_count += 1
                        results.append({
                            'league_id': league.id,
                            'league_name': league.name,
                            'status': 'success',
                            'matches_count': saved_count
                        })
                    else:
                        fail_count += 1
                        results.append({
                            'league_id': league.id,
                            'league_name': league.name,
                            'status': 'failed',
                            'error': 'Failed to save matches to database',
                            'matches_count': 0
                        })
                        
                except Exception as e:
                    fail_count += 1
                    results.append({
                        'league_id': league.id,
                        'league_name': league.name,
                        'status': 'failed',
                        'error': str(e),
                        'matches_count': 0
                    })
            
            return jsonify({
                'message': f'Bulk generation complete: {success_count} successful, {fail_count} failed',
                'success_count': success_count,
                'fail_count': fail_count,
                'total_processed': len(eligible_leagues),
                'results': results
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/leagues/<int:league_id>', methods=['DELETE'])
    def api_delete_league(league_id):
        """API endpoint to delete a league"""
        print(f"🗑️  DELETE request received for league_id: {league_id}")
        
        db = get_db()
        if db is None:
            print("❌ No database connection")
            return jsonify({'error': 'No database connection'}), 500
        
        try:
            # Use the same fallback pattern as in view_league
            league = None
            try:
                print(f"🔍 Trying db.get_league({league_id})")
                league = db.get_league(league_id)
                print(f"✅ Found league via get_league: {getattr(league, 'name', 'Unknown')}")
            except AttributeError as ae:
                print(f"⚠️  get_league method not available: {ae}")
                # Fallback to list_leagues and find by ID
                print("🔄 Falling back to list_leagues")
                leagues_list = db.list_leagues()
                for l in leagues_list:
                    if getattr(l, 'id', None) == league_id:
                        league = l
                        print(f"✅ Found league via fallback: {getattr(league, 'name', 'Unknown')}")
                        break
            except Exception as e:
                print(f"❌ Unexpected error in get_league: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': f'Error finding league: {str(e)}'}), 500
            
            if not league:
                print(f"❌ League {league_id} not found")
                return jsonify({'error': 'League not found'}), 404
            
            league_name = getattr(league, 'name', f'League {league_id}')
            print(f"🎯 About to delete league: {league_name}")
            
            # Cascade delete: matches -> teams -> league
            matches_deleted = 0
            teams_deleted = 0
            
            try:
                # Step 1: Delete all matches for this league
                print("🔍 Getting matches for league...")
                matches = db.list_matches(league=league)
                print(f"📋 Found {len(matches)} matches to delete")
                
                for match in matches:
                    try:
                        print(f"🗑️  Deleting match {getattr(match, 'id', 'unknown')}")
                        db.delete_match(match)
                        matches_deleted += 1
                    except Exception as match_error:
                        print(f"❌ Error deleting match {getattr(match, 'id', 'unknown')}: {match_error}")
                        # Continue with other matches
                
                print(f"✅ Deleted {matches_deleted} matches")
                
                # Step 2: Delete all teams for this league
                print("🔍 Getting teams for league...")
                teams = db.list_teams(league)
                print(f"👥 Found {len(teams)} teams to delete")
                
                for team in teams:
                    try:
                        print(f"🗑️  Deleting team {getattr(team, 'id', 'unknown')} - {getattr(team, 'name', 'Unknown')}")
                        db.delete_team(team)
                        teams_deleted += 1
                    except Exception as team_error:
                        print(f"❌ Error deleting team {getattr(team, 'id', 'unknown')}: {team_error}")
                        # Continue with other teams
                
                print(f"✅ Deleted {teams_deleted} teams")
                
                # Step 3: Delete the league itself
                print(f"🗑️  Deleting league: {league_name}")
                db.delete_league(league)  # This returns None, not bool
                print(f"✅ League deletion completed")
                
                # If we get here without exception, deletion was successful
                print(f"✅ Successfully deleted league: {league_name}")
                return jsonify({
                    'message': f'League "{league_name}" and all associated data ({matches_deleted} matches, {teams_deleted} teams) deleted successfully',
                    'league_id': league_id,
                    'matches_deleted': matches_deleted,
                    'teams_deleted': teams_deleted
                })
                
            except Exception as delete_error:
                print(f"❌ Exception in cascade delete: {delete_error}")
                print(f"❌ Exception type: {type(delete_error)}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': f'Database delete failed: {str(delete_error)}'}), 500
                
        except Exception as e:
            print(f"❌ Unexpected error in api_delete_league: {e}")
            print(f"❌ Exception type: {type(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Unexpected server error: {str(e)}'}), 500


