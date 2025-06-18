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
    
    
    # Helper function to export as JSON
    def export_as_json(data, filename):
        """Helper to export data as JSON"""
        json_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        response = make_response(json_str)
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response
    
    # Helper function to export as YAML
    def export_as_yaml(data, filename):
        """Helper to export data as YAML"""
        yaml_str = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        response = make_response(yaml_str)
        response.headers['Content-Type'] = 'application/x-yaml'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response
    
    @app.route('/teams/export')
    def export_teams():
        """Export teams - FIXED to use League objects"""
        try:
            db = get_db()
            if db is None:
                return jsonify({'error': 'No database connection'}), 500
            
            export_format = request.args.get('format', 'yaml').lower()
            league_id = request.args.get('league_id', type=int)
            
            # Get selected league if filtering
            selected_league = None
            if league_id:
                selected_league = db.get_league(league_id)
            
            # FIXED: Pass League object instead of league_id
            teams_list = db.list_teams(selected_league)
            
            # Convert teams to exportable format
            teams_data = []
            for team in teams_list:
                try:
                    if hasattr(team, 'to_yaml_dict'):
                        team_dict = team.to_yaml_dict()
                    else:
                        # Fallback: create dict manually
                        team_dict = create_team_dict_fallback(team)
                    teams_data.append(team_dict)
                except Exception as e:
                    return jsonify({'error': f'Error processing team {team.id}: {str(e)}'}), 500
            
            # Prepare export data
            export_data = {
                'teams': teams_data,
                'exported_at': datetime.now().isoformat(),
                'total_teams': len(teams_data)
            }
            
            # Generate filename
            if selected_league:
                filename = f"teams_{selected_league.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"
            else:
                filename = f"teams_all_{datetime.now().strftime('%Y%m%d')}"
            
            # Export based on format
            if export_format == 'json':
                return export_as_json(export_data, f"{filename}.json")
            else:  # Default to YAML
                return export_as_yaml(export_data, f"{filename}.yaml")
                
        except Exception as e:
            return jsonify({'error': f'Export failed: {str(e)}'}), 500
    
    
    @app.route('/teams/<int:team_id>/export')
    def export_single_team(team_id):
        """Export a single team to YAML format with error handling"""
        try:
            db = get_db()
            if db is None:
                return jsonify({'error': 'No database connection'}), 500
            
            team = db.get_team(team_id)
            if not team:
                return jsonify({'error': f'Team {team_id} not found'}), 404
            
            print(f"Exporting team: {team.name}")  # Debug
            
            # Convert team to exportable format
            try:
                if hasattr(team, 'to_yaml_dict'):
                    team_dict = team.to_yaml_dict()
                else:
                    print(f"Warning: Team {team_id} missing to_yaml_dict method, using fallback")
                    team_dict = create_team_dict_fallback(team)
            except Exception as e:
                print(f"Error converting team to dict: {str(e)}")
                return jsonify({'error': f'Error converting team: {str(e)}'}), 500
            
            # Prepare export data
            export_data = {
                'teams': [team_dict],
                'exported_at': datetime.now().isoformat(),
                'team_name': team.name
            }
            
            try:
                # Generate YAML
                yaml_str = yaml.dump(export_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
                print(f"Generated YAML, length: {len(yaml_str)}")  # Debug
                
                # Create response with proper headers
                safe_filename = secure_filename(team.name)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                
                response = make_response(yaml_str)
                response.headers['Content-Type'] = 'application/x-yaml'
                response.headers['Content-Disposition'] = f'attachment; filename=team_{safe_filename}_{timestamp}.yaml'
                return response
                
            except Exception as e:
                print(f"YAML export error: {str(e)}")
                return jsonify({'error': f'YAML serialization error: {str(e)}'}), 500
        
        except Exception as e:
            print(f"General export error: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': f'Export failed: {str(e)}', 'traceback': traceback.format_exc()}), 500
    
    
    @app.route('/teams/import', methods=['POST'])
    def import_teams():
        """Import teams from YAML file"""
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'error': 'No database connection'}), 500
        
        try:
            # Check if file was uploaded
            if 'yaml_file' not in request.files:
                return jsonify({'success': False, 'error': 'No file uploaded'}), 400
            
            file = request.files['yaml_file']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'}), 400
            
            # Check file extension
            if not file.filename.lower().endswith(('.yaml', '.yml')):
                return jsonify({'success': False, 'error': 'File must be a YAML file (.yaml or .yml)'}), 400
            
            # Read and parse YAML content
            try:
                yaml_content = file.read().decode('utf-8')
                data = yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                return jsonify({
                    'success': False, 
                    'error': f'Invalid YAML format: {str(e)}',
                    'details': str(e)
                }), 400
            except UnicodeDecodeError as e:
                return jsonify({
                    'success': False, 
                    'error': f'File encoding error: {str(e)}',
                    'details': 'File must be UTF-8 encoded'
                }), 400
            
            # Validate data structure
            if not isinstance(data, dict):
                return jsonify({
                    'success': False, 
                    'error': 'Invalid file format: Root element must be a dictionary'
                }), 400
            
            if 'teams' not in data:
                return jsonify({
                    'success': False, 
                    'error': 'Invalid file format: Missing "teams" key'
                }), 400
            
            if not isinstance(data['teams'], list):
                return jsonify({
                    'success': False, 
                    'error': 'Invalid file format: "teams" must be a list'
                }), 400
            
            # Import teams
            imported_count = 0
            updated_count = 0
            errors = []
            
            for i, team_data in enumerate(data['teams']):
                try:
                    # Check if it's already a Team object or needs conversion
                    if hasattr(team_data, '__dict__'):
                        team = team_data
                    else:
                        # Create Team from dict data
                        if hasattr(Team, 'from_yaml_dict'):
                            team = Team.from_yaml_dict(team_data)
                        else:
                            # Fallback: create Team object manually
                            team = create_team_from_dict_fallback(team_data, db)
                    
                    # Check if team already exists
                    existing_team = None
                    try:
                        existing_team = db.get_team(team.id) if hasattr(team, 'id') and team.id else None
                    except:
                        pass
                    
                    if existing_team:
                        # Update existing team
                        db.update_team(team)
                        updated_count += 1
                    else:
                        # Insert new team
                        db.add_team(team)
                        imported_count += 1
                        
                except Exception as e:
                    errors.append(f"Row {i+1}: {str(e)}")
                    continue
            
            result = {
                'success': True,
                'imported_count': imported_count,
                'updated_count': updated_count,
                'total_processed': imported_count + updated_count,
                'error_count': len(errors)
            }
            
            if errors:
                result['errors'] = errors[:10]  # Limit error messages
                if len(errors) > 10:
                    result['additional_errors'] = len(errors) - 10
            
            return jsonify(result)
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Import failed: {str(e)}',
                'traceback': traceback.format_exc()
            }), 500
    
    
    
    @app.route('/teams/export/test')
    def test_teams_export():
        """Test route to verify team export functionality"""
        try:
            db = get_db()
            if db is None:
                return jsonify({'error': 'No database connection', 'test': 'failed'})
            
            teams_list = db.list_teams()
            
            test_result = {
                'test': 'passed',
                'teams_count': len(teams_list),
                'yaml_available': 'yaml' in sys.modules,
                'json_available': 'json' in sys.modules,
                'teams_sample': []
            }
            
            # Test first team if available
            if teams_list:
                team = teams_list[0]
                test_result['teams_sample'] = [{
                    'id': team.id,
                    'name': team.name,
                    'has_to_yaml_dict': hasattr(team, 'to_yaml_dict'),
                    'captain': team.captain,
                    'league_name': team.league.name if hasattr(team, 'league') and team.league else 'Unknown'
                }]
            
            return jsonify(test_result)
            
        except Exception as e:
            return jsonify({
                'test': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc()
            })
    
    
    
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






def create_team_dict_fallback(team):
    """Fallback method to convert Team object to dictionary"""
    try:
        team_dict = {
            'id': team.id,
            'name': team.name,
            'league_id': team.league.id if hasattr(team, 'league') and team.league else None,
            'captain': team.captain
        }
        
        # Handle home facility - export the facility ID if available
        if hasattr(team, 'home_facility') and team.home_facility:
            if hasattr(team.home_facility, 'id') and team.home_facility.id:
                team_dict['home_facility_id'] = team.home_facility.id
            # Also include the facility name for reference
            if hasattr(team.home_facility, 'name'):
                team_dict['home_facility_name'] = team.home_facility.name
        elif hasattr(team, 'home_facility_id') and team.home_facility_id:
            # Fallback if only ID is available
            team_dict['home_facility_id'] = team.home_facility_id
        
        # Add optional fields if they exist
        if hasattr(team, 'preferred_days') and team.preferred_days:
            team_dict['preferred_days'] = team.preferred_days
        if hasattr(team, 'contact_email') and team.contact_email:
            team_dict['contact_email'] = team.contact_email
        if hasattr(team, 'notes') and team.notes:
            team_dict['notes'] = team.notes
        
        return team_dict
        
    except Exception as e:
        print(f"Fallback conversion error: {str(e)}")
        raise Exception(f"Could not convert team to dictionary: {str(e)}")


def create_team_from_dict_fallback(team_data, db):
    """Fallback method to create Team object from dictionary"""
    try:
        # Get league object if league_id is provided
        league = None
        if 'league_id' in team_data and team_data['league_id']:
            try:
                league = db.get_league(team_data['league_id'])
                if not league:
                    raise Exception(f"League with ID {team_data['league_id']} not found")
            except Exception as e:
                raise Exception(f"Invalid league_id {team_data['league_id']}: {str(e)}")
        
        # Handle home facility - get the actual Facility object
        home_facility = None
        
        if 'home_facility_id' in team_data and team_data['home_facility_id']:
            # Primary method: use facility ID to get Facility object
            try:
                home_facility = db.get_facility(team_data['home_facility_id'])
                if not home_facility:
                    raise Exception(f"Facility with ID {team_data['home_facility_id']} not found")
            except Exception as e:
                raise Exception(f"Invalid home_facility_id {team_data['home_facility_id']}: {str(e)}")
                
        elif 'home_facility' in team_data and team_data['home_facility']:
            # Legacy support: try to find facility by name
            facility_name = team_data['home_facility']
            try:
                facilities = db.list_facilities()
                for facility in facilities:
                    if facility.name == facility_name:
                        home_facility = facility
                        break
                
                if not home_facility:
                    # Create a minimal facility object for custom names
                    # This depends on your Facility class constructor
                    print(f"Warning: Facility '{facility_name}' not found in database, creating custom facility reference")
                    # You may need to adjust this based on your Facility class constructor
                    from usta import Facility
                    home_facility = Facility(
                        id=None,
                        name=facility_name,
                        location='Unknown',
                        schedule=None  # or create a default schedule
                    )
            except Exception as e:
                print(f"Error looking up facility by name: {str(e)}")
                # Create minimal facility object as fallback
                from usta import Facility
                home_facility = Facility(
                    id=None,
                    name=facility_name,
                    location='Unknown',
                    schedule=None
                )
        
        # Create Team with required fields
        team = Team(
            id=team_data.get('id'),
            name=team_data['name'],
            league=league,
            captain=team_data.get('captain', ''),
            home_facility=home_facility  # Pass the Facility object
        )
        
        # Add optional fields if they exist
        if 'preferred_days' in team_data:
            team.preferred_days = team_data['preferred_days']
        if 'contact_email' in team_data:
            team.contact_email = team_data['contact_email']
        if 'notes' in team_data:
            team.notes = team_data['notes']
        
        return team
        
    except Exception as e:
        print(f"Fallback creation error: {str(e)}")
        raise Exception(f"Could not create team from dictionary: {str(e)}")



