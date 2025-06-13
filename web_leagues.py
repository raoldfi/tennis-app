from flask import render_template, request, redirect, url_for, flash, jsonify, make_response
from typing import Optional, Type, Dict, Any

from werkzeug.utils import secure_filename
import yaml
import json
from datetime import datetime
import traceback

import utils
from usta_league import League
from web_database import get_db
from web_utils import get_usta_constants, create_league_dict_fallback, create_league_from_dict_fallback



def register_routes(app):
    """Register league-related routes"""


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
                        matches = utils.generate_matches(teams)
                        
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
    
    
    @app.route('/leagues/generate-matches', methods=['POST'])
    def generate_matches():
        """Generate matches for a league - FIXED to use League objects"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            league_id = int(request.form.get('league_id'))
            overwrite_existing = request.form.get('overwrite_existing', 'false').lower() == 'true'
            
            # Get the League object
            league = db.get_league(league_id)
            if not league:
                return jsonify({'error': f'League {league_id} not found'}), 404
            
            # Get teams in the league - FIXED to pass League object
            teams = db.list_teams(league)
            
            if len(teams) < 2:
                return jsonify({'error': 'Need at least 2 teams to generate matches'}), 400
            
            # Check for existing matches unless overwriting
            if not overwrite_existing:
                existing_matches = db.list_matches(league)  # Pass League object
                if existing_matches:
                    return jsonify({'error': f'League already has {len(existing_matches)} matches. Use overwrite option to replace them.'}), 400
            
            # Generate matches using the league's generate_matches method
            new_matches = utils.generate_matches(teams)
            
            # Save matches to database
            saved_matches = []
            for match in new_matches:
                try:
                    if overwrite_existing:
                        # Delete existing matches for this league first
                        existing = db.list_matches(league)
                        for existing_match in existing:
                            db.delete_match(existing_match.id)
                    
                    db.add_match(match)
                    saved_matches.append(match)
                except Exception as e:
                    print(f"Error saving match: {e}")
            
            return jsonify({
                'success': True,
                'created_count': len(saved_matches),
                'message': f'Generated {len(saved_matches)} matches for {league.name}'
            })
            
        except Exception as e:
            return jsonify({'error': f'Failed to generate matches: {str(e)}'}), 500
    
    
    
    # ==================== LEAGUE EXPORT/IMPORT ROUTES ====================
    
    @app.route('/leagues/export')
    def export_leagues():
        """Export all leagues to YAML or JSON format with comprehensive error handling"""
        try:
            db = get_db()
            if db is None:
                return jsonify({'error': 'No database connection'}), 500
            
            export_format = request.args.get('format', 'yaml').lower()
            print(f"Export format requested: {export_format}")  # Debug
            
            leagues_list = db.list_leagues()
            print(f"Found {len(leagues_list)} leagues")  # Debug
            
            # Convert leagues to exportable format
            leagues_data = []
            for i, league in enumerate(leagues_list):
                try:
                    # Check if league has to_yaml_dict method
                    if hasattr(league, 'to_yaml_dict'):
                        league_dict = league.to_yaml_dict()
                    else:
                        # Fallback: create dict manually
                        print(f"Warning: League {league.id} missing to_yaml_dict method, using fallback")
                        league_dict = create_league_dict_fallback(league)
                    
                    leagues_data.append(league_dict)
                    print(f"Processed league {i+1}: {league.name}")  # Debug
                    
                except Exception as e:
                    print(f"Error processing league {league.id}: {str(e)}")
                    return jsonify({'error': f'Error processing league {league.id}: {str(e)}'}), 500
            
            # Prepare export data
            export_data = {
                'leagues': leagues_data,
                'exported_at': datetime.now().isoformat(),
                'exported_count': len(leagues_data)
            }
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if export_format == 'json':
                try:
                    # Export as JSON
                    json_str = json.dumps(export_data, indent=2, ensure_ascii=False, default=str)
                    print(f"Generated JSON, length: {len(json_str)}")  # Debug
                    
                    # Create response with proper headers
                    response = make_response(json_str)
                    response.headers['Content-Type'] = 'application/json'
                    response.headers['Content-Disposition'] = f'attachment; filename=leagues_export_{timestamp}.json'
                    return response
                except Exception as e:
                    print(f"JSON export error: {str(e)}")
                    return jsonify({'error': f'JSON serialization error: {str(e)}'}), 500
            else:
                try:
                    # Export as YAML (default)
                    yaml_str = yaml.dump(export_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
                    print(f"Generated YAML, length: {len(yaml_str)}")  # Debug
                    
                    # Create response with proper headers
                    response = make_response(yaml_str)
                    response.headers['Content-Type'] = 'application/x-yaml'
                    response.headers['Content-Disposition'] = f'attachment; filename=leagues_export_{timestamp}.yaml'
                    return response
                except Exception as e:
                    print(f"YAML export error: {str(e)}")
                    return jsonify({'error': f'YAML serialization error: {str(e)}'}), 500
        
        except Exception as e:
            print(f"General export error: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': f'Export failed: {str(e)}', 'traceback': traceback.format_exc()}), 500
    
    
    @app.route('/leagues/<int:league_id>/export')
    def export_single_league(league_id):
        """Export a single league to YAML format with error handling"""
        try:
            db = get_db()
            if db is None:
                return jsonify({'error': 'No database connection'}), 500
            
            league = db.get_league(league_id)
            if not league:
                return jsonify({'error': f'League {league_id} not found'}), 404
            
            print(f"Exporting league: {league.name}")  # Debug
            
            # Convert league to exportable format
            try:
                if hasattr(league, 'to_yaml_dict'):
                    league_dict = league.to_yaml_dict()
                else:
                    print(f"Warning: League {league_id} missing to_yaml_dict method, using fallback")
                    league_dict = create_league_dict_fallback(league)
            except Exception as e:
                print(f"Error converting league to dict: {str(e)}")
                return jsonify({'error': f'Error converting league: {str(e)}'}), 500
            
            # Prepare export data
            export_data = {
                'leagues': [league_dict],
                'exported_at': datetime.now().isoformat(),
                'league_name': league.name
            }
            
            try:
                # Generate YAML
                yaml_str = yaml.dump(export_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
                print(f"Generated YAML, length: {len(yaml_str)}")  # Debug
                
                # Create response with proper headers
                safe_filename = secure_filename(f"{league.name}_{league.year}")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                
                response = make_response(yaml_str)
                response.headers['Content-Type'] = 'application/x-yaml'
                response.headers['Content-Disposition'] = f'attachment; filename=league_{safe_filename}_{timestamp}.yaml'
                return response
                
            except Exception as e:
                print(f"YAML export error: {str(e)}")
                return jsonify({'error': f'YAML serialization error: {str(e)}'}), 500
        
        except Exception as e:
            print(f"General export error: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': f'Export failed: {str(e)}', 'traceback': traceback.format_exc()}), 500
    
    
    @app.route('/leagues/import', methods=['POST'])
    def import_leagues():
        """Import leagues from YAML file"""
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
            
            if 'leagues' not in data:
                return jsonify({
                    'success': False, 
                    'error': 'Invalid file format: Missing "leagues" key'
                }), 400
            
            if not isinstance(data['leagues'], list):
                return jsonify({
                    'success': False, 
                    'error': 'Invalid file format: "leagues" must be a list'
                }), 400
            
            # Import leagues
            imported_count = 0
            updated_count = 0
            errors = []
            
            for i, league_data in enumerate(data['leagues']):
                try:
                    # Check if it's already a League object or needs conversion
                    if hasattr(league_data, '__dict__'):
                        league = league_data
                    else:
                        # Create League from dict data
                        if hasattr(League, 'from_yaml_dict'):
                            league = League.from_yaml_dict(league_data)
                        else:
                            # Fallback: create League object manually
                            league = create_league_from_dict_fallback(league_data)
                    
                    # Check if league already exists
                    existing_league = None
                    try:
                        existing_league = db.get_league(league.id) if hasattr(league, 'id') and league.id else None
                    except:
                        pass
                    
                    if existing_league:
                        # Update existing league
                        db.update_league(league)
                        updated_count += 1
                    else:
                        # Insert new league
                        db.add_league(league)
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
    
    # Test routes for export/import functionality
    @app.route('/leagues/export/test')
    def test_leagues_export():
        """Test route to verify league export functionality"""
        try:
            db = get_db()
            if db is None:
                return jsonify({'error': 'No database connection', 'test': 'failed'})
            
            leagues_list = db.list_leagues()
            
            test_result = {
                'test': 'passed',
                'leagues_count': len(leagues_list),
                'yaml_available': 'yaml' in sys.modules,
                'json_available': 'json' in sys.modules,
                'leagues_sample': []
            }
            
            # Test first league if available
            if leagues_list:
                league = leagues_list[0]
                test_result['leagues_sample'] = [{
                    'id': league.id,
                    'name': league.name,
                    'has_to_yaml_dict': hasattr(league, 'to_yaml_dict'),
                    'year': league.year,
                    'section': league.section
                }]
            
            return jsonify(test_result)
            
        except Exception as e:
            return jsonify({
                'test': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc()
            })
    
    
    @app.route('/api/generate-matches/<int:league_id>')
    def api_generate_matches(league_id):
        """API endpoint to generate matches - FIXED to ensure proper object loading"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            # Get league with full object loading
            league = db.get_league(league_id)
            if not league:
                return jsonify({'error': f'League {league_id} not found'}), 404
            
            # Get teams for this league
            teams = db.list_teams(league)
            if len(teams) < 2:
                return jsonify({'error': 'Need at least 2 teams to generate matches'}), 400
            
            # Generate matches using the league's algorithm
            matches = utils.generate_matches(teams)
            
            # Process the generated matches
            created_matches = []
            updated_matches = []
            failed_matches = []
    
            print(f"GENERATED {len(matches)} MATCHES")
            
            for match in matches:
                try:
                    # Check if match already exists
                    existing_match = db.get_match(match.id)
                    
                    if existing_match:
                        # Update existing match
                        db.update_match(match)
                        updated_matches.append({
                            'match_id': match.id,
                            'home_team': match.home_team.name,
                            'visitor_team': match.visitor_team.name,
                            'facility_id': match.facility_id
                        })
                    else:
                        # Create new match
                        db.add_match(match)
                        created_matches.append({
                            'match_id': match.id,
                            'home_team': match.home_team.name,
                            'visitor_team': match.visitor_team.name,
                            'facility_id': match.facility_id
                        })
                        
                except Exception as e:
                    failed_matches.append({
                        'match_id': getattr(match, 'id', 'unknown'),
                        'error': str(e)
                    })
                    
            print(f"GEN MATCHES SUCCEEDED")
    
            return jsonify({
                'success': True,
                'created_count': len(created_matches),
                'updated_count': len(updated_matches),
                'failed_count': len(failed_matches),
                'created_matches': created_matches,
                'updated_matches': updated_matches,
                'failed_matches': failed_matches if failed_matches else None
            })
            
        except Exception as e:
            return jsonify({'error': f'Failed to generate matches: {e}'}), 500

