"""

Game Filtering Service for post-fetch filtering of Chess.com games.



Since Chess.com API doesn't support native filtering, we fetch games

and then apply filters on the results.

"""

from datetime import datetime, timezone

from typing import Dict, List, Optional

from loguru import logger





class GameFilter:

    """Filter configuration for game queries."""

    

    def __init__(

        self,

        game_count: Optional[int] = None,

        start_date: Optional[datetime] = None,

        end_date: Optional[datetime] = None,

        time_controls: Optional[List[str]] = None,

        rated_only: Optional[bool] = None,

        unrated_only: Optional[bool] = None,

    ):

        """

        Initialize game filter.

        

        Args:

            game_count: Maximum number of games to return (e.g., 10, 25, 50)

            start_date: Filter games after this date

            end_date: Filter games before this date

            time_controls: List of time controls to include ['bullet', 'blitz', 'rapid', 'daily']

            rated_only: Only include rated games

            unrated_only: Only include unrated games

        """

        self.game_count = game_count

        self.start_date = start_date

        self.end_date = end_date

        self.time_controls = time_controls or []

        self.rated_only = rated_only

        self.unrated_only = unrated_only

        

        # Validation

        if rated_only and unrated_only:

            raise ValueError("Cannot specify both rated_only and unrated_only")

    

    @classmethod

    def from_dict(cls, filter_dict: Dict) -> "GameFilter":

        """

        Create GameFilter from dictionary.

        

        Args:

            filter_dict: Dictionary with filter parameters

            

        Returns:

            GameFilter instance

            

        Example:

            {

                "game_count": 25,

                "start_date": "2025-10-01T00:00:00Z",

                "end_date": "2025-11-01T00:00:00Z",

                "time_controls": ["blitz", "rapid"],

                "rated_only": true

            }

        """

        # Parse dates if provided as strings

        start_date = None

        if filter_dict.get("start_date"):

            if isinstance(filter_dict["start_date"], str):

                start_date = datetime.fromisoformat(filter_dict["start_date"].replace('Z', '+00:00'))

            else:

                start_date = filter_dict["start_date"]

        

        end_date = None

        if filter_dict.get("end_date"):

            if isinstance(filter_dict["end_date"], str):

                end_date = datetime.fromisoformat(filter_dict["end_date"].replace('Z', '+00:00'))

            else:

                end_date = filter_dict["end_date"]

        

        return cls(

            game_count=filter_dict.get("game_count"),

            start_date=start_date,

            end_date=end_date,

            time_controls=filter_dict.get("time_controls"),

            rated_only=filter_dict.get("rated_only"),

            unrated_only=filter_dict.get("unrated_only"),

        )

    

    def to_dict(self) -> Dict:

        """Convert filter to dictionary for serialization."""

        return {

            "game_count": self.game_count,

            "start_date": self.start_date.isoformat() if self.start_date else None,

            "end_date": self.end_date.isoformat() if self.end_date else None,

            "time_controls": self.time_controls,

            "rated_only": self.rated_only,

            "unrated_only": self.unrated_only,

        }





class FilterService:

    """Service for filtering games based on various criteria."""

    

    @staticmethod

    def apply_filters(games: List[Dict], game_filter: GameFilter) -> List[Dict]:

        """

        Apply filters to a list of games.

        

        Args:

            games: List of game dictionaries (from Chess.com API)

            game_filter: Filter configuration

            

        Returns:

            Filtered list of games

        """

        filtered_games = games.copy()

        

        # Apply date range filter

        if game_filter.start_date or game_filter.end_date:

            filtered_games = FilterService._filter_by_date_range(

                filtered_games,

                game_filter.start_date,

                game_filter.end_date

            )

            logger.debug(f"After date filter: {len(filtered_games)} games")

        

        # Apply time control filter

        if game_filter.time_controls:

            filtered_games = FilterService._filter_by_time_control(

                filtered_games,

                game_filter.time_controls

            )

            logger.debug(f"After time control filter: {len(filtered_games)} games")

        

        # Apply rated/unrated filter

        if game_filter.rated_only is not None or game_filter.unrated_only is not None:

            filtered_games = FilterService._filter_by_rated(

                filtered_games,

                game_filter.rated_only,

                game_filter.unrated_only

            )

            logger.debug(f"After rated filter: {len(filtered_games)} games")

        

        # Apply game count limit (after other filters)

        if game_filter.game_count:

            filtered_games = filtered_games[:game_filter.game_count]

            logger.debug(f"After count limit: {len(filtered_games)} games")

        

        logger.info(

            f"Filtered {len(games)} games down to {len(filtered_games)} "

            f"using filters: {game_filter.to_dict()}"

        )

        

        return filtered_games

    

    @staticmethod

    def _filter_by_date_range(

        games: List[Dict],

        start_date: Optional[datetime],

        end_date: Optional[datetime]

    ) -> List[Dict]:

        """Filter games by date range."""

        filtered = []

        

        for game in games:

            end_time = game.get("end_time")

            

            # Skip if no end_time

            if not end_time:

                continue

            

            # Convert timestamp to datetime if needed

            if isinstance(end_time, (int, float)):

                game_date = datetime.fromtimestamp(end_time, tz=timezone.utc)

            elif isinstance(end_time, datetime):

                game_date = end_time

            else:

                continue

            

            # Check date range

            if start_date and game_date < start_date:

                continue

            if end_date and game_date > end_date:

                continue

            

            filtered.append(game)

        

        return filtered

    

    @staticmethod

    def _filter_by_time_control(

        games: List[Dict],

        time_controls: List[str]

    ) -> List[Dict]:

        """

        Filter games by time control.

        

        Args:

            games: List of games

            time_controls: List of time control types to include

                          ['bullet', 'blitz', 'rapid', 'daily', 'all']

        

        Returns:

            Filtered games matching time controls

        """

        # If 'all' is in the list, return all games

        if 'all' in time_controls or not time_controls:

            return games

        

        # Normalize time control names

        normalized_controls = [tc.lower() for tc in time_controls]

        

        filtered = []

        for game in games:

            time_class = game.get("time_class", "").lower()

            

            if time_class in normalized_controls:

                filtered.append(game)

        

        return filtered

    

    @staticmethod

    def _filter_by_rated(

        games: List[Dict],

        rated_only: Optional[bool],

        unrated_only: Optional[bool]

    ) -> List[Dict]:

        """Filter games by rated/unrated status."""

        if rated_only is None and unrated_only is None:

            return games

        

        filtered = []

        for game in games:

            is_rated = game.get("rated", False)

            

            if rated_only and is_rated:

                filtered.append(game)

            elif unrated_only and not is_rated:

                filtered.append(game)

            elif not rated_only and not unrated_only:

                # Include all if neither is True

                filtered.append(game)

        

        return filtered

    

    @staticmethod

    def get_filter_summary(games: List[Dict]) -> Dict:

        """

        Get summary statistics of a game collection.

        

        Args:

            games: List of games

            

        Returns:

            Dictionary with summary stats

        """

        if not games:

            return {

                "total_games": 0,

                "time_controls": {},

                "rated_count": 0,

                "unrated_count": 0,

                "date_range": None

            }

        

        # Count time controls

        time_control_counts = {}

        rated_count = 0

        unrated_count = 0

        dates = []

        

        for game in games:

            # Time control

            time_class = game.get("time_class", "unknown")

            time_control_counts[time_class] = time_control_counts.get(time_class, 0) + 1

            

            # Rated status

            if game.get("rated", False):

                rated_count += 1

            else:

                unrated_count += 1

            

            # Date

            end_time = game.get("end_time")

            if end_time:

                if isinstance(end_time, (int, float)):

                    dates.append(datetime.fromtimestamp(end_time, tz=timezone.utc))

                elif isinstance(end_time, datetime):

                    dates.append(end_time)

        

        # Determine date range

        date_range = None

        if dates:

            date_range = {

                "earliest": min(dates).isoformat(),

                "latest": max(dates).isoformat()

            }

        

        return {

            "total_games": len(games),

            "time_controls": time_control_counts,

            "rated_count": rated_count,

            "unrated_count": unrated_count,

            "date_range": date_range

        }





# Factory function

def get_filter_service() -> FilterService:

    """Get FilterService instance."""

    return FilterService()

