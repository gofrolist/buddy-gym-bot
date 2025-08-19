import React, { useEffect, useMemo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Button, Input } from "./components/ui";

declare global {
  interface Window { Telegram: any }
}

interface Exercise {
  id: string;
  name: string;
}

interface SetData {
  exercise: string;
  weight: number;
  reps: number;
}

interface WorkoutSet {
  id: string;
  exercise: string;
  weight: number;
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
      target: string;
      sets: {
        load?: string;
        reps?: string;
        rest_sec?: number;
      }[];
      equipment_ok?: string[];
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
  return Math.round(kg * 2.20462 * 10) / 10; // Round to 1 decimal place
}

// Function to convert lbs to kg
function lbsToKg(lbs: number): number {
  return Math.round(lbs * 0.453592 * 10) / 10; // Round to 1 decimal place
}

function tgUser() {
  try {
    return window.Telegram?.WebApp?.initDataUnsafe?.user;
  } catch {
    return null;
  }
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

  // Plan and history data
  const [currentPlan, setCurrentPlan] = useState<WorkoutPlan | null>(null);
  const [workoutHistory, setWorkoutHistory] = useState<WorkoutHistory[]>([]);

  // Unit system state
  const [unitSystem, setUnitSystem] = useState<UnitSystem>(() => detectUnitSystem());

  // UI state
  const [suggestions, setSuggestions] = useState<Exercise[]>([]);
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
    const lc = user?.language_code?.slice(0, 2) || "en";
    i18n.changeLanguage(lc);

    try {
      window.Telegram?.WebApp?.expand?.();
    } catch {}

    // Load initial data
    fetchCurrentPlan();
    fetchWorkoutHistory();

    // Load saved workout state
    loadWorkoutState();
  }, [user, i18n, loadWorkoutState]);

  // Auto-populate workout with plan exercises when plan is loaded
  useEffect(() => {
    if (currentPlan && currentPlan.days && currentPlan.days.length > 0) {
      // Get today's workout or first available workout
      const today = new Date().toLocaleDateString('en-US', { weekday: 'short' });
      const todayWorkout = currentPlan.days.find(day =>
        day.weekday === today
      ) || currentPlan.days[0]; // Fallback to first day if today not found

      if (todayWorkout && todayWorkout.exercises) {
        // Extract unique exercise names from the plan and clean them for API calls
        const planExercises = todayWorkout.exercises.map(ex => {
          // Keep original name for display, but also store cleaned version for API calls
          const cleanedName = cleanExerciseName(ex.name);
          console.log(`Exercise: "${ex.name}" -> cleaned: "${cleanedName}"`);
          return ex.name; // Keep original name for display
        });
        setExercises(planExercises);

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
    if (!user?.id) return;

    try {
      const response = await fetch(`/api/v1/plan/current?tg_user_id=${user.id}`, {
        headers: { "Content-Type": "application/json" },
      });

      if (response.ok) {
        const data = await response.json();
        console.log("Plan API response:", data);
        if (data.success && data.plan) {
          console.log("Setting current plan:", data.plan);
          setCurrentPlan(data.plan);
        } else {
          console.log("No plan data or API not successful");
        }
      }
    } catch (error) {
      console.error("Error fetching current plan:", error);
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

  // Search exercises with debouncing
  const queryExercises = useCallback(async (query: string) => {
    if (!query.trim()) {
      setSuggestions([]);
      return;
    }

    try {
      console.log("Querying exercises:", query);
      const resp = await fetch(`/api/v1/exercises/search?q=${encodeURIComponent(query)}`);

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      }

      const data = await resp.json();
      setSuggestions(data.items || []);
    } catch (error) {
      console.error("Exercise search failed:", error);
      setSuggestions([]);
    }
  }, []);

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
    const exerciseName = prompt("Enter exercise name:");
    if (exerciseName && exerciseName.trim()) {
      setExercises(prev => [...prev, exerciseName.trim()]);
    }
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

  // Extract key components from exercise name for targeted searches
  const extractExerciseComponents = (exerciseName: string) => {
    const name = exerciseName.toLowerCase();

    // Common equipment types
    const equipment = name.includes('barbell') ? 'barbell' :
                     name.includes('dumbbell') ? 'dumbbell' :
                     name.includes('cable') ? 'cable' :
                     name.includes('machine') ? 'machine' :
                     name.includes('band') ? 'band' :
                     name.includes('smith') ? 'smith machine' : null;

    // Common body parts
    const bodyPart = name.includes('bench') || name.includes('chest') ? 'chest' :
                     name.includes('squat') || name.includes('leg') ? 'upper legs' :
                     name.includes('deadlift') || name.includes('back') ? 'back' :
                     name.includes('row') ? 'back' :
                     name.includes('press') ? 'shoulders' :
                     name.includes('curl') ? 'upper arms' : null;

    // Common muscles
    const muscle = name.includes('bench') ? 'pectorals' :
                   name.includes('squat') ? 'quadriceps' :
                   name.includes('deadlift') ? 'glutes' :
                   name.includes('row') ? 'lats' :
                   name.includes('press') ? 'deltoids' :
                   name.includes('curl') ? 'biceps' : null;

    return { equipment, bodyPart, muscle };
  };

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

  // Helper function to search by equipment
  const searchByEquipment = async (equipment: string, exerciseName: string): Promise<ExerciseDBData | null> => {
    try {
      const response = await fetch(`https://www.exercisedb.dev/api/v1/equipments/${encodeURIComponent(equipment)}/exercises`);
      if (response.ok) {
        const data = await response.json();
        if (data && data.success && data.data && data.data.length > 0) {
          // Find best match from equipment-specific results
          const bestMatch = data.data.find((ex: ExerciseDBData) =>
            ex.name.toLowerCase().includes(exerciseName.toLowerCase()) ||
            exerciseName.toLowerCase().includes(ex.name.toLowerCase())
          );
          return bestMatch || data.data[0];
        }
      }
    } catch (error) {
      console.log(`Equipment search failed for "${equipment}":`, error);
    }
    return null;
  };

  // Helper function to search by body part
  const searchByBodyPart = async (bodyPart: string, exerciseName: string): Promise<ExerciseDBData | null> => {
    try {
      const response = await fetch(`https://www.exercisedb.dev/api/v1/bodyparts/${encodeURIComponent(bodyPart)}/exercises`);
      if (response.ok) {
        const data = await response.json();
        if (data && data.success && data.data && data.data.length > 0) {
          // Find best match from body part results
          const bestMatch = data.data.find((ex: ExerciseDBData) =>
            ex.name.toLowerCase().includes(exerciseName.toLowerCase()) ||
            exerciseName.toLowerCase().includes(ex.name.toLowerCase())
          );
          return bestMatch || data.data[0];
        }
      }
    } catch (error) {
      console.log(`Body part search failed for "${bodyPart}":`, error);
    }
    return null;
  };

  // Helper function to search by muscle
  const searchByMuscle = async (muscle: string, exerciseName: string): Promise<ExerciseDBData | null> => {
    try {
      const response = await fetch(`https://www.exercisedb.dev/api/v1/muscles/${encodeURIComponent(muscle)}/exercises`);
      if (response.ok) {
        const data = await response.json();
        if (data && data.success && data.data && data.data.length > 0) {
          // Find best match from muscle results
          const bestMatch = data.data.find((ex: ExerciseDBData) =>
            ex.name.toLowerCase().includes(exerciseName.toLowerCase()) ||
            exerciseName.toLowerCase().includes(ex.name.toLowerCase())
          );
          return bestMatch || data.data[0];
        }
      }
    } catch (error) {
      console.log(`Muscle search failed for "${muscle}":`, error);
    }
    return null;
  };

  // Handle exercise help (ExerciseDB API)
  const handleExerciseHelp = async (exerciseName: string) => {
    try {

      // Clean the exercise name for better search (keep equipment info)
      const cleanedName = cleanExerciseName(exerciseName);
      console.log(`Searching for exercise: "${exerciseName}" (cleaned: "${cleanedName}")`);

      // Use the correct ExerciseDB search API
      const searchEndpoint = `https://www.exercisedb.dev/api/v1/exercises/search?q=${encodeURIComponent(cleanedName)}&limit=10`;

      const response = await fetch(searchEndpoint, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
        mode: 'cors'
      });

      if (response.ok) {
                const data = await response.json();
        console.log(`Search results for "${cleanedName}":`, data);

        if (data && data.success && data.data && data.data.length > 0) {
          // Find the best match from the search results
          let bestMatch = data.data[0];

          // Try to find exact match first
          const exactMatch = data.data.find((ex: ExerciseDBData) =>
            ex.name.toLowerCase().includes(cleanedName.toLowerCase()) ||
            cleanedName.toLowerCase().includes(ex.name.toLowerCase())
          );

          if (exactMatch) {
            bestMatch = exactMatch;
          }

          // Use the correct field names from the API response
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
              const fallbackData = await fallbackResponse.json();
              if (fallbackData && fallbackData.success && fallbackData.data && fallbackData.data.length > 0) {
                                const fallbackExercise = fallbackData.data[0];
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

  // Handle exercise name editing (when clicking on exercise title)
  const handleExerciseNameEdit = (exerciseName: string) => {
    const newName = prompt(`Enter new name for "${exerciseName}":`, exerciseName);
    if (newName && newName.trim() && newName !== exerciseName) {
      setExercises(prev => prev.map(ex => ex === exerciseName ? newName.trim() : ex));
      // Also update workout sets if they exist
      setWorkoutSets(prev => prev.map(set =>
        set.exercise === exerciseName ? { ...set, exercise: newName.trim() } : set
      ));
    }
  };

  // Handle exercise deletion (when clicking on delete button)
  const handleExerciseDelete = (exerciseName: string) => {
    if (confirm(`Are you sure you want to delete "${exerciseName}"?`)) {
      setExercises(prev => prev.filter(ex => ex !== exerciseName));
      // Also remove workout sets for this exercise
      setWorkoutSets(prev => prev.filter(set => set.exercise !== exerciseName));
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
        // Add new set
        const newSet: WorkoutSet = {
          id: Date.now().toString(),
          exercise: currentExercise,
          weight,
          reps,
          rpe: null,
          isCompleted: false,
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

  // Handle completing a set
  const handleCompleteSet = async (setId: string) => {
    setWorkoutSets(prev => {
      const updated = prev.map(set =>
        set.id === setId
          ? { ...set, isCompleted: !set.isCompleted }
          : set
      );

      // Save to API when set is completed
      const updatedSet = updated.find(set => set.id === setId);
      if (updatedSet) {
        saveSetToAPI(updatedSet);
      }

      return updated;
    });
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
          is_completed: set.isCompleted,
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

  // Handle editing exercise name in plan
  const handlePlanExerciseEdit = (dayIndex: number, exerciseIndex: number) => {
    if (!currentPlan || !currentPlan.days) return;

    const exercise = currentPlan.days[dayIndex].exercises[exerciseIndex];
    const newName = prompt(`Enter new name for "${exercise.name}":`, exercise.name);

    if (newName && newName.trim() && newName !== exercise.name) {
      // Update the plan state
      setCurrentPlan(prev => {
        if (!prev || !prev.days) return prev;

        const updated = { ...prev };
        updated.days![dayIndex].exercises[exerciseIndex].name = newName.trim();
        return updated;
      });

      // Also update workout exercises if they match
      setExercises(prev => prev.map(ex => ex === exercise.name ? newName.trim() : ex));
      setWorkoutSets(prev => prev.map(set =>
        set.exercise === exercise.name ? { ...set, exercise: newName.trim() } : set
      ));
    }
  };

  // Handle editing exercise target in plan
  const handlePlanExerciseTargetEdit = (dayIndex: number, exerciseIndex: number) => {
    if (!currentPlan || !currentPlan.days) return;

    const exercise = currentPlan.days[dayIndex].exercises[exerciseIndex];
    const newTarget = prompt(`Enter new target for "${exercise.name}":`, exercise.target);

    if (newTarget && newTarget.trim() && newTarget !== exercise.target) {
      setCurrentPlan(prev => {
        if (!prev || !prev.days) return prev;

        const updated = { ...prev };
        updated.days![dayIndex].exercises[exerciseIndex].target = newTarget.trim();
        return updated;
      });
    }
  };

  // Handle editing set details in plan
  const handlePlanSetEdit = (dayIndex: number, exerciseIndex: number, setIndex: number) => {
    if (!currentPlan || !currentPlan.days) return;

    const set = currentPlan.days[dayIndex].exercises[exerciseIndex].sets[setIndex];
    const newLoad = prompt(`Enter new load for set ${setIndex + 1}:`, set.load || '');
    const newReps = prompt(`Enter new reps for set ${setIndex + 1}:`, set.reps || '');
    const newRest = prompt(`Enter new rest time (seconds) for set ${setIndex + 1}:`, set.rest_sec?.toString() || '');

    if (newLoad !== null || newReps !== null || newRest !== null) {
      setCurrentPlan(prev => {
        if (!prev || !prev.days) return prev;

        const updated = { ...prev };
        const targetSet = updated.days![dayIndex].exercises[exerciseIndex].sets[setIndex];

        if (newLoad !== null && newLoad.trim()) targetSet.load = newLoad.trim();
        if (newReps !== null && newReps.trim()) targetSet.reps = newReps.trim();
        if (newRest !== null && newRest.trim()) targetSet.rest_sec = parseInt(newRest) || 0;

        return updated;
      });
    }
  };

  // Handle adding new exercise to a day
  const handleAddPlanExercise = (dayIndex: number) => {
    if (!currentPlan || !currentPlan.days) return;

    const exerciseName = prompt("Enter exercise name:");
    if (exerciseName && exerciseName.trim()) {
      const target = prompt("Enter target muscles:");
      const load = prompt("Enter load (e.g., 'moderate', 'heavy'):");
      const reps = prompt("Enter reps (e.g., '3x8-10'):");
      const rest = prompt("Enter rest time in seconds:");

      if (exerciseName.trim()) {
        setCurrentPlan(prev => {
          if (!prev || !prev.days) return prev;

          const updated = { ...prev };
          const newExercise = {
            name: exerciseName.trim(),
            target: target?.trim() || '',
            sets: [{
              load: load?.trim() || '',
              reps: reps?.trim() || '',
              rest_sec: parseInt(rest || '60') || 60
            }],
            equipment_ok: []
          };

          updated.days![dayIndex].exercises.push(newExercise);
          return updated;
        });

        // Also add to workout exercises if not already there
        setExercises(prev => {
          if (!prev.includes(exerciseName.trim())) {
            return [...prev, exerciseName.trim()];
          }
          return prev;
        });
      }
    }
  };

  // Handle adding new set to an exercise
  const handleAddPlanSet = (dayIndex: number, exerciseIndex: number) => {
    if (!currentPlan || !currentPlan.days) return;

    const load = prompt("Enter load (e.g., 'moderate', 'heavy'):");
    const reps = prompt("Enter reps (e.g., '3x8-10'):");
    const rest = prompt("Enter rest time in seconds:");

    if (load?.trim() || reps?.trim()) {
      setCurrentPlan(prev => {
        if (!prev || !prev.days) return prev;

        const updated = { ...prev };
        const newSet = {
          load: load?.trim() || '',
          reps: reps?.trim() || '',
          rest_sec: parseInt(rest || '60') || 60
        };

        updated.days![dayIndex].exercises[exerciseIndex].sets.push(newSet);
        return updated;
      });
    }
  };

  // Handle deleting exercise from plan
  const handleDeletePlanExercise = (dayIndex: number, exerciseIndex: number) => {
    if (!currentPlan || !currentPlan.days) return;

    const exercise = currentPlan.days[dayIndex].exercises[exerciseIndex];
    if (confirm(`Are you sure you want to delete "${exercise.name}" from the plan?`)) {
      setCurrentPlan(prev => {
        if (!prev || !prev.days) return prev;

        const updated = { ...prev };
        updated.days![dayIndex].exercises.splice(exerciseIndex, 1);
        return updated;
      });
    }
  };

  // Handle deleting set from plan
  const handleDeletePlanSet = (dayIndex: number, exerciseIndex: number, setIndex: number) => {
    if (!currentPlan || !currentPlan.days) return;

    if (confirm(`Are you sure you want to delete set ${setIndex + 1}?`)) {
      setCurrentPlan(prev => {
        if (!prev || !prev.days) return prev;

        const updated = { ...prev };
        updated.days![dayIndex].exercises[exerciseIndex].sets.splice(setIndex, 1);
        return updated;
      });
    }
  };

  // Handle schedule request
  const handleScheduleRequest = async () => {
    if (!scheduleRequest.trim() || !user?.id) return;

    setScheduleLoading(true);

    try {
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
        })
      });

      if (response.ok) {
        const data = await response.json();

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
          setCurrentPlan(data.plan);
          // Also update the workout tab exercises if they exist
          if (data.plan.days && data.plan.days.length > 0) {
            const today = new Date().toLocaleDateString('en-US', { weekday: 'short' });
            const todayWorkout = data.plan.days.find(day => day.weekday === today);
            if (todayWorkout && todayWorkout.exercises) {
              setExercises(todayWorkout.exercises.map(ex => ex.name));
            }
          }
        }

        // Show success message
        alert(`Request sent successfully!\n\nResponse: ${newEntry.response}`);
      } else {
        const errorData = await response.json().catch(() => ({}));
        alert(`Failed to send request: ${errorData.message || response.statusText}`);
      }
    } catch (error) {
      console.error('Error sending schedule request:', error);
      alert('Failed to send request. Please check your connection and try again.');
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

  // Format weight display with correct unit
  const formatWeight = (weightKg: number): string => {
    if (unitSystem === 'imperial') {
      const lbs = kgToLbs(weightKg);
      return `${lbs} lbs`;
    }
    return `${weightKg} kg`;
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

  // Handle weight input change with unit conversion
  const handleWeightInputChange = (value: string) => {
    if (!value) {
      setCurrentWeight('');
      return;
    }

    const numValue = parseFloat(value);
    if (isNaN(numValue)) return;

    if (unitSystem === 'imperial') {
      // Convert lbs to kg for storage
      const kgValue = lbsToKg(numValue);
      setCurrentWeight(kgValue.toString());
    } else {
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
                  <h3 className="exercise-title">{exerciseName}</h3>
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
                    className="exercise-action"
                    onClick={() => handleExerciseHelp(exerciseName)}
                    title="Get exercise help"
                  >
                    ?
                  </button>
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
                  {planExercise.sets && planExercise.sets.length > 0 && (
                    <div className="plan-details">
                      {planExercise.sets.map((set, index) => (
                        <span key={index} className="plan-detail">
                          {set.reps && `${set.reps} reps`}
                          {set.rest_sec && set.reps && ' • '}
                          {set.rest_sec && `${set.rest_sec}s rest`}
                        </span>
                      ))}
                    </div>
                  )}
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
                        {formatWeight(set.weight)}
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
                        <button
                          className={`set-action-button set-action-button--complete ${set.isCompleted ? 'completed' : ''}`}
                          onClick={() => handleCompleteSet(set.id)}
                          title={set.isCompleted ? "Set completed" : "Mark set as complete"}
                        >
                          {set.isCompleted ? '✓' : '○'}
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
                  <h3 className="exercise-title">{exerciseName}</h3>
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
                    className="exercise-action"
                    onClick={() => handleExerciseHelp(exerciseName)}
                    title="Get exercise help"
                  >
                    ?
                  </button>
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
                  {planExercise.sets && planExercise.sets.length > 0 && (
                    <div className="plan-details">
                      {planExercise.sets.map((set, index) => (
                        <span key={index} className="plan-detail">
                          {set.reps && `${set.reps} reps`}
                          {set.rest_sec && set.reps && ' • '}
                          {set.rest_sec && `${set.rest_sec}s rest`}
                        </span>
                      ))}
                    </div>
                  )}
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
                  onChange={(e) => setCurrentReps(e.target.value)}
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
    </>
  );

    // Render current plan content
  const renderCurrentPlan = () => {
    console.log("Rendering plan, currentPlan:", currentPlan);

    return (
      <div className="plan-content">
        <div className="plan-header">
          <h2 className="plan-title">Current Workout Plan</h2>
        </div>

        {currentPlan ? (
          <div className="plan-details">
            <h3 className="plan-name">{currentPlan.program_name || 'Unnamed Plan'}</h3>

            {currentPlan.days && currentPlan.days.length > 0 ? (
              currentPlan.days.map((day, dayIndex) => (
                <div key={dayIndex} className="plan-day-card">
                  <div className="plan-day-header">
                    <h4 className="plan-day-name">{day.weekday}</h4>
                    <span className="plan-day-focus">{day.focus}</span>
                    <span className="plan-day-time">{day.time}</span>
                  </div>

                  {day.exercises && day.exercises.length > 0 ? (
                    <div className="plan-day-exercises">
                      {day.exercises.map((exercise, exerciseIndex) => (
                        <div key={exerciseIndex} className="plan-exercise-card">
                          <div className="plan-exercise-header">
                            <h5 className="plan-exercise-name">{exercise.name}</h5>
                            <span className="plan-exercise-target">{exercise.target}</span>
                          </div>
                          <div className="plan-exercise-details">
                            {exercise.sets.map((set, setIndex) => (
                              <div key={setIndex} className="plan-set-detail">
                                <span className="plan-detail">
                                  {set.load && `${set.load} load`}
                                  {set.reps && ` • ${set.reps} reps`}
                                  {set.rest_sec && ` • ${set.rest_sec}s rest`}
                                </span>
                                <button
                                  className="plan-set-action plan-set-action--edit"
                                  onClick={() => handlePlanSetEdit(dayIndex, exerciseIndex, setIndex)}
                                  title="Edit set"
                                >
                                  ✏️
                                </button>
                                <button
                                  className="plan-set-action plan-set-action--delete"
                                  onClick={() => handleDeletePlanSet(dayIndex, exerciseIndex, setIndex)}
                                  title="Delete set"
                                >
                                  ×
                                </button>
                              </div>
                            ))}
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
                              className="plan-exercise-action plan-exercise-action--target"
                              onClick={() => handlePlanExerciseTargetEdit(dayIndex, exerciseIndex)}
                              title="Edit exercise target"
                            >
                              ⚙️
                            </button>
                            <button
                              className="plan-exercise-action plan-exercise-action--add-set"
                              onClick={() => handleAddPlanSet(dayIndex, exerciseIndex)}
                              title="Add new set"
                            >
                              +
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
              {scheduleLoading ? 'Sending...' : 'Send Request'}
            </button>
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
              const exerciseGroups: Record<string, { name: string; sets: WorkoutSet[]; totalReps: number; maxWeight: number }> = {};

              session.sets.forEach(set => {
                if (!exerciseGroups[set.exercise]) {
                  exerciseGroups[set.exercise] = {
                    name: set.exercise,
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
                    {Object.values(exerciseGroups).map((exercise: { name: string; sets: WorkoutSet[]; totalReps: number; maxWeight: number }, exerciseIndex) => (
                      <div key={exerciseIndex} className="history-exercise">
                        <span className="history-exercise-name">{exercise.name}</span>
                        <span className="history-exercise-stats">
                          {exercise.sets.length} sets
                          {!exercise.sets.some(set => set.isBackendData) && (
                            <>
                              • {exercise.totalReps} reps • {formatWeight(exercise.maxWeight)} max
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
