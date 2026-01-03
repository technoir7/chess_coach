import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class OpeningDB:
    """
    Client for the Lichess Opening Explorer API (Masters database).
    Documentation: https://lichess.org/api#tag/Opening-Explorer
    """
    
    BASE_URL = "https://explorer.lichess.ovh/masters"

    def get_opening(self, fen: str) -> Dict:
        """
        Fetch opening data for a given FEN.
        Returns a dictionary with opening name, ECO, and top moves.
        """
        try:
            # Lichess API requires 'fen' parameter. 
            # We also request 'moves=5' to get top 5 moves stats.
            params = {
                "fen": fen,
                "moves": 5
            }
            
            response = requests.get(self.BASE_URL, params=params, timeout=2)
            
            if response.status_code != 200:
                logger.warning(f"Lichess API returned status {response.status_code}")
                return {}
                
            data = response.json()
            
            # Extract relevant info
            opening_info = data.get("opening", {})
            name = opening_info.get("name", "Unknown Opening")
            eco = opening_info.get("eco", "A00")
            
            moves = []
            for move in data.get("moves", []):
                moves.append({
                    "san": move["san"],
                    "white": move["white"],
                    "draw": move["draw"],
                    "black": move["black"],
                    "total": move["white"] + move["draw"] + move["black"]
                })
            
            return {
                "name": name,
                "eco": eco,
                "moves": moves
            }
            
        except requests.RequestException as e:
            logger.warning(f"Failed to connect to Lichess API: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error parsing opening data: {e}")
            return {}
