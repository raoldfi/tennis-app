from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from usta import Team, League, Match, Facility

class TennisDB(ABC):
    """
    Abstract base class for a tennis scheduling database system.
    Manages teams, leagues, matches, and facilities.
    """

    @abstractmethod
    def add_team(self, team: Team) -> None:
        pass

    @abstractmethod
    def get_team(self, team_id: int) -> Optional[Team]:
        pass

    @abstractmethod
    def list_teams(self, league_id: Optional[int] = None) -> List[Team]:
        pass

    @abstractmethod
    def add_league(self, league: League) -> None:
        pass

    @abstractmethod
    def get_league(self, league_id: int) -> Optional[League]:
        pass

    @abstractmethod
    def list_leagues(self) -> List[League]:
        pass

    @abstractmethod
    def add_match(self, match: Match) -> None:
        pass

    @abstractmethod
    def get_match(self, match_id: int) -> Optional[Match]:
        pass

    @abstractmethod
    def list_matches(self, league_id: Optional[int] = None) -> List[Match]:
        pass

    @abstractmethod
    def add_facility(self, facility: Facility) -> None:
        pass

    @abstractmethod
    def get_facility(self, facility_id: int) -> Optional[Facility]:
        pass

    @abstractmethod
    def list_facilities(self) -> List[Facility]:
        pass