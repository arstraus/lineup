import os
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, Time, ForeignKey, JSON, Float, UniqueConstraint
import sqlalchemy as sa  # Add this import for the "sa" reference
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import JSONB
import streamlit as st
from dotenv import load_dotenv
import hashlib
import secrets
import uuid

# Try to load environment variables from .env for local development
load_dotenv()

# Get database connection string with better error handling
DATABASE_URL = None

# First try Streamlit secrets (for cloud deployment)
try:
    DATABASE_URL = st.secrets["DATABASE_URL"]
except Exception:
    # Fall back to environment variable (for local development)
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    if not DATABASE_URL:
        print("WARNING: DATABASE_URL not found in Streamlit secrets or environment variables.")
        print("Please set DATABASE_URL in your .env file or Streamlit secrets.")
        # Instead of raising an error immediately, we'll continue and let the app show a proper error message

# Create SQLAlchemy engine
if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
else:
    # Create a fallback SQLite in-memory engine for development
    # This will allow the app to start but most database operations will fail gracefully
    print("WARNING: Using in-memory SQLite database as fallback. Most operations will fail.")
    engine = create_engine('sqlite:///:memory:')

# Create base class for declarative models
Base = declarative_base()

# Define database models
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    salt = Column(String, nullable=False)
    created_at = Column(sa.DateTime, server_default=sa.func.now())
    
    # Relationships
    teams = relationship("Team", back_populates="user", cascade="all, delete-orphan")
    
    def set_password(self, password):
        """Hash password with salt"""
        self.salt = secrets.token_hex(16)
        self.password_hash = hashlib.sha256((password + self.salt).encode()).hexdigest()
    
    def check_password(self, password):
        """Verify password"""
        return self.password_hash == hashlib.sha256((password + self.salt).encode()).hexdigest()


class Team(Base):
    __tablename__ = 'teams'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    league = Column(String)
    head_coach = Column(String)
    assistant_coach1 = Column(String)
    assistant_coach2 = Column(String)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="teams")
    players = relationship("Player", back_populates="team", cascade="all, delete-orphan")
    games = relationship("Game", back_populates="team", cascade="all, delete-orphan")

class Player(Base):
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey('teams.id', ondelete='CASCADE'))
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    jersey_number = Column(String, nullable=False)
    
    # Relationships
    team = relationship("Team", back_populates="players")
    player_availability = relationship("PlayerAvailability", back_populates="player", cascade="all, delete-orphan")
    
    def full_name(self):
        return f"{self.first_name} {self.last_name} (#{self.jersey_number})"

class Game(Base):
    __tablename__ = 'games'
    
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey('teams.id', ondelete='CASCADE'))
    game_number = Column(Integer, nullable=False)
    date = Column(Date)
    time = Column(Time)
    opponent = Column(String)
    innings = Column(Integer, default=6)
    
    # Relationships
    team = relationship("Team", back_populates="games")
    batting_order = relationship("BattingOrder", back_populates="game", uselist=False, cascade="all, delete-orphan")
    fielding_rotations = relationship("FieldingRotation", back_populates="game", cascade="all, delete-orphan")
    player_availability = relationship("PlayerAvailability", back_populates="game", cascade="all, delete-orphan")

class BattingOrder(Base):
    __tablename__ = 'batting_orders'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), unique=True)
    order_data = Column(JSONB)  # Store the list of jersey numbers as JSON
    
    # Relationships
    game = relationship("Game", back_populates="batting_order")

class FieldingRotation(Base):
    __tablename__ = 'fielding_rotations'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'))
    inning = Column(Integer, nullable=False)
    positions = Column(JSONB)  # Store the positions dictionary as JSON
    
    # Relationships
    game = relationship("Game", back_populates="fielding_rotations")
    
    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint('game_id', 'inning', name='uq_fielding_rotation_game_inning'),
    )

class PlayerAvailability(Base):
    __tablename__ = 'player_availability'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'))
    player_id = Column(Integer, ForeignKey('players.id', ondelete='CASCADE'))
    available = Column(Boolean, default=True)
    can_play_catcher = Column(Boolean, default=False)
    
    # Relationships
    game = relationship("Game", back_populates="player_availability")
    player = relationship("Player", back_populates="player_availability")
    
    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint('game_id', 'player_id', name='uq_player_availability_game_player'),
    )


# Create all tables in the database
def create_tables():
    Base.metadata.create_all(engine)

# Create a session to interact with the database
def get_db_session():
    Session = sessionmaker(bind=engine)
    return Session()

# Helper functions to convert between dataframes and database models
def roster_df_to_db(team_id, roster_df):
    """Convert roster dataframe to Player objects"""
    players = []
    for _, row in roster_df.iterrows():
        player = Player(
            team_id=team_id,
            first_name=row['First Name'],
            last_name=row['Last Name'],
            jersey_number=str(row['Jersey Number'])
        )
        players.append(player)
    return players

def roster_db_to_df(players):
    """Convert Player objects to roster dataframe"""
    data = {
        "First Name": [],
        "Last Name": [],
        "Jersey Number": []
    }
    
    for player in players:
        data["First Name"].append(player.first_name)
        data["Last Name"].append(player.last_name)
        data["Jersey Number"].append(player.jersey_number)
    
    return pd.DataFrame(data)

def schedule_df_to_db(team_id, schedule_df):
    """Convert schedule dataframe to Game objects"""
    games = []
    for _, row in schedule_df.iterrows():
        game = Game(
            team_id=team_id,
            game_number=row['Game #'],
            date=row['Date'] if pd.notna(row['Date']) else None,
            time=row['Time'] if 'Time' in row and pd.notna(row['Time']) else None,
            opponent=row['Opponent'],
            innings=row['Innings']
        )
        games.append(game)
    return games

def schedule_db_to_df(games):
    """Convert Game objects to schedule dataframe"""
    data = {
        "Game #": [],
        "Date": [],
        "Time": [],
        "Opponent": [],
        "Innings": []
    }
    
    for game in games:
        data["Game #"].append(game.game_number)
        data["Date"].append(game.date)
        data["Time"].append(game.time)
        data["Opponent"].append(game.opponent)
        data["Innings"].append(game.innings)
    
    df = pd.DataFrame(data)
    # Ensure Date column is datetime type
    df["Date"] = pd.to_datetime(df["Date"])
    return df

def delete_team(team_id):
    """Delete a team and all its associated data from the database"""
    session = get_db_session()
    try:
        # Find the team
        team = session.query(Team).filter(Team.id == team_id).one()
        
        # Store name for confirmation message
        team_name = team.name
        
        # The cascading delete set up in the database models should handle
        # deleting all the related data (players, games, etc.)
        session.delete(team)
        session.commit()
        
        return True, team_name
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()


# User authentication functions
def create_user(email, password):
    """Create a new user"""
    session = get_db_session()
    try:
        # Check if user already exists
        existing_user = session.query(User).filter(User.email == email).first()
        if existing_user:
            return None, "Email already registered"
            
        user = User(email=email)
        user.set_password(password)
        session.add(user)
        session.commit()
        return user.id, "User created successfully"
    except Exception as e:
        session.rollback()
        return None, str(e)
    finally:
        session.close()

def verify_user(email, password):
    """Verify user credentials"""
    session = get_db_session()
    try:
        user = session.query(User).filter(User.email == email).first()
        if user and user.check_password(password):
            return user.id
        return None
    finally:
        session.close()

def get_teams_for_user(user_id):
    """Get all teams owned by a specific user"""
    session = get_db_session()
    try:
        teams = session.query(Team).filter(
            (Team.user_id == user_id) | (Team.user_id == None)
        ).all()
        return [(team.id, team.name) for team in teams]
    finally:
        session.close()

def get_teams_with_details_for_user(user_id):
    """Get all teams with details owned by a specific user"""
    session = get_db_session()
    try:
        teams = session.query(Team).filter(
            (Team.user_id == user_id) | (Team.user_id == None)
        ).all()
        team_details = []
        for team in teams:
            team_details.append({
                "id": team.id, 
                "name": team.name,
                "league": team.league,
                "head_coach": team.head_coach
            })
        return team_details
    finally:
        session.close()
        
# Modified function to create team with user_id
def create_team_with_user(team_info, user_id):
    """Create a new team with user ownership"""
    session = get_db_session()
    try:
        team = Team(
            name=team_info["team_name"],
            league=team_info.get("league", ""),
            head_coach=team_info.get("head_coach", ""),
            assistant_coach1=team_info.get("assistant_coach1", ""),
            assistant_coach2=team_info.get("assistant_coach2", ""),
            user_id=user_id
        )
        session.add(team)
        session.commit()
        return team.id
    except Exception as e:
        session.rollback()
        print(f"Error creating team: {e}")
        return None
    finally:
        session.close()

# Initialize the database (run this when setting up the app)
if __name__ == "__main__":
    create_tables()
    print("Database tables created successfully")