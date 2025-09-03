# Development Guide

## Local Development Mode

When developing the Gym Buddy Bot web application locally, you can use the built-in development mode that simulates the Telegram WebApp environment.

### Features

- **Mock Telegram User**: Automatically creates a mock Telegram user with ID `123456789`
- **Editable User ID**: You can change the user ID in the UI for testing different scenarios
- **API Integration**: All API calls work with the mock user ID
- **Theme Support**: Simulates Telegram's light theme

### How to Use

**Option 1: Quick Start (Recommended)**
```bash
./scripts/dev.sh
```

**Option 2: Manual Start**

1. **Start the backend server**:
   ```bash
   cd /path/to/gym-buddy-bot
   DATABASE_URL="sqlite+aiosqlite:///./local_dev.db" BOT_TOKEN="test-token" ADMIN_CHAT_ID="123456789" uv run uvicorn buddy_gym_bot.server.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Start the frontend**:
   ```bash
   cd webapp
   npm run dev
   ```

3. **Open the application** in your browser at `http://localhost:3000`

**Note**: The backend uses SQLite for local development to avoid database type mismatch issues.

3. **Development Mode Indicator**: You'll see a "Dev Mode" indicator at the top of the page showing the current user ID

4. **Change User ID**: Use the input field next to the dev mode indicator to change the user ID for testing

5. **Test AI Features**: The AI Workout Planner will work with the mock user ID, allowing you to test the scheduling functionality

### API Endpoints

The following API endpoints work with the mock user ID:

- `POST /api/v1/schedule` - Generate workout plans
- `GET /api/v1/plan/current` - Get current plan
- `POST /api/v1/plan/update` - Update plan
- `POST /api/v1/workout` - Log workout sets
- `GET /api/v1/workout/history` - Get workout history
- `POST /api/v1/workout/finish` - Finish workout session

### Environment Variables

Make sure you have the following environment variables set in your `.env` file:

```env
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=your_database_url
```

### Testing Different Scenarios

1. **New User**: Use a new user ID to test the onboarding flow
2. **Existing User**: Use an existing user ID to test plan loading and history
3. **AI Generation**: Test the AI workout planner with different prompts

### Switching Between Development and Production

The application automatically detects whether it's running in development mode:
- **Development**: Uses mock Telegram WebApp when `window.Telegram.WebApp` is not available
- **Production**: Uses the real Telegram WebApp when running inside Telegram

### Troubleshooting

- **"Telegram user ID not available"**: This error has been fixed by ensuring the AI Workout Planner only renders when the Telegram WebApp is properly initialized. The component now waits for both `isInitialized` and `telegramWebApp?.initDataUnsafe?.user?.id` to be available before rendering.
- **API errors**: The frontend will gracefully fall back to local storage if API calls fail. Check the console for warnings about API failures.
- **Database errors**: The backend now uses SQLite for local development, which resolves type mismatch issues. If you encounter database problems, run `uv run python scripts/reset_db.py` to reset the database.
- **Bot token errors**: The server skips bot initialization when using the test token, so bot-related errors should not occur in development mode.
- **Theme issues**: The development mode uses a light theme by default. You can modify the mock theme in the code if needed.

### Testing the Fix

To verify that the "Telegram user ID not available" error is resolved:

1. **Open the browser console** (F12)
2. **Navigate to the Plan tab**
3. **Try the AI Workout Planner** - you should see debug logs showing:
   - `🔧 Development Mode: Created mock Telegram WebApp with user ID: 123456789`
   - `🔧 State Update: isInitialized = true, telegramWebApp = [object]`
   - `🔧 generateWorkoutPlan: Using userId = 123456789`

If you still see the error, check that:
- The backend server is running on port 8000
- The frontend is running on port 3000
- Both servers were started with the correct environment variables

### Debug Script

If you're still getting the "Telegram user ID not available" error, you can run this debug script in your browser console:

1. Open the browser console (F12)
2. Copy and paste the contents of `webapp/debug-script.js`
3. Press Enter to execute

This will manually set up the mock Telegram WebApp and reload the page to apply the changes.

### Console Debugging

The development mode now includes console logging to help debug issues:

- Look for messages starting with `🔧 Development Mode:` to see when the mock is created
- Look for messages starting with `🔧 generateWorkoutPlan:` to see the state of the Telegram WebApp when generating plans

### Hydration Issues

If you see hydration errors (server/client mismatch), this is normal during the first load. The application:

1. Starts with `telegramWebApp` as `null`
2. Initializes the mock Telegram WebApp in `useEffect` after the component mounts
3. Shows the AI Workout Planner only after initialization is complete

This prevents hydration mismatches between server-side and client-side rendering.
