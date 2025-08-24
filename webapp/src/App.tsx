import React, { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Button, Input } from "./components/ui";

// Recent changes (2025-08-22):
// - Removed "?" button from workout tab exercises (duplicated exercise name click functionality)
// - Unified exercise editing behavior across workout and plan tabs using search modal
// - Created handleExerciseEdit() function for consistent editing experience
// - Simplified handleSelectExerciseForPlan() logic for better maintainability

declare global {
  interface Window { Telegram: any }
}





interface WorkoutSet {
  id: string;
  exercise: string;
  weight: number;  // Stored in kg (canonical unit)
  input_weight: number;  // What user typed (for auditability)
  input_unit: 'kg' | 'lbs';  // What unit user entered
  reps: number;
  rpe: number | null;
  isCompleted: boolean;
  isPR: boolean;
  isBackendData?: boolean; // Optional flag to identify backend data
}

interface WorkoutPlan {
  id?: string;
  program_name?: string;
  days?: {
    weekday: string;
    time: string;
    focus: string;
    exercises: {
      name: string;
      exercise_db_id: string;
      sets: number;
      reps: string;
    }[];
  }[];
  weeks?: number;
  timezone?: string;
  days_per_week?: number;
}

interface WorkoutHistory {
  id: string;
  date: string;
  duration: number;
  exercises: {
    name: string;
    exercise_db_id?: string; // Add optional exercise_db_id for history
    sets: number;
    totalReps: number;
    maxWeight: number;
  }[];
}



type TabType = 'workout' | 'plan' | 'history';

// Unit system types
type UnitSystem = 'metric' | 'imperial';

// Function to detect user's preferred unit system
function detectUnitSystem(): UnitSystem {
  try {
    // Method 1: Check locale (most reliable)
    const locale = navigator.language || navigator.languages?.[0] || 'en-US';
    const country = locale.split('-')[1]?.toUpperCase();

    // Countries that typically use imperial units
    const imperialCountries = ['US', 'GB', 'CA', 'AU', 'NZ', 'IE'];

    if (country && imperialCountries.includes(country)) {
      return 'imperial';
    }

    // Method 2: Check if locale contains imperial indicators
    if (locale.toLowerCase().includes('en-us') || locale.toLowerCase().includes('en-gb')) {
      return 'imperial';
    }

    // Method 3: Check device language
    const deviceLang = navigator.language?.toLowerCase() || '';
    if (deviceLang.startsWith('en')) {
      // Default to imperial for English speakers (most are US/UK)
      return 'imperial';
    }

    // Default to metric for most other locales
    return 'metric';
  } catch {
    // Fallback to imperial (US default)
    return 'imperial';
  }
}

// Function to convert kg to lbs
function kgToLbs(kg: number): number {
  // Round to nearest 0.5 lbs for better UX
  return Math.round(kg * 2.20462 * 2) / 2;
}

// Function to convert lbs to kg
function lbsToKg(lbs: number): number {
  return lbs * 0.453592; // Keep precision for kg storage
}

function tgUser() {
  try {
    const user = window.Telegram?.WebApp?.initDataUnsafe?.user;
    console.log("tgUser() called, result:", user);
    console.log("window.Telegram:", window.Telegram);
    console.log("window.Telegram?.WebApp:", window.Telegram?.WebApp);
    console.log("window.Telegram?.WebApp?.initDataUnsafe:", window.Telegram?.WebApp?.initDataUnsafe);
    return user;
  } catch (error) {
    console.error("Error in tgUser():", error);
    return null;
  }
}

// API response normalization functions
function getItems(payload: any): any[] {
  if (!payload) return [];
  if (Array.isArray(payload.items)) return payload.items;
  if (Array.isArray(payload.data)) return payload.data;
  if (Array.isArray(payload.results)) return payload.results;
  return [];
}

function isOk(payload: any): boolean {
  return Boolean(payload?.success ?? payload?.ok ?? false);
}

export default function App() {
  const { t, i18n } = useTranslation();
  const user = useMemo(() => tgUser(), []);

  // Detect if running in Main App mode (full screen) vs Mini App mode
  const isMainApp = useMemo(() => {
    try {
      return window.Telegram?.WebApp?.platform !== 'ios' && window.Telegram?.WebApp?.platform !== 'android';
    } catch {
      return false;
    }
  }, []);

  // Tab state
  const [activeTab, setActiveTab] = useState<TabType>('workout');

  // Workout state
  const [workoutStartTime, setWorkoutStartTime] = useState(Date.now());
  const [isWorkoutActive, setIsWorkoutActive] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [pausedTime, setPausedTime] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [currentExercise, setCurrentExercise] = useState("");
  const [currentWeight, setCurrentWeight] = useState("");
  const [currentReps, setCurrentReps] = useState("");
  const [currentRPE, setCurrentRPE] = useState("");
  const [showKeypad, setShowKeypad] = useState(false);
  const [inputMode, setInputMode] = useState<"weight" | "reps" | "rpe">("weight");
  const [editingSetId, setEditingSetId] = useState<string | null>(null);

  // Workout data - start with empty
  const [workoutSets, setWorkoutSets] = useState<WorkoutSet[]>([]);
  const [exercises, setExercises] = useState<string[]>([]);
  const [exerciseDbIds, setExerciseDbIds] = useState<Record<string, string>>({});

  // Plan and history data
  const [currentPlan, setCurrentPlan] = useState<WorkoutPlan | null>(null);
  const [workoutHistory, setWorkoutHistory] = useState<WorkoutHistory[]>([]);

  // Unit system state
  const [unitSystem, setUnitSystem] = useState<UnitSystem>(() => detectUnitSystem());

  // UI state
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Exercise help modal state
  const [showExerciseModal, setShowExerciseModal] = useState(false);
  const [exerciseModalData, setExerciseModalData] = useState<ExerciseDBData | null>(null);

  // Schedule request state
  const [scheduleRequest, setScheduleRequest] = useState("");
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [scheduleHistory, setScheduleHistory] = useState<Array<{
    id: string;
    request: string;
    response: string;
    timestamp: string;
  }>>([]);

  // Component to render exercise names as clickable links when they have exercise_db_id
  const ExerciseName: React.FC<{
    name: string;
    exercise_db_id?: string;
    className?: string;
  }> = ({ name, exercise_db_id, className }) => {
    if (exercise_db_id && exercise_db_id !== 'null' && exercise_db_id.trim() !== '') {
      // Create a clickable span that shows exercise info in popup
      return (
        <span
          className={`exercise-name-link ${className || ''}`}
          title={`Click to view ${name} details`}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && handleExerciseHelpById(exercise_db_id, name)}
          onClick={() => handleExerciseHelpById(exercise_db_id, name)}
          style={{ cursor: 'pointer' }}
        >
          {name}
        </span>
      );
    }

    // Regular text if no valid exercise_db_id
    return <span className={className}>{name}</span>;
  };

  // Save workout state to localStorage
  const saveWorkoutState = useCallback(() => {
    try {
      const workoutState = {
        workoutStartTime,
        isWorkoutActive,
        isPaused,
        pausedTime,
        workoutSets,
        exercises,
        timestamp: Date.now()
      };
      localStorage.setItem('workoutState', JSON.stringify(workoutState));
      console.log('Workout state saved to localStorage');
    } catch (error) {
      console.error('Failed to save workout state:', error);
    }
  }, [workoutStartTime, isWorkoutActive, isPaused, pausedTime, workoutSets, exercises]);

  // Load workout state from localStorage
  const loadWorkoutState = useCallback(() => {
    try {
      const savedState = localStorage.getItem('workoutState');
      if (savedState) {
        const workoutState = JSON.parse(savedState);

        // Check if the saved state is from today (within 24 hours)
        const isToday = (Date.now() - workoutState.timestamp) < 24 * 60 * 60 * 1000;

        if (isToday && workoutState.isWorkoutActive) {
          // Restore workout state
          setWorkoutStartTime(workoutState.workoutStartTime);
          setIsWorkoutActive(workoutState.isWorkoutActive);
          setIsPaused(workoutState.isPaused);
          setPausedTime(workoutState.pausedTime);
          setWorkoutSets(workoutState.workoutSets);
          setExercises(workoutState.exercises);

          console.log('Workout state restored from localStorage');

          // Show notification that workout was restored
          if (workoutState.workoutSets.length > 0) {
            alert(`Welcome back! Your workout with ${workoutState.workoutSets.length} sets has been restored.`);
          }
        } else {
          // Clear old workout state
          localStorage.removeItem('workoutState');
          console.log('Old workout state cleared');
        }
      }
    } catch (error) {
      console.error('Failed to load workout state:', error);
      localStorage.removeItem('workoutState');
    }
  }, []);

  // Initialize app
  useEffect(() => {
    console.log("App initialization started");
    console.log("User object:", user);
    console.log("User ID:", user?.id);
    console.log("Telegram WebApp:", window.Telegram?.WebApp);

    // ✅ Always try to restore first
    loadWorkoutState();

    const lc = user?.language_code?.slice(0, 2) || "en";
    i18n.changeLanguage(lc);

    try {
      window.Telegram?.WebApp?.expand?.();
    } catch {}

    if (user?.id) {
      console.log("User available, loading data...");
      fetchCurrentPlan();
      fetchWorkoutHistory();
      return; // cleanup not needed here
    } else {
      console.log("No user ID available, will retry in 1 second...");
      // Retry path without skipping the restore above
      const retryTimer = setTimeout(() => {
        console.log("Retrying to get user data...");
        const retryUser = tgUser();
        if (retryUser?.id) {
          console.log("User data now available, loading data...");
          fetchCurrentPlan();
          fetchWorkoutHistory();
        } else {
          console.log("Still no user data after retry");
        }
      }, 1000);

      return () => clearTimeout(retryTimer);
    }
  }, [user, i18n, loadWorkoutState]);

  // Auto-populate workout with plan exercises when plan is loaded
  useEffect(() => {
    if (currentPlan && currentPlan.days && currentPlan.days.length > 0) {
      // Get today's workout or first available workout
      const todayShort = new Date().toLocaleDateString('en-US', { weekday: 'short' }); // Mon
      const todayLong = new Date().toLocaleDateString('en-US', { weekday: 'long' });  // Monday
      const todayWorkout = currentPlan.days.find(day =>
        day.weekday === todayShort || day.weekday === todayLong
      ) ?? currentPlan.days[0]; // Fallback to first day if today not found

      if (todayWorkout && todayWorkout.exercises) {
        // Extract unique exercise names from the plan and clean them for API calls
        const planExercises = todayWorkout.exercises.map(ex => {
          // Keep original name for display, but also store cleaned version for API calls
          const cleanedName = cleanExerciseName(ex.name);
          console.log(`Exercise: "${ex.name}" -> cleaned: "${cleanedName}"`);
          return ex.name; // Keep original name for display
        });
        setExercises(planExercises);

        // Update exerciseDbIds mapping for exercises loaded from plan
        setExerciseDbIds(prev => {
          const newMapping = { ...prev };
          todayWorkout.exercises.forEach(ex => {
            if (ex.exercise_db_id) {
              newMapping[ex.name] = ex.exercise_db_id;
            }
          });
          return newMapping;
        });

        console.log("Auto-populated workout with plan exercises:", planExercises);
      }
    }
  }, [currentPlan]);

  // Refresh workout history when switching to history tab
  useEffect(() => {
    if (activeTab === 'history') {
      fetchWorkoutHistory();
    }
  }, [activeTab]);

  // Save workout state whenever it changes
  useEffect(() => {
    if (workoutSets.length > 0 || exercises.length > 0) {
      saveWorkoutState();
    }
  }, [workoutSets, exercises, saveWorkoutState]);

  // Save workout state when timer state changes
  useEffect(() => {
    if (isWorkoutActive) {
      saveWorkoutState();
    }
  }, [isWorkoutActive, isPaused, pausedTime, saveWorkoutState]);

  // Fetch current workout plan
  const fetchCurrentPlan = async () => {
    console.log("fetchCurrentPlan called with user ID:", user?.id);
    if (!user?.id) {
      console.log("No user ID, returning early");
      return;
    }

    try {
      console.log("Making API call to /api/v1/plan/current");
      const response = await fetch(`/api/v1/plan/current?tg_user_id=${user.id}`, {
        headers: { "Content-Type": "application/json" },
      });

      console.log("API response status:", response.status);
      console.log("API response ok:", response.ok);

      if (response.ok) {
        const data = await response.json();
        console.log("Plan API response:", data);
        if (data.success && data.plan) {
          console.log("Setting current plan:", data.plan);
          setCurrentPlan(data.plan);
        } else {
          console.log("No plan data or API not successful");
        }
      } else {
        console.error("API call failed with status:", response.status);
        console.error("Response text:", await response.text());
      }
    } catch (error) {
      console.error("Error fetching current plan:", error);
    }
  };

  // Save plan changes to API
  const savePlanChanges = async (updatedPlan: WorkoutPlan) => {
    if (!user?.id) return;

    try {
      const response = await fetch("/api/v1/plan/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tg_user_id: user.id,
          plan: updatedPlan
        }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          console.log("Plan changes saved successfully");
          // Update local state with the saved plan
          setCurrentPlan(data.plan);
        } else {
          console.error("Failed to save plan:", data.error);
          alert("Failed to save plan changes. Please try again.");
        }
      } else {
        console.error("Failed to save plan:", response.statusText);
        alert("Failed to save plan changes. Please try again.");
      }
    } catch (error) {
      console.error("Error saving plan:", error);
      alert("Failed to save plan changes. Please try again.");
    }
  };

  // Fetch workout history
  const fetchWorkoutHistory = async () => {
    if (!user?.id) return;

    try {
      const response = await fetch(`/api/v1/workout/history?tg_user_id=${user.id}`, {
        headers: { "Content-Type": "application/json" },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.history) {
          setWorkoutHistory(data.history);
        }
      }
    } catch (error) {
      console.error("Error fetching workout history:", error);
    }
  };

  // Tick the timer every second when active and not paused
  useEffect(() => {
    if (!isWorkoutActive || isPaused) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [isWorkoutActive, isPaused]);

  // Calculate workout duration with pause support
  const workoutDuration = useMemo(() => {
    if (!isWorkoutActive) return 0;

    if (isPaused) {
      return Math.floor((pausedTime - workoutStartTime) / 1000);
    } else {
      const elapsed = now - workoutStartTime;
      return Math.floor(elapsed / 1000);
    }
  }, [isWorkoutActive, isPaused, workoutStartTime, pausedTime, now]);

  const formatTime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };



  // Handle workout controls
  const handlePauseResume = () => {
    if (isPaused) {
      // Resume workout - adjust start time to account for paused duration
      const newStartTime = Date.now() - (pausedTime - workoutStartTime);
      setWorkoutStartTime(newStartTime);
      setPausedTime(0);
      setIsPaused(false);
      setNow(Date.now());
    } else {
      // Pause workout - record current time
      const pausedAt = Date.now();
      setPausedTime(pausedAt);
      setIsPaused(true);
      setNow(pausedAt);
    }
  };

  const handleCancelWorkout = () => {
    if (confirm("Are you sure you want to cancel this workout?")) {
      setIsWorkoutActive(false);
    }
  };

  // Handle adding new exercise
  const handleAddExercise = () => {
    // Show exercise search modal for workout tab
    setSearchingDayIndex(-1); // -1 indicates workout tab
    setExerciseSearchQuery("");
    setExerciseSearchResults([]);
    setShowExerciseSearch(true);
  };

  // Clean exercise name for API search (keep equipment, just clean formatting)
  const cleanExerciseName = (exerciseName: string): string => {
    return exerciseName
      .replace(/\([^)]*\)/g, '') // Remove parentheses content
      .replace(/\s+/g, ' ') // Normalize multiple spaces
      .trim();
  };

  // Define the exercise data type based on actual API response
  interface ExerciseDBData {
    exerciseId: string;
    name: string;
    gifUrl: string;
    targetMuscles: string[];
    bodyParts: string[];
    equipments: string[];
    secondaryMuscles: string[];
    instructions: string[];
  }

  // Helper function to search exercises by general query
  const searchExercises = async (query: string): Promise<ExerciseDBData | null> => {
    try {
      const response = await fetch(`https://www.exercisedb.dev/api/v1/exercises/search?q=${encodeURIComponent(query)}&limit=10`);
      if (response.ok) {
        const data = await response.json();
        if (data && data.success && data.data && data.data.length > 0) {
          return data.data[0];
        }
      }
    } catch (error) {
      console.log(`Search failed for "${query}":`, error);
    }
    return null;
  };

  // Handle exercise help (ExerciseDB API)
  const handleExerciseHelp = async (exerciseName: string) => {
    try {

      // Clean the exercise name for better search (keep equipment info)
      const cleanedName = cleanExerciseName(exerciseName);
      console.log(`Searching for exercise: "${exerciseName}" (cleaned: "${cleanedName}")`);

      // Use our local ExerciseDB endpoint
      const searchEndpoint = `/api/v1/exercises/search?q=${encodeURIComponent(cleanedName)}&limit=10`;

      const response = await fetch(searchEndpoint, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
      });

      if (response.ok) {
        const json = await response.json();
        console.log(`Search results for "${cleanedName}":`, json);

        if (isOk(json) && getItems(json).length > 0) {
          // Find the best match from the search results
          let bestMatch = getItems(json)[0];

          // Try to find exact match first
          const exactMatch = getItems(json).find((ex: ExerciseDBData) =>
            ex.name.toLowerCase().includes(cleanedName.toLowerCase()) ||
            cleanedName.toLowerCase().includes(ex.name.toLowerCase())
          );

          if (exactMatch) {
            bestMatch = exactMatch;
          }

          // Show exercise data in modal with GIF
          setExerciseModalData(bestMatch);
          setShowExerciseModal(true);
        } else {
          // Try with just the first word as fallback
          const firstWord = cleanedName.split(' ')[0];
          if (firstWord.length > 2) {
            console.log(`Trying fallback search with first word: "${firstWord}"`);
            const fallbackResponse = await fetch(`https://www.exercisedb.dev/api/v1/exercises/search?q=${encodeURIComponent(firstWord)}&limit=5`);

            if (fallbackResponse.ok) {
              const fallbackJson = await fallbackResponse.json();
              const items = getItems(fallbackJson);
              if (items.length > 0) {
                const fallbackExercise = items[0];
                // Show fallback exercise in modal with GIF
                setExerciseModalData(fallbackExercise);
                setShowExerciseModal(true);
                return;
              }
            }
          }

          // No data found
          alert(`No detailed information found for "${exerciseName}".\n\nThis exercise might be:\n• A custom exercise\n• Named differently in our database\n• A compound movement\n\nYou can search online for proper form and technique.`);
        }
      } else {
        console.error(`API response not ok: ${response.status} ${response.statusText}`);
        alert(`Could not fetch exercise information for ${exerciseName}.\n\nAPI returned: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      console.error("Error fetching exercise help:", error);
      alert(`Could not fetch exercise information for ${exerciseName}.\n\nPlease check your internet connection or try again later.`);
    }
  };

  // Handle exercise help by ID (for ExerciseName component)
  const handleExerciseHelpById = async (exerciseDbId: string, exerciseName: string) => {
    try {
      // First try to fetch by ID from backend
      try {
        const byId = await fetch(`/api/v1/exercises/${encodeURIComponent(exerciseDbId)}`);
        if (byId.ok) {
          const exerciseData = await byId.json();
          setExerciseModalData(exerciseData);
          setShowExerciseModal(true);
          return;
        }
      } catch {}

      // Fallback to name search
      const exerciseData = await searchExercises(exerciseName);
      if (exerciseData) {
        setExerciseModalData(exerciseData);
        setShowExerciseModal(true);
      } else {
        // Fallback to a more general search if specific exercise not found
        const fallbackResponse = await fetch(`https://www.exercisedb.dev/api/v1/exercises/search?q=${encodeURIComponent(exerciseName)}&limit=10`);
        if (fallbackResponse.ok) {
          const fallbackJson = await fallbackResponse.json();
          const items = getItems(fallbackJson);
          if (items.length > 0) {
            setExerciseModalData(items[0]);
            setShowExerciseModal(true);
          } else {
            alert(`No detailed information found for "${exerciseName}".\n\nThis exercise might be:\n• A custom exercise\n• Named differently in our database\n• A compound movement\n\nYou can search online for proper form and technique.`);
          }
        } else {
          alert(`Could not fetch exercise information for ${exerciseName}.\n\nAPI returned: ${fallbackResponse.status} ${fallbackResponse.statusText}`);
        }
      }
    } catch (error) {
      console.error("Error fetching exercise help by ID:", error);
      alert(`Could not fetch exercise information for ${exerciseName}.\n\nPlease check your internet connection or try again later.`);
    }
  };

    // Unified exercise editing function that works for all tabs
  const handleExerciseEdit = (context: {
    type: 'workout' | 'plan';
    exerciseName: string;
    dayIndex?: number;
    exerciseIndex?: number;
  }) => {
        // Open exercise search modal with current exercise name pre-filled
    setExerciseSearchQuery(context.exerciseName);

    if (context.type === 'workout') {
      setSearchingDayIndex(-1); // -1 indicates workout tab
      setSearchingExerciseIndex(-1); // -1 indicates editing existing exercise in workout
    } else {
      // Plan tab
      if (context.dayIndex !== undefined && context.exerciseIndex !== undefined) {
        setSearchingDayIndex(context.dayIndex);
        setSearchingExerciseIndex(context.exerciseIndex);
      } else {
        console.error('Plan editing requires dayIndex and exerciseIndex');
        return;
      }
    }

    setShowExerciseSearch(true);



    // Search for the current exercise to show alternatives
    if (context.exerciseName.trim().length >= 2) {
      searchExercisesForPlan(context.exerciseName);
    }
  };

  // Handle exercise name editing (when clicking on exercise title) - now uses unified function
  const handleExerciseNameEdit = (exerciseName: string) => {
    handleExerciseEdit({
      type: 'workout',
      exerciseName
    });
  };

  // Handle editing exercise name in plan - now uses unified function
  const handlePlanExerciseEdit = async (dayIndex: number, exerciseIndex: number) => {
    if (!currentPlan || !currentPlan.days) return;

    const exercise = currentPlan.days[dayIndex].exercises[exerciseIndex];

    handleExerciseEdit({
      type: 'plan',
      exerciseName: exercise.name,
      dayIndex,
      exerciseIndex
    });
  };

  // Handle exercise deletion (when clicking on delete button)
  const handleExerciseDelete = (exerciseName: string) => {
    if (confirm(`Are you sure you want to delete "${exerciseName}"?`)) {
      setExercises(prev => prev.filter(ex => ex !== exerciseName));
      // Also remove workout sets for this exercise
      setWorkoutSets(prev => prev.filter(set => set.exercise !== exerciseName));
      // Clean up exerciseDbIds mapping
      setExerciseDbIds(prev => {
        const newMapping = { ...prev };
        delete newMapping[exerciseName];
        return newMapping;
      });
    }
  };

  // Handle adding new set
  const handleAddSet = (exerciseName: string) => {
    // Store current scroll position before opening input
    const currentScrollY = window.scrollY;

    setCurrentExercise(exerciseName);
    setCurrentWeight("");
    setCurrentReps("");
    setCurrentRPE("");
    setInputMode("weight");
    setShowKeypad(true);

    // Focus on weight input after a short delay to ensure UI has updated
    setTimeout(() => {
      const weightInput = document.querySelector('.weight-input__field') as HTMLInputElement;
      if (weightInput) {
        weightInput.focus();
        // Smooth scroll to input section without losing focus
        const inputSection = document.getElementById('input-section');
        if (inputSection) {
          inputSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }
    }, 150);
  };

  // Handle editing set
  const handleEditSet = (set: WorkoutSet) => {
    setEditingSetId(set.id);
    setCurrentExercise(set.exercise);
    setCurrentWeight(set.weight.toString());
    setCurrentReps(set.reps.toString());
    setCurrentRPE(set.rpe?.toString() || "");
    setInputMode("weight");
    setShowKeypad(true);
  };

  // Switch between weight and reps input
  const switchInputMode = () => {
    if (inputMode === "weight" && currentWeight) {
      setInputMode("reps");
    } else if (inputMode === "reps" && currentReps) {
      // All fields filled, ready to save
      handleDone();
    }
  };

  const handleDone = () => {
    console.log("HandleDone called:", { currentWeight, currentReps, currentExercise, editingSetId });

    if (currentWeight && currentReps) {
      const weight = parseFloat(currentWeight);
      const reps = parseInt(currentReps);

      console.log("Parsed values:", { weight, reps });

      if (editingSetId) {
        // Update existing set
        setWorkoutSets(prev => prev.map(set =>
          set.id === editingSetId
            ? { ...set, weight, reps }
            : set
        ));
        setEditingSetId(null);
      } else {
        // Add new set with single-unit storage and input tracking
        const weightKg = parseFloat(currentWeight);
        const inputWeight = unitSystem === 'imperial' ?
          parseFloat(getWeightInputValue()) :
          weightKg;

        const newSet: WorkoutSet = {
          id: Date.now().toString(),
          exercise: currentExercise,
          weight: weightKg,
          input_weight: inputWeight,
          input_unit: unitSystem === 'metric' ? 'kg' : 'lbs',
          reps,
          rpe: null,
          isCompleted: true, // Automatically mark as completed
          isPR: false
        };
        console.log("Adding new set:", newSet);
        setWorkoutSets(prev => [...prev, newSet]);

        // Save new set to API
        saveSetToAPI(newSet);
      }

      setShowKeypad(false);
      setCurrentWeight("");
      setCurrentReps("");
      setInputMode("weight");

      // Restore scroll position to where user was before opening input
      // This helps maintain focus on the workout progress
      setTimeout(() => {
        if (window.scrollY > 0) {
          window.scrollTo(0, Math.max(0, window.scrollY - 150));
        }
      }, 100);
    } else {
      console.log("Missing values:", { currentWeight, currentReps });
      // If we have weight but no reps, switch to reps input
      if (currentWeight && !currentReps) {
        setInputMode("reps");
      }
    }
  };

  // Save set to API
  const saveSetToAPI = async (set: WorkoutSet) => {
    try {
      const response = await fetch("/api/v1/workout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tg_user_id: user?.id || 0,
          exercise: set.exercise,
          weight_kg: set.weight,
          reps: set.reps,
          is_completed: set.isCompleted, // Include completion status
          workout_session_id: workoutStartTime.toString()
        }),
      });

      if (!response.ok) {
        console.error("Failed to save set to API:", response.statusText);
      } else {
        console.log("Set saved to API successfully");
      }
    } catch (error) {
      console.error("Error saving set to API:", error);
    }
  };

  // Handle adding new exercise to a day with search
  const handleAddPlanExercise = async (dayIndex: number) => {
    if (!currentPlan || !currentPlan.days) return;

    setSearchingDayIndex(dayIndex);
    setExerciseSearchQuery("");
    setExerciseSearchResults([]);
    setShowExerciseSearch(true);
  };

  // Exercise search state for manual editing
  const [exerciseSearchQuery, setExerciseSearchQuery] = useState("");
  const [exerciseSearchResults, setExerciseSearchResults] = useState<Array<{
    id: string;
    name: string;
    category: string;
    equipment: string;
    instructions: string[];
  }>>([]);
  const [showExerciseSearch, setShowExerciseSearch] = useState(false);
  const [searchingDayIndex, setSearchingDayIndex] = useState<number | null>(null);
  const [searchingExerciseIndex, setSearchingExerciseIndex] = useState<number | null>(null);

  // Debounced search for plan/exercise search
  const debouncedSearch = useRef<number | null>(null);

  // Search exercises for manual plan editing
  const searchExercisesForPlan = async (query: string) => {
    if (!query.trim()) {
      setExerciseSearchResults([]);
      return;
    }

    try {
      const response = await fetch(`/api/v1/exercises/search?q=${encodeURIComponent(query)}&limit=15`);
      if (response.ok) {
        const json = await response.json();
        if (isOk(json) || getItems(json).length) {
          setExerciseSearchResults(getItems(json));
        } else {
          setExerciseSearchResults([]);
        }
      }
    } catch (error) {
      console.error("Exercise search failed:", error);
      setExerciseSearchResults([]);
    }
  };

  // Handle exercise search input change
  const handleExerciseSearchChange = (query: string) => {
    setExerciseSearchQuery(query);
    if (debouncedSearch.current) window.clearTimeout(debouncedSearch.current);
    if (query.trim().length < 2) {
      setExerciseSearchResults([]);
      return;
    }
    debouncedSearch.current = window.setTimeout(() => searchExercisesForPlan(query), 250);
  };

  // Handle selecting an exercise from search results
  const handleSelectExerciseForPlan = async (exercise: {
    id: string;
    name: string;
    category: string;
    equipment: string;
    instructions: string[];
  }) => {
    if (searchingDayIndex === null) return;

    if (searchingDayIndex === -1) {
      // Workout tab - either adding new exercise or editing existing one
      if (searchingExerciseIndex === -1) {
        // Editing existing exercise in workout
        const oldExerciseName = exerciseSearchQuery; // This was the original name
        setExercises(prev => prev.map(ex => ex === oldExerciseName ? exercise.name : ex));
        setWorkoutSets(prev => prev.map(set =>
          set.exercise === oldExerciseName ? { ...set, exercise: exercise.name } : set
        ));
      } else {
        // Adding new exercise to workout
        setExercises(prev => {
          if (!prev.includes(exercise.name)) {
            return [...prev, exercise.name];
          }
          return prev;
        });
        // Store the exercise_db_id for clickable functionality
        setExerciseDbIds(prev => ({
          ...prev,
          [exercise.name]: exercise.id
        }));
      }

      // Close search modal
      setShowExerciseSearch(false);
      setSearchingDayIndex(null);
      setSearchingExerciseIndex(null);
      return;
    }

    // Plan tab - either adding new exercise or editing existing one
    if (!currentPlan || !currentPlan.days) return;

    if (searchingExerciseIndex !== null) {
      // Editing existing exercise
      const reps = prompt("Enter reps (e.g., '8', '10', '5-8'):", currentPlan.days[searchingDayIndex].exercises[searchingExerciseIndex].reps);
      const sets = prompt("Enter number of sets:", currentPlan.days[searchingDayIndex].exercises[searchingExerciseIndex].sets.toString());

      if (exercise.name && reps && sets) {
        const updatedPlan = { ...currentPlan };
        updatedPlan.days![searchingDayIndex].exercises[searchingExerciseIndex] = {
          name: exercise.name,
          exercise_db_id: exercise.id,
          sets: parseInt(sets) || 3,
          reps: reps.trim()
        };

        // Save to API
        await savePlanChanges(updatedPlan);

        // Also update workout exercises if they match
        const oldExerciseName = currentPlan.days![searchingDayIndex].exercises[searchingExerciseIndex].name;
        setExercises(prev => prev.map(ex => ex === oldExerciseName ? exercise.name : ex));
        setWorkoutSets(prev => prev.map(set =>
          set.exercise === oldExerciseName ? { ...set, exercise: exercise.name } : set
        ));

        // Update exerciseDbIds mapping for the new exercise name
        setExerciseDbIds(prev => {
          const newMapping = { ...prev };
          // Remove old mapping
          delete newMapping[oldExerciseName];
          // Add new mapping
          newMapping[exercise.name] = exercise.id;
          return newMapping;
        });

        // Close search modal
        setShowExerciseSearch(false);
        setSearchingDayIndex(null);
        setSearchingExerciseIndex(null);
      }
    } else {
      // Adding new exercise
      const reps = prompt("Enter reps (e.g., '8', '10', '5-8'):");
      const sets = prompt("Enter number of sets:", "3");

      if (exercise.name && reps && sets) {
        const updatedPlan = { ...currentPlan };
        const newExercise = {
          name: exercise.name,
          exercise_db_id: exercise.id,
          sets: parseInt(sets) || 3,
          reps: reps.trim()
        };

        updatedPlan.days![searchingDayIndex].exercises.push(newExercise);

        // Save to API
        await savePlanChanges(updatedPlan);

        // Also add to workout exercises if not already there
        setExercises(prev => {
          if (!prev.includes(exercise.name)) {
            return [...prev, exercise.name];
          }
          return prev;
        });
        // Store the exercise_db_id for clickable functionality
        setExerciseDbIds(prev => ({
          ...prev,
          [exercise.name]: exercise.id
        }));

        // Close search modal
        setShowExerciseSearch(false);
        setSearchingDayIndex(null);
        setSearchingExerciseIndex(null);
      }
    }
  };

  // Handle viewing exercise details from search results
  const handleViewExerciseDetails = async (exercise: {
    id: string;
    name: string;
    category: string;
    equipment: string;
    instructions: string[];
  }) => {
    try {
      // Create exercise data using local search results
      const exerciseData: ExerciseDBData = {
        exerciseId: exercise.id,
        name: exercise.name,
        gifUrl: "", // Will be populated from external API if available
        targetMuscles: exercise.category ? [exercise.category] : [],
        bodyParts: exercise.category ? [exercise.category] : [],
        equipments: [exercise.equipment],
        secondaryMuscles: [],
        instructions: exercise.instructions
      };

      // Enhance the data mapping based on available fields
      if (exercise.category) {
        // Map category to more specific muscle groups
        const categoryLower = exercise.category.toLowerCase();
        if (categoryLower.includes('chest') || categoryLower.includes('pectoral')) {
          exerciseData.targetMuscles = ['pectorals'];
          exerciseData.bodyParts = ['chest'];
        } else if (categoryLower.includes('back') || categoryLower.includes('lat')) {
          exerciseData.targetMuscles = ['lats'];
          exerciseData.bodyParts = ['back'];
        } else if (categoryLower.includes('shoulder') || categoryLower.includes('deltoid')) {
          exerciseData.targetMuscles = ['deltoids'];
          exerciseData.bodyParts = ['shoulders'];
        } else if (categoryLower.includes('arm') || categoryLower.includes('bicep') || categoryLower.includes('tricep')) {
          exerciseData.targetMuscles = categoryLower.includes('bicep') ? ['biceps'] : ['triceps'];
          exerciseData.bodyParts = ['upper arms'];
        } else if (categoryLower.includes('leg') || categoryLower.includes('quad') || categoryLower.includes('hamstring')) {
          exerciseData.targetMuscles = ['quadriceps', 'hamstrings'];
          exerciseData.bodyParts = ['upper legs'];
        } else if (categoryLower.includes('core') || categoryLower.includes('ab')) {
          exerciseData.targetMuscles = ['abs'];
          exerciseData.bodyParts = ['waist'];
        }
      }

      // Try to get only the GIF from external ExerciseDB API
      try {
        const response = await fetch(`https://www.exercisedb.dev/api/v1/exercises/search?q=${encodeURIComponent(exercise.name)}&limit=5`);
        if (response.ok) {
          const data = await response.json();
          if (data && data.success && data.data && data.data.length > 0) {
            // Find the best match by name similarity for GIF
            const bestMatch = data.data.find((ex: any) =>
              ex.name.toLowerCase() === exercise.name.toLowerCase() ||
              ex.name.toLowerCase().includes(exercise.name.toLowerCase()) ||
              exercise.name.toLowerCase().includes(ex.name.toLowerCase())
            ) || data.data[0];

            if (bestMatch && bestMatch.gifUrl) {
              exerciseData.gifUrl = bestMatch.gifUrl;
              console.log('Found GIF from external API:', bestMatch.gifUrl);
            }
          }
        }
      } catch (gifError) {
        console.log('Could not fetch GIF from external API, using local data only:', gifError);
      }

      console.log('Using local exercise data with external GIF:', exerciseData);
      setExerciseModalData(exerciseData);
      setShowExerciseModal(true);
    } catch (error) {
      console.error("Failed to create exercise data:", error);
      // Fallback: create basic exercise data from search result
      const fallbackData: ExerciseDBData = {
        exerciseId: exercise.id,
        name: exercise.name,
        gifUrl: "",
        targetMuscles: exercise.category ? [exercise.category] : [],
        bodyParts: exercise.category ? [exercise.category] : [],
        equipments: [exercise.equipment],
        secondaryMuscles: [],
        instructions: exercise.instructions
      };

      console.log('Using fallback data due to error:', fallbackData);
      setExerciseModalData(fallbackData);
      setShowExerciseModal(true);
    }
  };

  // Handle deleting exercise from plan
  const handleDeletePlanExercise = async (dayIndex: number, exerciseIndex: number) => {
    if (!currentPlan || !currentPlan.days) return;

    const exercise = currentPlan.days[dayIndex].exercises[exerciseIndex];
    if (confirm(`Are you sure you want to delete "${exercise.name}" from the plan?`)) {
      const updatedPlan = { ...currentPlan };
      updatedPlan.days![dayIndex].exercises.splice(exerciseIndex, 1);

      // Save to API
      await savePlanChanges(updatedPlan);
    }
  };

  // Handle editing a whole day in the plan
  const handleEditDay = async (dayIndex: number) => {
    if (!currentPlan || !currentPlan.days) return;

    const day = currentPlan.days[dayIndex];

    // Prompt for new day details
    const newWeekday = prompt("Enter day of week:", day.weekday);
    const newFocus = prompt("Enter focus area:", day.focus);
    const newTime = prompt("Enter time:", day.time);

    if (newWeekday && newFocus && newTime) {
      const updatedPlan = { ...currentPlan };
      updatedPlan.days![dayIndex] = {
        ...day,
        weekday: newWeekday.trim(),
        focus: newFocus.trim(),
        time: newTime.trim()
      };

      // Save to API
      await savePlanChanges(updatedPlan);
    }
  };

  // Handle deleting a whole day from the plan
  const handleDeleteDay = async (dayIndex: number) => {
    if (!currentPlan || !currentPlan.days) return;

    const day = currentPlan.days[dayIndex];
    if (confirm(`Are you sure you want to delete the entire "${day.weekday}" day with ${day.exercises?.length || 0} exercises?`)) {
      const updatedPlan = { ...currentPlan };
      updatedPlan.days!.splice(dayIndex, 1);

      // Save to API
      await savePlanChanges(updatedPlan);
    }
  };

  // Handle schedule request
  const handleScheduleRequest = async () => {
    if (!scheduleRequest.trim() || !user?.id) return;

    setScheduleLoading(true);

    try {
      console.log('Sending schedule request:', {
        tg_user_id: user.id,
        message: scheduleRequest.trim(),
        context: {
          current_plan: currentPlan ? {
            program_name: currentPlan.program_name,
            weeks: currentPlan.weeks,
            days_per_week: currentPlan.days_per_week,
            days_count: currentPlan.days ? currentPlan.days.length : 0
          } : null,
          workout_history_count: workoutHistory.length,
          current_workout: {
            active: isWorkoutActive,
            duration: workoutDuration,
            sets_count: workoutSets.length
          }
        }
      });

      const response = await fetch('/api/v1/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tg_user_id: user.id,
          message: scheduleRequest.trim(),
          context: {
            current_plan: currentPlan ? {
              program_name: currentPlan.program_name,
              weeks: currentPlan.weeks,
              days_per_week: currentPlan.days_per_week,
              days_count: currentPlan.days ? currentPlan.days.length : 0
            } : null,
            workout_history_count: workoutHistory.length,
            current_workout: {
              active: isWorkoutActive,
              duration: workoutDuration,
              sets_count: workoutSets.length
            }
          }
        }),
        ...(typeof AbortSignal?.timeout === "function"
          ? { signal: AbortSignal.timeout(120000) }
          : (() => {
              const c = new AbortController();
              setTimeout(() => c.abort(), 120000);
              return { signal: c.signal };
            })()
        )
      });

      console.log('Schedule response status:', response.status);
      console.log('Schedule response headers:', Object.fromEntries(response.headers.entries()));

      if (response.ok) {
        let data;
        try {
          const responseText = await response.text();
          console.log('Raw response text:', responseText);

          if (!responseText.trim()) {
            throw new Error('Empty response received');
          }

          data = JSON.parse(responseText);
          console.log('Parsed schedule response data:', data);
        } catch (parseError) {
          console.error('Failed to parse response as JSON:', parseError);
          alert(`Request sent but received invalid response format. Please try again.`);
          return;
        }

        // Handle new error types from updated backend
        if (data.success === false) {
          // New format: structured error response
          if (data.message) {
            // Provide specific guidance for common error types
            if (data.message.includes("Failed to extract workout constraints")) {
              alert("Could not understand your workout request. Please be more specific about:\n\n• Days of the week (e.g., 'Monday, Wednesday, Friday')\n• Duration (e.g., '30 min', '45 min', or '1 hour')\n• Focus area (e.g., 'upper body', 'lower body', 'full body')\n\nExample: 'Create a 3-day plan for Monday, Wednesday, Friday with 30 min upper body workouts'");
            } else if (data.message.includes("Failed to generate workout plan")) {
              alert("Could not generate a workout plan. Please try rephrasing your request or be more specific about your requirements.");
            } else {
              alert(`Request failed: ${data.message}`);
            }
          } else {
            alert("Request failed. Please try again.");
          }
          return;
        }

        // Add to schedule history
        const newEntry = {
          id: Date.now().toString(),
          request: scheduleRequest.trim(),
          response: data.response || data.message || 'Request processed successfully',
          timestamp: new Date().toISOString()
        };

        setScheduleHistory(prev => [newEntry, ...prev]);
        setScheduleRequest("");

        // If the response includes a new plan, update it
        if (data.plan) {
          console.log("Received new plan from schedule request:", data.plan);

          // Validate plan structure
          if (data.plan.days && Array.isArray(data.plan.days) && data.plan.days.length > 0) {
            // Validate each day has the required structure
            const validDays = data.plan.days.filter(day =>
              day.weekday &&
              day.exercises &&
              Array.isArray(day.exercises) &&
              day.exercises.length > 0
            );

            if (validDays.length > 0) {
              console.log(`Plan validation successful: ${validDays.length} valid days found`);

              // Create a sanitized plan object to prevent UI crashes
              const sanitizedPlan = {
                ...data.plan,
                days: validDays.map(day => ({
                  ...day,
                  exercises: day.exercises.map(ex => ({
                    name: ex.name || 'Unknown Exercise',
                    exercise_db_id: ex.exercise_db_id || '',
                    sets: typeof ex.sets === 'number' ? ex.sets : 3,
                    reps: ex.reps || '8-12'
                  }))
                }))
              };

              setCurrentPlan(sanitizedPlan);

              // Also update the workout tab exercises if they exist
              const todayShort = new Date().toLocaleDateString('en-US', { weekday: 'short' }); // Mon
              const todayLong = new Date().toLocaleDateString('en-US', { weekday: 'long' });  // Monday
              const todayWorkout = validDays.find(day =>
                day.weekday === todayShort || day.weekday === todayLong
              );
              if (todayWorkout && todayWorkout.exercises) {
                setExercises(todayWorkout.exercises.map(ex => ex.name || 'Unknown Exercise'));

                // Update exerciseDbIds mapping for exercises loaded from plan
                setExerciseDbIds(prev => {
                  const newMapping = { ...prev };
                  todayWorkout.exercises.forEach(ex => {
                    if (ex.exercise_db_id && ex.name) {
                      newMapping[ex.name] = ex.exercise_db_id;
                    }
                  });
                  return newMapping;
                });
              }

              // Show success message with plan update
              alert(`Request sent successfully!\n\nYour workout plan has been updated with ${validDays.length} workout days.`);
            } else {
              console.warn("Plan validation failed: no valid days found");
              alert(`Request sent successfully!\n\nResponse: ${newEntry.response}\n\nNote: Plan data was incomplete.`);
            }
          } else {
            console.warn("Plan validation failed: invalid plan structure");
            alert(`Request sent successfully!\n\nResponse: ${newEntry.response}\n\nNote: Plan data was incomplete.`);
          }
        } else {
          console.log("No plan in schedule response:", data);
          // Show success message without plan update
          alert(`Request sent successfully!\n\nResponse: ${newEntry.response}`);
        }
      } else {
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errorData = await response.json();
          console.log('Error response data:', errorData);

          // Handle new structured error format from updated backend
          if (errorData.success === false && errorData.message) {
            errorMessage = errorData.message;
          } else if (errorData.message) {
            errorMessage = errorData.message;
          } else if (errorData.detail) {
            errorMessage = errorData.detail;
          } else if (errorData.error) {
            errorMessage = errorData.error;
          }
        } catch (parseError) {
          console.log('Could not parse error response as JSON');
        }

        console.error('Schedule request failed:', errorMessage);

        // Offer retry for certain error types
        if (response.status >= 500) {
          const retry = confirm(`Request failed: ${errorMessage}\n\nThis appears to be a server error. Would you like to try again?`);
          if (retry) {
            // Retry the request
            setTimeout(() => handleScheduleRequest(), 2000);
            return;
          }
        }

        alert(`Failed to send request: ${errorMessage}`);
      }
    } catch (error) {
      console.error('Error sending schedule request:', error);
      let errorMessage = 'Unknown error occurred';

      if (error instanceof TypeError && error.message.includes('fetch')) {
        errorMessage = 'Network error - please check your connection';
      } else if (error instanceof Error) {
        if (error.name === 'TimeoutError') {
          errorMessage = 'Request timed out - the AI is taking longer than expected. Please try again.';
        } else if (error.name === 'AbortError') {
          errorMessage = 'Request was cancelled - please try again';
        } else if (error.message.includes('Failed to extract workout constraints')) {
          errorMessage = 'Could not understand your request. Please be more specific about days, duration, and focus.';
        } else if (error.message.includes('Failed to generate workout plan')) {
          errorMessage = 'Could not generate a plan. Please try rephrasing your request.';
        } else {
          errorMessage = error.message;
        }
      }

      // Show error with retry option for timeout errors
      if (error instanceof Error && error.name === 'TimeoutError') {
        const retry = confirm(`${errorMessage}\n\nWould you like to try again?`);
        if (retry) {
          // Retry the request after a short delay
          setTimeout(() => handleScheduleRequest(), 2000);
          return;
        }
      }

      alert(`Failed to send request: ${errorMessage}`);
    } finally {
      setScheduleLoading(false);
    }
  };

  // Handle finishing workout
  const handleFinishWorkout = async () => {
    if (confirm("Are you sure you want to finish this workout?")) {
      setIsWorkoutActive(false);

      // Save all workout data to API
      try {
        const workoutData = {
          tg_user_id: user?.id || 0,
          workout_session_id: workoutStartTime.toString(),
          duration_seconds: workoutDuration,
          exercises: workoutSets.map(set => ({
            exercise: set.exercise,
            weight_kg: set.weight,
            reps: set.reps,
            rpe: set.rpe, // Include RPE in the payload
            is_completed: set.isCompleted
          })),
          completed_at: new Date().toISOString()
        };

        const response = await fetch("/api/v1/workout/finish", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(workoutData),
        });

        if (response.ok) {
          console.log("Workout finished and saved to API");

          // Clear workout state from localStorage since workout is complete
          localStorage.removeItem('workoutState');
          console.log('Workout state cleared from localStorage');

          // Refresh workout history to show the completed workout
          await fetchWorkoutHistory();

          // Show success message
          try {
            window.Telegram?.WebApp?.showPopup({
                title: "Workout Complete! 🏋️",
                message: `Great job! Your workout has been saved. Duration: ${formatTime(workoutDuration)}`
            });
          } catch {}
        } else {
          console.error("Failed to finish workout:", response.statusText);
        }
    } catch (error) {
        console.error("Error finishing workout:", error);
      }
    }
  };

  // Group sets by exercise
  const exerciseGroups = useMemo(() => {
    const groups: Record<string, WorkoutSet[]> = {};
    workoutSets.forEach(set => {
      if (!groups[set.exercise]) {
        groups[set.exercise] = [];
      }
      groups[set.exercise].push(set);
    });

    // Sort sets by ID to maintain order and assign sequential numbers
    Object.keys(groups).forEach(exerciseName => {
      groups[exerciseName].sort((a, b) => parseInt(a.id) - parseInt(b.id));
    });

    return groups;
  }, [workoutSets]);

  // Get sequential set number for display
  const getSetNumber = (exerciseName: string, setId: string) => {
    const exerciseSets = workoutSets.filter(set => set.exercise === exerciseName);
    const sortedSets = exerciseSets.sort((a, b) => parseInt(a.id) - parseInt(b.id));
    const setIndex = sortedSets.findIndex(set => set.id === setId);
    return setIndex + 1;
  };

  // Format weight display with correct unit using stored values
  const formatWeight = (set: WorkoutSet): string => {
    if (unitSystem === 'imperial') {
      // Convert stored kg to lbs for display with proper rounding
      const lbs = kgToLbs(set.weight);
      return `${lbs} lbs`;
    } else {
      // Round kg to 1 decimal place for clean display
      const roundedKg = Math.round(set.weight * 10) / 10;
      return `${roundedKg} kg`;
    }
  };

  // Format weight from kg value (for history calculations)
  const formatWeightFromKg = (weightKg: number): string => {
    if (unitSystem === 'imperial') {
      const lbs = kgToLbs(weightKg);
      return `${lbs} lbs`;
    } else {
      // Round kg to 1 decimal place for clean display
      const roundedKg = Math.round(weightKg * 10) / 10;
      return `${roundedKg} kg`;
    }
  };

  // Get original input display (for tooltips/debugging)
  const getOriginalInputDisplay = (set: WorkoutSet): string => {
    if (set.input_unit === 'lbs') {
      return `${set.input_weight} lbs`;
    } else {
      return `${set.input_weight} kg`;
    }
  };

  // Get weight input value in the correct unit
  const getWeightInputValue = (): string => {
    if (!currentWeight) return '';

    const weightKg = parseFloat(currentWeight);
    if (isNaN(weightKg)) return currentWeight;

    if (unitSystem === 'imperial') {
      return kgToLbs(weightKg).toString();
    }
    return weightKg.toString();
  };

  // Handle weight input change with dual-unit storage
  const handleWeightInputChange = (value: string) => {
    if (!value) {
      setCurrentWeight('');
      return;
    }

    const numValue = parseFloat(value);
    if (isNaN(numValue)) return;

    if (unitSystem === 'imperial') {
      // Store lbs value directly, convert to kg for calculations
      const kgValue = lbsToKg(numValue);
      setCurrentWeight(kgValue.toString());
    } else {
      // Store kg value directly
      setCurrentWeight(value);
    }
  };

    // Render workout tracker content
  const renderWorkoutTracker = () => (
    <>
      {/* Workout Header */}
      <div className="workout-header">
        <div className="workout-timer">
          {formatTime(workoutDuration)}
        </div>

        <div className="workout-controls">
          <button className="workout-control" onClick={handlePauseResume}>
            <span className="workout-control__icon">{isPaused ? '▶' : '⏸'}</span>
          </button>
          <button
            className="workout-control workout-control--unit"
            onClick={() => setUnitSystem(prev => prev === 'metric' ? 'imperial' : 'metric')}
            title={`Switch to ${unitSystem === 'metric' ? 'lbs' : 'kg'}`}
          >
            <span className="workout-control__icon">
              {unitSystem === 'metric' ? '🇺🇸' : '🌍'}
            </span>
          </button>
          <button className="workout-control workout-control--finish" onClick={handleFinishWorkout}>
            <span className="workout-control__icon">🏁</span>
          </button>
        </div>
      </div>

      {/* Workout Content */}
      <div className="workout-content">
        {/* Show exercises that have sets */}
        {Object.entries(exerciseGroups).map(([exerciseName, sets]) => {
          // Find plan info for this exercise
          const planExercise = currentPlan?.days?.flatMap(day => day.exercises)?.find(ex => ex.name === exerciseName);

  return (
            <div key={exerciseName} className="exercise-card">
              <div className="exercise-header">
                <div className="exercise-title-container">
                  <h3 className="exercise-title">
                    <ExerciseName
                      name={exerciseName}
                      exercise_db_id={planExercise?.exercise_db_id}
                    />
                  </h3>
                  <button
                    className="exercise-action exercise-action--edit"
                    onClick={() => handleExerciseNameEdit(exerciseName)}
                    title="Edit exercise name"
                  >
                    ✏️
                  </button>
                </div>
                <div className="exercise-actions">
                  <button
                    className="exercise-action exercise-action--delete"
                    onClick={() => handleExerciseDelete(exerciseName)}
                    title="Delete exercise"
                  >
                    ×
                  </button>
                </div>
              </div>

              {/* Show plan info if available */}
              {planExercise && (
                <div className="exercise-plan-info">
                  <div className="plan-details">
                    <span className="plan-detail">
                      {planExercise.sets} sets • {planExercise.reps}
                    </span>
                  </div>
                </div>
              )}

              <div className="sets-container">
                <div className="sets-table">
                  <div className="sets-table-header">
                    <div className="sets-table-cell sets-table-cell--set">Set</div>
                    <div className="sets-table-cell sets-table-cell--weight">Weight</div>
                    <div className="sets-table-cell sets-table-cell--reps">Reps</div>
                    <div className="sets-table-cell sets-table-cell--actions">Actions</div>
                  </div>

                  {sets.map((set) => (
                    <div key={set.id} className={`sets-table-row ${set.isCompleted ? 'sets-table-row--completed' : ''}`}>
                      <div className="sets-table-cell sets-table-cell--set">
                        <div className="set-number">
                          {getSetNumber(exerciseName, set.id)}
                          {set.isPR && <span className="pr-badge">PR</span>}
                        </div>
                      </div>
                      <div className="sets-table-cell sets-table-cell--weight">
                        {formatWeight(set)}
                      </div>
                      <div className="sets-table-cell sets-table-cell--reps">
                        {set.reps}
                      </div>
                      <div className="sets-table-cell sets-table-cell--actions">
                        <button
                          className="set-action-button set-action-button--edit"
                          onClick={() => handleEditSet(set)}
                          title="Edit set"
                        >
                          ✏️
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="add-set-row">
                  <span className="add-set-label">Set</span>
                  <button className="add-button" onClick={() => handleAddSet(exerciseName)}>+</button>
                </div>
              </div>
            </div>
          );
        })}

        {/* Show exercises without sets */}
        {exercises.filter(ex => !workoutSets.some(set => set.exercise === ex)).map(exerciseName => {
          // Find plan info for this exercise
          const planExercise = currentPlan?.days?.flatMap(day => day.exercises)?.find(ex => ex.name === exerciseName);

          return (
            <div key={exerciseName} className="exercise-card">
              <div className="exercise-header">
                <div className="exercise-title-container">
                  <h3 className="exercise-title">
                    <ExerciseName
                      name={exerciseName}
                      exercise_db_id={planExercise?.exercise_db_id || exerciseDbIds[exerciseName]}
                    />
                  </h3>
                  <button
                    className="exercise-action exercise-action--edit"
                    onClick={() => handleExerciseNameEdit(exerciseName)}
                    title="Edit exercise name"
                  >
                    ✏️
                  </button>
                </div>
                <div className="exercise-actions">
                  <button
                    className="exercise-action exercise-action--delete"
                    onClick={() => handleExerciseDelete(exerciseName)}
                    title="Delete exercise"
                  >
                    ×
                  </button>
                </div>
              </div>

              {/* Show plan info if available */}
              {planExercise && (
                <div className="exercise-plan-info">
                  <div className="plan-details">
                    <span className="plan-detail">
                      {planExercise.sets} sets • {planExercise.reps}
                    </span>
                  </div>
                </div>
              )}

              <div className="add-set-row">
                <span className="add-set-label">Set</span>
                <button className="add-button" onClick={() => handleAddSet(exerciseName)}>+</button>
              </div>
            </div>
          );
        })}

        <div className="action-buttons">
          <button className="action-button action-button--exercise" onClick={handleAddExercise}>
            <span className="action-button__icon">+</span>
            Exercise
          </button>
        </div>
      </div>

      {/* Input Section */}
      {showKeypad && (
        <div className="input-section" id="input-section">
          <div className="input-header">
            <div className="input-fields">
              <div className={`input-field ${inputMode === "weight" ? "input-field--active" : ""}`}>
                <label className="input-label">Weight</label>
                <input
                  type="number"
                  inputMode="numeric"
                  value={getWeightInputValue()}
                  onChange={(e) => handleWeightInputChange(e.target.value)}
                  className="weight-input__field"
                  placeholder="0"
                  min="0"
                  step={unitSystem === 'imperial' ? "1" : "0.5"}
                  autoFocus={inputMode === "weight"}
                  onFocus={(e) => {
                    // Smooth scroll to input section when focused
                    const inputSection = document.getElementById('input-section');
                    if (inputSection) {
                      inputSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                    // Maintain focus on the input field
                    setTimeout(() => {
                      e.target.focus();
                    }, 100);
                  }}
                />
                <span className="weight-input__unit">
                  {unitSystem === 'imperial' ? 'lbs' : 'kg'}
                </span>
              </div>
              <div className={`input-field ${inputMode === "reps" ? "input-field--active" : ""}`}>
                <label className="input-label">Reps</label>
                <input
                  type="number"
                  inputMode="numeric"
                  value={currentReps}
                  onChange={(e) => {
                    // Only allow integers for reps
                    const value = e.target.value;
                    if (value === '' || /^\d+$/.test(value)) {
                      setCurrentReps(value);
                    }
                  }}
                  className="weight-input__field"
                  placeholder="0"
                  min="1"
                  step="1"
                  autoFocus={inputMode === "reps"}
                  onFocus={(e) => {
                    // Smooth scroll to input section when focused
                    const inputSection = document.getElementById('input-section');
                    if (inputSection) {
                      inputSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                    // Maintain focus on the input field
                    setTimeout(() => {
                      e.target.focus();
                    }, 100);
                  }}
                />
                <span className="weight-input__unit">reps</span>
            </div>
          </div>

            <div className="input-actions">
              <button className="done-button" onClick={handleDone}>
                ✓
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Exercise Search Modal for Workout Tab */}
      {showExerciseSearch && searchingDayIndex === -1 && (
        <div className="exercise-search-modal-overlay" onClick={() => {
          setShowExerciseSearch(false);
          setSearchingDayIndex(null);
          setSearchingExerciseIndex(null);
        }}>
          <div className="exercise-search-modal" onClick={(e) => e.stopPropagation()}>
            <div className="exercise-search-modal-header">
              <h3 className="exercise-search-modal-title">
                {searchingExerciseIndex === -1 ? 'Edit Exercise in Workout' : 'Add Exercise to Workout'}
              </h3>
              <button
                className="exercise-search-modal-close"
                onClick={() => {
                  setShowExerciseSearch(false);
                  setSearchingDayIndex(null);
                  setSearchingExerciseIndex(null);
                }}
              >
                ✕
              </button>
            </div>

            <div className="exercise-search-modal-content">
              <div className="exercise-search-input-container">
                {searchingExerciseIndex === -1 && (
                  <div className="exercise-edit-note">
                    Currently editing: <strong>{exerciseSearchQuery}</strong>
                  </div>
                )}
                <input
                  type="text"
                  className="exercise-search-input"
                  placeholder="Type exercise name (e.g., 'bench press', 'squat')"
                  value={exerciseSearchQuery}
                  onChange={(e) => handleExerciseSearchChange(e.target.value)}
                  autoFocus
                />
              </div>

              {exerciseSearchResults.length > 0 && (
                <div className="exercise-search-results">
                  <div className="exercise-search-results-header">
                    <span className="exercise-search-results-count">
                      {exerciseSearchResults.length} exercises found
                    </span>
                  </div>
                  <div className="exercise-search-results-list">
                    {exerciseSearchResults.map((exercise) => (
                      <div
                        key={exercise.id}
                        className="exercise-search-result-item"
                      >
                        <div className="exercise-search-result-content" onClick={() => handleSelectExerciseForPlan(exercise)}>
                          <div className="exercise-search-result-name">{exercise.name}</div>
                          <div className="exercise-search-result-details">
                            <span className="exercise-search-result-category">{exercise.category}</span>
                            <span className="exercise-search-result-equipment">{exercise.equipment}</span>
                          </div>
                          {exercise.instructions && exercise.instructions.length > 0 && (
                            <div className="exercise-search-result-preview">
                              {exercise.instructions[0].substring(0, 80)}...
                            </div>
                          )}
                        </div>
                        <div className="exercise-search-result-actions">
                          <button
                            className="exercise-search-result-action exercise-search-result-action--details"
                            onClick={() => handleViewExerciseDetails(exercise)}
                            title="View exercise details"
                          >
                            👁️
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {exerciseSearchQuery && exerciseSearchResults.length === 0 && (
                <div className="exercise-search-no-results">
                  <p>No exercises found for "{exerciseSearchQuery}"</p>
                  <p className="exercise-search-tip">
                    Try different keywords or browse by category
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );

    // Render current plan content
  const renderCurrentPlan = () => {
    console.log("Rendering plan, currentPlan:", currentPlan);
    console.log("Plan days:", currentPlan?.days);
    console.log("Plan exercises:", currentPlan?.days?.flatMap(day => day.exercises));

    return (
      <div className="plan-content">


        {currentPlan ? (
          <div className="plan-details">
            <h3 className="plan-name">{currentPlan.program_name || 'Unnamed Plan'}</h3>

            {currentPlan.days && currentPlan.days.length > 0 ? (
              currentPlan.days.map((day, dayIndex) => (
                <div key={dayIndex} className="plan-day-card">
                  <div className="plan-day-header">
                    <div className="plan-day-info">
                      <h4 className="plan-day-name">{day.weekday}</h4>
                      <span className="plan-day-focus">{day.focus}</span>
                      <span className="plan-day-time">{day.time}</span>
                    </div>
                    <div className="plan-day-actions">
                      <button
                        className="plan-day-action plan-day-action--edit"
                        onClick={() => handleEditDay(dayIndex)}
                        title="Edit day"
                      >
                        ✏️
                      </button>
                      <button
                        className="plan-day-action plan-day-action--delete"
                        onClick={() => handleDeleteDay(dayIndex)}
                        title="Delete day"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>

                  {day.exercises && day.exercises.length > 0 ? (
                    <div className="plan-day-exercises">
                      {day.exercises.map((exercise, exerciseIndex) => (
                        <div key={exerciseIndex} className="plan-exercise-card">
                          <div className="plan-exercise-header">
                            <h5 className="plan-exercise-name">
                              <ExerciseName
                                name={exercise.name}
                                exercise_db_id={exercise.exercise_db_id}
                                className="exercise-name-text"
                              />
                            </h5>
                          </div>
                          <div className="plan-exercise-details">
                            <div className="plan-set-detail">
                              <span className="plan-detail">
                                {exercise.sets} sets • {exercise.reps}
                              </span>
                            </div>
                          </div>
                          <div className="plan-exercise-actions">
                            <button
                              className="plan-exercise-action plan-exercise-action--edit"
                              onClick={() => handlePlanExerciseEdit(dayIndex, exerciseIndex)}
                              title="Edit exercise name"
                            >
                              ✏️
                            </button>
                            <button
                              className="plan-exercise-action plan-exercise-action--delete"
                              onClick={() => handleDeletePlanExercise(dayIndex, exerciseIndex)}
                              title="Delete exercise"
                            >
                              ×
                            </button>
                          </div>
                        </div>
                      ))}
                      <button
                        className="plan-add-exercise-button"
                        onClick={() => handleAddPlanExercise(dayIndex)}
                        title="Add new exercise to this day"
                      >
                        + Add Exercise
                      </button>
                    </div>
                  ) : (
                    <div className="empty-state">
                      <p>No exercises for this day.</p>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="empty-state">
                <p>Plan has no days defined.</p>
              </div>
            )}
          </div>
        ) : (
          <div className="empty-state">
            <p>No current workout plan found.</p>
            <p>Contact your trainer to get a plan assigned.</p>
          </div>
        )}

        {/* Schedule Request Section - Moved to bottom */}
        <div className="schedule-request-section">
          <div className="schedule-request-header">
            <h3 className="schedule-request-title">Request Plan Changes</h3>
            <p className="schedule-request-description">
              Ask your trainer to modify your workout plan, add exercises, or adjust training parameters.
            </p>
            <div className="schedule-request-tips">
              <p><strong>Tips for better results:</strong></p>
              <ul>
                <li>Specify days clearly (e.g., "Monday, Wednesday, Friday")</li>
                <li>Include duration (e.g., "30 min", "45 min", "1 hour")</li>
                <li>Mention focus areas (e.g., "upper body", "lower body", "strength")</li>
                <li>Example: "Create a 3-day plan for Mon/Wed/Fri with 30 min upper body workouts"</li>
              </ul>
            </div>
          </div>

          <div className="schedule-request-form">
            <textarea
              className="schedule-request-input"
              value={scheduleRequest}
              onChange={(e) => setScheduleRequest(e.target.value)}
              placeholder="e.g., 'Can we add more chest exercises on Monday?' or 'I want to focus more on strength training' or 'Please reduce the volume, I'm feeling fatigued'"
              rows={3}
              disabled={scheduleLoading}
            />
            <button
              className="schedule-request-button"
              onClick={handleScheduleRequest}
              disabled={!scheduleRequest.trim() || scheduleLoading}
            >
              {scheduleLoading ? 'Generating Plan...' : 'Send Request'}
            </button>

            {scheduleLoading && (
              <div className="schedule-loading-info">
                <p>AI is analyzing your request and generating a workout plan...</p>
                <p>This may take up to 2 minutes for complex requests.</p>
              </div>
            )}
          </div>
        </div>

        {/* Schedule History - Moved to bottom */}
        {scheduleHistory.length > 0 && (
          <div className="schedule-history-section">
            <h3 className="schedule-history-title">Recent Conversations</h3>
            <div className="schedule-history-list">
              {scheduleHistory.slice(0, 5).map((entry) => (
                <div key={entry.id} className="schedule-history-item">
                  <div className="schedule-history-request">
                    <div className="schedule-history-label">You:</div>
                    <div className="schedule-history-content">{entry.request}</div>
                    <div className="schedule-history-time">
                      {new Date(entry.timestamp).toLocaleDateString()} {new Date(entry.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                  <div className="schedule-history-response">
                    <div className="schedule-history-label">Trainer:</div>
                    <div className="schedule-history-content">{entry.response}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}



        {/* Exercise Search Modal for Plan Tab */}
        {showExerciseSearch && searchingDayIndex !== -1 && (
          <div className="exercise-search-modal-overlay" onClick={() => {
            setShowExerciseSearch(false);
            setSearchingDayIndex(null);
            setSearchingExerciseIndex(null);
          }}>
            <div className="exercise-search-modal" onClick={(e) => e.stopPropagation()}>
              <div className="exercise-search-modal-header">
                <h3 className="exercise-search-modal-title">
                  {searchingExerciseIndex !== null ? 'Edit Exercise in Plan' : 'Add Exercise to Plan'}
                </h3>
                <button
                  className="exercise-search-modal-close"
                  onClick={() => {
                    setShowExerciseSearch(false);
                    setSearchingDayIndex(null);
                    setSearchingExerciseIndex(null);
                  }}
                >
                  ✕
                </button>
              </div>

              <div className="exercise-search-modal-content">
                <div className="exercise-search-input-container">
                  {searchingExerciseIndex !== null && currentPlan && currentPlan.days && (
                    <div className="exercise-edit-note">
                      Currently editing: <strong>{currentPlan.days[searchingDayIndex!].exercises[searchingExerciseIndex].name}</strong>
                    </div>
                  )}
                  <input
                    type="text"
                    className="exercise-search-input"
                    placeholder="Type exercise name (e.g., 'bench press', 'squat')"
                    value={exerciseSearchQuery}
                    onChange={(e) => handleExerciseSearchChange(e.target.value)}
                    autoFocus
                  />
                </div>

                {exerciseSearchResults.length > 0 && (
                  <div className="exercise-search-results">
                    <div className="exercise-search-results-header">
                      <span className="exercise-search-results-count">
                        {exerciseSearchResults.length} exercises found
                      </span>
                    </div>
                    <div className="exercise-search-results-list">
                      {exerciseSearchResults.map((exercise) => (
                        <div
                          key={exercise.id}
                          className="exercise-search-result-item"
                        >
                          <div className="exercise-search-result-content" onClick={() => handleSelectExerciseForPlan(exercise)}>
                            <div className="exercise-search-result-name">{exercise.name}</div>
                            <div className="exercise-search-result-details">
                              <span className="exercise-search-result-category">{exercise.category}</span>
                              <span className="exercise-search-result-equipment">{exercise.equipment}</span>
                            </div>
                            {exercise.instructions && exercise.instructions.length > 0 && (
                              <div className="exercise-search-result-preview">
                                {exercise.instructions[0].substring(0, 80)}...
                              </div>
                            )}
                          </div>
                          <div className="exercise-search-result-actions">
                            <button
                              className="exercise-search-result-action exercise-search-result-action--details"
                              onClick={() => handleViewExerciseDetails(exercise)}
                              title="View exercise details"
                            >
                              👁️
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {exerciseSearchQuery && exerciseSearchResults.length === 0 && (
                  <div className="exercise-search-no-results">
                    <p>No exercises found for "{exerciseSearchQuery}"</p>
                    <p className="exercise-search-tip">
                      Try different keywords or browse by category
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

    // Render history/statistics content
  const renderHistory = () => {
    // Always show current workout sets grouped by exercise, regardless of backend history
    const currentWorkoutSessions = workoutSets.reduce((sessions, set) => {
      const today = new Date().toDateString();

      if (!sessions[today]) {
        sessions[today] = {
          date: today,
          sets: [],
          totalDuration: 0
        };
      }

      sessions[today].sets.push(set);
      return sessions;
    }, {} as Record<string, { date: string; sets: WorkoutSet[]; totalDuration: number }>);

    // Convert to array and sort by date (newest first)
    const sortedCurrentSessions = Object.values(currentWorkoutSessions)
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

    // Combine backend history with current session data
    const allSessions = [...sortedCurrentSessions];

    // Add backend history if available
    if (workoutHistory.length > 0) {
      workoutHistory.forEach(workout => {
        // Check if we already have a session for this date
        const existingSessionIndex = allSessions.findIndex(session =>
          new Date(session.date).toDateString() === new Date(workout.date).toDateString()
        );

        if (existingSessionIndex >= 0) {
          // Merge backend data with current session data
          const existingSession = allSessions[existingSessionIndex];
          // Add backend exercises to the existing session
          workout.exercises.forEach(backendExercise => {
            // Check if exercise already exists in current session
            const existingExercise = existingSession.sets.find(set => set.exercise === backendExercise.name);
            if (!existingExercise) {
              // Add placeholder set for backend exercise (since we don't have full set data)
              allSessions[existingSessionIndex].sets.push({
                id: `backend-${workout.id}-${backendExercise.name}`,
                exercise: backendExercise.name,
                weight: 0,
                input_weight: 0,
                input_unit: 'kg' as const,
                reps: 0,
                rpe: null,
                isCompleted: true,
                isPR: false,
                isBackendData: true // Flag to identify backend data
              });
            }
          });
        } else {
          // Create new session for backend data
          const backendSession = {
            date: workout.date,
            sets: workout.exercises.map(ex => ({
              id: `backend-${workout.id}-${ex.name}`,
              exercise: ex.name,
              weight: 0,
              input_weight: 0,
              input_unit: 'kg' as const,
              reps: 0,
              rpe: null,
              isCompleted: true,
              isPR: false,
              isBackendData: true
            })),
            totalDuration: workout.duration,
            isBackendData: true
          };
          allSessions.push(backendSession);
        }
      });
    }

    // Sort all sessions by date (newest first)
    allSessions.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

    return (
      <div className="history-content">
        <div className="history-header">
          <h2 className="history-title">Workout History</h2>
        </div>

        {allSessions.length > 0 ? (
          <div className="history-list">
            {allSessions.map((session, sessionIndex) => {
              // Group sets by exercise within this session
              const exerciseGroups: Record<string, { name: string; exercise_db_id?: string; sets: WorkoutSet[]; totalReps: number; maxWeight: number }> = {};

              session.sets.forEach(set => {
                if (!exerciseGroups[set.exercise]) {
                  // Try to find exercise_db_id from current plan
                  const planExercise = currentPlan?.days?.flatMap(day => day.exercises)?.find(ex => ex.name === set.exercise);

                  exerciseGroups[set.exercise] = {
                    name: set.exercise,
                    exercise_db_id: planExercise?.exercise_db_id,
                    sets: [],
                    totalReps: 0,
                    maxWeight: 0
                  };
                }

                exerciseGroups[set.exercise].sets.push(set);
                if (!set.isBackendData) {
                  exerciseGroups[set.exercise].totalReps += set.reps;
                  exerciseGroups[set.exercise].maxWeight = Math.max(exerciseGroups[set.exercise].maxWeight, set.weight);
                }
              });

              return (
                <div key={sessionIndex} className="history-card">
                  <div className="history-card-header">
                    <span className="history-date">{new Date(session.date).toLocaleDateString()}</span>
                    <span className="history-duration">
                      {session.sets.length > 0 ? `${session.sets.length} sets total` : '00:00:00'}
                    </span>
                  </div>

                  <div className="history-exercises">
                    {Object.values(exerciseGroups).map((exercise: { name: string; exercise_db_id?: string; sets: WorkoutSet[]; totalReps: number; maxWeight: number }, exerciseIndex) => (
                      <div key={exerciseIndex} className="history-exercise">
                        <span className="history-exercise-name">
                          <ExerciseName
                            name={exercise.name}
                            exercise_db_id={exercise.exercise_db_id}
                          />
                        </span>
                        <span className="history-exercise-stats">
                          {exercise.sets.length} sets
                          {!exercise.sets.some(set => set.isBackendData) && (
                            <>
                              • {exercise.totalReps} reps • {formatWeightFromKg(exercise.maxWeight)} max
                            </>
                          )}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="empty-state">
            <p>No workout history found.</p>
            <p>Complete your first workout to see it here!</p>
          </div>
        )}
      </div>
    );
  };

    return (
    <div className={`workout-app ${showKeypad ? 'keypad-active' : ''} ${isMainApp ? 'main-app' : ''}`}>
      {/* Tab Content */}
      {activeTab === 'workout' && renderWorkoutTracker()}
      {activeTab === 'plan' && renderCurrentPlan()}
      {activeTab === 'history' && renderHistory()}

            {/* Tab Navigation */}
      {!showKeypad && (
        <div className="tab-navigation">
          <button
            className={`tab-button ${activeTab === 'plan' ? 'tab-button--active' : ''}`}
            onClick={() => {
              setActiveTab('plan');
              setShowKeypad(false);
            }}
          >
            Plan
          </button>
          <button
            className={`tab-button ${activeTab === 'workout' ? 'tab-button--active' : ''}`}
            onClick={() => {
              setActiveTab('workout');
              setShowKeypad(false);
            }}
          >
            Workout
          </button>
          <button
            className={`tab-button ${activeTab === 'history' ? 'tab-button--active' : ''}`}
            onClick={() => {
              setActiveTab('history');
              setShowKeypad(false);
            }}
          >
            History
          </button>
        </div>
      )}

      {/* Exercise Help Modal */}
      {showExerciseModal && exerciseModalData && (
        <div className="exercise-modal-overlay" onClick={() => setShowExerciseModal(false)}>
          <div className="exercise-modal" onClick={(e) => e.stopPropagation()}>
            <div className="exercise-modal-header">
              <h3 className="exercise-modal-title">{exerciseModalData.name}</h3>
              <button
                className="exercise-modal-close"
                onClick={() => setShowExerciseModal(false)}
              >
                ✕
              </button>
            </div>

            <div className="exercise-modal-content">
              {/* Exercise GIF */}
              {exerciseModalData.gifUrl && (
                <div className="exercise-gif-container">
                  <img
                    src={exerciseModalData.gifUrl}
                    alt={exerciseModalData.name}
                    className="exercise-gif"
                  />
                </div>
              )}

              {/* Exercise Details */}
              <div className="exercise-details">
                <div className="exercise-detail-row">
                  <span className="exercise-detail-label">Target:</span>
                  <span className="exercise-detail-value">{exerciseModalData.targetMuscles?.join(', ') || 'N/A'}</span>
                </div>
                <div className="exercise-detail-row">
                  <span className="exercise-detail-label">Body Part:</span>
                  <span className="exercise-detail-value">{exerciseModalData.bodyParts?.join(', ') || 'N/A'}</span>
                </div>
                <div className="exercise-detail-row">
                  <span className="exercise-detail-label">Equipment:</span>
                  <span className="exercise-detail-value">{exerciseModalData.equipments?.join(', ') || 'N/A'}</span>
                </div>
                {exerciseModalData.secondaryMuscles && exerciseModalData.secondaryMuscles.length > 0 && (
                  <div className="exercise-detail-row">
                    <span className="exercise-detail-label">Secondary:</span>
                    <span className="exercise-detail-value">{exerciseModalData.secondaryMuscles.join(', ')}</span>
                  </div>
                )}
              </div>

              {/* Instructions */}
              {exerciseModalData.instructions && exerciseModalData.instructions.length > 0 && (
                <div className="exercise-instructions">
                  <h4 className="instructions-title">Instructions:</h4>
                  <ol className="instructions-list">
                    {exerciseModalData.instructions.map((instruction, index) => (
                      <li key={index} className="instruction-item">
                        {instruction.replace(/^Step:\d+\s*/, '')}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
