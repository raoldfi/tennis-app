from flask import render_template, request, redirect, url_for, flash, jsonify, make_response
from werkzeug.utils import secure_filename
import yaml
import json
from datetime import datetime
import traceback
from typing import Optional, Type, Dict, Any


from usta_team import Team
from web_database import get_db



def register_routes(app):
    """Register facility-related routes"""
    
    # Fixed teams route
    @app.route('/teams')
    def teams():
        """View teams with optional league filter - FIXED to enhance teams properly"""
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))

        print("TRYING TO LIST TEAMS IN WEB APP")
        
        # Handle league_id parameter safely
        league_id = None
        selected_league = None
        try:
            league_id_str = request.args.get('league_id')
            if league_id_str:
                league_id = int(league_id_str)
                selected_league = db.get_league(league_id)
        except (ValueError, TypeError):
            # If conversion fails, ignore the parameter
            league_id = None
            selected_league = None
        
        # Get search query
        search_query = request.args.get('search', '').strip()
        
        try:
            # Get teams - Pass League object instead of ID
            teams_list = db.list_teams(selected_league)  # Pass League object or None
            leagues_list = db.list_leagues()  # For filter dropdown

            print(f"FOUND {len(teams_list)} teams")
            
            # Apply search filter if provided
            if search_query:
                teams_list = filter_teams_by_search(teams_list, search_query)
            
            # CRITICAL FIX: Enhance teams with facility info for the template
            enhanced_teams = enhance_teams_with_facility_info(teams_list, db)
            
            return render_template('teams.html', 
                                 teams=enhanced_teams,  # Pass enhanced teams
                                 leagues=leagues_list, 
                                 selected_league=selected_league,
                                 search_query=search_query)
        except Exception as e:
            flash(f'Error loading teams: {e}', 'error')
            return redirect(url_for('index'))
    
    @app.route('/teams/add', methods=['GET', 'POST'])
    def add_team():
        # ADD THIS LINE - Get database connection first!
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            try:
                # Get facility object instead of facility name
                facility_id = int(request.form.get('home_facility_id'))
                facility = db.get_facility(facility_id)
                if not facility:
                    flash('Invalid facility selected.', 'error')
                    return redirect(url_for('add_team'))
                
                # Create team with Facility object
                team = Team(
                    id=int(request.form.get('id')),
                    name=request.form.get('name'),
                    league=db.get_league(int(request.form.get('league_id'))),
                    home_facility=facility,  # CHANGED: pass Facility object
                    captain=request.form.get('captain') or None,
                    preferred_days=request.form.getlist('preferred_days')
                )
                
                db.add_team(team)
                flash('Team added successfully!', 'success')
                return redirect(url_for('teams'))
                
            except Exception as e:
                flash(f'Error adding team: {e}', 'error')
        
        # GET request - show form
        leagues = db.list_leagues()
        facilities = db.list_facilities()  # For dropdown
        return render_template('add_team.html', leagues=leagues, facilities=facilities)

    
    
    
    @app.route('/teams/<int:team_id>')
    def view_team(team_id):
        """View a single team with full details"""
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))
        
        try:
            team = db.get_team(team_id)
            if not team:
                flash(f'Team #{team_id} not found', 'error')
                return redirect(url_for('teams'))
            
            # Get recent matches (last 10)
            matches = db.list_matches(team=team)
            
            return render_template('view_team.html', 
                                 team=team,
                                 matches=matches)
            
        except Exception as e:
            flash(f'Error loading team: {str(e)}', 'error')
            return redirect(url_for('teams'))

    

    
    @app.route('/teams/<int:team_id>/edit', methods=['GET', 'POST'])
    def edit_team(team_id):
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))
        
        try:
            team = db.get_team(team_id)
            if not team:
                flash('Team not found.', 'error')
                return redirect(url_for('teams'))
        except Exception as e:
            flash(f'Error loading team: {e}', 'error')
            return redirect(url_for('teams'))
        
        if request.method == 'POST':
            try:
                # Get facility object instead of facility name
                facility_id = int(request.form.get('home_facility_id'))
                facility = db.get_facility(facility_id)
                if not facility:
                    flash('Invalid facility selected.', 'error')
                    return redirect(url_for('edit_team', team_id=team_id))
                
                # Update team with new Facility object
                updated_team = Team(
                    id=team.id,
                    name=request.form.get('name'),
                    league=db.get_league(int(request.form.get('league_id'))),
                    home_facility=facility,  # CHANGED: pass Facility object
                    captain=request.form.get('captain') or None,
                    preferred_days=request.form.getlist('preferred_days')
                )
                
                db.update_team(updated_team)
                flash('Team updated successfully!', 'success')
                return redirect(url_for('teams'))
                
            except Exception as e:
                flash(f'Error updating team: {e}', 'error')
        
        # GET request - show form
        try:
            leagues = db.list_leagues()
            facilities = db.list_facilities()  # For dropdown
            return render_template('edit_team.html', team=team, leagues=leagues, facilities=facilities)
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
    
    

    
    # ==================== API ROUTES ====================
    
    @app.route('/api/teams/<int:league_id>')
    def api_teams_by_league(league_id):
        """API endpoint to get teams by league"""
        return jsonify([])  # Return empty list for now
    
    
    # Add utility route for facility migration
    @app.route('/admin/migrate-teams', methods=['GET', 'POST'])
    def migrate_teams_to_facility_names():
        """Admin route to migrate teams from facility IDs to facility names"""
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            try:
                dry_run = request.form.get('dry_run', 'true').lower() == 'true'
                
                # Perform migration using the team manager's migration method
                if hasattr(db.team_manager, 'migrate_teams_to_facility_names'):
                    result = db.team_manager.migrate_teams_to_facility_names(dry_run=dry_run)
                    
                    if result['status'] == 'no_migration_needed':
                        flash(result['message'], 'info')
                    elif dry_run:
                        flash(f"Dry run completed: {result['successful_migrations']} teams would be migrated, {result['failed_migrations']} would fail", 'info')
                    else:
                        flash(f"Migration completed: {result['successful_migrations']} teams migrated, {result['failed_migrations']} failed", 'success')
                    
                    return render_template('admin_migrate_teams.html', migration_result=result)
                else:
                    flash('Migration functionality not available', 'error')
                    
            except Exception as e:
                flash(f'Error during migration: {e}', 'error')
        
        # GET request - show migration form
        return render_template('admin_migrate_teams.html')
    
    
    # Add utility route to find teams by facility
    @app.route('/api/teams/by-facility/<facility_name>')
    def api_teams_by_facility_name(facility_name):
        """API endpoint to get teams by facility name - optimized"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            exact_match = request.args.get('exact', 'true').lower() == 'true'
            teams_list = db.team_manager.get_teams_by_facility_name(facility_name, exact_match=exact_match)
            
            # Direct object access instead of manual field extraction
            teams_data = [
                {
                    'id': team.id,
                    'name': team.name,
                    'captain': getattr(team, 'captain', ''),
                    'home_facility': team.home_facility.name if hasattr(team, 'home_facility') and team.home_facility else '',
                    'league_name': team.league.name,
                    'league_id': team.league.id
                }
                for team in teams_list
            ]
            
            return jsonify({
                'facility_name': facility_name,
                'exact_match': exact_match,
                'teams_count': len(teams_data),
                'teams': teams_data
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500


# =========== Helpers ==========


def enhance_teams_with_facility_info(teams_list, db):
    """
    Enhance teams with facility information for the template
    This function was missing but is required by the teams.html template
    """
    enhanced_teams = []
    
    for team in teams_list:
        # Get facility information
        facility_name = "No facility assigned"
        facility_exists = False
        facility_id = None
        facility_location = None
        
        if hasattr(team, 'home_facility') and team.home_facility:
            if hasattr(team.home_facility, 'name'):
                # Team has a Facility object
                facility_name = team.home_facility.name
                facility_exists = True
                facility_id = getattr(team.home_facility, 'id', None)
                facility_location = getattr(team.home_facility, 'location', None)
            else:
                # Team has a facility name string
                facility_name = str(team.home_facility)
                # Check if this facility exists in the database
                facilities = db.list_facilities()
                for facility in facilities:
                    if facility.name == facility_name:
                        facility_exists = True
                        facility_id = facility.id
                        facility_location = facility.location
                        break
        
        # Check if team has preferred days
        has_preferred_days = (hasattr(team, 'preferred_days') and 
                            team.preferred_days and 
                            len(team.preferred_days) > 0)
        
        # Create enhanced team object
        enhanced_team = {
            'team': team,  # This is what the template expects!
            'facility_name': facility_name,
            'facility_exists': facility_exists,
            'facility_id': facility_id,
            'facility_location': facility_location,
            'has_preferred_days': has_preferred_days
        }
        
        enhanced_teams.append(enhanced_team)
    
    return enhanced_teams





def filter_teams_by_search(teams_list, search_query):
    """
    Filter teams based on search query
    Searches across: team name, captain, facility name, contact email, league name
    """
    if not search_query:
        return teams_list
    
    # Split search query into individual terms for more flexible matching
    search_terms = [term.lower().strip() for term in search_query.split() if term.strip()]
    filtered_teams = []
    
    for team in teams_list:
        # Create searchable text from team attributes
        searchable_text = []
        
        # Team name
        if hasattr(team, 'name') and team.name:
            searchable_text.append(team.name.lower())
        
        # Captain name
        if hasattr(team, 'captain') and team.captain:
            searchable_text.append(team.captain.lower())
        
        # Contact email
        if hasattr(team, 'contact_email') and team.contact_email:
            searchable_text.append(team.contact_email.lower())
        
        # League name
        if hasattr(team, 'league') and team.league and hasattr(team.league, 'name'):
            searchable_text.append(team.league.name.lower())
        
        # Facility name
        if hasattr(team, 'home_facility') and team.home_facility:
            if hasattr(team.home_facility, 'name'):
                searchable_text.append(team.home_facility.name.lower())
            else:
                searchable_text.append(str(team.home_facility).lower())
        
        # Join all searchable text
        full_text = ' '.join(searchable_text)
        
        # Check if all search terms are found
        matches_all_terms = all(term in full_text for term in search_terms)
        
        if matches_all_terms:
            filtered_teams.append(team)
    
    return filtered_teams

def search_teams_advanced(teams_list, search_query):
    """
    Advanced search with field-specific matching
    Supports queries like: captain:john facility:club league:3.0
    """
    if not search_query:
        return teams_list
    
    # Parse field-specific search terms
    field_searches = {}
    general_terms = []
    
    # Split by spaces and look for field:value patterns
    terms = search_query.split()
    for term in terms:
        if ':' in term and len(term.split(':', 1)) == 2:
            field, value = term.split(':', 1)
            field = field.lower().strip()
            value = value.lower().strip()
            if field and value:
                if field not in field_searches:
                    field_searches[field] = []
                field_searches[field].append(value)
        else:
            general_terms.append(term.lower().strip())
    
    filtered_teams = []
    
    for team in teams_list:
        matches = True
        
        # Check field-specific searches
        for field, values in field_searches.items():
            field_match = False
            
            for value in values:
                if field in ['name', 'team']:
                    if hasattr(team, 'name') and team.name and value in team.name.lower():
                        field_match = True
                        break
                elif field in ['captain', 'cap']:
                    if hasattr(team, 'captain') and team.captain and value in team.captain.lower():
                        field_match = True
                        break
                elif field in ['facility', 'fac']:
                    if hasattr(team, 'home_facility') and team.home_facility:
                        facility_name = ""
                        if hasattr(team.home_facility, 'name'):
                            facility_name = team.home_facility.name.lower()
                        elif isinstance(team.home_facility, str):
                            facility_name = team.home_facility.lower()
                        if value in facility_name:
                            field_match = True
                            break
                elif field in ['league', 'lg']:
                    if hasattr(team, 'league') and team.league:
                        if hasattr(team.league, 'name') and team.league.name and value in team.league.name.lower():
                            field_match = True
                            break
                        if hasattr(team.league, 'division') and team.league.division and value in team.league.division.lower():
                            field_match = True
                            break
                elif field in ['email', 'contact']:
                    if hasattr(team, 'contact_email') and team.contact_email and value in team.contact_email.lower():
                        field_match = True
                        break
                elif field in ['day', 'days']:
                    if hasattr(team, 'preferred_days') and team.preferred_days:
                        for day in team.preferred_days:
                            if value in day.lower():
                                field_match = True
                                break
                        if field_match:
                            break
            
            if not field_match:
                matches = False
                break
        
        # Check general search terms (search across all fields)
        if matches and general_terms:
            # Use the existing general search logic
            searchable_text = []
            
            if hasattr(team, 'name') and team.name:
                searchable_text.append(team.name.lower())
            if hasattr(team, 'captain') and team.captain:
                searchable_text.append(team.captain.lower())
            if hasattr(team, 'contact_email') and team.contact_email:
                searchable_text.append(team.contact_email.lower())
            if hasattr(team, 'home_facility') and team.home_facility:
                if hasattr(team.home_facility, 'name') and team.home_facility.name:
                    searchable_text.append(team.home_facility.name.lower())
                elif isinstance(team.home_facility, str):
                    searchable_text.append(team.home_facility.lower())
            if hasattr(team, 'league') and team.league:
                if hasattr(team.league, 'name') and team.league.name:
                    searchable_text.append(team.league.name.lower())
                if hasattr(team.league, 'division') and team.league.division:
                    searchable_text.append(team.league.division.lower())
            
            combined_text = ' '.join(searchable_text)
            
            for term in general_terms:
                if term not in combined_text:
                    matches = False
                    break
        
        if matches:
            filtered_teams.append(team)
    
    return filtered_teams





