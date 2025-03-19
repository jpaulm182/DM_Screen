#!/bin/bash

# Activate the virtual environment
source venv/bin/activate

# Run the application
python main.py

# Deactivate the virtual environment when the application closes
deactivate 