import pandas as pd
from sqlalchemy import desc, and_, func
from sqlalchemy.orm.exc import NoResultFound

from database import (
    get_db_session, Team, Player, Game, BattingOrder, 
    FieldingRotation, PlayerAvailability, 
    roster_df_to_db, roster_db_to_df, 
    schedule_df_to_db, schedule_db_to_df
)

# Team Operations
def get_team(team_id):
    """Get team by ID"""
    session = get_db_session()
    try:
        team = session.query(Team).filter(Team.id == team_id).one()
        return team
    except NoResultFound:
        return None
    finally:
        session.close()

def create_team(team_info):
    """Create a new team"""
    session = get_db_session()
    try:
        team = Team(
            name=team_info.get("team_name", ""),
            league=team_info.get("league", ""),
            head_coach=team_info.get("head_coach", ""),
            assistant_coach1=team_info.get("assistant_coach1", ""),
            assistant_coach2=team_info.get("assistant_coach2", "")
        )
        session.add(team)
        session.commit()
        return team.id
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def update_team(team_id, team_info):
    """Update team information"""
    session = get_db_session()
    try:
        team = session.query(Team).filter(Team.id == team_id).one()
        team.name = team_info.get("team_name", team.name)
        team.league = team_info.get("league", team.league)
        team.head_coach = team_info.get("head_coach", team.head_coach)
        team.assistant_coach1 = team_info.get("assistant_coach1", team.assistant_coach1)
        team.assistant_coach2 = team_info.get("assistant_coach2", team.assistant_coach2)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_team_info(team_id):
    """Get team info dictionary"""
    session = get_db_session()
    try:
        team = session.query(Team).filter(Team.id == team_id).one()
        return {
            "team_name": team.name,
            "league": team.league,
            "head_coach": team.head_coach,
            "assistant_coach1": team.assistant_coach1,
            "assistant_coach2": team.assistant_coach2
        }
    except NoResultFound:
        return {
            "team_name": "",
            "league": "",
            "head_coach": "",
            "assistant_coach1": "",
            "assistant_coach2": ""
        }
    finally:
        session.close()

# Player Operations
def get_roster(team_id):
    """Get team roster as dataframe"""
    session = get_db_session()
    try:
        players = session.query(Player).filter(Player.team_id == team_id).all()
        return roster_db_to_df(players)
    finally:
        session.close()

def update_roster(team_id, roster_df):
    """Update team roster from dataframe"""
    session = get_db_session()
    try:
        # Get current players
        current_players = session.query(Player).filter(Player.team_id == team_id).all()
        current_jerseys = {p.jersey_number: p for p in current_players}
        
        # Track changes for jersey number updates
        jersey_changes = {}
        
        # Process each player in the new roster
        for _, row in roster_df.iterrows():
            first_name = row['First Name']
            last_name = row['Last Name']
            jersey_number = str(row['Jersey Number'])
            
            # See if we can find a match by name in current players
            player_match = None
            for p in current_players:
                if p.first_name == first_name and p.last_name == last_name:
                    player_match = p
                    break
            
            if player_match:
                # Player exists, update jersey if changed
                if player_match.jersey_number != jersey_number:
                    # Track the change for updating dependencies
                    jersey_changes[player_match.jersey_number] = jersey_number
                    # Update jersey
                    player_match.jersey_number = jersey_number
            else:
                # New player, add them
                new_player = Player(
                    team_id=team_id,
                    first_name=first_name,
                    last_name=last_name,
                    jersey_number=jersey_number
                )
                session.add(new_player)
        
        # Find players to remove (in old roster but not in new)
        new_player_names = set((row['First Name'], row['Last Name']) for _, row in roster_df.iterrows())
        players_to_remove = [
            p for p in current_players 
            if (p.first_name, p.last_name) not in new_player_names
        ]
        
        # Remove players no longer in roster
        for player in players_to_remove:
            session.delete(player)
        
        session.commit()
        
        # Update jersey references in batting orders and fielding rotations
        if jersey_changes:
            _update_jersey_references(session, team_id, jersey_changes)
            session.commit()
            
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def _update_jersey_references(session, team_id, jersey_changes):
    """Update jersey number references in batting orders and fielding rotations"""
    # Update batting orders
    batting_orders = session.query(BattingOrder).join(Game).filter(Game.team_id == team_id).all()
    for batting_order in batting_orders:
        if batting_order.order_data:
            updated = False
            order_data = batting_order.order_data
            for old_jersey, new_jersey in jersey_changes.items():
                if old_jersey in order_data:
                    # Replace old jersey with new jersey
                    index = order_data.index(old_jersey)
                    order_data[index] = new_jersey
                    updated = True
            if updated:
                batting_order.order_data = order_data
    
    # Update fielding rotations
    fielding_rotations = session.query(FieldingRotation).join(Game).filter(Game.team_id == team_id).all()
    for rotation in fielding_rotations:
        if rotation.positions:
            updated = False
            positions = rotation.positions
            for old_jersey, new_jersey in jersey_changes.items():
                if old_jersey in positions:
                    # Copy position for old jersey to new jersey
                    positions[new_jersey] = positions[old_jersey]
                    # Remove old jersey
                    del positions[old_jersey]
                    updated = True
            if updated:
                rotation.positions = positions

# Game Operations
def get_schedule(team_id):
    """Get team schedule as dataframe"""
    session = get_db_session()
    try:
        games = session.query(Game).filter(Game.team_id == team_id).order_by(Game.game_number).all()
        return schedule_db_to_df(games)
    finally:
        session.close()

def update_schedule(team_id, schedule_df):
    """Update team schedule from dataframe"""
    session = get_db_session()
    try:
        # Get current games
        current_games = session.query(Game).filter(Game.team_id == team_id).all()
        current_game_numbers = {g.game_number: g for g in current_games}
        
        # Process each game in the new schedule
        for _, row in schedule_df.iterrows():
            game_number = int(row['Game #'])
            
            if game_number in current_game_numbers:
                # Update existing game
                game = current_game_numbers[game_number]
                game.date = row['Date'] if pd.notna(row['Date']) else None
                game.time = row['Time'] if 'Time' in row and pd.notna(row['Time']) else None
                game.opponent = row['Opponent']
                game.innings = row['Innings']
            else:
                # Create new game
                new_game = Game(
                    team_id=team_id,
                    game_number=game_number,
                    date=row['Date'] if pd.notna(row['Date']) else None,
                    time=row['Time'] if 'Time' in row and pd.notna(row['Time']) else None,
                    opponent=row['Opponent'],
                    innings=row['Innings']
                )
                session.add(new_game)
        
        # Remove games not in the new schedule
        new_game_numbers = set(int(row['Game #']) for _, row in schedule_df.iterrows())
        games_to_remove = [
            g for g in current_games 
            if g.game_number not in new_game_numbers
        ]
        
        for game in games_to_remove:
            session.delete(game)
        
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_game_by_number(team_id, game_number):
    """Get a game by its game number"""
    session = get_db_session()
    try:
        game = session.query(Game).filter(
            Game.team_id == team_id,
            Game.game_number == game_number
        ).one()
        return game
    except NoResultFound:
        return None
    finally:
        session.close()

# Batting Order Operations
def get_batting_orders(team_id):
    """Get all batting orders for team as dictionary {game_number: order_list}"""
    session = get_db_session()
    try:
        result = {}
        batting_orders = session.query(BattingOrder, Game.game_number).join(Game).filter(
            Game.team_id == team_id
        ).all()
        
        for batting_order, game_number in batting_orders:
            result[game_number] = batting_order.order_data
            
        return result
    finally:
        session.close()

def update_batting_order(team_id, game_number, batting_order):
    """Update batting order for a game"""
    session = get_db_session()
    try:
        # Get the game
        game = session.query(Game).filter(
            Game.team_id == team_id,
            Game.game_number == game_number
        ).one()
        
        # Check if batting order exists
        existing = session.query(BattingOrder).filter(
            BattingOrder.game_id == game.id
        ).first()
        
        if existing:
            # Update existing
            existing.order_data = batting_order
        else:
            # Create new
            new_order = BattingOrder(
                game_id=game.id,
                order_data=batting_order
            )
            session.add(new_order)
            
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

# Fielding Rotation Operations
def get_fielding_rotations(team_id):
    """Get all fielding rotations for team as nested dictionary {game_number: {inning_key: positions}}"""
    session = get_db_session()
    try:
        result = {}
        rotations = session.query(FieldingRotation, Game.game_number).join(Game).filter(
            Game.team_id == team_id
        ).all()
        
        for rotation, game_number in rotations:
            if game_number not in result:
                result[game_number] = {}
                
            inning_key = f"Inning {rotation.inning}"
            result[game_number][inning_key] = rotation.positions
            
        return result
    finally:
        session.close()

def update_fielding_rotation(team_id, game_number, inning, positions):
    """Update fielding rotation for a game inning"""
    session = get_db_session()
    try:
        # Get the game
        game = session.query(Game).filter(
            Game.team_id == team_id,
            Game.game_number == game_number
        ).one()
        
        # Check if rotation exists
        existing = session.query(FieldingRotation).filter(
            FieldingRotation.game_id == game.id,
            FieldingRotation.inning == inning
        ).first()
        
        if existing:
            # Update existing
            existing.positions = positions
        else:
            # Create new
            new_rotation = FieldingRotation(
                game_id=game.id,
                inning=inning,
                positions=positions
            )
            session.add(new_rotation)
            
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

# Player Availability Operations
def get_player_availability(team_id):
    """Get player availability for all games as nested dictionary {game_number: {key: {jersey: value}}}"""
    session = get_db_session()
    try:
        result = {}
        
        # Join PlayerAvailability, Game, and Player to get all data
        availability_data = session.query(
            PlayerAvailability, Game.game_number, Player.jersey_number
        ).join(Game).join(Player).filter(
            Game.team_id == team_id
        ).all()
        
        for availability, game_number, jersey in availability_data:
            if game_number not in result:
                result[game_number] = {
                    "Available": {},
                    "Can Play Catcher": {}
                }
                
            # Add availability and catcher info
            result[game_number]["Available"][jersey] = availability.available
            result[game_number]["Can Play Catcher"][jersey] = availability.can_play_catcher
            
        return result
    finally:
        session.close()

def update_player_availability(team_id, game_number, availability_data):
    """Update player availability for a game
    
    availability_data should be a dictionary:
    {
        "Available": {jersey: boolean, ...},
        "Can Play Catcher": {jersey: boolean, ...}
    }
    """
    session = get_db_session()
    try:
        # Get the game
        game = session.query(Game).filter(
            Game.team_id == team_id,
            Game.game_number == game_number
        ).one()
        
        # Get all players for this team with jersey mapping
        players = session.query(Player).filter(Player.team_id == team_id).all()
        jersey_to_player = {p.jersey_number: p for p in players}
        
        # Process availability data
        for jersey, is_available in availability_data["Available"].items():
            if jersey in jersey_to_player:
                player = jersey_to_player[jersey]
                can_play_catcher = availability_data["Can Play Catcher"].get(jersey, False)
                
                # Check if there's an existing record
                existing = session.query(PlayerAvailability).filter(
                    PlayerAvailability.game_id == game.id,
                    PlayerAvailability.player_id == player.id
                ).first()
                
                if existing:
                    # Update existing
                    existing.available = is_available
                    existing.can_play_catcher = can_play_catcher
                else:
                    # Create new
                    new_availability = PlayerAvailability(
                        game_id=game.id,
                        player_id=player.id,
                        available=is_available,
                        can_play_catcher=can_play_catcher
                    )
                    session.add(new_availability)
        
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

# Analytical Operations
def analyze_batting_fairness(team_id):
    """Analyze the fairness of batting orders across all games"""
    session = get_db_session()
    try:
        # Get the team's players
        players = session.query(Player).filter(Player.team_id == team_id).all()
        
        # Create a mapping from jersey number to player name for easier lookup
        jersey_to_player = {}
        for player in players:
            jersey = player.jersey_number
            player_name = f"{player.first_name} {player.last_name} (#{jersey})"
            jersey_to_player[jersey] = player_name
        
        # Initialize counters
        num_players = len(players)
        player_names = [p.full_name() for p in players]
        batting_counts = pd.DataFrame(0, index=player_names, columns=range(1, num_players + 1))
        
        # Get all batting orders
        batting_orders = session.query(BattingOrder, Game.game_number).join(Game).filter(
            Game.team_id == team_id
        ).all()
        
        # Count the batting positions for each player across all games
        for batting_order, game_number in batting_orders:
            for i, jersey in enumerate(batting_order.order_data, 1):
                if i <= len(batting_counts.columns) and jersey in jersey_to_player:
                    player = jersey_to_player[jersey]
                    batting_counts.loc[player, i] += 1
        
        return batting_counts
    finally:
        session.close()

def analyze_fielding_fairness(team_id):
    """Analyze the fairness of fielding positions across all games"""
    session = get_db_session()
    try:
        # Get the team's players
        players = session.query(Player).filter(Player.team_id == team_id).all()
        
        # Create a mapping from jersey number to player name for easier lookup
        jersey_to_player = {}
        for player in players:
            jersey = player.jersey_number
            player_name = f"{player.first_name} {player.last_name} (#{jersey})"
            jersey_to_player[jersey] = player_name
        
        # Constants for position categories
        INFIELD = ["Pitcher", "1B", "2B", "3B", "SS"]
        OUTFIELD = ["Catcher", "LF", "RF", "LC", "RC"]
        BENCH = ["Bench"]
        
        # Initialize counters for infield, outfield, and bench positions
        player_names = [p.full_name() for p in players]
        position_counts = pd.DataFrame(0, index=player_names, columns=["Infield", "Outfield", "Bench", "Total Innings"])
        
        # Get all games for this team
        games = session.query(Game).filter(Game.team_id == team_id).all()
        
        # Get all fielding rotations
        for game in games:
            # Get innings for this game
            innings = game.innings
            
            # Get fielding rotations for this game
            rotations = session.query(FieldingRotation).filter(
                FieldingRotation.game_id == game.id
            ).all()
            
            # Process each inning's rotation
            for rotation in rotations:
                if rotation.inning <= innings and rotation.positions:
                    # Process each player's position
                    for jersey, position in rotation.positions.items():
                        if jersey in jersey_to_player:
                            player = jersey_to_player[jersey]
                            position_counts.loc[player, "Total Innings"] += 1
                            
                            if position in INFIELD:
                                position_counts.loc[player, "Infield"] += 1
                            elif position in OUTFIELD:
                                position_counts.loc[player, "Outfield"] += 1
                            elif position in BENCH:
                                position_counts.loc[player, "Bench"] += 1
        
        # Calculate percentages
        for col in ["Infield", "Outfield", "Bench"]:
            position_counts[f"{col} %"] = (position_counts[col] / position_counts["Total Innings"] * 100).round(1)
            
        return position_counts
    finally:
        session.close()