"""
Multi-Component Import/Export Module for Tennis Web Application

This module provides streamlined import/export functionality that leverages
the native import/export methods from SQLiteTennisDB (YAMLImportExportMixin).

Key Features:
- Multi-component files (any combination of leagues, facilities, teams, matches)
- Smart content detection and processing
- Direct integration with database import/export methods
- Support for YAML and JSON formats
- Comprehensive error handling and progress tracking

Usage:
    # In web_app.py
    import web_import_export
    web_import_export.register_routes(app)

Author: Tennis App Development Team
"""

from flask import request, jsonify, make_response
from werkzeug.utils import secure_filename
import yaml
import json
from datetime import datetime
import traceback
import tempfile
import os
from typing import Dict, List, Any, Optional

from web_database import get_db


class ComponentInfo:
    """Information about supported components"""
    
    COMPONENTS = {
        'leagues': {
            'display_name': 'Leagues',
            'icon': 'fas fa-trophy',
            'color': 'warning'
        },
        'facilities': {
            'display_name': 'Facilities',
            'icon': 'fas fa-building',
            'color': 'info'
        },
        'teams': {
            'display_name': 'Teams',
            'icon': 'fas fa-users',
            'color': 'success'
        },
        'matches': {
            'display_name': 'Matches',
            'icon': 'fas fa-calendar',
            'color': 'primary'
        }
    }

    @classmethod
    def get_all_components(cls):
        """Get list of all supported component names"""
        return list(cls.COMPONENTS.keys())


def register_routes(app):
    """Register multi-component import/export routes"""
    
    @app.route('/api/import-export/analyze', methods=['POST'])
    def analyze_file():
        """Analyze uploaded file to determine what components it contains"""
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Validate file type
            if not file.filename.lower().endswith(('.yaml', '.yml')):
                return jsonify({'error': 'File must be a YAML file (.yaml or .yml)'}), 400
            
            # Parse YAML content
            try:
                content = file.read().decode('utf-8')
                file.seek(0)  # Reset file pointer for potential future reads
                data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                return jsonify({'error': f'Invalid YAML format: {str(e)}'}), 400
            except UnicodeDecodeError:
                return jsonify({'error': 'File encoding not supported. Please use UTF-8.'}), 400
            
            # Analyze content
            analysis = _analyze_content(data)
            
            return jsonify({
                'success': True,
                'analysis': analysis,
                'filename': file.filename,
                'file_size': len(content)
            })
            
        except Exception as e:
            return jsonify({
                'error': f'Analysis failed: {str(e)}',
                'traceback': traceback.format_exc() if app.debug else None
            }), 500
    
    
    @app.route('/api/import-export/import', methods=['POST'])
    def import_data():
        """Universal import endpoint that handles any combination of components"""
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Validate file type
            if not file.filename.lower().endswith(('.yaml', '.yml')):
                return jsonify({'error': 'File must be a YAML file (.yaml or .yml)'}), 400
            
            db = get_db()
            if db is None:
                return jsonify({'error': 'No database connection'}), 500
            
            # Get import options
            skip_existing = request.form.get('skip_existing', 'true').lower() == 'true'
            validate_only = request.form.get('validate_only', 'false').lower() == 'true'
            
            # Save file temporarily
            temp_filename = secure_filename(file.filename)
            temp_path = os.path.join(tempfile.gettempdir(), f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{temp_filename}")
            
            try:
                file.save(temp_path)
                
                # Use the database's built-in import method
                stats = db.import_from_yaml(temp_path, 
                                           skip_existing=skip_existing,
                                           validate_only=validate_only)
                
                # Process and enhance statistics
                processed_stats = _process_import_stats(stats)
                
                return jsonify({
                    'success': True,
                    'stats': processed_stats,
                    'components_processed': _get_processed_components(stats),
                    'summary': _create_summary(stats),
                    'validate_only': validate_only,
                    'total_imported': stats.get('total_imported', 0),
                    'total_errors': stats.get('total_errors', 0)
                })
                
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Import failed: {str(e)}',
                'traceback': traceback.format_exc() if app.debug else None
            }), 500
    
    
    @app.route('/api/import-export/export')
    def export_data():
        """Export database components with flexible filtering"""
        try:
            db = get_db()
            if db is None:
                return jsonify({'error': 'No database connection'}), 500
            
            export_format = request.args.get('format', 'yaml').lower()
            components = request.args.getlist('components')  # Optional component filtering
            
            # Validate format
            if export_format not in ['yaml', 'json']:
                return jsonify({'error': 'Format must be yaml or json'}), 400
            
            # Generate export
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if components:
                # Filtered export
                content, filename = _create_filtered_export(db, components, export_format, timestamp)
            else:
                # Complete database export
                content, filename = _create_complete_export(db, export_format, timestamp)
            
            content_type = 'application/json' if export_format == 'json' else 'application/x-yaml'
            return _create_download_response(content, filename, content_type)
            
        except Exception as e:
            return jsonify({
                'error': f'Export failed: {str(e)}',
                'traceback': traceback.format_exc() if app.debug else None
            }), 500
    
    
    @app.route('/api/import-export/examples/<example_type>')
    def get_example(example_type):
        """Get example files for different scenarios"""
        try:
            if example_type == 'complete':
                content = _generate_complete_example()
                filename = "example_complete_database.yaml"
            elif example_type in ComponentInfo.COMPONENTS:
                content = _generate_component_example(example_type)
                filename = f"example_{example_type}.yaml"
            elif example_type == 'mixed':
                content = _generate_mixed_example()
                filename = "example_mixed_components.yaml"
            else:
                return jsonify({'error': f'Unknown example type: {example_type}'}), 400
            
            return _create_download_response(content, filename, 'application/x-yaml')
            
        except Exception as e:
            return jsonify({'error': f'Failed to generate example: {str(e)}'}), 500
    
    
    @app.route('/api/import-export/components')
    def get_component_info():
        """Get information about available components and their current counts"""
        try:
            db = get_db()
            if db is None:
                return jsonify({'error': 'No database connection'}), 500
            
            component_info = {}
            
            for component, config in ComponentInfo.COMPONENTS.items():
                try:
                    if component == 'leagues':
                        count = len(db.list_leagues())
                    elif component == 'facilities':
                        count = len(db.list_facilities())
                    elif component == 'teams':
                        count = len(db.list_teams())
                    elif component == 'matches':
                        from usta import MatchType
                        count = len(db.list_matches(match_type=MatchType.ALL))
                    else:
                        count = 0
                        
                    component_info[component] = {
                        'display_name': config['display_name'],
                        'icon': config['icon'],
                        'color': config['color'],
                        'current_count': count
                    }
                except Exception as e:
                    component_info[component] = {
                        'display_name': config['display_name'],
                        'icon': config['icon'],
                        'color': config['color'],
                        'current_count': 0,
                        'error': str(e)
                    }
            
            return jsonify({
                'success': True,
                'components': component_info,
                'total_items': sum(info.get('current_count', 0) for info in component_info.values())
            })
            
        except Exception as e:
            return jsonify({
                'error': f'Failed to get component info: {str(e)}',
                'traceback': traceback.format_exc() if app.debug else None
            }), 500


# ==================== UTILITY FUNCTIONS ====================

def _analyze_content(data):
    """Analyze YAML content to determine what components are present"""
    if not isinstance(data, dict):
        return {
            'components_found': [],
            'component_counts': {},
            'total_items': 0,
            'is_valid': False,
            'error': 'Root level must be a dictionary'
        }
    
    component_counts = {}
    components_found = []
    total_items = 0
    
    for component in ComponentInfo.get_all_components():
        if component in data:
            items = data[component]
            if isinstance(items, list):
                count = len(items)
                component_counts[component] = count
                total_items += count
                if count > 0:
                    components_found.append(component)
            else:
                component_counts[component] = 0
        else:
            component_counts[component] = 0
    
    # Validate structure
    has_valid_components = total_items > 0
    has_metadata = 'metadata' in data
    
    return {
        'components_found': components_found,
        'component_counts': component_counts,
        'total_items': total_items,
        'is_valid': has_valid_components,
        'has_metadata': has_metadata,
        'metadata': data.get('metadata', {}),
        'structure_valid': isinstance(data, dict) and has_valid_components
    }


def _process_import_stats(stats):
    """Process and enhance import statistics"""
    processed = {}
    
    for component in ComponentInfo.get_all_components():
        if component in stats:
            component_stats = stats[component]
            processed[component] = {
                'processed': component_stats.get('processed', 0),
                'imported': component_stats.get('imported', 0),
                'skipped': component_stats.get('skipped', 0),
                'errors': component_stats.get('errors', []),
                'error_count': len(component_stats.get('errors', [])),
                'success_rate': _calculate_success_rate(component_stats),
                'had_data': component_stats.get('processed', 0) > 0
            }
    
    # Add totals and overall info
    processed['summary'] = {
        'total_processed': stats.get('total_processed', 0),
        'total_imported': stats.get('total_imported', 0),
        'total_skipped': stats.get('total_skipped', 0),
        'total_errors': stats.get('total_errors', 0),
        'duration_seconds': stats.get('duration_seconds', 0),
        'overall_success': stats.get('total_errors', 0) == 0
    }
    
    return processed


def _calculate_success_rate(component_stats):
    """Calculate success rate for a component"""
    processed = component_stats.get('processed', 0)
    if processed == 0:
        return 100.0
    
    errors = len(component_stats.get('errors', []))
    return ((processed - errors) / processed) * 100.0


def _get_processed_components(stats):
    """Get list of components that were actually processed"""
    processed = []
    for component in ComponentInfo.get_all_components():
        if component in stats and stats[component].get('processed', 0) > 0:
            processed.append(component)
    return processed


def _create_summary(stats):
    """Create a human-readable summary of import statistics"""
    summary_parts = []
    
    for component in ComponentInfo.get_all_components():
        if component in stats:
            component_stats = stats[component]
            imported = component_stats.get('imported', 0)
            skipped = component_stats.get('skipped', 0)
            errors = len(component_stats.get('errors', []))
            
            if imported > 0 or skipped > 0 or errors > 0:
                display_name = ComponentInfo.COMPONENTS[component]['display_name']
                summary_parts.append(f"{display_name}: {imported} imported, {skipped} skipped, {errors} errors")
    
    return '; '.join(summary_parts) if summary_parts else 'No data processed'


def _create_complete_export(db, export_format, timestamp):
    """Create complete database export"""
    temp_filename = f"tennis_database_{timestamp}.yaml"
    temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
    
    try:
        # Use database's built-in export
        db.export_to_yaml(temp_path)
        
        with open(temp_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if export_format == 'json':
            data = yaml.safe_load(content)
            content = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            filename = f"tennis_database_{timestamp}.json"
        else:
            filename = temp_filename
        
        return content, filename
        
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def _create_filtered_export(db, components, export_format, timestamp):
    """Create filtered export with only specified components"""
    # First get complete export
    temp_filename = f"tennis_complete_{timestamp}.yaml"
    temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
    
    try:
        db.export_to_yaml(temp_path)
        
        with open(temp_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f.read())
        
        # Filter to requested components
        filtered_data = {}
        if 'metadata' in data:
            filtered_data['metadata'] = data['metadata']
            filtered_data['metadata']['filtered_components'] = components
        
        for component in components:
            if component in data and component in ComponentInfo.COMPONENTS:
                filtered_data[component] = data[component]
        
        # Convert to requested format
        if export_format == 'json':
            content = json.dumps(filtered_data, indent=2, ensure_ascii=False, default=str)
            filename = f"tennis_{'_'.join(components)}_{timestamp}.json"
        else:
            content = yaml.dump(filtered_data, default_flow_style=False, 
                              sort_keys=False, allow_unicode=True, indent=2, width=120)
            filename = f"tennis_{'_'.join(components)}_{timestamp}.yaml"
        
        return content, filename
        
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def _create_download_response(content, filename, content_type):
    """Create a download response with proper headers"""
    response = make_response(content)
    response.headers['Content-Type'] = content_type
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _generate_complete_example():
    """Generate example YAML with all components"""
    return """metadata:
  export_timestamp: '2024-01-01T12:00:00'
  format_version: '1.0'
  description: Complete tennis database example with all components

leagues:
- id: 1
  name: Spring Adult League
  year: 2024
  section: Southern California
  region: West
  age_group: 18 & Over
  division: '4.0'
  num_lines_per_match: 3
  num_matches: 10

facilities:
- id: 1
  name: Tennis Center West
  short_name: TCW
  location: 123 Tennis Lane, Tennis City, CA 12345
  total_courts: 8
- id: 2
  name: Tennis Center East
  short_name: TCE
  location: 456 Court Street, Tennis City, CA 12345
  total_courts: 6

teams:
- id: 1
  name: Tennis Center West Team A
  league_id: 1
  home_facility_id: 1
  captain: John Doe
- id: 2
  name: Tennis Center East Team A
  league_id: 1
  home_facility_id: 2
  captain: Jane Smith

matches:
- id: 1
  league_id: 1
  home_team_id: 1
  visitor_team_id: 2
  date: '2024-03-15'
  scheduled_times:
  - '09:00'
  - '12:00'
  - '15:00'
"""


def _generate_component_example(component):
    """Generate example YAML for a specific component"""
    examples = {
        'leagues': """metadata:
  export_timestamp: '2024-01-01T12:00:00'
  format_version: '1.0'
  component: leagues

leagues:
- id: 1
  name: Spring Adult League
  year: 2024
  section: Southern California
  region: West
  age_group: 18 & Over
  division: '4.0'
  num_lines_per_match: 3
  num_matches: 10
""",
        'facilities': """metadata:
  export_timestamp: '2024-01-01T12:00:00'
  format_version: '1.0'
  component: facilities

facilities:
- id: 1
  name: Tennis Center West
  short_name: TCW
  location: 123 Tennis Lane, Tennis City, CA 12345
  total_courts: 8
""",
        'teams': """metadata:
  export_timestamp: '2024-01-01T12:00:00'
  format_version: '1.0'
  component: teams

teams:
- id: 1
  name: Tennis Center West Team A
  league_id: 1
  home_facility_id: 1
  captain: John Doe
""",
        'matches': """metadata:
  export_timestamp: '2024-01-01T12:00:00'
  format_version: '1.0'
  component: matches

matches:
- id: 1
  league_id: 1
  home_team_id: 1
  visitor_team_id: 2
  date: '2024-03-15'
  scheduled_times:
  - '09:00'
  - '12:00'
  - '15:00'
"""
    }
    
    return examples.get(component, "# No example available")


def _generate_mixed_example():
    """Generate example with mixed components (not complete database)"""
    return """metadata:
  export_timestamp: '2024-01-01T12:00:00'
  format_version: '1.0'
  description: Example showing import of leagues and facilities only

leagues:
- id: 1
  name: Summer League
  year: 2024
  section: Southern California
  region: West
  age_group: 18 & Over
  division: '3.5'
  num_lines_per_match: 3
  num_matches: 8

facilities:
- id: 10
  name: New Tennis Complex
  short_name: NTC
  location: 789 New Court Blvd, Tennis City, CA 12345
  total_courts: 12
"""