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

  // Form state
  const [exercise, setExercise] = useState("");
  const [weight, setWeight] = useState("60");
  const [reps, setReps] = useState("5");

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
  }, [user, i18n]);

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

  // Validate form data
  const validateForm = useCallback((): boolean => {
    const newErrors: Record<string, string> = {};

    if (!exercise.trim()) {
      newErrors.exercise = t("exercise_required");
    }

    const weightNum = parseFloat(weight);
    if (isNaN(weightNum) || weightNum <= 0) {
      newErrors.weight = t("weight_invalid");
    }

    const repsNum = parseInt(reps, 10);
    if (isNaN(repsNum) || repsNum <= 0) {
      newErrors.reps = t("reps_invalid");
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [exercise, weight, reps, t]);

  // Add workout set
  const addSet = useCallback(async () => {
    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      const setData: SetData = {
        exercise: exercise.trim(),
        weight: parseFloat(weight),
        reps: parseInt(reps, 10),
      };

      console.log("Sending set:", setData);

      const resp = await fetch("/api/v1/track/set", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tg_id: user?.id || 0,
          ...setData
        }),
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      }

      const data = await resp.json();
      console.log("Add set response:", data);

      if (data.ok) {
        // Show success message
        try {
          window.Telegram?.WebApp?.showPopup({
            title: "Saved ✅",
            message: t("saved")
          });
        } catch {}

        // Reset form
        setExercise("");
        setWeight("60");
        setReps("5");
        setErrors({});
      } else {
        throw new Error(data.error || "Unknown error");
      }
    } catch (error) {
      console.error("Add set failed:", error);
      setErrors({ general: t("save_failed") });
    } finally {
      setLoading(false);
    }
  }, [exercise, weight, reps, user?.id, t, validateForm]);

  // Handle exercise input change
  const handleExerciseChange = useCallback((value: string) => {
    setExercise(value);
    setErrors(prev => ({ ...prev, exercise: "" }));
    queryExercises(value);
  }, [queryExercises]);

  // Handle weight input change
  const handleWeightChange = useCallback((value: string) => {
    setWeight(value);
    setErrors(prev => ({ ...prev, weight: "" }));
  }, []);

  // Handle reps input change
  const handleRepsChange = useCallback((value: string) => {
    setReps(value);
    setErrors(prev => ({ ...prev, reps: "" }));
  }, []);

  return (
    <div className="app">
      <header className="app__header">
        <h1 className="app__title">{t("title")}</h1>
      </header>

      <main className="app__main">
        <form className="workout-form" onSubmit={(e) => { e.preventDefault(); addSet(); }}>
          <Input
            label={t("exercise")}
            value={exercise}
            onChange={handleExerciseChange}
            placeholder="Bench Press"
            error={errors.exercise}
            required
            list="exlist"
          />

          <datalist id="exlist">
            {suggestions.map((s) => (
              <option key={s.id} value={s.name} />
            ))}
          </datalist>

          <div className="form-row">
            <div className="form-row__item">
              <Input
                label={t("weight")}
                type="number"
                value={weight}
                onChange={handleWeightChange}
                error={errors.weight}
                min={0.1}
                step={0.5}
                required
              />
            </div>
            <div className="form-row__item">
              <Input
                label={t("reps")}
                type="number"
                value={reps}
                onChange={handleRepsChange}
                error={errors.reps}
                min={1}
                step={1}
                required
              />
            </div>
          </div>

          {errors.general && (
            <div className="error-message">{errors.general}</div>
          )}

          <Button
            onClick={addSet}
            loading={loading}
            disabled={loading}
            fullWidth
            type="submit"
          >
            {loading ? t("saving") : t("add_set")}
          </Button>
        </form>
      </main>
    </div>
  );
}
