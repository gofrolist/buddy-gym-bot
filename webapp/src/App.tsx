import React, { useState, useEffect, useRef } from 'react';
import {
  Undo2,
  ChevronDown,
  Eraser,
  ChevronsRight,
  MoreVertical,
  Link2,
  Check,
  Plus,
} from 'lucide-react';

const cn = (...classNames: (string | false | null | undefined)[]) =>
  classNames.filter(Boolean).join(' ');

type WorkoutSet = {
  id: string;
  setIndex: number;
  prev: string;
  weight: string;
  reps: string;
  completed: boolean;
};

type Exercise = {
  id: string;
  name: string;
  sets: WorkoutSet[];
};

type FocusedInput = {
  exerciseId: string;
  setIndex: string;
  type: 'weight' | 'reps';
} | null;

const App: React.FC = () => {
  const [workout, setWorkout] = useState<Exercise[]>([]);
  const [isWorkoutActive, setIsWorkoutActive] = useState(true);
  const [showKeypad, setShowKeypad] = useState(false);
  const [focusedInput, setFocusedInput] = useState<FocusedInput>(null);
  const [unit, setUnit] = useState<'lb' | 'kg'>('lb');
  const focusedInputRef = useRef<HTMLDivElement | null>(null);

  const initialData: { default: Exercise[]; empty: Exercise[] } = {
    default: [
      {
        id: 'squat',
        name: 'Squat (Barbell)',
        sets: [
          { id: 'set-1', setIndex: 1, prev: '135 lb', weight: '135', reps: '5', completed: true },
          { id: 'set-2', setIndex: 2, prev: '135 lb', weight: '135', reps: '5', completed: true },
          { id: 'set-3', setIndex: 3, prev: '135 lb', weight: '140', reps: '', completed: false },
          { id: 'set-4', setIndex: 4, prev: '135 lb', weight: '', reps: '', completed: false },
          { id: 'set-5', setIndex: 5, prev: '135 lb', weight: '', reps: '', completed: false },
        ],
      },
      {
        id: 'bench-press',
        name: 'Bench Press (Barbell)',
        sets: [
          { id: 'set-1-b', setIndex: 1, prev: '95 lb', weight: '95', reps: '5', completed: true },
          { id: 'set-2-b', setIndex: 2, prev: '95 lb', weight: '', reps: '', completed: false },
        ],
      },
    ],
    empty: [
      {
        id: 'squat-empty',
        name: 'Squat (Barbell)',
        sets: [
          { id: 'set-1', setIndex: 1, prev: '-', weight: '', reps: '', completed: false },
          { id: 'set-2', setIndex: 2, prev: '-', weight: '', reps: '', completed: false },
          { id: 'set-3', setIndex: 3, prev: '-', weight: '', reps: '', completed: false },
          { id: 'set-4', setIndex: 4, prev: '-', weight: '', reps: '', completed: false },
          { id: 'set-5', setIndex: 5, prev: '-', weight: '', reps: '', completed: false },
        ],
      },
    ],
  };

  useEffect(() => {
    setWorkout(initialData.default);
  }, []);

  useEffect(() => {
    if (showKeypad && focusedInputRef.current) {
      setTimeout(() => {
        focusedInputRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        });
      }, 300);
    }
  }, [showKeypad, focusedInput]);

  const handleCellClick = (exerciseId: string, setId: string, type: 'weight' | 'reps') => {
    setFocusedInput({ exerciseId, setIndex: setId, type });
    setShowKeypad(true);
  };

  const handleKeypadKey = (key: string) => {
    if (!focusedInput) return;
    setWorkout(prev =>
      prev.map(ex =>
        ex.id === focusedInput.exerciseId
          ? {
              ...ex,
              sets: ex.sets.map(s => {
                if (s.id === focusedInput.setIndex) {
                  const currentVal = s[focusedInput.type];
                  let newVal = currentVal + key;
                  if (key === '.') {
                    newVal = currentVal.includes('.') ? currentVal : newVal;
                  }
                  return { ...s, [focusedInput.type]: newVal };
                }
                return s;
              }),
            }
          : ex,
      ),
    );
  };

  const handleNext = () => {
    if (!focusedInput) return;
    const { exerciseId, setIndex, type } = focusedInput;
    const currentExercise = workout.find(ex => ex.id === exerciseId);
    if (!currentExercise) return;
    const currentSetIndex = currentExercise.sets.findIndex(s => s.id === setIndex);
    const currentSet = currentExercise.sets[currentSetIndex];

    setWorkout(prev =>
      prev.map(ex => {
        if (ex.id !== exerciseId) return ex;
        let newSets = [...ex.sets];
        if (type === 'reps' && currentSet.reps !== '') {
          newSets = newSets.map(s => (s.id === setIndex ? { ...s, completed: true } : s));
        }
        return { ...ex, sets: newSets };
      }),
    );

    if (type === 'weight') {
      setFocusedInput({ exerciseId, setIndex, type: 'reps' });
    } else {
      const nextSet = currentExercise.sets[currentSetIndex + 1];
      if (nextSet) {
        setFocusedInput({ exerciseId, setIndex: nextSet.id, type: 'weight' });
      } else {
        handleDone();
      }
    }
  };

  const handleClear = () => {
    if (!focusedInput) return;
    setWorkout(prev =>
      prev.map(ex =>
        ex.id === focusedInput.exerciseId
          ? {
              ...ex,
              sets: ex.sets.map(s =>
                s.id === focusedInput.setIndex ? { ...s, [focusedInput.type]: '' } : s,
              ),
            }
          : ex,
      ),
    );
  };

  const handleDone = () => {
    setShowKeypad(false);
    setFocusedInput(null);
  };

  const handleUnitToggle = () => {
    setUnit(unit === 'lb' ? 'kg' : 'lb');
  };

  return (
    <div className="bg-gray-100 min-h-screen text-gray-900 font-['Inter'] relative overflow-hidden">
      <div className="sticky top-0 z-20 bg-gradient-to-b from-gray-100 to-transparent pt-4">
        <AppBar
          onFinish={() => setIsWorkoutActive(false)}
          onUndo={() => console.log('Undo')}
          isWorkoutActive={isWorkoutActive}
        />
      </div>

      <div className="p-4 space-y-8 pb-48">
        {workout.map(exercise => (
          <ExerciseCard
            key={exercise.id}
            exercise={exercise}
            focusedInput={focusedInput}
            onCellClick={(setId, type) => handleCellClick(exercise.id, setId, type)}
            unit={unit}
            ref={focusedInputRef}
          />
        ))}

        <button className="w-full h-14 border border-gray-300 text-gray-600 rounded-2xl border-2 flex items-center justify-center space-x-2">
          <Plus className="h-5 w-5 mr-2" /> <span>Add Exercise</span>
        </button>
      </div>

      <NumericKeypad
        isVisible={showKeypad}
        onKeyClick={handleKeypadKey}
        onNext={handleNext}
        onClear={handleClear}
        onDone={handleDone}
        onUnitToggle={handleUnitToggle}
        unit={unit}
      />
    </div>
  );
};

type AppBarProps = {
  onFinish: () => void;
  onUndo: () => void;
  isWorkoutActive: boolean;
};

const AppBar: React.FC<AppBarProps> = ({ onFinish, onUndo, isWorkoutActive }) => (
  <div className="flex flex-col gap-2 p-4">
    <div className="flex items-center justify-between">
      <button onClick={onUndo} className="p-2 rounded-full bg-gray-200 hover:bg-gray-300 text-gray-700">
        <Undo2 size={24} />
      </button>
      <div className="flex-1 ml-4">
        <h1 className="text-xl font-semibold text-gray-900">Strong 5×5 – Workout B</h1>
      </div>
      <button
        onClick={onFinish}
        className={cn(
          'px-6 py-3 font-semibold rounded-full transition-colors duration-200',
          isWorkoutActive ? 'bg-blue-600 hover:bg-blue-500 text-white' : 'bg-gray-300 text-gray-400 cursor-not-allowed',
        )}
        disabled={!isWorkoutActive}
      >
        Finish
      </button>
    </div>
  </div>
);

type ExerciseCardProps = {
  exercise: Exercise;
  focusedInput: FocusedInput;
  onCellClick: (setId: string, type: 'weight' | 'reps') => void;
  unit: string;
};

const ExerciseCard = React.forwardRef<HTMLDivElement, ExerciseCardProps>(
  ({ exercise, focusedInput, onCellClick, unit }, ref) => {
    return (
      <div className="bg-white p-4 rounded-[24px] shadow-lg shadow-black/10">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">{exercise.name}</h2>
          <div className="flex items-center space-x-2 text-gray-500">
            <Link2 size={20} />
            <MoreVertical size={20} />
          </div>
        </div>
        <div className="w-full overflow-hidden rounded-2xl">
          <div className="grid grid-cols-[1fr_1.5fr_2fr_2fr_1fr] text-sm text-gray-600 font-semibold px-2 py-3 border-b border-gray-200">
            <div>Set</div>
            <div>Previous</div>
            <div>Weight ({unit})</div>
            <div>Reps</div>
            <div>Done</div>
          </div>
          {exercise.sets.map(set => {
            const isWeightFocused =
              focusedInput &&
              focusedInput.exerciseId === exercise.id &&
              focusedInput.setIndex === set.id &&
              focusedInput.type === 'weight';
            const isRepsFocused =
              focusedInput &&
              focusedInput.exerciseId === exercise.id &&
              focusedInput.setIndex === set.id &&
              focusedInput.type === 'reps';
            return (
              <div
                key={set.id}
                className={cn(
                  'grid grid-cols-[1fr_1.5fr_2fr_2fr_1fr] items-center text-gray-900 text-base py-3 px-2 transition-colors duration-200',
                  set.completed ? 'bg-green-100' : 'hover:bg-gray-100',
                )}
              >
                <div className="flex justify-center items-center">
                  <span
                    className={cn(
                      'w-8 h-8 rounded-full flex items-center justify-center font-semibold text-sm',
                      set.completed ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-700',
                    )}
                  >
                    {set.setIndex}
                  </span>
                </div>
                <div className="text-gray-500 text-sm">{set.prev}</div>
                <div
                  className={cn(
                    'flex items-center justify-center p-2 rounded-lg transition-all duration-200 cursor-pointer',
                    isWeightFocused ? 'ring-2 ring-blue-500 bg-white' : 'bg-gray-50',
                  )}
                  onClick={() => onCellClick(set.id, 'weight')}
                  ref={isWeightFocused ? (ref as React.RefObject<HTMLDivElement>) : null}
                >
                  {set.weight}
                </div>
                <div
                  className={cn(
                    'flex items-center justify-center p-2 rounded-lg transition-all duration-200 cursor-pointer',
                    isRepsFocused ? 'ring-2 ring-blue-500 bg-white' : 'bg-gray-50',
                  )}
                  onClick={() => onCellClick(set.id, 'reps')}
                  ref={isRepsFocused ? (ref as React.RefObject<HTMLDivElement>) : null}
                >
                  {set.reps}
                </div>
                <div className="flex justify-center">
                  <Check
                    className={cn(
                      'w-6 h-6 transition-colors duration-200',
                      set.completed ? 'text-green-500' : 'text-gray-300',
                    )}
                  />
                </div>
              </div>
            );
          })}
        </div>
        <button className="mt-4 w-full h-12 text-blue-600 border border-blue-600 hover:bg-blue-600 hover:text-white rounded-xl">
          + Add Set
        </button>
      </div>
    );
  },
);

type NumericKeypadProps = {
  isVisible: boolean;
  onKeyClick: (key: string) => void;
  onNext: () => void;
  onClear: () => void;
  onDone: () => void;
  onUnitToggle: () => void;
  unit: string;
};

const NumericKeypad: React.FC<NumericKeypadProps> = ({
  isVisible,
  onKeyClick,
  onNext,
  onClear,
  onDone,
  onUnitToggle,
  unit,
}) => {
  const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '.', '0'];

  return (
    <div
      className={cn(
        'fixed inset-x-0 bottom-0 z-50 bg-white p-4 rounded-t-3xl shadow-2xl transition-transform duration-300 ease-in-out transform',
        isVisible ? 'translate-y-0' : 'translate-y-full',
      )}
    >
      <div className="flex justify-between items-center mb-4">
        <button
          onClick={onUnitToggle}
          className="text-gray-700 text-sm font-semibold rounded-full bg-gray-200 hover:bg-gray-300 px-3"
        >
          <span className={cn(unit === 'kg' && 'text-gray-900')}>{unit === 'kg' ? 'kg' : 'lb'}</span>
        </button>
        <button onClick={onDone} className="p-2 rounded-full bg-gray-200 hover:bg-gray-300 text-gray-700">
          <ChevronDown size={28} />
        </button>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {keys.slice(0, 9).map(key => (
          <button
            key={key}
            onClick={() => onKeyClick(key)}
            className="h-16 text-2xl font-semibold bg-gray-200 hover:bg-gray-300 text-gray-900 rounded-2xl shadow-sm"
          >
            {key}
          </button>
        ))}
        <button
          onClick={() => onKeyClick('.')}
          className="h-16 text-2xl font-semibold bg-gray-200 hover:bg-gray-300 text-gray-900 rounded-2xl shadow-sm"
        >
          .
        </button>
        <button
          onClick={() => onKeyClick('0')}
          className="h-16 text-2xl font-semibold bg-gray-200 hover:bg-gray-300 text-gray-900 rounded-2xl shadow-sm"
        >
          0
        </button>
        <button
          onClick={onNext}
          className="h-16 text-2xl font-semibold bg-blue-600 hover:bg-blue-500 text-white rounded-2xl shadow-sm"
        >
          <ChevronsRight size={28} />
        </button>
      </div>

      <button
        onClick={onClear}
        className="w-full h-16 mt-2 text-2xl font-semibold bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-2xl shadow-sm"
      >
        <Eraser size={28} />
      </button>
    </div>
  );
};

export default App;

