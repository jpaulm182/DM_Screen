"""
Time and Travel Pace Tracker panel for DM Screen

Provides tools for tracking game time and calculating travel times and
distances based on various travel paces in D&D 5e.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
    QPushButton, QLabel, QTextEdit, QGroupBox,
    QScrollArea, QSlider, QSpinBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QTabWidget,
    QTimeEdit, QDateEdit, QCheckBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal, QTime, QDate
from PySide6.QtGui import QFont

import json
from pathlib import Path
from app.ui.panels.base_panel import BasePanel

class TimeTrackerPanel(BasePanel):
    """
    Time tracker panel that allows DMs to track game time and
    calculate travel distances and times for D&D 5e gameplay.
    """
    
    # Panel metadata
    PANEL_TYPE = "time_tracker"
    PANEL_NAME = "Time & Travel"
    PANEL_DESCRIPTION = "Track game time and calculate travel distances and paces"
    
    def __init__(self, app_state, panel_id=None):
        """Initialize the time tracker panel"""
        super().__init__(app_state, "Time & Travel")
        
        # Time tracking state
        self.game_hour = 12
        self.game_minute = 0
        self.game_day = 1
        self.game_month = 1
        self.game_year = 1490  # Default Forgotten Realms year
        
        # Travel state
        self.travel_pace = "Normal"  # Fast, Normal, or Slow
        self.travel_terrain = "Road/Trail"
        self.travel_vehicle = "On Foot"
        self.travel_distance = 0  # Miles
        self.travel_hours = 8  # Hours per day
        
        # Calendar data (default to Forgotten Realms)
        self.calendar_type = "Forgotten Realms"
        self.month_names = [
            "Hammer", "Alturiak", "Ches", "Tarsakh", "Mirtul", "Kythorn",
            "Flamerule", "Eleasis", "Eleint", "Marpenoth", "Uktar", "Nightal"
        ]
        self.days_per_month = 30  # Standard in most D&D settings
        
        # Travel pace data (miles per hour)
        self.travel_paces = {
            "Fast": 4,       # 30 miles per day
            "Normal": 3,     # 24 miles per day
            "Slow": 2        # 18 miles per day
        }
        
        # Terrain modifiers (multipliers)
        self.terrain_modifiers = {
            "Road/Trail": 1.0,
            "Plains/Grassland": 0.75,
            "Forest/Woodlands": 0.5,
            "Hills": 0.5,
            "Mountains": 0.25,
            "Swamp/Marsh": 0.25,
            "Desert": 0.5,
            "Arctic": 0.25,
            "Jungle": 0.25
        }
        
        # Vehicle/Mount modifiers (multipliers)
        self.vehicle_modifiers = {
            "On Foot": 1.0,
            "Horse (riding)": 1.5,
            "Horse (war)": 1.2,
            "Pony": 1.0,
            "Camel": 1.1,
            "Wagon/Cart": 0.8,
            "Carriage": 1.0,
            "Boat (rowboat)": 1.5,
            "Ship (sailing)": 2.0,
            "Airship": 8.0,
            "Flying Mount": 6.0
        }
        
        # Declare UI elements as class attributes before setup_ui
        # Time tracking controls
        self.hour_spinner = None
        self.minute_spinner = None
        self.day_spinner = None
        self.month_combo = None
        self.year_spinner = None
        self.day_night_label = None
        self.current_time_label = None
        self.time_notes = None
        self.weather_check = None
        self.weather_notes = None
        
        # Travel controls
        self.pace_combo = None
        self.terrain_combo = None
        self.vehicle_combo = None
        self.hours_spinner = None
        self.distance_spinner = None
        self.travel_miles_label = None
        self.travel_days_label = None
        self.travel_hours_label = None
        
        # Now setup the UI
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the user interface"""
        # Create main layout directly on the widget
        main_layout = QVBoxLayout(self)
        
        # Create tab widget for Time and Travel sections
        tab_widget = QTabWidget()
        
        # --- Time Tracking Tab ---
        time_widget = QWidget()
        time_layout = QVBoxLayout()
        
        # Current Game Time Group
        time_group = QGroupBox("Current Game Time")
        time_form = QFormLayout()
        
        # Time Controls
        time_control_layout = QHBoxLayout()
        
        # Hour Spinner
        self.hour_spinner = QSpinBox()
        self.hour_spinner.setRange(0, 23)
        self.hour_spinner.setValue(self.game_hour)
        self.hour_spinner.valueChanged.connect(self._update_hour)
        
        # Minute Spinner
        self.minute_spinner = QSpinBox()
        self.minute_spinner.setRange(0, 59)
        self.minute_spinner.setValue(self.game_minute)
        self.minute_spinner.setSingleStep(5)
        self.minute_spinner.valueChanged.connect(self._update_minute)
        
        # Time labels
        time_control_layout.addWidget(QLabel("Hour:"))
        time_control_layout.addWidget(self.hour_spinner)
        time_control_layout.addWidget(QLabel("Minute:"))
        time_control_layout.addWidget(self.minute_spinner)
        time_form.addRow("Time:", time_control_layout)
        
        # Date Controls
        date_control_layout = QHBoxLayout()
        
        # Day Spinner
        self.day_spinner = QSpinBox()
        self.day_spinner.setRange(1, self.days_per_month)
        self.day_spinner.setValue(self.game_day)
        self.day_spinner.valueChanged.connect(self._update_day)
        
        # Month Combo
        self.month_combo = QComboBox()
        self.month_combo.addItems(self.month_names)
        self.month_combo.setCurrentIndex(self.game_month - 1)
        self.month_combo.currentIndexChanged.connect(self._update_month)
        
        # Year Spinner
        self.year_spinner = QSpinBox()
        self.year_spinner.setRange(1, 9999)
        self.year_spinner.setValue(self.game_year)
        self.year_spinner.valueChanged.connect(self._update_year)
        
        # Date labels
        date_control_layout.addWidget(QLabel("Day:"))
        date_control_layout.addWidget(self.day_spinner)
        date_control_layout.addWidget(QLabel("Month:"))
        date_control_layout.addWidget(self.month_combo)
        date_control_layout.addWidget(QLabel("Year:"))
        date_control_layout.addWidget(self.year_spinner)
        time_form.addRow("Date:", date_control_layout)
        
        # Time Advancement Buttons
        time_adv_layout = QHBoxLayout()
        
        self.advance_minute_btn = QPushButton("1 Minute")
        self.advance_minute_btn.clicked.connect(lambda: self._advance_time(minutes=1))
        time_adv_layout.addWidget(self.advance_minute_btn)
        
        self.advance_ten_minute_btn = QPushButton("10 Minutes")
        self.advance_ten_minute_btn.clicked.connect(lambda: self._advance_time(minutes=10))
        time_adv_layout.addWidget(self.advance_ten_minute_btn)
        
        self.advance_hour_btn = QPushButton("1 Hour")
        self.advance_hour_btn.clicked.connect(lambda: self._advance_time(hours=1))
        time_adv_layout.addWidget(self.advance_hour_btn)
        
        self.advance_day_btn = QPushButton("1 Day")
        self.advance_day_btn.clicked.connect(lambda: self._advance_time(days=1))
        time_adv_layout.addWidget(self.advance_day_btn)
        
        time_form.addRow("Advance:", time_adv_layout)
        
        # Rest Buttons
        rest_layout = QHBoxLayout()
        
        self.short_rest_btn = QPushButton("Short Rest (1 hour)")
        self.short_rest_btn.clicked.connect(lambda: self._advance_time(hours=1, is_rest=True))
        rest_layout.addWidget(self.short_rest_btn)
        
        self.long_rest_btn = QPushButton("Long Rest (8 hours)")
        self.long_rest_btn.clicked.connect(lambda: self._advance_time(hours=8, is_rest=True))
        rest_layout.addWidget(self.long_rest_btn)
        
        time_form.addRow("Rest:", rest_layout)
        
        # Day/Night Cycle Display
        self.day_night_label = QLabel("Day (Morning)")
        self.day_night_label.setAlignment(Qt.AlignCenter)
        self.day_night_label.setFont(QFont("Arial", 14, QFont.Bold))
        time_form.addRow("Time of Day:", self.day_night_label)
        
        # Current time display
        self.current_time_label = QLabel("12:00 PM, 1 Hammer, 1490 DR")
        self.current_time_label.setAlignment(Qt.AlignCenter)
        self.current_time_label.setFont(QFont("Arial", 14, QFont.Bold))
        time_form.addRow("", self.current_time_label)
        
        # Clock Notes
        self.time_notes = QTextEdit()
        self.time_notes.setPlaceholderText("Enter time-related notes here...")
        time_form.addRow("Notes:", self.time_notes)
        
        time_group.setLayout(time_form)
        time_layout.addWidget(time_group)
        
        # Weather indication
        weather_layout = QHBoxLayout()
        
        self.weather_check = QCheckBox("Update Weather")
        self.weather_check.setChecked(True)
        weather_layout.addWidget(self.weather_check)
        
        self.weather_notes = QLabel("Weather will update when advancing days or long rests")
        weather_layout.addWidget(self.weather_notes)
        
        time_layout.addLayout(weather_layout)
        
        time_widget.setLayout(time_layout)
        tab_widget.addTab(time_widget, "Time Tracker")
        
        # --- Travel Tracker Tab ---
        travel_widget = QWidget()
        travel_layout = QVBoxLayout()
        
        # Travel Calculator Group
        travel_group = QGroupBox("Travel Calculator")
        travel_form = QFormLayout()
        
        # Travel Pace Selection
        self.pace_combo = QComboBox()
        self.pace_combo.addItems(list(self.travel_paces.keys()))
        self.pace_combo.setCurrentText(self.travel_pace)
        self.pace_combo.currentTextChanged.connect(self._update_pace)
        travel_form.addRow("Travel Pace:", self.pace_combo)
        
        # Terrain Selection
        self.terrain_combo = QComboBox()
        self.terrain_combo.addItems(list(self.terrain_modifiers.keys()))
        self.terrain_combo.setCurrentText(self.travel_terrain)
        self.terrain_combo.currentTextChanged.connect(self._update_terrain)
        travel_form.addRow("Terrain Type:", self.terrain_combo)
        
        # Vehicle/Mount Selection
        self.vehicle_combo = QComboBox()
        self.vehicle_combo.addItems(list(self.vehicle_modifiers.keys()))
        self.vehicle_combo.setCurrentText(self.travel_vehicle)
        self.vehicle_combo.currentTextChanged.connect(self._update_vehicle)
        travel_form.addRow("Transport:", self.vehicle_combo)
        
        # Travel Hours Per Day
        self.hours_spinner = QSpinBox()
        self.hours_spinner.setRange(1, 24)
        self.hours_spinner.setValue(self.travel_hours)
        self.hours_spinner.valueChanged.connect(self._update_travel_hours)
        travel_form.addRow("Hours per day:", self.hours_spinner)
        
        # Travel Distance Input
        distance_layout = QHBoxLayout()
        
        self.distance_spinner = QSpinBox()
        self.distance_spinner.setRange(1, 9999)
        self.distance_spinner.setValue(self.travel_distance)
        self.distance_spinner.valueChanged.connect(self._update_distance)
        distance_layout.addWidget(self.distance_spinner)
        distance_layout.addWidget(QLabel("miles"))
        
        self.calculate_btn = QPushButton("Calculate Travel Time")
        self.calculate_btn.clicked.connect(self._calculate_travel)
        distance_layout.addWidget(self.calculate_btn)
        
        travel_form.addRow("Distance:", distance_layout)
        
        # Results
        self.travel_result = QTextEdit()
        self.travel_result.setReadOnly(True)
        self.travel_result.setMaximumHeight(100)
        travel_form.addRow("Travel Time:", self.travel_result)
        
        # Apply Travel Button
        self.apply_travel_btn = QPushButton("Apply Travel Time to Clock")
        self.apply_travel_btn.clicked.connect(self._apply_travel)
        travel_form.addRow("", self.apply_travel_btn)
        
        # Common Distances Reference
        distances_group = QGroupBox("Common Distances")
        distances_layout = QVBoxLayout()
        
        self.distances_table = QTableWidget(8, 2)
        self.distances_table.setHorizontalHeaderLabels(["Location", "Distance (miles)"])
        self.distances_table.horizontalHeader().setStretchLastSection(True)
        
        # Set some common distances as examples
        distances = [
            ("Village to Village", "5-10"),
            ("Village to Town", "15-30"),
            ("Town to City", "30-100"),
            ("City to Capital", "100-300"),
            ("Width of Kingdom", "300-1000"),
            ("Continent Width", "3000-5000"),
            ("Forest Width", "50-300"),
            ("Mountain Range Width", "100-500")
        ]
        
        for i, (location, distance) in enumerate(distances):
            self.distances_table.setItem(i, 0, QTableWidgetItem(location))
            self.distances_table.setItem(i, 1, QTableWidgetItem(distance))
        
        distances_layout.addWidget(self.distances_table)
        distances_group.setLayout(distances_layout)
        
        travel_group.setLayout(travel_form)
        travel_layout.addWidget(travel_group)
        travel_layout.addWidget(distances_group)
        
        travel_widget.setLayout(travel_layout)
        tab_widget.addTab(travel_widget, "Travel Pace")
        
        # Add the tab widget to the main layout
        main_layout.addWidget(tab_widget)
        
        # Set up the main layout
        self.setLayout(main_layout)
        
        # Update the time display
        self._update_time_display()
        
    def _update_hour(self, value):
        """Update the hour value"""
        self.game_hour = value
        self._update_time_display()
        
    def _update_minute(self, value):
        """Update the minute value"""
        self.game_minute = value
        self._update_time_display()
        
    def _update_day(self, value):
        """Update the day value"""
        self.game_day = value
        self._update_time_display()
        
    def _update_month(self, index):
        """Update the month value"""
        self.game_month = index + 1
        self._update_time_display()
        
    def _update_year(self, value):
        """Update the year value"""
        self.game_year = value
        self._update_time_display()
        
    def _advance_time(self, minutes=0, hours=0, days=0, is_rest=False):
        """Advance the game time by the specified amount"""
        total_minutes = minutes + (hours * 60) + (days * 24 * 60)
        
        # Add minutes
        self.game_minute += total_minutes
        
        # Convert excess minutes to hours
        hour_overflow = self.game_minute // 60
        self.game_minute %= 60
        
        # Add hours
        self.game_hour += hour_overflow
        
        # Convert excess hours to days
        day_overflow = self.game_hour // 24
        self.game_hour %= 24
        
        # Add days
        self.game_day += day_overflow
        
        # Handle month/year overflow
        while self.game_day > self.days_per_month:
            self.game_day -= self.days_per_month
            self.game_month += 1
            
            if self.game_month > 12:
                self.game_month = 1
                self.game_year += 1
        
        # Update UI elements
        self.hour_spinner.setValue(self.game_hour)
        self.minute_spinner.setValue(self.game_minute)
        self.day_spinner.setValue(self.game_day)
        self.month_combo.setCurrentIndex(self.game_month - 1)
        self.year_spinner.setValue(self.game_year)
        
        # Update the time display
        self._update_time_display()
        
        # Update weather if requested and advancing a day or long rest
        if self.weather_check.isChecked() and (days > 0 or (is_rest and hours >= 8)):
            print("Weather update would be triggered here")
            # In a future integration, this would call the weather panel to update
            # self.update_weather.emit(days)
        
    def _update_time_display(self):
        """Update the time display label"""
        # Format time with AM/PM
        hour_12 = self.game_hour % 12
        if hour_12 == 0:
            hour_12 = 12
        am_pm = "AM" if self.game_hour < 12 else "PM"
        
        # Create time string
        time_str = f"{hour_12}:{self.game_minute:02d} {am_pm}, {self.game_day} {self.month_names[self.game_month-1]}, {self.game_year} DR"
        self.current_time_label.setText(time_str)
        
        # Update day/night cycle indication
        if 5 <= self.game_hour < 8:
            day_night = "Dawn"
        elif 8 <= self.game_hour < 12:
            day_night = "Day (Morning)"
        elif 12 <= self.game_hour < 17:
            day_night = "Day (Afternoon)"
        elif 17 <= self.game_hour < 20:
            day_night = "Dusk"
        else:
            day_night = "Night"
            
        self.day_night_label.setText(day_night)
        
    def _update_pace(self, pace):
        """Update the travel pace"""
        self.travel_pace = pace
        
    def _update_terrain(self, terrain):
        """Update the travel terrain"""
        self.travel_terrain = terrain
        
    def _update_vehicle(self, vehicle):
        """Update the travel vehicle/mount"""
        self.travel_vehicle = vehicle
        
    def _update_travel_hours(self, hours):
        """Update the travel hours per day"""
        self.travel_hours = hours
        
    def _update_distance(self, distance):
        """Update the travel distance"""
        self.travel_distance = distance
        
    def _calculate_travel(self):
        """Calculate travel time based on current settings"""
        try:
            # Get the base pace in miles per hour
            base_pace = self.travel_paces.get(self.travel_pace, 3)
            
            # Apply terrain modifier
            terrain_mod = self.terrain_modifiers.get(self.travel_terrain, 1.0)
            
            # Apply vehicle/mount modifier
            vehicle_mod = self.vehicle_modifiers.get(self.travel_vehicle, 1.0)
            
            # Calculate effective pace
            effective_pace = base_pace * terrain_mod * vehicle_mod
            
            # Calculate time needed in hours
            if effective_pace > 0:
                total_hours = self.travel_distance / effective_pace
                
                # Calculate days needed based on hours per day of travel
                days = int(total_hours // self.travel_hours)
                remaining_hours = int(total_hours % self.travel_hours)
                
                # Format result
                result = f"Distance: {self.travel_distance} miles\n"
                result += f"Effective pace: {effective_pace:.1f} miles per hour\n"
                
                if days > 0:
                    result += f"Travel time: {days} day{'s' if days != 1 else ''}"
                    if remaining_hours > 0:
                        result += f" and {remaining_hours} hour{'s' if remaining_hours != 1 else ''}"
                else:
                    result += f"Travel time: {remaining_hours} hour{'s' if remaining_hours != 1 else ''}"
                
                self.travel_result.setText(result)
                
                # Store travel time for applying to clock
                self.calculated_travel_days = days
                self.calculated_travel_hours = remaining_hours
            else:
                self.travel_result.setText("Error: Effective pace is zero.")
        except Exception as e:
            self.travel_result.setText(f"Calculation error: {str(e)}")
            
    def _apply_travel(self):
        """Apply the calculated travel time to the game clock"""
        try:
            # Check if a calculation has been performed
            if hasattr(self, 'calculated_travel_days') and hasattr(self, 'calculated_travel_hours'):
                # Advance the time
                self._advance_time(
                    hours=self.calculated_travel_hours,
                    days=self.calculated_travel_days
                )
                
                # Add a note about the travel
                travel_note = (
                    f"Traveled {self.travel_distance} miles through {self.travel_terrain} "
                    f"at {self.travel_pace} pace via {self.travel_vehicle}.\n"
                    f"Travel time: {self.calculated_travel_days} days and {self.calculated_travel_hours} hours.\n\n"
                )
                
                # Add note to the time notes
                current_notes = self.time_notes.toPlainText()
                self.time_notes.setText(travel_note + current_notes)
                
                # Switch to time tab
                self.parent().setCurrentIndex(0)
            else:
                self.travel_result.setText("Please calculate travel time first.")
        except Exception as e:
            self.travel_result.setText(f"Error applying travel: {str(e)}")
            
    def save_state(self):
        """Save the panel state"""
        return {
            "game_hour": self.game_hour,
            "game_minute": self.game_minute,
            "game_day": self.game_day,
            "game_month": self.game_month,
            "game_year": self.game_year,
            "travel_pace": self.travel_pace,
            "travel_terrain": self.travel_terrain,
            "travel_vehicle": self.travel_vehicle,
            "travel_distance": self.travel_distance,
            "travel_hours": self.travel_hours,
            "time_notes": self.time_notes.toPlainText()
        }
        
    def restore_state(self, state):
        """Restore panel state from saved data"""
        if not state:
            return
            
        # Restore time values
        self.game_hour = state.get("game_hour", 12)
        self.game_minute = state.get("game_minute", 0)
        self.game_day = state.get("game_day", 1)
        self.game_month = state.get("game_month", 1)
        self.game_year = state.get("game_year", 1490)
        
        # Update time spinners and combo boxes
        self.hour_spinner.setValue(self.game_hour)
        self.minute_spinner.setValue(self.game_minute)
        self.day_spinner.setValue(self.game_day)
        self.month_combo.setCurrentIndex(self.game_month - 1)
        self.year_spinner.setValue(self.game_year)
        
        # Restore travel values
        self.travel_pace = state.get("travel_pace", "Normal")
        self.travel_terrain = state.get("travel_terrain", "Road/Trail")
        self.travel_vehicle = state.get("travel_vehicle", "On Foot")
        self.travel_distance = state.get("travel_distance", 0)
        self.travel_hours = state.get("travel_hours", 8)
        
        # Update travel combo boxes and spinners
        self.pace_combo.setCurrentText(self.travel_pace)
        self.terrain_combo.setCurrentText(self.travel_terrain)
        self.vehicle_combo.setCurrentText(self.travel_vehicle)
        self.distance_spinner.setValue(self.travel_distance)
        self.hours_spinner.setValue(self.travel_hours)
        
        # Restore notes
        self.time_notes.setText(state.get("time_notes", ""))
        
        # Update the time display
        self._update_time_display() 