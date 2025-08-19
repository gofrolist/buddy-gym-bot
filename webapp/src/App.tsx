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
}

interface WorkoutPlan {
  id: string;
  name: string;
  exercises: {
    name: string;
    sets: number;
    reps: string;
    weight?: string;
  }[];
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

  // UI state
  const [suggestions, setSuggestions] = useState<Exercise[]>([]);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

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
  }, [user, i18n]);

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

  // Handle adding new set
  const handleAddSet = (exerciseName: string) => {
    setCurrentExercise(exerciseName);
    setCurrentWeight("");
    setCurrentReps("");
    setCurrentRPE("");
    setInputMode("weight");
    setShowKeypad(true);
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

  // Switch between weight, reps, and RPE input
  const switchInputMode = () => {
    if (inputMode === "weight" && currentWeight) {
      setInputMode("reps");
    } else if (inputMode === "reps" && currentReps) {
      setInputMode("rpe");
    } else if (inputMode === "rpe" && currentRPE) {
      // All fields filled, ready to save
      handleDone();
    }
  };

  const handleDone = () => {
    console.log("HandleDone called:", { currentWeight, currentReps, currentRPE, currentExercise, editingSetId });

    if (currentWeight && currentReps) {
      const weight = parseFloat(currentWeight);
      const reps = parseInt(currentReps);
      const rpe = currentRPE ? parseFloat(currentRPE) : null;

      console.log("Parsed values:", { weight, reps, rpe });

      if (editingSetId) {
        // Update existing set
        setWorkoutSets(prev => prev.map(set =>
          set.id === editingSetId
            ? { ...set, weight, reps, rpe }
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
          rpe,
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
      setCurrentRPE("");
      setInputMode("weight");
    } else {
      console.log("Missing values:", { currentWeight, currentReps, currentRPE });
      // If we have weight but no reps, switch to reps input
      if (currentWeight && !currentReps) {
        setInputMode("reps");
      } else if (currentReps && !currentRPE) {
        setInputMode("rpe");
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
          rpe: set.rpe, // Include RPE in the payload
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
          <button className="workout-control">
            <span className="workout-control__icon">⚙</span>
          </button>
          <button className="workout-control workout-control--finish" onClick={handleFinishWorkout}>
            <span className="workout-control__icon">🏁</span>
          </button>
        </div>
      </div>

      {/* Workout Content */}
      <div className="workout-content">
        {/* Show exercises that have sets */}
        {Object.entries(exerciseGroups).map(([exerciseName, sets]) => (
          <div key={exerciseName} className="exercise-card">
            <div className="exercise-header">
              <h3 className="exercise-title">{exerciseName}</h3>
              <div className="exercise-actions">
                <button className="exercise-action">?</button>
                <button className="exercise-action">⋮</button>
              </div>
            </div>

            <div className="sets-container">
              <div className="sets-table">
                <div className="sets-table-header">
                  <div className="sets-table-cell sets-table-cell--set">Set</div>
                  <div className="sets-table-cell sets-table-cell--weight">Weight</div>
                  <div className="sets-table-cell sets-table-cell--reps">Reps</div>
                  <div className="sets-table-cell sets-table-cell--rpe">RPE</div>
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
                      {set.weight} kg
                    </div>
                    <div className="sets-table-cell sets-table-cell--reps">
                      {set.reps}
                    </div>
                    <div className="sets-table-cell sets-table-cell--rpe">
                      {set.rpe !== null ? set.rpe : '-'}
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
        ))}

        {/* Show exercises without sets */}
        {exercises.filter(ex => !workoutSets.some(set => set.exercise === ex)).map(exerciseName => (
          <div key={exerciseName} className="exercise-card">
            <div className="exercise-header">
              <h3 className="exercise-title">{exerciseName}</h3>
              <div className="exercise-actions">
                <button className="exercise-action">?</button>
                <button className="exercise-action">⋮</button>
              </div>
            </div>

            <div className="add-set-row">
              <span className="add-set-label">Set</span>
              <button className="add-button" onClick={() => handleAddSet(exerciseName)}>+</button>
            </div>
          </div>
        ))}

        <div className="action-buttons">
          <button className="action-button action-button--exercise" onClick={handleAddExercise}>
            <span className="action-button__icon">+</span>
            Exercise
          </button>
        </div>
      </div>

      {/* Input Section */}
      {showKeypad && (
        <div className="input-section">
          <div className="input-header">
            <div className="input-fields">
              <div className={`input-field ${inputMode === "weight" ? "input-field--active" : ""}`}>
                <label className="input-label">Weight</label>
                <input
                  type="number"
                  inputMode="numeric"
                  value={currentWeight}
                  onChange={(e) => setCurrentWeight(e.target.value)}
                  className="weight-input__field"
                  placeholder="0"
                  min="0"
                  step="0.5"
                  autoFocus={inputMode === "weight"}
                />
                <span className="weight-input__unit">kg</span>
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
                />
                <span className="weight-input__unit">reps</span>
              </div>
              <div className={`input-field ${inputMode === "rpe" ? "input-field--active" : ""}`}>
                <label className="input-label">RPE</label>
                <div className="rpe-picker">
                  <button
                    className="rpe-picker-button rpe-picker-button--decrease"
                    onClick={() => {
                      const current = parseInt(currentRPE) || 7;
                      if (current > 5) {
                        setCurrentRPE((current - 1).toString());
                      }
                    }}
                  >
                    −
                  </button>
                  <div className="rpe-picker-value">
                    {currentRPE || '7'}
                  </div>
                  <button
                    className="rpe-picker-button rpe-picker-button--increase"
                    onClick={() => {
                      const current = parseInt(currentRPE) || 7;
                      if (current < 10) {
                        setCurrentRPE((current + 1).toString());
                      }
                    }}
                  >
                    +
                  </button>
                </div>
                <span className="weight-input__unit">RPE</span>
              </div>
            </div>

            <div className="input-actions">
              <button className="cancel-button" onClick={() => setShowKeypad(false)}>
                Cancel
              </button>
              <button className="done-button" onClick={handleDone}>
                Done
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
            <h3 className="plan-name">{currentPlan.name || 'Unnamed Plan'}</h3>

            {currentPlan.exercises && currentPlan.exercises.length > 0 ? (
              currentPlan.exercises.map((exercise, index) => (
                <div key={index} className="plan-exercise-card">
                  <div className="plan-exercise-header">
                    <h4 className="plan-exercise-name">{exercise.name}</h4>
                  </div>
                  <div className="plan-exercise-details">
                    <span className="plan-detail">Sets: {exercise.sets}</span>
                    <span className="plan-detail">Reps: {exercise.reps}</span>
                    {exercise.weight && <span className="plan-detail">Weight: {exercise.weight}</span>}
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-state">
                <p>Plan has no exercises defined.</p>
              </div>
            )}
          </div>
        ) : (
          <div className="empty-state">
            <p>No current workout plan found.</p>
            <p>Contact your trainer to get a plan assigned.</p>
          </div>
        )}
      </div>
    );
  };

  // Render history/statistics content
  const renderHistory = () => (
    <div className="history-content">
      <div className="history-header">
        <h2 className="history-title">Workout History</h2>
      </div>

      {workoutHistory.length > 0 ? (
        <div className="history-list">
          {workoutHistory.map((workout) => (
            <div key={workout.id} className="history-card">
              <div className="history-card-header">
                <span className="history-date">{new Date(workout.date).toLocaleDateString()}</span>
                <span className="history-duration">{formatTime(workout.duration)}</span>
              </div>

              <div className="history-exercises">
                {workout.exercises.map((exercise, index) => (
                  <div key={index} className="history-exercise">
                    <span className="history-exercise-name">{exercise.name}</span>
                    <span className="history-exercise-stats">
                      {exercise.sets} sets • {exercise.totalReps} reps • {exercise.maxWeight}kg max
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <p>No workout history found.</p>
          <p>Complete your first workout to see it here!</p>
        </div>
      )}
    </div>
  );

    return (
    <div className={`workout-app ${showKeypad ? 'keypad-active' : ''}`}>
      {/* Tab Content */}
      {activeTab === 'workout' && renderWorkoutTracker()}
      {activeTab === 'plan' && renderCurrentPlan()}
      {activeTab === 'history' && renderHistory()}

            {/* Tab Navigation */}
      {!showKeypad && (
        <div className="tab-navigation">
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
          className={`tab-button ${activeTab === 'plan' ? 'tab-button--active' : ''}`}
          onClick={() => {
            setActiveTab('plan');
            setShowKeypad(false);
          }}
        >
          Plan
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
    </div>
  );
}
