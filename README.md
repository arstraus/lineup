# Baseball Lineup Manager 🏆⚾

## Overview

Baseball Lineup Manager is a comprehensive Streamlit application designed to help coaches and team managers efficiently manage team rosters, game schedules, batting orders, and fielding rotations.

### Key Features

- 📋 Team Roster Management
- 📆 Game Schedule Creation
- 🏏 Batting Order Configuration
- 🥎 Fielding Rotation Planning
- 📊 Fairness Analysis
  - Batting Position Distribution
  - Fielding Position Distribution
- 📝 Game Summary and Export
- 💾 Data Import/Export Functionality

## Prerequisites

- Python 3.8+
- pip (Python package manager)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/arstraus/lineup.git
cd lineup
```

2. Create a virtual environment (optional but recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

3. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

```bash
streamlit run lineup.py
```

## How to Use

### Team Roster
- Upload a CSV with player information
- Download a template to help you create your roster

### Game Schedule
- Create and manage game schedules
- Add opponents, dates, and number of innings

### Batting Order & Fielding Rotation
- Configure batting orders for each game
- Set fielding positions for each inning
- Validate and analyze position fairness

### Data Management
- Export your team data as a JSON file
- Import previously saved team data
- Generate example data for testing

## Export and Import
- Export your team data to continue working later
- Share lineup configurations with other coaches

## Contact

Andrew Straus - arstraus@example.com

Project Link: [https://github.com/arstraus/lineup](https://github.com/arstraus/lineup)