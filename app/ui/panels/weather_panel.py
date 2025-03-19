"""
Weather and environmental effects panel for DM Screen

Provides weather generation, tracking, and environmental condition effects
reference for D&D 5e gameplay.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
    QPushButton, QLabel, QTextEdit, QGroupBox,
    QScrollArea, QSlider, QSpinBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

import random
import json
from pathlib import Path
from app.ui.panels.base_panel import BasePanel

class WeatherPanel(BasePanel):
    """
    Weather panel that allows DMs to generate and track weather conditions
    and view associated environmental effects.
    """
    
    # Panel metadata
    PANEL_TYPE = "weather"
    PANEL_NAME = "Weather & Environment"
    PANEL_DESCRIPTION = "Generate and track weather conditions and environmental effects"
    
    def __init__(self, app_state, panel_id=None):
        """Initialize the weather panel"""
        super().__init__(app_state, "Weather & Environment")
        
        # Weather state
        self.current_climate = "Temperate"
        self.current_season = "Summer"
        self.current_temperature = "Mild"
        self.current_wind = "Calm"
        self.current_precipitation = "None"
        
        # Weather data
        self.weather_data = {}
        self.effects_data = {}
        
        # Load weather data first to ensure it's available before UI references it
        self._load_weather_data()
        
        # Setup UI after data is loaded
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the user interface"""
        # Create main layout directly on the widget
        main_layout = QVBoxLayout(self)
        
        # --- Weather Generation Controls ---
        controls_group = QGroupBox("Weather Controls")
        controls_layout = QFormLayout()
        
        # Climate selection
        self.climate_combo = QComboBox()
        self.climate_combo.addItems(["Arctic", "Desert", "Temperate", "Tropical", "Mountain"])
        self.climate_combo.setCurrentText(self.current_climate)
        self.climate_combo.currentTextChanged.connect(self._update_climate)
        controls_layout.addRow("Climate:", self.climate_combo)
        
        # Season selection
        self.season_combo = QComboBox()
        self.season_combo.addItems(["Spring", "Summer", "Fall", "Winter"])
        self.season_combo.setCurrentText(self.current_season)
        self.season_combo.currentTextChanged.connect(self._update_season)
        controls_layout.addRow("Season:", self.season_combo)
        
        # Generate button
        generate_layout = QHBoxLayout()
        self.generate_btn = QPushButton("Generate Weather")
        self.generate_btn.clicked.connect(self._generate_weather)
        generate_layout.addWidget(self.generate_btn)
        
        # Save button
        self.save_btn = QPushButton("Save Weather")
        self.save_btn.clicked.connect(self._save_weather)
        generate_layout.addWidget(self.save_btn)
        
        controls_layout.addRow("", generate_layout)
        controls_group.setLayout(controls_layout)
        main_layout.addWidget(controls_group)
        
        # --- Current Weather Display ---
        weather_group = QGroupBox("Current Weather")
        weather_layout = QFormLayout()
        
        # Temperature display
        self.temperature_label = QLabel(self.current_temperature)
        self.temperature_label.setFont(QFont("Arial", 12))
        weather_layout.addRow("Temperature:", self.temperature_label)
        
        # Wind display
        self.wind_label = QLabel(self.current_wind)
        self.wind_label.setFont(QFont("Arial", 12))
        weather_layout.addRow("Wind:", self.wind_label)
        
        # Precipitation display
        self.precipitation_label = QLabel(self.current_precipitation)
        self.precipitation_label.setFont(QFont("Arial", 12))
        weather_layout.addRow("Precipitation:", self.precipitation_label)
        
        weather_group.setLayout(weather_layout)
        main_layout.addWidget(weather_group)
        
        # --- Environmental Effects ---
        effects_group = QGroupBox("Environmental Effects")
        effects_layout = QVBoxLayout()
        
        self.effects_text = QTextEdit()
        self.effects_text.setReadOnly(True)
        effects_layout.addWidget(self.effects_text)
        
        effects_group.setLayout(effects_layout)
        main_layout.addWidget(effects_group)
        
        # --- Time Progression ---
        time_group = QGroupBox("Weather Progression")
        time_layout = QHBoxLayout()
        
        self.progress_btn = QPushButton("Next Day")
        self.progress_btn.clicked.connect(self._progress_day)
        time_layout.addWidget(self.progress_btn)
        
        self.time_btn = QPushButton("6 Hours Later")
        self.time_btn.clicked.connect(self._progress_hours)
        time_layout.addWidget(self.time_btn)
        
        time_group.setLayout(time_layout)
        main_layout.addWidget(time_group)
        
        # Set the main layout
        main_layout.addStretch()
    
    def _load_weather_data(self):
        """Load weather data from JSON files"""
        try:
            # Get the data directory
            data_dir = Path(__file__).parent.parent.parent / "data" / "weather"
            
            # Check if the directory exists
            if not data_dir.exists():
                data_dir.mkdir(parents=True, exist_ok=True)
                self._create_default_weather_data(data_dir)
            
            # Load weather data
            weather_file = data_dir / "weather_data.json"
            if weather_file.exists():
                with open(weather_file, 'r') as f:
                    self.weather_data = json.load(f)
            else:
                self._create_default_weather_data(data_dir)
            
            # Load effects data
            effects_file = data_dir / "effects_data.json"
            if effects_file.exists():
                with open(effects_file, 'r') as f:
                    self.effects_data = json.load(f)
            else:
                self._create_default_effects_data(data_dir)
            
        except Exception as e:
            print(f"Error loading weather data: {e}")
            # Create default data if loading fails
            self._create_default_weather_data(data_dir)
            self._create_default_effects_data(data_dir)
    
    def _create_default_weather_data(self, data_dir):
        """Create default weather data if none exists"""
        # Basic weather data for different climates and seasons
        self.weather_data = {
            "Arctic": {
                "Winter": {
                    "temperature": ["Freezing", "Frigid", "Glacial", "Cold"],
                    "wind": ["Calm", "Breeze", "Windy", "Gale", "Blizzard"],
                    "precipitation": ["None", "Light Snow", "Heavy Snow", "Blizzard"]
                },
                "Spring": {
                    "temperature": ["Freezing", "Cold", "Chilly", "Cool"],
                    "wind": ["Calm", "Breeze", "Windy", "Gale"],
                    "precipitation": ["None", "Light Snow", "Snow", "Sleet", "Freezing Rain"]
                },
                "Summer": {
                    "temperature": ["Cold", "Cool", "Mild", "Warm"],
                    "wind": ["Calm", "Breeze", "Windy"],
                    "precipitation": ["None", "Drizzle", "Light Rain", "Rain"]
                },
                "Fall": {
                    "temperature": ["Cool", "Cold", "Chilly", "Freezing"],
                    "wind": ["Calm", "Breeze", "Windy", "Gale"],
                    "precipitation": ["None", "Drizzle", "Rain", "Sleet", "Light Snow"]
                }
            },
            "Desert": {
                "Winter": {
                    "temperature": ["Cold", "Cool", "Mild", "Warm"],
                    "wind": ["Calm", "Breeze", "Windy", "Sandstorm"],
                    "precipitation": ["None", "Light Rain", "Rain"]
                },
                "Spring": {
                    "temperature": ["Cool", "Mild", "Warm", "Hot"],
                    "wind": ["Calm", "Breeze", "Windy", "Sandstorm"],
                    "precipitation": ["None", "Light Rain"]
                },
                "Summer": {
                    "temperature": ["Warm", "Hot", "Scorching", "Blistering"],
                    "wind": ["Calm", "Breeze", "Hot Wind", "Sandstorm"],
                    "precipitation": ["None", "None", "None", "Light Rain"]
                },
                "Fall": {
                    "temperature": ["Hot", "Warm", "Mild", "Cool"],
                    "wind": ["Calm", "Breeze", "Windy", "Sandstorm"],
                    "precipitation": ["None", "Light Rain", "Rain"]
                }
            },
            "Temperate": {
                "Winter": {
                    "temperature": ["Freezing", "Cold", "Chilly", "Cool"],
                    "wind": ["Calm", "Breeze", "Windy", "Gale"],
                    "precipitation": ["None", "Drizzle", "Rain", "Sleet", "Snow", "Heavy Snow"]
                },
                "Spring": {
                    "temperature": ["Cool", "Mild", "Warm"],
                    "wind": ["Calm", "Breeze", "Windy"],
                    "precipitation": ["None", "Drizzle", "Light Rain", "Rain", "Thunderstorm"]
                },
                "Summer": {
                    "temperature": ["Mild", "Warm", "Hot"],
                    "wind": ["Calm", "Breeze", "Windy"],
                    "precipitation": ["None", "Drizzle", "Rain", "Thunderstorm"]
                },
                "Fall": {
                    "temperature": ["Warm", "Mild", "Cool", "Cold"],
                    "wind": ["Calm", "Breeze", "Windy", "Gale"],
                    "precipitation": ["None", "Drizzle", "Rain", "Heavy Rain"]
                }
            },
            "Tropical": {
                "Winter": {
                    "temperature": ["Warm", "Hot"],
                    "wind": ["Calm", "Breeze", "Windy", "Tropical Storm"],
                    "precipitation": ["None", "Drizzle", "Rain", "Heavy Rain", "Thunderstorm"]
                },
                "Spring": {
                    "temperature": ["Warm", "Hot", "Humid"],
                    "wind": ["Calm", "Breeze", "Windy", "Tropical Storm"],
                    "precipitation": ["None", "Drizzle", "Rain", "Heavy Rain", "Monsoon"]
                },
                "Summer": {
                    "temperature": ["Hot", "Humid", "Scorching"],
                    "wind": ["Calm", "Breeze", "Windy", "Hurricane"],
                    "precipitation": ["None", "Rain", "Heavy Rain", "Monsoon", "Hurricane"]
                },
                "Fall": {
                    "temperature": ["Hot", "Warm", "Humid"],
                    "wind": ["Calm", "Breeze", "Windy", "Tropical Storm"],
                    "precipitation": ["None", "Drizzle", "Rain", "Heavy Rain", "Thunderstorm"]
                }
            },
            "Mountain": {
                "Winter": {
                    "temperature": ["Glacial", "Freezing", "Frigid", "Cold"],
                    "wind": ["Calm", "Breeze", "Windy", "Gale", "Blizzard"],
                    "precipitation": ["None", "Snow", "Heavy Snow", "Blizzard"]
                },
                "Spring": {
                    "temperature": ["Freezing", "Cold", "Cool", "Mild"],
                    "wind": ["Calm", "Breeze", "Windy", "Gale"],
                    "precipitation": ["None", "Rain", "Snow", "Sleet"]
                },
                "Summer": {
                    "temperature": ["Cool", "Mild", "Warm"],
                    "wind": ["Calm", "Breeze", "Windy"],
                    "precipitation": ["None", "Rain", "Thunderstorm", "Hail"]
                },
                "Fall": {
                    "temperature": ["Mild", "Cool", "Cold", "Freezing"],
                    "wind": ["Calm", "Breeze", "Windy", "Gale"],
                    "precipitation": ["None", "Rain", "Sleet", "Snow"]
                }
            }
        }
        
        # Save default data to file
        with open(data_dir / "weather_data.json", 'w') as f:
            json.dump(self.weather_data, f, indent=4)
    
    def _create_default_effects_data(self, data_dir):
        """Create default environmental effects data"""
        self.effects_data = {
            "Temperature": {
                "Glacial": "Unprotected creatures must make a DC 10 Constitution saving throw every hour or gain one level of exhaustion. Movement through snow is halved.",
                "Freezing": "Unprotected creatures must make a DC 10 Constitution saving throw every hour or gain one level of exhaustion.",
                "Frigid": "Creatures have disadvantage on Constitution saves to avoid exhaustion from cold.",
                "Cold": "No significant mechanical effects, but uncomfortable without proper clothing.",
                "Cool": "No mechanical effects.",
                "Mild": "Comfortable temperature with no mechanical effects.",
                "Warm": "No mechanical effects, but uncomfortable for heavily dressed characters.",
                "Hot": "Creatures have disadvantage on Constitution saves to avoid exhaustion from heat.",
                "Scorching": "Unprotected creatures must make a DC 10 Constitution saving throw every hour or gain one level of exhaustion.",
                "Blistering": "Unprotected creatures must make a DC 10 Constitution saving throw every hour or gain one level of exhaustion. Water consumption is doubled.",
                "Humid": "Constitution checks to avoid exhaustion are made with disadvantage in hot, humid conditions."
            },
            "Wind": {
                "Calm": "No wind effects. Smoke rises vertically.",
                "Breeze": "No mechanical effects. Light objects might be moved slightly.",
                "Windy": "Disadvantage on ranged weapon attacks and Perception checks that rely on hearing.",
                "Gale": "Disadvantage on ranged weapon attacks. Small creatures must succeed on a DC 10 Strength saving throw or be knocked prone when moving against the wind.",
                "Hot Wind": "Creatures have disadvantage on Constitution saves against exhaustion from heat.",
                "Blizzard": "Heavily obscured area (effectively blinded beyond 5 feet). Disadvantage on Perception checks. Movement is halved.",
                "Sandstorm": "Heavily obscured area (effectively blinded beyond 5 feet). Disadvantage on Perception checks. Creatures must cover mouth and nose or suffer disadvantage on Constitution saves.",
                "Tropical Storm": "Heavily obscured area outdoors (effectively blinded beyond 10 feet). Disadvantage on Perception checks and ranged attacks.",
                "Hurricane": "Heavily obscured area (effectively blinded beyond 5 feet). Creatures must succeed on a DC 15 Strength saving throw or be knocked prone and pushed 5 feet at the start of each turn."
            },
            "Precipitation": {
                "None": "No precipitation effects.",
                "Drizzle": "No mechanical effects.",
                "Light Rain": "No significant mechanical effects.",
                "Rain": "Disadvantage on Perception checks that rely on sight or hearing. Fire-based effects have disadvantage or reduced effectiveness.",
                "Heavy Rain": "Lightly obscured area. Disadvantage on Perception checks that rely on sight or hearing. Fire-based spells and effects have disadvantage or reduced effectiveness.",
                "Thunderstorm": "As heavy rain, plus occasional thunder and lightning. Characters in metal armor have disadvantage on Dexterity saving throws against lightning damage.",
                "Monsoon": "Heavily obscured area (effectively blinded beyond 20 feet). Disadvantage on all Perception checks. Movement is halved. Fire-based effects automatically fail.",
                "Sleet": "Lightly obscured area. Surfaces become slippery (difficult terrain).",
                "Freezing Rain": "Surfaces become extremely slippery (difficult terrain). Dexterity (Acrobatics) checks to avoid falling are made with disadvantage.",
                "Light Snow": "No significant mechanical effects.",
                "Snow": "Lightly obscured area. Movement costs are doubled unless using snowshoes or similar equipment.",
                "Heavy Snow": "Lightly obscured area. Movement costs are doubled unless using snowshoes or similar equipment. Tracks are covered in 1d4 hours.",
                "Blizzard": "Heavily obscured area (effectively blinded beyond 5 feet). Movement costs are tripled.",
                "Hail": "Creatures in the open take 1d4 bludgeoning damage per minute of exposure."
            }
        }
        
        # Save default data to file
        with open(data_dir / "effects_data.json", 'w') as f:
            json.dump(self.effects_data, f, indent=4)
    
    def _update_climate(self, climate):
        """Update the current climate"""
        self.current_climate = climate
    
    def _update_season(self, season):
        """Update the current season"""
        self.current_season = season
    
    def _generate_weather(self):
        """Generate random weather based on climate and season"""
        try:
            climate_data = self.weather_data.get(self.current_climate, {})
            season_data = climate_data.get(self.current_season, {})
            
            if not season_data:
                print(f"No weather data for {self.current_climate} in {self.current_season}")
                return
            
            # Generate temperature
            temp_options = season_data.get("temperature", ["Mild"])
            self.current_temperature = random.choice(temp_options)
            self.temperature_label.setText(self.current_temperature)
            
            # Generate wind
            wind_options = season_data.get("wind", ["Calm"])
            self.current_wind = random.choice(wind_options)
            self.wind_label.setText(self.current_wind)
            
            # Generate precipitation
            precip_options = season_data.get("precipitation", ["None"])
            self.current_precipitation = random.choice(precip_options)
            self.precipitation_label.setText(self.current_precipitation)
            
            # Update effects text
            self._update_effects()
            
        except Exception as e:
            print(f"Error generating weather: {e}")
    
    def _update_effects(self):
        """Update the environmental effects text based on current weather"""
        effects_text = ""
        
        # Add temperature effects
        temp_effect = self.effects_data.get("Temperature", {}).get(self.current_temperature, "No effects.")
        effects_text += f"<h3>Temperature Effects ({self.current_temperature})</h3>\n{temp_effect}\n\n"
        
        # Add wind effects
        wind_effect = self.effects_data.get("Wind", {}).get(self.current_wind, "No effects.")
        effects_text += f"<h3>Wind Effects ({self.current_wind})</h3>\n{wind_effect}\n\n"
        
        # Add precipitation effects
        precip_effect = self.effects_data.get("Precipitation", {}).get(self.current_precipitation, "No effects.")
        effects_text += f"<h3>Precipitation Effects ({self.current_precipitation})</h3>\n{precip_effect}\n\n"
        
        # Set the effects text
        self.effects_text.setHtml(effects_text)
    
    def _save_weather(self):
        """Save the current weather conditions"""
        # In a future implementation, this could save to a campaign log
        # For now, just display a message
        print(f"Weather saved: {self.current_climate}, {self.current_season}, {self.current_temperature}, {self.current_wind}, {self.current_precipitation}")
    
    def _progress_day(self):
        """Progress weather to the next day"""
        # 75% chance of weather changing
        if random.random() < 0.75:
            self._generate_weather()
    
    def _progress_hours(self):
        """Progress weather by 6 hours"""
        # 30% chance of weather changing in 6 hours
        if random.random() < 0.3:
            self._generate_weather()
    
    def save_state(self):
        """Save the current state of the panel"""
        return {
            "climate": self.current_climate,
            "season": self.current_season,
            "temperature": self.current_temperature,
            "wind": self.current_wind,
            "precipitation": self.current_precipitation
        }
    
    def restore_state(self, state):
        """Restore the panel state from saved data"""
        if not state:
            return
            
        # Restore climate and season
        self.current_climate = state.get("climate", "Temperate")
        self.current_season = state.get("season", "Summer")
        
        # Update combos
        self.climate_combo.setCurrentText(self.current_climate)
        self.season_combo.setCurrentText(self.current_season)
        
        # Restore weather conditions
        self.current_temperature = state.get("temperature", "Mild")
        self.current_wind = state.get("wind", "Calm")
        self.current_precipitation = state.get("precipitation", "None")
        
        # Update labels
        self.temperature_label.setText(self.current_temperature)
        self.wind_label.setText(self.current_wind)
        self.precipitation_label.setText(self.current_precipitation)
        
        # Update effects
        self._update_effects()