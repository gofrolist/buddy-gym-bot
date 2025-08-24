# Gym Buddy Bot Web App

A React-based web application for managing workout plans and tracking exercises.

## Features

### Plan Management
- View current workout plan with days, exercises, and sets
- **NEW**: Edit entire workout days (weekday, focus, time)
- **NEW**: Delete entire workout days with confirmation
- Add/remove exercises from specific days
- Edit exercise names and details
- Request plan changes from trainers via AI

### Workout Tracking
- Track sets, reps, and weights during workouts
- Support for both metric (kg) and imperial (lbs) units
- Exercise search and selection
- Workout history and statistics

### Exercise Database
- Search exercises by name
- View exercise details, instructions, and GIFs
- Exercise categorization by body parts and equipment

## New Day-Level Actions

The plan tab now includes buttons to edit and delete entire workout days:

- **Edit Day (✏️)**: Click to modify the day's weekday, focus area, and time
- **Delete Day (🗑️)**: Click to remove the entire day and all its exercises

### Usage

1. Navigate to the **Plan** tab
2. Each workout day now displays edit and delete buttons in the top-right corner
3. Click the edit button to modify day details via prompts
4. Click the delete button to remove the entire day (with confirmation)

### Technical Details

- Day editing uses browser prompts for simplicity
- All changes are automatically saved to the backend API
- The UI updates immediately after successful operations
- Proper error handling and user confirmation for destructive actions

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

## Architecture

- React 18 with TypeScript
- CSS modules for styling
- Telegram WebApp integration
- Responsive design for mobile and desktop
- Internationalization support (English/Russian)
