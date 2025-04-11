# Panel Layout System Testing Instructions

## Overview
The panel layout system has been improved to address issues with panels getting squished, overlapping, or becoming unreadable when more than two panels are displayed. The new system implements:

1. Smart tabbing based on the number of visible panels
2. Minimum size enforcement for panels
3. Percentage-based sizing for better space utilization
4. User-configurable layout settings

## Testing Steps

### Basic Layout Testing
1. Launch the application
2. Open 2-3 panels from different categories (e.g., Combat Tracker, Conditions, Session Notes)
3. Verify that panels are organized in a readable manner without excessive overlap
4. Click "View > Smart Organize Panels" to test the organization function

### Multiple Panel Testing
1. Open 5-6 panels from different categories
2. Verify that panels are automatically tabbed when appropriate
3. Test switching between tabs within panel groups

### Panel Settings Testing
1. Go to "View > Panel Display Settings"
2. Experiment with different settings:
   - Increase/decrease the "Auto-tab threshold" (2-10)
   - Toggle "Always tab" options for different panel categories
   - Adjust minimum panel sizes
   - Toggle percentage-based sizing
3. Click "Save" and verify changes take effect

### Display Scaling
1. Resize the application window to different sizes
2. Verify that panels adjust appropriately to the available space
3. Test on different monitor configurations if available

### Panel Interaction
1. Try dragging tabs to reorder them
2. Detach a tab to make it a floating panel
3. Reattach floating panels
4. Try moving panels between different areas of the screen

## Expected Results
- Panels should maintain readability regardless of how many are displayed
- When many panels are open, they should automatically organize into tabs by category
- Minimum sizes should prevent panels from becoming too small to use
- The panel layout should adapt to the application window size

## Reporting Issues
If you encounter any issues with the panel layout system, please note:
1. The number of panels open when the issue occurred
2. The specific panel types involved
3. Your current panel settings configuration
4. Steps to reproduce the issue
5. Screenshots if possible
