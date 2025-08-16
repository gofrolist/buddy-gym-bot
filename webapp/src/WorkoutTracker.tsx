import React, { useState, useEffect } from 'react';
import { Play, Pause, MoreHorizontal, Check, X, Settings } from 'lucide-react';

interface SetData {
  id: number;
  weight: number;
  reps: number;
  completed: boolean;
  previous: number | null;
}

interface Exercise {
  name: string;
  type: string;
  sets: SetData[];
}

interface WorkoutData {
  name: string;
  date: string;
  exercises: Exercise[];
}

const WorkoutTracker: React.FC = () => {
  const [timer, setTimer] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [workoutData, setWorkoutData] = useState<WorkoutData>({
    name: 'Strong 5x5 - Workout B',
    date: 'Aug 15, 2025',
    exercises: [
      {
        name: 'Squat (Barbell)',
        type: 'barbell',
        sets: [
          { id: 1, weight: 20, reps: 5, completed: true, previous: null },
          { id: 2, weight: 20, reps: 5, completed: false, previous: null },
          { id: 3, weight: 20, reps: 5, completed: false, previous: null },
          { id: 4, weight: 20, reps: 5, completed: false, previous: null },
          { id: 5, weight: 20, reps: 5, completed: false, previous: null }
        ]
      },
      {
        name: 'Overhead Press (Barbell)',
        type: 'barbell',
        sets: []
      },
      {
        name: 'Bench Press',
        type: 'barbell',
        sets: [
          { id: 1, weight: 20, reps: 5, completed: false, previous: null },
          { id: 2, weight: 20, reps: 5, completed: false, previous: null }
        ]
      }
    ]
  });

  useEffect(() => {
    let interval: NodeJS.Timer | undefined;
    if (isRunning) {
      interval = setInterval(() => {
        setTimer((t) => t + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isRunning]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const toggleTimer = () => setIsRunning(!isRunning);

  const updateSet = (exerciseIndex: number, setIndex: number, field: keyof SetData, value: number | boolean | null) => {
    setWorkoutData((prev) => {
      const newData = { ...prev };
      (newData.exercises[exerciseIndex].sets[setIndex] as any)[field] = value;
      return { ...newData };
    });
  };

  const toggleSetComplete = (exerciseIndex: number, setIndex: number) => {
    setWorkoutData((prev) => {
      const newData = { ...prev };
      const set = newData.exercises[exerciseIndex].sets[setIndex];
      set.completed = !set.completed;
      return { ...newData };
    });
  };

  const addSet = (exerciseIndex: number) => {
    setWorkoutData((prev) => {
      const newData = { ...prev };
      const exercise = newData.exercises[exerciseIndex];
      const lastSet = exercise.sets[exercise.sets.length - 1];
      const newSet: SetData = {
        id: exercise.sets.length + 1,
        weight: lastSet ? lastSet.weight : 20,
        reps: lastSet ? lastSet.reps : 5,
        completed: false,
        previous: null,
      };
      exercise.sets.push(newSet);
      return { ...newData };
    });
  };

  const saveWorkout = async () => {
    try {
      const response = await fetch('/api/workouts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workoutData),
      });
      if (response.ok) {
        console.log('Workout saved successfully');
      }
    } catch (error) {
      console.error('Error saving workout:', error);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="flex items-center justify-between p-4 bg-gray-800">
        <button className="p-2 rounded-full bg-gray-700">
          <X className="w-6 h-6" />
        </button>
        <div className="flex items-center gap-4">
          <span className="text-lg font-medium">00:{formatTime(timer)}</span>
          <button onClick={toggleTimer} className="p-3 rounded-full bg-gray-600">
            {isRunning ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6" />}
          </button>
          <button className="p-3 rounded-full bg-gray-600">
            <Settings className="w-6 h-6" />
          </button>
          <button onClick={saveWorkout} className="px-6 py-2 bg-green-500 rounded-full font-medium">
            Finish
          </button>
        </div>
      </div>

      <div className="p-4">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-2xl font-bold">{workoutData.name}</h1>
          <button className="p-1">
            <MoreHorizontal className="w-6 h-6 text-blue-400" />
          </button>
        </div>
        <div className="flex items-center gap-4 text-gray-400 text-sm">
          <span>📅 {workoutData.date}</span>
          <span>⏱️ {formatTime(timer)}</span>
        </div>
      </div>

      <div className="px-4 space-y-6">
        {workoutData.exercises.map((exercise, exerciseIndex) => (
          <div key={exerciseIndex} className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-blue-400">{exercise.name}</h3>
              <div className="flex gap-2">
                <button className="p-2 rounded-full bg-blue-500">
                  <span className="text-xs">📈</span>
                </button>
                <button className="p-1">
                  <MoreHorizontal className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="grid grid-cols-5 gap-4 mb-3 text-sm text-gray-400">
              <span>Set</span>
              <span>Previous</span>
              <span>lbs</span>
              <span>Reps</span>
              <span></span>
            </div>

            {exercise.sets.map((set, setIndex) => (
              <div key={set.id} className="grid grid-cols-5 gap-4 items-center mb-3">
                <span className="text-white">{set.id}</span>
                <span className="text-gray-500">—</span>
                <div className="relative">
                  <input
                    type="number"
                    value={set.weight}
                    onChange={(e) => updateSet(exerciseIndex, setIndex, 'weight', parseFloat(e.target.value) || 0)}
                    className="w-full bg-gray-700 rounded px-3 py-2 text-center text-white border-2 border-blue-400"
                    placeholder="20"
                  />
                </div>
                <div className="relative">
                  <input
                    type="number"
                    value={set.reps}
                    onChange={(e) => updateSet(exerciseIndex, setIndex, 'reps', parseInt(e.target.value) || 0)}
                    className="w-full bg-gray-700 rounded px-3 py-2 text-center text-white"
                    placeholder="5"
                  />
                </div>
                <button
                  onClick={() => toggleSetComplete(exerciseIndex, setIndex)}
                  className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    set.completed ? 'bg-green-500' : 'bg-gray-600 border-2 border-gray-500'
                  }`}
                >
                  {set.completed && <Check className="w-5 h-5" />}
                </button>
              </div>
            ))}

            <button
              onClick={() => addSet(exerciseIndex)}
              className="w-full py-3 mt-4 bg-gray-700 rounded-lg text-gray-300 font-medium hover:bg-gray-600 transition-colors"
            >
              + Add Set
            </button>
          </div>
        ))}

        <div className="flex gap-4 mb-8">
          <button className="flex-1 py-3 bg-gray-800 rounded-lg border border-red-500 text-red-400 font-medium">
            + Exercise
          </button>
          <button className="flex-1 py-3 bg-gray-800 rounded-lg border border-red-500 text-red-400 font-medium">
            + Special set
          </button>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h4 className="font-medium">Summary</h4>
            <button>
              <span className="text-gray-400">❓</span>
            </button>
          </div>
          <div className="flex justify-center mb-4">
            <div className="relative">
              <div className="w-32 h-40 bg-gray-700 rounded-lg flex items-center justify-center">
                <div className="text-center">
                  <div className="w-16 h-8 bg-red-500 rounded mb-2 mx-auto opacity-80"></div>
                  <div className="text-xs text-gray-300">Chest</div>
                </div>
              </div>
            </div>
          </div>
          <div className="flex justify-center">
            <span className="text-gray-400 text-sm">kg</span>
            <button className="ml-auto px-4 py-1 bg-gray-700 rounded text-sm">Done</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkoutTracker;
