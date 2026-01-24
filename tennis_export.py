"""
Tennis Database Export Module

This module provides export functionality for tennis database records to multiple formats:
- YAML: Human-readable format with full schema support
- Excel: Spreadsheet format for easy viewing and analysis

Features:
- Export all data or filter by component (leagues, facilities, teams, matches)
- Filter by league for teams and matches
- Excel export creates separate sheets for each component
- Automatic format detection from file extension

Usage:
    from tennis_export import TennisExporter

    exporter = TennisExporter(db)
    exporter.export_to_yaml('export.yaml', components=['leagues', 'teams'])
    exporter.export_to_excel('export.xlsx', league_id=1)

Author: Tennis App Development Team
"""

import os
import yaml
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TennisExporter:
    """Handles export of tennis database records to various formats"""

    def __init__(self, db):
        """
        Initialize exporter with database connection

        Args:
            db: TennisDBInterface implementation (e.g., SQLiteTennisDB)
        """
        self.db = db

    def export(self, file_path: str,
               format: str = 'auto',
               components: Optional[List[str]] = None,
               league_id: Optional[int] = None,
               include_metadata: bool = True) -> Dict[str, Any]:
        """
        Export data to specified format

        Args:
            file_path: Path to output file
            format: Export format ('yaml', 'excel', or 'auto' to detect from extension)
            components: List of components to export (['leagues', 'facilities', 'teams', 'matches'])
                       or None for all components
            league_id: Optional league ID to filter teams and matches
            include_metadata: Include metadata section in export (YAML only)

        Returns:
            Dictionary with export statistics

        Raises:
            ValueError: If format is invalid or cannot be determined
            ImportError: If required libraries are not available (e.g., pandas for Excel)
            RuntimeError: If export fails
        """
        # Auto-detect format from extension
        if format == 'auto':
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.xlsx', '.xls']:
                format = 'excel'
            elif ext in ['.yaml', '.yml']:
                format = 'yaml'
            else:
                raise ValueError(f"Unable to determine format from extension '{ext}'. "
                               "Please specify format='yaml' or format='excel'")

        # Default to all components if not specified
        if components is None:
            components = ['leagues', 'facilities', 'teams', 'matches']

        # Validate components
        valid_components = {'leagues', 'facilities', 'teams', 'matches'}
        invalid = set(components) - valid_components
        if invalid:
            raise ValueError(f"Invalid components: {invalid}. Valid: {valid_components}")

        # Dispatch to appropriate export method
        if format == 'yaml':
            return self.export_to_yaml(file_path, components, league_id, include_metadata)
        elif format == 'excel':
            return self.export_to_excel(file_path, components, league_id)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def export_to_yaml(self, file_path: str,
                       components: List[str],
                       league_id: Optional[int] = None,
                       include_metadata: bool = True) -> Dict[str, Any]:
        """
        Export data to YAML format

        Args:
            file_path: Path to output YAML file
            components: List of components to export
            league_id: Optional league ID to filter teams and matches
            include_metadata: Include metadata section in export

        Returns:
            Dictionary with export statistics
        """
        try:
            start_time = datetime.now()

            # If exporting all components without filtering, use built-in method
            if (set(components) == {'leagues', 'facilities', 'teams', 'matches'}
                and league_id is None):
                stats = self.db.export_to_yaml(file_path)
                stats['format'] = 'yaml'
                stats['file_path'] = file_path
                return stats

            # Otherwise, do filtered export
            export_data = {}
            stats = {
                'format': 'yaml',
                'file_path': file_path,
                'leagues': 0,
                'facilities': 0,
                'teams': 0,
                'matches': 0,
                'total': 0
            }

            # Add metadata
            if include_metadata:
                export_data['metadata'] = {
                    'export_timestamp': start_time.isoformat(),
                    'format_version': '1.0',
                    'components': components
                }
                if league_id:
                    export_data['metadata']['league_filter'] = league_id

            # Export each component
            if 'leagues' in components:
                leagues = self._get_leagues(league_id)
                export_data['leagues'] = [league.to_dict() for league in leagues]
                stats['leagues'] = len(export_data['leagues'])
                stats['total'] += stats['leagues']

            if 'facilities' in components:
                facilities = self.db.list_facilities()
                export_data['facilities'] = [facility.to_yaml_dict() for facility in facilities]
                stats['facilities'] = len(export_data['facilities'])
                stats['total'] += stats['facilities']

            if 'teams' in components:
                teams = self._get_teams(league_id)
                export_data['teams'] = [team.to_dict() for team in teams]
                stats['teams'] = len(export_data['teams'])
                stats['total'] += stats['teams']

            if 'matches' in components:
                matches = self._get_matches(league_id)
                export_data['matches'] = [match.to_dict() for match in matches]
                stats['matches'] = len(export_data['matches'])
                stats['total'] += stats['matches']

            # Write YAML file
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(export_data, f, default_flow_style=False,
                         sort_keys=False, allow_unicode=True, indent=2, width=120)

            # Add timing info
            duration = (datetime.now() - start_time).total_seconds()
            stats['duration_seconds'] = duration

            logger.info(f"YAML export completed: {stats['total']} records in {duration:.2f}s")
            return stats

        except Exception as e:
            error_msg = f"YAML export failed: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def export_to_excel(self, file_path: str,
                        components: List[str],
                        league_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Export data to Excel format

        Args:
            file_path: Path to output Excel file (.xlsx)
            components: List of components to export
            league_id: Optional league ID to filter teams and matches

        Returns:
            Dictionary with export statistics

        Raises:
            ImportError: If pandas or openpyxl is not installed
        """
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError("Excel export requires pandas and openpyxl libraries. "
                            "Install with: pip install pandas openpyxl") from e

        try:
            start_time = datetime.now()
            dataframes = {}
            stats = {
                'format': 'excel',
                'file_path': file_path,
                'leagues': 0,
                'facilities': 0,
                'teams': 0,
                'matches': 0,
                'total': 0,
                'sheets': []
            }

            # Export each component to a DataFrame
            if 'leagues' in components:
                leagues = self._get_leagues(league_id)
                if leagues:
                    leagues_data = self._leagues_to_dict_list(leagues)
                    dataframes['Leagues'] = pd.DataFrame(leagues_data)
                    stats['leagues'] = len(leagues_data)
                    stats['total'] += stats['leagues']
                    stats['sheets'].append('Leagues')

            if 'facilities' in components:
                facilities = self.db.list_facilities()
                if facilities:
                    facilities_data = self._facilities_to_dict_list(facilities)
                    dataframes['Facilities'] = pd.DataFrame(facilities_data)
                    stats['facilities'] = len(facilities_data)
                    stats['total'] += stats['facilities']
                    stats['sheets'].append('Facilities')

            if 'teams' in components:
                teams = self._get_teams(league_id)
                if teams:
                    teams_data = self._teams_to_dict_list(teams)
                    dataframes['Teams'] = pd.DataFrame(teams_data)
                    stats['teams'] = len(teams_data)
                    stats['total'] += stats['teams']
                    stats['sheets'].append('Teams')

            if 'matches' in components:
                matches = self._get_matches(league_id)
                if matches:
                    matches_data = self._matches_to_dict_list(matches)
                    dataframes['Matches'] = pd.DataFrame(matches_data)
                    stats['matches'] = len(matches_data)
                    stats['total'] += stats['matches']
                    stats['sheets'].append('Matches')

            # Write to Excel file
            if dataframes:
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    for sheet_name, df in dataframes.items():
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        # Auto-adjust column widths
                        worksheet = writer.sheets[sheet_name]
                        for column in worksheet.columns:
                            max_length = 0
                            column_letter = column[0].column_letter
                            for cell in column:
                                try:
                                    if len(str(cell.value)) > max_length:
                                        max_length = len(str(cell.value))
                                except:
                                    pass
                            adjusted_width = min(max_length + 2, 50)
                            worksheet.column_dimensions[column_letter].width = adjusted_width

            # Add timing info
            duration = (datetime.now() - start_time).total_seconds()
            stats['duration_seconds'] = duration

            logger.info(f"Excel export completed: {stats['total']} records in {duration:.2f}s")
            return stats

        except Exception as e:
            error_msg = f"Excel export failed: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    # ========== Helper Methods ==========

    def _get_leagues(self, league_id: Optional[int]) -> List:
        """Get leagues, optionally filtered by ID"""
        if league_id:
            league = self.db.get_league(league_id)
            return [league] if league else []
        return self.db.list_leagues()

    def _get_teams(self, league_id: Optional[int]) -> List:
        """Get teams, optionally filtered by league"""
        if league_id:
            league = self.db.get_league(league_id)
            return self.db.list_teams(league) if league else []
        return self.db.list_teams()

    def _get_matches(self, league_id: Optional[int]) -> List:
        """Get matches, optionally filtered by league"""
        from usta_match import MatchType
        if league_id:
            league = self.db.get_league(league_id)
            return self.db.list_matches(league=league, match_type=MatchType.ALL) if league else []
        return self.db.list_matches(match_type=MatchType.ALL)

    def _leagues_to_dict_list(self, leagues: List) -> List[Dict[str, Any]]:
        """Convert leagues to list of dictionaries suitable for Excel"""
        result = []
        for league in leagues:
            league_dict = league.to_dict()
            # Flatten list fields for Excel
            league_dict['preferred_days'] = ', '.join(league_dict.get('preferred_days', []))
            league_dict['backup_days'] = ', '.join(league_dict.get('backup_days', []))
            result.append(league_dict)
        return result

    def _facilities_to_dict_list(self, facilities: List) -> List[Dict[str, Any]]:
        """Convert facilities to list of dictionaries suitable for Excel"""
        result = []
        for facility in facilities:
            # Use simple dict for Excel (not full YAML dict with schedule)
            fac_dict = {
                'id': facility.id,
                'name': facility.name,
                'short_name': facility.short_name,
                'location': facility.location,
                'total_courts': facility.total_courts
            }
            result.append(fac_dict)
        return result

    def _teams_to_dict_list(self, teams: List) -> List[Dict[str, Any]]:
        """Convert teams to list of dictionaries suitable for Excel"""
        result = []
        for team in teams:
            team_dict = team.to_dict()
            # Add human-readable fields
            team_dict['league_name'] = team.league.name
            team_dict['home_facility'] = team.get_primary_facility().name if team.preferred_facilities else ''
            # Flatten list fields
            team_dict['preferred_days'] = ', '.join(team_dict.get('preferred_days', []))
            # Remove complex nested objects
            team_dict.pop('preferred_facility_ids', None)
            result.append(team_dict)
        return result

    def _matches_to_dict_list(self, matches: List) -> List[Dict[str, Any]]:
        """Convert matches to list of dictionaries suitable for Excel"""
        result = []
        for match in matches:
            match_dict = match.to_dict()
            # Add human-readable fields
            match_dict['league_name'] = match.league.name
            match_dict['home_team_name'] = match.home_team.name
            match_dict['visitor_team_name'] = match.visitor_team.name
            match_dict['status'] = match.get_status()

            # Flatten scheduling information
            if match.scheduling:
                match_dict['facility_name'] = match.scheduling.facility.name
                match_dict['date'] = str(match.scheduling.date)
                match_dict['scheduled_times'] = ', '.join(match.scheduling.scheduled_times)
            else:
                match_dict['facility_name'] = ''
                match_dict['date'] = ''
                match_dict['scheduled_times'] = ''

            result.append(match_dict)
        return result
