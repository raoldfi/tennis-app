"""
Tennis Web App - League Management Routes
Modern API endpoints compatible with TennisUI frontend
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, make_response
from werkzeug.utils import secure_filename
import yaml
import json
from datetime import datetime
import traceback
import tempfile
import os

import utils
from usta_league import League
from web_database import get_db


def register_routes(app):
    """Register league-related routes with modern API endpoints"""

    # ==================== MAIN LEAGUES PAGE ====================
    
    @app.route('/leagues')
    def leagues():
        """Main leagues page - display all leagues"""
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

    # ==================== MODERN API ENDPOINTS ====================

    @app.route('/api/import-leagues', methods=['POST'])
    def api_import_leagues():
        """Modern API endpoint for importing leagues from YAML"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500

        try:
            # Validate file upload
            if 'yaml_file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400

            file = request.files['yaml_file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            if not file.filename.lower().endswith(('.yaml', '.yml')):
                return jsonify({'error': 'File must be a YAML file (.yaml or .yml)'}), 400

            # Read and parse YAML content
            try:
                yaml_content = file.read().decode('utf-8')
                data = yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                return jsonify({'error': f'Invalid YAML format: {str(e)}'}), 400
            except UnicodeDecodeError:
                return jsonify({'error': 'File must be UTF-8 encoded'}), 400

            # Validate data structure
            if not isinstance(data, dict):
                return jsonify({'error': 'Invalid file format: Root element must be a dictionary'}), 400

            if 'leagues' not in data:
                return jsonify({'error': 'Invalid file format: Missing "leagues" key'}), 400

            leagues_data = data['leagues']
            if not isinstance(leagues_data, list):
                return jsonify({'error': 'Invalid file format: "leagues" must be a list'}), 400

            # Process leagues
            imported_count = 0
            updated_count = 0
            errors = []

            for i, league_data in enumerate(leagues_data):
                try:
                    # Validate required fields
                    required_fields = ['id', 'name', 'year']
                    for field in required_fields:
                        if field not in league_data:
                            errors.append(f'League {i+1}: Missing required field "{field}"')
                            continue

                    # Create League object
                    league = League(
                        id=league_data['id'],
                        name=league_data['name'],
                        year=league_data['year'],
                        section=league_data.get('section', ''),
                        region=league_data.get('region', ''),
                        age_group=league_data.get('age_group', ''),
                        division=league_data.get('division', ''),
                        num_lines_per_match=league_data.get('num_lines_per_match', 3),
                        num_matches=league_data.get('num_matches', 10),
                        allow_split_lines=league_data.get('allow_split_lines', False),
                        start_date=league_data.get('start_date'),
                        end_date=league_data.get('end_date'),
                        preferred_days=league_data.get('preferred_days', [])
                    )

                    # Check if league exists
                    existing_league = db.get_league(league.id)
                    if existing_league:
                        db.update_league(league)
                        updated_count += 1
                    else:
                        db.add_league(league)
                        imported_count += 1

                except Exception as e:
                    errors.append(f'League {i+1} ({league_data.get("name", "Unknown")}): {str(e)}')

            # Prepare response
            result = {
                'imported_count': imported_count,
                'updated_count': updated_count,
                'total_processed': imported_count + updated_count,
                'error_count': len(errors)
            }

            if errors:
                result['errors'] = errors[:10]  # Limit to first 10 errors
                if len(errors) > 10:
                    result['additional_errors'] = len(errors) - 10

            if imported_count > 0 or updated_count > 0:
                result['message'] = f'Successfully processed {imported_count + updated_count} leagues'
                return jsonify(result)
            else:
                result['error'] = 'No leagues were imported successfully'
                return jsonify(result), 400

        except Exception as e:
            return jsonify({
                'error': f'Import failed: {str(e)}',
                'traceback': traceback.format_exc() if app.debug else None
            }), 500

    @app.route('/api/export-leagues')
    def api_export_leagues():
        """Modern API endpoint for exporting leagues"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500

        try:
            export_format = request.args.get('format', 'yaml').lower()
            league_ids = request.args.get('ids')
            
            # Get leagues to export
            if league_ids:
                # Export specific leagues
                league_id_list = [int(id) for id in league_ids.split(',')]
                leagues_list = []
                for league_id in league_id_list:
                    league = db.get_league(league_id)
                    if league:
                        leagues_list.append(league)
            else:
                # Export all leagues
                leagues_list = db.list_leagues()

            if not leagues_list:
                return jsonify({'error': 'No leagues found to export'}), 404

            # Convert to export format
            leagues_data = []
            for league in leagues_list:
                if hasattr(league, 'to_yaml_dict'):
                    leagues_data.append(league.to_yaml_dict())
                else:
                    # Fallback for older league objects
                    leagues_data.append({
                        'id': league.id,
                        'name': league.name,
                        'year': league.year,
                        'section': getattr(league, 'section', ''),
                        'region': getattr(league, 'region', ''),
                        'age_group': getattr(league, 'age_group', ''),
                        'division': getattr(league, 'division', ''),
                        'num_lines_per_match': getattr(league, 'num_lines_per_match', 3),
                        'num_matches': getattr(league, 'num_matches', 10),
                        'allow_split_lines': getattr(league, 'allow_split_lines', False),
                        'start_date': getattr(league, 'start_date', None),
                        'end_date': getattr(league, 'end_date', None),
                        'preferred_days': getattr(league, 'preferred_days', [])
                    })

            # Create response
            if export_format == 'json':
                response_data = {'leagues': leagues_data}
                response = make_response(json.dumps(response_data, indent=2))
                response.headers['Content-Type'] = 'application/json'
                response.headers['Content-Disposition'] = 'attachment; filename=leagues.json'
            else:  # YAML format
                response_data = {'leagues': leagues_data}
                yaml_content = yaml.dump(response_data, default_flow_style=False, allow_unicode=True)
                response = make_response(yaml_content)
                response.headers['Content-Type'] = 'application/x-yaml'
                response.headers['Content-Disposition'] = 'attachment; filename=leagues.yaml'

            return response

        except Exception as e:
            return jsonify({
                'error': f'Export failed: {str(e)}',
                'traceback': traceback.format_exc() if app.debug else None
            }), 500

    @app.route('/api/export-league/<int:league_id>')
    def api_export_single_league(league_id):
        """Export a single league"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500

        try:
            league = db.get_league(league_id)
            if not league:
                return jsonify({'error': f'League {league_id} not found'}), 404

            export_format = request.args.get('format', 'yaml').lower()
            
            # Convert to export format
            if hasattr(league, 'to_yaml_dict'):
                league_data = league.to_yaml_dict()
            else:
                league_data = {
                    'id': league.id,
                    'name': league.name,
                    'year': league.year,
                    'section': getattr(league, 'section', ''),
                    'region': getattr(league, 'region', ''),
                    'age_group': getattr(league, 'age_group', ''),
                    'division': getattr(league, 'division', ''),
                    'num_lines_per_match': getattr(league, 'num_lines_per_match', 3),
                    'num_matches': getattr(league, 'num_matches', 10),
                    'allow_split_lines': getattr(league, 'allow_split_lines', False),
                    'start_date': getattr(league, 'start_date', None),
                    'end_date': getattr(league, 'end_date', None),
                    'preferred_days': getattr(league, 'preferred_days', [])
                }

            # Create filename-safe league name
            safe_name = "".join(c for c in league.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')

            if export_format == 'json':
                response_data = {'leagues': [league_data]}
                response = make_response(json.dumps(response_data, indent=2))
                response.headers['Content-Type'] = 'application/json'
                response.headers['Content-Disposition'] = f'attachment; filename={safe_name}_league.json'
            else:  # YAML format
                response_data = {'leagues': [league_data]}
                yaml_content = yaml.dump(response_data, default_flow_style=False, allow_unicode=True)
                response = make_response(yaml_content)
                response.headers['Content-Type'] = 'application/x-yaml'
                response.headers['Content-Disposition'] = f'attachment; filename={safe_name}_league.yaml'

            return response

        except Exception as e:
            return jsonify({'error': f'Export failed: {str(e)}'}), 500

    @app.route('/api/generate-matches/<int:league_id>')
    def api_generate_matches(league_id):
        """Modern API endpoint for generating matches"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500

        try:
            # Get league
            league = db.get_league(league_id)
            if not league:
                return jsonify({'error': f'League {league_id} not found'}), 404

            # Get teams for this league
            teams = db.list_teams(league)
            if len(teams) < 2:
                return jsonify({
                    'error': f'Need at least 2 teams to generate matches. League "{league.name}" has only {len(teams)} team(s).'
                }), 400

            # Check for existing matches
            existing_matches = db.list_matches(league)
            overwrite_existing = request.args.get('overwrite', 'false').lower() == 'true'
            
            if existing_matches and not overwrite_existing:
                return jsonify({
                    'error': f'League "{league.name}" already has {len(existing_matches)} matches. Use overwrite option to replace them.'
                }), 400

            # Generate matches
            new_matches = utils.generate_matches(teams)

            # Save matches to database
            saved_count = 0
            
            if overwrite_existing and existing_matches:
                # Delete existing matches first
                for existing_match in existing_matches:
                    db.delete_match(existing_match.id)

            # Add new matches
            for match in new_matches:
                try:
                    db.add_match(match)
                    saved_count += 1
                except Exception as e:
                    app.logger.error(f"Error saving match: {e}")

            return jsonify({
                'created_count': saved_count,
                'message': f'Generated {saved_count} matches for league "{league.name}"'
            })

        except Exception as e:
            return jsonify({'error': f'Failed to generate matches: {str(e)}'}), 500

    # ==================== LEAGUE CRUD OPERATIONS ====================

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
                    'id': int(request.form.get('id')),
                    'name': request.form.get('name', '').strip(),
                    'year': int(request.form.get('year')),
                    'section': request.form.get('section', '').strip(),
                    'region': request.form.get('region', '').strip(),
                    'age_group': request.form.get('age_group', '').strip(),
                    'division': request.form.get('division', '').strip(),
                    'num_lines_per_match': int(request.form.get('num_lines_per_match', 3)),
                    'num_matches': int(request.form.get('num_matches', 10)),
                    'allow_split_lines': bool(request.form.get('allow_split_lines')),
                    'start_date': request.form.get('start_date') or None,
                    'end_date': request.form.get('end_date') or None,
                    'preferred_days': request.form.getlist('preferred_days')
                }

                # Validate required fields
                if not league_data['name']:
                    flash('League name is required', 'error')
                    return render_template('add_league.html')

                # Create League object
                league = League(**league_data)

                # Check if league ID already exists
                if db.get_league(league.id):
                    flash(f'League with ID {league.id} already exists', 'error')
                    return render_template('add_league.html')

                # Add to database
                db.add_league(league)
                flash(f'League "{league.name}" added successfully!', 'success')
                return redirect(url_for('leagues'))

            except ValueError as e:
                flash(f'Invalid input: {e}', 'error')
            except Exception as e:
                flash(f'Error adding league: {e}', 'error')

        return render_template('add_league.html')

    @app.route('/leagues/<int:league_id>/edit', methods=['GET', 'POST'])
    def edit_league(league_id):
        """Edit an existing league"""
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))

        league = db.get_league(league_id)
        if not league:
            flash(f'League {league_id} not found', 'error')
            return redirect(url_for('leagues'))

        if request.method == 'POST':
            try:
                # Update league properties
                league.name = request.form.get('name', '').strip()
                league.year = int(request.form.get('year'))
                league.section = request.form.get('section', '').strip()
                league.region = request.form.get('region', '').strip()
                league.age_group = request.form.get('age_group', '').strip()
                league.division = request.form.get('division', '').strip()
                league.num_lines_per_match = int(request.form.get('num_lines_per_match', 3))
                league.num_matches = int(request.form.get('num_matches', 10))
                league.allow_split_lines = bool(request.form.get('allow_split_lines'))
                league.start_date = request.form.get('start_date') or None
                league.end_date = request.form.get('end_date') or None
                league.preferred_days = request.form.getlist('preferred_days')

                # Validate
                if not league.name:
                    flash('League name is required', 'error')
                    return render_template('edit_league.html', league=league)

                # Update in database
                db.update_league(league)
                flash(f'League "{league.name}" updated successfully!', 'success')
                return redirect(url_for('leagues'))

            except ValueError as e:
                flash(f'Invalid input: {e}', 'error')
            except Exception as e:
                flash(f'Error updating league: {e}', 'error')

        return render_template('edit_league.html', league=league)

    @app.route('/leagues/<int:league_id>/delete', methods=['POST'])
    def delete_league(league_id):
        """Delete a league"""
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))

        try:
            league = db.get_league(league_id)
            if not league:
                flash(f'League {league_id} not found', 'error')
                return redirect(url_for('leagues'))

            # Check for dependent data
            teams = db.list_teams(league)
            matches = db.list_matches(league)
            
            if teams or matches:
                flash(f'Cannot delete league "{league.name}": it has {len(teams)} teams and {len(matches)} matches. Delete those first.', 'error')
                return redirect(url_for('leagues'))

            # Delete league
            db.delete_league(league_id)
            flash(f'League "{league.name}" deleted successfully!', 'success')

        except Exception as e:
            flash(f'Error deleting league: {e}', 'error')

        return redirect(url_for('leagues'))

    # ==================== UTILITY ENDPOINTS ====================

    @app.route('/api/leagues')
    def api_list_leagues():
        """API endpoint to list all leagues"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500

        try:
            leagues_list = db.list_leagues()
            leagues_data = []
            
            for league in leagues_list:
                league_dict = {
                    'id': league.id,
                    'name': league.name,
                    'year': league.year,
                    'section': getattr(league, 'section', ''),
                    'region': getattr(league, 'region', ''),
                    'age_group': getattr(league, 'age_group', ''),
                    'division': getattr(league, 'division', ''),
                    'num_lines_per_match': getattr(league, 'num_lines_per_match', 3),
                    'num_matches': getattr(league, 'num_matches', 10),
                    'allow_split_lines': getattr(league, 'allow_split_lines', False),
                    'start_date': getattr(league, 'start_date', None),
                    'end_date': getattr(league, 'end_date', None),
                    'preferred_days': getattr(league, 'preferred_days', [])
                }
                leagues_data.append(league_dict)

            return jsonify(leagues_data)

        except Exception as e:
            return jsonify({'error': f'Failed to list leagues: {str(e)}'}), 500