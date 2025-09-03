"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Calendar,
  Dumbbell,
  History,
  Plus,
  Timer,
  Search,
  Play,
  Pause,
  Square,
  TrendingUp,
  Award,
  BarChart3,
  Target,
  Sparkles,
  Send,
  Loader2,
  Trash2,
  X,
} from "lucide-react"
import { translate as t, getLocaleValue } from "@/lib/i18n"
import { apiUrl } from "@/lib/utils"

interface TelegramWebApp {
  initData: string
  initDataUnsafe: {
    user?: {
      id: number
      first_name: string
      last_name?: string
      username?: string
      language_code?: string
    }
  }
  colorScheme: "light" | "dark"
  themeParams: {
    bg_color?: string
    text_color?: string
    hint_color?: string
    link_color?: string
    button_color?: string
    button_text_color?: string
    secondary_bg_color?: string
  }
  isExpanded: boolean
  viewportHeight: number
  viewportStableHeight: number
  expand(): void
  close(): void
  ready(): void
  MainButton: {
    text: string
    color: string
    textColor: string
    isVisible: boolean
    isActive: boolean
    show(): void
    hide(): void
    enable(): void
    disable(): void
    setText(text: string): void
    onClick(callback: () => void): void
    offClick(callback: () => void): void
  }
  BackButton: {
    isVisible: boolean
    show(): void
    hide(): void
    onClick(callback: () => void): void
    offClick(callback: () => void): void
  }
  onEvent(eventType: string, eventHandler: () => void): void
  offEvent(eventType: string, eventHandler: () => void): void
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp
    }
  }
}

interface Exercise {
  id: string
  name: string
  muscle: string
  category: string
  equipment: string
  sets?: number
  reps?: number
  weight?: number
}

interface APIResponse {
  ok: boolean
  items: Exercise[]
  query?: string
  category?: string
  equipment?: string
  total: number
}

interface WorkoutSet {
  reps: number
  weight: number
  completed: boolean
}

interface WorkoutExercise {
  id: string
  name: string
  sets: WorkoutSet[]
}

interface WorkoutSession {
  id: string
  date: string
  exercises: WorkoutExercise[]
  duration: number
}

interface AppData {
  weeklyPlan: Record<string, Exercise[]>
  workoutHistory: WorkoutSession[]
  settings: {
    restDuration: number
    selectedDay: string
  }
  version: string
  lastSaved: string
}

const DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


async function loadPlanFromAPI(tgUserId: number): Promise<Record<string, Exercise[]>> {
  try {
    const response = await fetch(apiUrl(`/api/v1/plan/current?tg_user_id=${tgUserId}`))
    if (!response.ok) {
      console.warn(`API request failed with status ${response.status}, using local fallback`)
      return {}
    }

    const data = await response.json()
    if (data.success && data.plan) {
      return data.plan
    }
    return {}
  } catch (error) {
    console.warn("Failed to load plan from API, using local fallback:", error)
    return {}
  }
}

async function savePlanToAPI(tgUserId: number, plan: Record<string, Exercise[]>): Promise<boolean> {
  try {
    const response = await fetch(apiUrl(`/api/v1/plan/update`), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        tg_user_id: tgUserId,
        plan: plan,
      }),
    })

    if (!response.ok) {
      console.warn(`API request failed with status ${response.status}, using local fallback`)
      return false
    }

    const data = await response.json()
    return data.success
  } catch (error) {
    console.warn("Failed to save plan to API, using local fallback:", error)
    return false
  }
}

async function logWorkoutSet(
  tgUserId: number,
  exercise: string,
  weight: number,
  reps: number,
  isCompleted = true,
): Promise<boolean> {
  try {
    const response = await fetch(apiUrl(`/api/v1/workout`), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        tg_user_id: tgUserId,
        exercise: exercise,
        weight_kg: weight * 0.453592, // Convert lbs to kg for API
        reps: reps,
        rpe: null,
        is_warmup: false,
        is_completed: isCompleted,
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()
    return data.success
  } catch (error) {
    console.error("Failed to log workout set:", error)
    return false
  }
}

async function loadWorkoutHistoryFromAPI(tgUserId: number): Promise<WorkoutSession[]> {
  try {
    const response = await fetch(apiUrl(`/api/v1/workout/history?tg_user_id=${tgUserId}`))
    if (!response.ok) {
      console.warn(`API request failed with status ${response.status}, using local fallback`)
      return []
    }

    const data = await response.json()
    if (data.success && data.history) {
      // Convert API format to UI format
      return data.history.map((session: any) => ({
        id: session.id,
        date: new Date(session.date).toLocaleDateString(),
        duration: session.duration,
        exercises: session.exercises.map((exercise: any) => ({
          id: `${session.id}-${exercise.name}`,
          name: exercise.name,
          sets: Array.from({ length: exercise.sets }, (_, i) => ({
            reps: Math.floor(exercise.totalReps / exercise.sets),
            weight: Math.round(exercise.maxWeight * 2.20462), // Convert kg to lbs
            completed: true,
          })),
        })),
      }))
    }
    return []
  } catch (error) {
    console.warn("Failed to load workout history from API, using local fallback:", error)
    return []
  }
}

async function finishWorkoutSession(tgUserId: number): Promise<boolean> {
  try {
    const response = await fetch(apiUrl(`/api/v1/workout/finish`), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        tg_user_id: tgUserId,
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()
    return data.success
  } catch (error) {
    console.error("Failed to finish workout session:", error)
    return false
  }
}

const DATA_STORAGE_KEY = "fittracker_data"
const APP_VERSION = "1.0.0"

function saveAppData(data: Partial<AppData>) {
  try {
    const existingData = loadAppData()
    const updatedData: AppData = {
      ...existingData,
      ...data,
      version: APP_VERSION,
      lastSaved: new Date().toISOString(),
    }
    localStorage.setItem(DATA_STORAGE_KEY, JSON.stringify(updatedData))
    return true
  } catch (error) {
    console.error("Failed to save app data:", error)
    return false
  }
}

function loadAppData(): AppData {
  try {
    const stored = localStorage.getItem(DATA_STORAGE_KEY)
    if (stored) {
      const data = JSON.parse(stored)
      // Migration logic for older versions
      if (!data.version || data.version !== APP_VERSION) {
        return migrateData(data)
      }
      return data
    }
  } catch (error) {
    console.error("Failed to load app data:", error)
  }

  return {
    weeklyPlan: {},
    workoutHistory: [],
    settings: {
      restDuration: 90,
      selectedDay: "Monday",
    },
    version: APP_VERSION,
    lastSaved: new Date().toISOString(),
  }
}

function migrateData(oldData: any): AppData {
  // Handle migration from older versions
  return {
    weeklyPlan: oldData.weeklyPlan || {},
    workoutHistory: oldData.workoutHistory || [],
    settings: {
      restDuration: oldData.restDuration || 90,
      selectedDay: oldData.selectedDay || "Monday",
    },
    version: APP_VERSION,
    lastSaved: new Date().toISOString(),
  }
}

function exportAppData(): string {
  const data = loadAppData()
  return JSON.stringify(data, null, 2)
}

function importAppData(jsonData: string): boolean {
  try {
    const data = JSON.parse(jsonData)
    // Validate data structure
    if (data && typeof data === "object") {
      const migratedData = migrateData(data)
      localStorage.setItem(DATA_STORAGE_KEY, JSON.stringify(migratedData))
      return true
    }
    return false
  } catch (error) {
    console.error("Failed to import app data:", error)
    return false
  }
}

function downloadBackup() {
  const data = exportAppData()
  const blob = new Blob([data], { type: "application/json" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `fittracker-backup-${new Date().toISOString().split("T")[0]}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function AIWorkoutPlanner({
  onPlanGenerated,
  weeklyPlan,
  telegramWebApp,
  devUserId,
  userLanguage,
}: {
  onPlanGenerated: (plan: Record<string, Exercise[]>) => void;
  weeklyPlan: Record<string, Exercise[]>;
  telegramWebApp: TelegramWebApp | null;
  devUserId: number;
  userLanguage: string;
}) {
  // Check if we're in development mode
  const isDevelopment = typeof window !== "undefined" && !window.Telegram?.WebApp
  if (isDevelopment) {
  console.log("🔧 AIWorkoutPlanner: Component rendered with telegramWebApp =", telegramWebApp)
  console.log("🔧 AIWorkoutPlanner: telegramWebApp?.initDataUnsafe?.user =", telegramWebApp?.initDataUnsafe?.user)
  }
  const [prompt, setPrompt] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)
  const [suggestions] = useState<string[]>(() => getLocaleValue(userLanguage, "ai.suggestions") || [])
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const generateWorkoutPlan = async (userPrompt: string) => {
    setIsGenerating(true)
    setErrorMessage(null)

    try {
      if (isDevelopment) {
      console.log("🔧 generateWorkoutPlan: telegramWebApp =", telegramWebApp)
      console.log("🔧 generateWorkoutPlan: telegramWebApp?.initDataUnsafe?.user =", telegramWebApp?.initDataUnsafe?.user)
      }
      const tgUserId = telegramWebApp?.initDataUnsafe?.user?.id
      if (isDevelopment) console.log("🔧 generateWorkoutPlan: tgUserId =", tgUserId)

      // Fallback to development user ID if telegramWebApp is not available
      const userId = tgUserId || (isDevelopment ? devUserId : null)
      if (isDevelopment) console.log("🔧 generateWorkoutPlan: Using userId =", userId)

      if (!userId) {
        console.error("Telegram user ID not available")
        return
      }

      const response = await fetch(apiUrl(`/api/v1/schedule`), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          tg_user_id: userId,
          message: userPrompt,
          context: {
            current_plan: weeklyPlan,
          },
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const data = await response.json()

      if (data.success && data.plan) {
        // Convert API plan format to UI format
        const convertedPlan = convertApiPlanToUIFormat(data.plan)
        onPlanGenerated(convertedPlan)
        setPrompt("")
      } else {
        // Show AI response even if no plan was generated
        if (isDevelopment) console.log("AI Response:", data.response)
      }
    } catch (error) {
      console.error("Failed to generate workout plan:", error)
      setErrorMessage("Failed to generate workout plan. Please try again or create a plan manually.")
    } finally {
      setIsGenerating(false)
    }
  }

  const convertApiPlanToUIFormat = (apiPlan: any): Record<string, Exercise[]> => {
    const uiPlan: Record<string, Exercise[]> = {}

    // Map abbreviated day names to full day names
    const dayMapping: Record<string, string> = {
      "Mon": "Monday",
      "Tue": "Tuesday",
      "Wed": "Wednesday",
      "Thu": "Thursday",
      "Fri": "Friday",
      "Sat": "Saturday",
      "Sun": "Sunday"
    }

    if (apiPlan.days) {
      apiPlan.days.forEach((day: any) => {
        // The API returns day.weekday (e.g., "Mon", "Wed", "Fri")
        const abbreviatedDay = day.weekday || day.name || day.day_name
        const fullDayName = dayMapping[abbreviatedDay] || abbreviatedDay

        if (fullDayName && day.exercises) {
          uiPlan[fullDayName] = day.exercises.map((exercise: any) => ({
            id: Date.now().toString() + Math.random(),
            name: exercise.name || exercise.exercise_name,
            sets: exercise.sets || 3,
            reps: exercise.reps || 10,
            weight: exercise.weight || 0,
          }))
        }
      })
    }

    if (isDevelopment) {
    console.log("🔧 convertApiPlanToUIFormat: API plan =", apiPlan)
    console.log("🔧 convertApiPlanToUIFormat: Converted UI plan =", uiPlan)
    }
    return uiPlan
  }

  // Removed legacy local plan generators; backend is the single source of truth

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Sparkles className="w-5 h-5" />
          {t(userLanguage, "ai.planner_title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder={t(userLanguage, "ai.input_placeholder")}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && !isGenerating && prompt.trim() && generateWorkoutPlan(prompt)}
              className="flex-1"
            />
            <Button onClick={() => generateWorkoutPlan(prompt)} disabled={isGenerating || !prompt.trim()} size="sm">
              {isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </Button>
          </div>

          {errorMessage && (
            <div className="text-sm text-red-500">
              {errorMessage}
            </div>
          )}

          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">{t(userLanguage, "ai.quick_suggestions")}</p>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((suggestion, index) => (
                <Button
                  key={index}
                  variant="outline"
                  size="sm"
                  onClick={() => setPrompt(suggestion)}
                  className="text-xs"
                  disabled={isGenerating}
                >
                  {suggestion}
                </Button>
              ))}
            </div>
          </div>
        </div>

        {isGenerating && (
          <div className="flex items-center justify-center py-8">
            <div className="flex items-center gap-3">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
              <div className="text-center">
                <p className="font-medium">{t(userLanguage, "ai.generating")}</p>
                <p className="text-sm text-muted-foreground">{t(userLanguage, "ai.analyzing")}</p>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ExerciseSelector({
  onSelectExercise,
  onClose,
  userLanguage,
}: { onSelectExercise: (exercise: Exercise) => void; onClose: () => void; userLanguage: string }) {
  const [searchTerm, setSearchTerm] = useState("")
  const [selectedMuscle, setSelectedMuscle] = useState("All")
  const [exercisePreview, setExercisePreview] = useState<any | null>(null)
  const [exercises, setExercises] = useState<Exercise[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [categories, setCategories] = useState<string[]>(["All"]) // dynamic categories

  // Load categories once
  useEffect(() => {
    const loadCategories = async () => {
      try {
        const resp = await fetch(apiUrl(`/api/v1/exercises/categories`))
        if (!resp.ok) return
        const data = await resp.json()
        const items: string[] = Array.isArray(data?.items) ? data.items : []
        // Ensure capitalization for display
        const display = items.map((c) => c.trim()).filter(Boolean)
        setCategories(["All", ...display])
      } catch {
        // ignore; keep default
      }
    }
    loadCategories()
  }, [])

  const debouncedSearch = useCallback(
    debounce(async (term: string, muscle: string) => {
      if (!term && muscle === "All") {
        setExercises([])
        return
      }

      setLoading(true)
      setError(null)

      try {
        let url = ""
        if (term) {
          // Search by query
          url = apiUrl(`/api/v1/exercises/search?q=${encodeURIComponent(term)}&limit=20`)
        } else if (muscle !== "All") {
          // Search by category (use normalized value)
          url = apiUrl(`/api/v1/exercises/category/${encodeURIComponent(muscle)}?limit=20`)
        }

        if (url) {
          const response = await fetch(url)
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`)
          }

          const data: APIResponse = await response.json()
          setExercises(data.items || [])
        }
      } catch (err) {
        console.error("Exercise search failed:", err)
        setError("Failed to load exercises. Please try again.")
        setExercises([])
      } finally {
        setLoading(false)
      }
    }, 300),
    [],
  )

  useEffect(() => {
    debouncedSearch(searchTerm, selectedMuscle)
  }, [searchTerm, selectedMuscle, debouncedSearch])

  useEffect(() => {
    // Initial state: show nothing until user starts searching or picks a category
    // Keep default selectedMuscle as "All"
  }, [debouncedSearch])

  return (
    <div className="fixed inset-0 bg-background z-50 flex flex-col">
      <div className="flex items-center justify-between p-4 border-b">
        <h2 className="text-xl font-semibold">{t(userLanguage, "exercise.select_title")}</h2>
        <Button variant="ghost" size="sm" onClick={onClose}>
          <X className="w-5 h-5" />
        </Button>
      </div>

      <div className="p-4 space-y-4 border-b">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder={t(userLanguage, "exercise.search_placeholder")}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          {categories.map((muscle) => (
            <Button
              key={muscle}
              variant={selectedMuscle === muscle ? "default" : "outline"}
              size="sm"
              onClick={() => setSelectedMuscle(muscle)}
              className="text-xs capitalize"
            >
              {muscle}
            </Button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <div className="text-muted-foreground">{t(userLanguage, "exercise.loading")}</div>
          </div>
        )}

        {error && (
          <div className="flex items-center justify-center py-8">
            <div className="text-red-500 text-center">
              <p>{error}</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-2 bg-transparent"
                onClick={() => debouncedSearch(searchTerm, selectedMuscle)}
              >
                {t(userLanguage, "exercise.retry")}
              </Button>
            </div>
          </div>
        )}

        {!loading && !error && exercises.length === 0 && (searchTerm || selectedMuscle !== "All") && (
          <div className="flex items-center justify-center py-8">
            <div className="text-muted-foreground text-center">
              <p>{t(userLanguage, "exercise.none_found")}</p>
              <p className="text-sm mt-1">{t(userLanguage, "exercise.try_different")}</p>
            </div>
          </div>
        )}

        {!loading && !error && exercises.length === 0 && !searchTerm && selectedMuscle === "All" && (
          <div className="flex items-center justify-center py-8">
            <div className="text-muted-foreground text-center">
              <p>{t(userLanguage, "exercise.prompt_search_or_pick")}</p>
            </div>
          </div>
        )}

        <div className="space-y-3">
          {exercises.map((exercise) => (
            <div
              key={exercise.id}
              className="flex items-center justify-between p-4 border border-border rounded-lg hover:bg-muted cursor-pointer transition-colors"
            >
              <div className="flex-1" onClick={() => setExercisePreview(exercise)}>
                <p className="font-medium text-base underline decoration-dotted">
                  {exercise.name}
                </p>
                <div className="flex gap-2 mt-2">
                  <Badge variant="secondary" className="text-xs capitalize">
                    {(exercise as any).body_parts?.[0] || exercise.muscle || exercise.category || "-"}
                  </Badge>
                  <Badge variant="outline" className="text-xs">
                    {exercise.equipment}
                  </Badge>
                </div>
              </div>
              <button
                aria-label="Add exercise"
                onClick={() => onSelectExercise(exercise)}
                className="ml-3"
              >
                <Plus className="w-5 h-5 text-muted-foreground" />
              </button>
            </div>
          ))}
        </div>
      </div>
      <ExercisePreviewDialog exercise={exercisePreview} onClose={() => setExercisePreview(null)} userLanguage={userLanguage} />
    </div>
  )
}

function ExercisePreviewDialog({ exercise, onClose, userLanguage }: { exercise: any | null; onClose: () => void; userLanguage: string }) {
  if (!exercise) return null
  return (
    <Dialog open={!!exercise} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{exercise.name}</DialogTitle>
          <DialogDescription>
            {(exercise as any).body_parts?.[0] || exercise.category || exercise.equipment || t(userLanguage, "exercise.details")}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          {exercise.image && (
            <img src={exercise.image} alt={exercise.name} className="w-full rounded" />
          )}
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div>
              <span className="text-muted-foreground">{t(userLanguage, "exercise.target")}</span>
              <span className="ml-2 font-medium">{(exercise as any).target_muscles?.[0] || exercise.muscle || '-'}</span>
            </div>
            <div>
              <span className="text-muted-foreground">{t(userLanguage, "exercise.body_part")}</span>
              <span className="ml-2 font-medium">{(exercise as any).body_parts?.[0] || exercise.category || '-'}</span>
            </div>
            <div>
              <span className="text-muted-foreground">{t(userLanguage, "exercise.equipment")}</span>
              <span className="ml-2 font-medium">{exercise.equipment || '-'}</span>
            </div>
          </div>
          {exercise.instructions && Array.isArray(exercise.instructions) && (
            <div className="mt-2">
              <p className="font-semibold">{t(userLanguage, "exercise.instructions")}</p>
              <div className="pl-1 space-y-1 text-sm">
                {exercise.instructions.map((step: string, idx: number) => (
                  <div key={idx}>{step}</div>
                ))}
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button onClick={onClose} variant="outline">
            {t(userLanguage, "exercise.close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function debounce<T extends (...args: any[]) => any>(func: T, wait: number): T {
  let timeout: NodeJS.Timeout | null = null
  return ((...args: any[]) => {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => func(...args), wait)
  }) as T
}

function calculateWorkoutStats(workoutHistory: WorkoutSession[]) {
  if (workoutHistory.length === 0) return null

  const totalWorkouts = workoutHistory.length
  const totalDuration = workoutHistory.reduce((sum, session) => sum + session.duration, 0)
  const avgDuration = Math.round(totalDuration / totalWorkouts)

  // Calculate total volume (weight × reps)
  const totalVolume = workoutHistory.reduce((sum, session) => {
    return (
      sum +
      session.exercises.reduce((exerciseSum, exercise) => {
        return (
          exerciseSum +
          exercise.sets.reduce((setSum, set) => {
            return setSum + (set.completed ? set.weight * set.reps : 0)
          }, 0)
        )
      }, 0)
    )
  }, 0)

  // Find most frequent exercises
  const exerciseFrequency: Record<string, number> = {}
  workoutHistory.forEach((session) => {
    session.exercises.forEach((exercise) => {
      exerciseFrequency[exercise.name] = (exerciseFrequency[exercise.name] || 0) + 1
    })
  })

  const topExercises = Object.entries(exerciseFrequency)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 3)

  return {
    totalWorkouts,
    avgDuration,
    totalVolume,
    topExercises,
  }
}

function calculatePersonalRecords(workoutHistory: WorkoutSession[]) {
  const prs: Record<string, { weight: number; reps: number; date: string }> = {}

  workoutHistory.forEach((session) => {
    session.exercises.forEach((exercise) => {
      exercise.sets.forEach((set) => {
        if (set.completed) {
          const currentPR = prs[exercise.name]
          const oneRepMax = set.weight * (1 + set.reps / 30) // Epley formula approximation

          if (!currentPR || oneRepMax > currentPR.weight * (1 + currentPR.reps / 30)) {
            prs[exercise.name] = {
              weight: set.weight,
              reps: set.reps,
              date: session.date,
            }
          }
        }
      })
    })
  })

  return Object.entries(prs)
    .sort(([, a], [, b]) => b.weight * (1 + b.reps / 30) - a.weight * (1 + a.reps / 30))
    .slice(0, 5)
}

function getRecentProgress(workoutHistory: WorkoutSession[], exerciseName: string) {
  const recentSessions = workoutHistory
    .filter((session) => session.exercises.some((ex) => ex.name === exerciseName))
    .slice(0, 5)
    .reverse()

  return recentSessions
    .map((session) => {
      const exercise = session.exercises.find((ex) => ex.name === exerciseName)
      if (!exercise) return null

      const bestSet = exercise.sets
        .filter((set) => set.completed)
        .reduce(
          (best, set) => {
            const oneRepMax = set.weight * (1 + set.reps / 30)
            const bestOneRepMax = best ? best.weight * (1 + best.reps / 30) : 0
            return oneRepMax > bestOneRepMax ? set : best
          },
          null as WorkoutSet | null,
        )

      return bestSet
        ? {
            date: session.date,
            weight: bestSet.weight,
            reps: bestSet.reps,
          }
        : null
    })
    .filter(Boolean)
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
}: {
  title: string
  value: string | number
  subtitle?: string
  icon: any
  trend?: "up" | "down" | "neutral"
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold">{value}</p>
            {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
          </div>
          <div className="flex items-center gap-2">
            <Icon className="w-5 h-5 text-muted-foreground" />
            {trend && (
              <TrendingUp
                className={`w-4 h-4 ${
                  trend === "up" ? "text-green-500" : trend === "down" ? "text-red-500" : "text-muted-foreground"
                }`}
              />
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// Add development mode detection and mock Telegram WebApp
const isDevelopment = process.env.NODE_ENV === 'development' || typeof window !== 'undefined' && window.location.hostname === 'localhost'

// Mock Telegram WebApp for development
const createMockTelegramWebApp = (userId: number = 123456789): TelegramWebApp => ({
  initData: '',
  initDataUnsafe: {
    user: {
      id: userId,
      first_name: 'Dev User',
      last_name: 'Test',
      username: 'devuser',
      language_code: 'en'
    }
  },
  colorScheme: 'light',
  themeParams: {
    bg_color: '#ffffff',
    text_color: '#000000',
    hint_color: '#999999',
    link_color: '#2481cc',
    button_color: '#2481cc',
    button_text_color: '#ffffff',
    secondary_bg_color: '#f1f1f1'
  },
  isExpanded: true,
  viewportHeight: 600,
  viewportStableHeight: 600,
  expand: () => {},
  close: () => {},
  ready: () => {},
  MainButton: {
    text: '',
    color: '',
    textColor: '',
    isVisible: false,
    isActive: false,
    show: () => {},
    hide: () => {},
    enable: () => {},
    disable: () => {},
    setText: () => {},
    onClick: () => {},
    offClick: () => {}
  },
  BackButton: {
    isVisible: false,
    show: () => {},
    hide: () => {},
    onClick: () => {},
    offClick: () => {}
  },
  onEvent: () => {},
  offEvent: () => {}
})

export default function WorkoutTracker() {
  const [activeTab, setActiveTab] = useState("workout")
  const [weeklyPlan, setWeeklyPlan] = useState<Record<string, Exercise[]>>({})
  const [currentWorkout, setCurrentWorkout] = useState<WorkoutExercise[]>([])
  const [workoutHistory, setWorkoutHistory] = useState<WorkoutSession[]>([])
  const [selectedDay, setSelectedDay] = useState("Monday")
  const [workoutTimer, setWorkoutTimer] = useState(0)
  const [isWorkoutActive, setIsWorkoutActive] = useState(false)
  const [showExerciseSelector, setShowExerciseSelector] = useState(false)
  const [isTimerRunning, setIsTimerRunning] = useState(false)
  const [restDuration, setRestDuration] = useState(90)
  const [historyView, setHistoryView] = useState<"sessions" | "stats">("sessions")
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const [dayAliases, setDayAliases] = useState<Record<string, string>>({
    Monday: "Upper Body",
    Tuesday: "Leg Day",
    Wednesday: "Core",
    Thursday: "Push Day",
    Friday: "Pull Day",
    Saturday: "Full Body",
    Sunday: "Rest Day",
  })

  const [devUserId, setDevUserId] = useState<number>(123456789)
  const [planExercisePreview, setPlanExercisePreview] = useState<any | null>(null)

  // Helper: fetch full exercise info by name from API (first match)
  const fetchExerciseDetailsByName = useCallback(async (name: string) => {
    try {
      const resp = await fetch(apiUrl(`/api/v1/exercises/search?q=${encodeURIComponent(name)}&limit=1`))
      if (!resp.ok) return null
      const data = await resp.json()
      const item = (data?.items && data.items[0]) || null
      return item
    } catch {
      return null
    }
  }, [])

  // Initialize telegramWebApp as null, will be set in useEffect
  const [telegramWebApp, setTelegramWebApp] = useState<TelegramWebApp | null>(null)
  const [userLanguage, setUserLanguage] = useState<string>("en")
  const [isDarkTheme, setIsDarkTheme] = useState<boolean>(false)
  const [isInitialized, setIsInitialized] = useState<boolean>(false)
  const initializedRef = useRef<boolean>(false)
  const dataLoadedRef = useRef<boolean>(false)
  const initialLoadRef = useRef<boolean>(true)
  const lastUserIdRef = useRef<number | null>(null)

  useEffect(() => {
    // Initialize Telegram WebApp
    if (typeof window !== "undefined" && !initializedRef.current) {
      initializedRef.current = true
      if (window.Telegram?.WebApp) {
        // Real Telegram WebApp
        const tg = window.Telegram.WebApp
        setTelegramWebApp(tg)

        // Detect theme
        setIsDarkTheme(tg.colorScheme === "dark")

        // Detect language
        const userLang = tg.initDataUnsafe.user?.language_code || "en"
        setUserLanguage(userLang)

        // Apply Telegram theme colors
        if (tg.themeParams.bg_color) {
          document.documentElement.style.setProperty("--background", tg.themeParams.bg_color)
        }
        if (tg.themeParams.text_color) {
          document.documentElement.style.setProperty("--foreground", tg.themeParams.text_color)
        }
        if (tg.themeParams.button_color) {
          document.documentElement.style.setProperty("--primary", tg.themeParams.button_color)
        }
        if (tg.themeParams.button_text_color) {
          document.documentElement.style.setProperty("--primary-foreground", tg.themeParams.button_text_color)
        }

        // Expand the app to full height
        tg.expand()

        // Ready the app
        tg.ready()

        // Handle theme changes
        tg.onEvent("themeChanged", () => {
          setIsDarkTheme(tg.colorScheme === "dark")
          // Reapply theme colors
          if (tg.themeParams.bg_color) {
            document.documentElement.style.setProperty("--background", tg.themeParams.bg_color)
          }
          if (tg.themeParams.text_color) {
            document.documentElement.style.setProperty("--foreground", tg.themeParams.text_color)
          }
        })
      } else if (isDevelopment) {
        // Development mode - create mock Telegram WebApp
        const mockTg = createMockTelegramWebApp(devUserId)
        if (isDevelopment) {
        console.log("🔧 Development Mode: Created mock Telegram WebApp with user ID:", mockTg.initDataUnsafe.user?.id)
        console.log("🔧 Development Mode: Mock object:", mockTg)
        console.log("🔧 Development Mode: About to set telegramWebApp state")
        }

        // Force immediate state update
        setTelegramWebApp(mockTg)
        if (isDevelopment) console.log("🔧 Development Mode: setTelegramWebApp called")

        // Mock the window.Telegram object for development
        window.Telegram = { WebApp: mockTg }
        if (isDevelopment) console.log("🔧 Development Mode: window.Telegram set to:", window.Telegram)

        // Mark as initialized after setting the mock
        setIsInitialized(true)
        return // Exit early to avoid setting isInitialized twice
      }

      // Mark as initialized (only for real Telegram WebApp)
      setIsInitialized(true)
    }
  }, [isDevelopment])

  // Update mock Telegram WebApp when devUserId changes - only once
  useEffect(() => {
    if (isDevelopment && initializedRef.current && !telegramWebApp) {
      const mockTg = createMockTelegramWebApp(devUserId)
      setTelegramWebApp(mockTg)
      window.Telegram = { WebApp: mockTg }
      if (isDevelopment) console.log("🔧 Development Mode: Created mock Telegram WebApp with user ID:", devUserId)
    }
  }, [devUserId, isDevelopment, telegramWebApp])

  // Debug useEffect to monitor state changes
  useEffect(() => {
    if (isDevelopment) console.log("🔧 State Update: isInitialized =", isInitialized, "telegramWebApp =", telegramWebApp)
    if (telegramWebApp) {
      if (isDevelopment) console.log("🔧 State Update: telegramWebApp.initDataUnsafe.user =", telegramWebApp.initDataUnsafe?.user)
    }
  }, [isInitialized, telegramWebApp])

  useEffect(() => {
    const initializeApp = async () => {
      const appData = loadAppData()

      // Try to load plan from API if Telegram WebApp is available
      if (telegramWebApp?.initDataUnsafe?.user?.id) {
        const tgUserId = telegramWebApp.initDataUnsafe.user.id
        const apiPlan = await loadPlanFromAPI(tgUserId)
        const apiHistory = await loadWorkoutHistoryFromAPI(tgUserId)

        if (Object.keys(apiPlan).length > 0) {
          setWeeklyPlan(apiPlan)
        } else {
          setWeeklyPlan(appData.weeklyPlan)
        }

        if (apiHistory.length > 0) {
          setWorkoutHistory(apiHistory)
        } else {
          setWorkoutHistory(appData.workoutHistory)
        }
      } else {
        setWeeklyPlan(appData.weeklyPlan)
        setWorkoutHistory(appData.workoutHistory)
      }

      setRestDuration(appData.settings.restDuration)
      setSelectedDay(appData.settings.selectedDay)

      // Restore active workout if exists
      const savedWorkout = localStorage.getItem("currentWorkout")
      if (savedWorkout) {
        try {
          const parsed = JSON.parse(savedWorkout)
          const timeDiff = Math.floor((Date.now() - parsed.timestamp) / 1000)
          if (timeDiff < 3600) {
            setCurrentWorkout(parsed.workout)
            setWorkoutTimer(parsed.timer + timeDiff)
            setIsWorkoutActive(true)
          }
        } catch (error) {
          console.error("Failed to restore workout:", error)
        }
      }
    }

    // Only initialize when telegramWebApp is available and we haven't loaded data yet
    if (telegramWebApp && isInitialized) {
      const currentUserId = telegramWebApp.initDataUnsafe?.user?.id

      // Only load data if user ID has changed or we haven't loaded data yet
      if (currentUserId && (currentUserId !== lastUserIdRef.current || !dataLoadedRef.current)) {
        lastUserIdRef.current = currentUserId
        dataLoadedRef.current = true
        if (isDevelopment) console.log("🔧 Loading data for user ID:", currentUserId)
        initializeApp()
      }
    }
  }, [telegramWebApp, isInitialized])

  useEffect(() => {
    // Skip saving on initial load
    if (initialLoadRef.current) {
      initialLoadRef.current = false
      return
    }

    const savePlan = async () => {
      // Save to localStorage as backup
      saveAppData({
        weeklyPlan,
        workoutHistory,
        settings: {
          restDuration,
          selectedDay,
        },
      })

      // Save to API if Telegram WebApp is available
      if (telegramWebApp?.initDataUnsafe?.user?.id) {
        const tgUserId = telegramWebApp.initDataUnsafe.user.id
        await savePlanToAPI(tgUserId, weeklyPlan)
      }
    }

    if (Object.keys(weeklyPlan).length > 0) {
      savePlan()
    }
  }, [weeklyPlan, telegramWebApp])

  useEffect(() => {
    const autoSaveInterval = setInterval(() => {
      saveAppData({
        weeklyPlan,
        workoutHistory,
        settings: {
          restDuration,
          selectedDay,
        },
      })
    }, 60000) // Save every minute

    return () => clearInterval(autoSaveInterval)
  }, [weeklyPlan, workoutHistory, restDuration, selectedDay])

  useEffect(() => {
    saveAppData({
      weeklyPlan,
      workoutHistory,
      settings: {
        restDuration,
        selectedDay,
      },
    })
  }, [weeklyPlan, workoutHistory, restDuration, selectedDay])

  useEffect(() => {
    if (isTimerRunning && isWorkoutActive) {
      timerRef.current = setInterval(() => {
        setWorkoutTimer((prev) => prev + 1)
      }, 1000)
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [isTimerRunning, isWorkoutActive])

  useEffect(() => {
    if (isWorkoutActive && currentWorkout.length > 0) {
      const autoSaveInterval = setInterval(() => {
        localStorage.setItem(
          "currentWorkout",
          JSON.stringify({
            workout: currentWorkout,
            timer: workoutTimer,
            timestamp: Date.now(),
          }),
        )
      }, 30000)

      return () => clearInterval(autoSaveInterval)
    }
  }, [currentWorkout, workoutTimer, isWorkoutActive])

  const handleDataChange = () => {
    // Force reload data from storage
    const appData = loadAppData()
    setWeeklyPlan(appData.weeklyPlan)
    setWorkoutHistory(appData.workoutHistory)
    setRestDuration(appData.settings.restDuration)
    setSelectedDay(appData.settings.selectedDay)
  }

  const handleAIPlanGenerated = async (generatedPlan: Record<string, Exercise[]>) => {
    if (isDevelopment) console.log("🔧 handleAIPlanGenerated: Received plan =", generatedPlan)
    setWeeklyPlan(generatedPlan)
    if (isDevelopment) console.log("🔧 handleAIPlanGenerated: Set weeklyPlan state")

    if (telegramWebApp?.initDataUnsafe?.user?.id) {
      const tgUserId = telegramWebApp.initDataUnsafe.user.id
      await savePlanToAPI(tgUserId, generatedPlan)
      if (isDevelopment) console.log("🔧 handleAIPlanGenerated: Plan saved to API")
    }

    if (isDevelopment) console.log("AI workout plan generated successfully!")
  }

  // Debug effect to monitor weeklyPlan changes
  useEffect(() => {
    if (isDevelopment) {
    console.log("🔧 weeklyPlan state changed:", weeklyPlan)
    console.log("🔧 selectedDay:", selectedDay)
    console.log("🔧 weeklyPlan[selectedDay]:", weeklyPlan[selectedDay])
    }
  }, [weeklyPlan, selectedDay])

  const toggleWorkoutTimer = () => {
    setIsTimerRunning(!isTimerRunning)
  }

  const resetWorkoutTimer = () => {
    setWorkoutTimer(0)
    setIsTimerRunning(false)
  }

  const addExerciseToPlan = (day: string, exercise: any) => {
    const newExercise: Exercise = {
      id: Date.now().toString(),
      name: exercise.name,
      muscle: exercise.muscle,
      category: exercise.category,
      equipment: exercise.equipment,
      sets: 3,
      reps: 10,
      weight: 0,
    }

    setWeeklyPlan((prev) => ({
      ...prev,
      [day]: [...(prev[day] || []), newExercise],
    }))
    setShowExerciseSelector(false)
  }

  const updatePlanExercise = (day: string, exerciseId: string, field: keyof Exercise, value: number) => {
    setWeeklyPlan((prev) => ({
      ...prev,
      [day]: prev[day]?.map((ex) => (ex.id === exerciseId ? { ...ex, [field]: value } : ex)) || [],
    }))
  }

  const startWorkoutFromPlan = (day: string) => {
    const dayPlan = weeklyPlan[day] || []
    const workoutExercises: WorkoutExercise[] = dayPlan.map((exercise) => ({
      id: exercise.id,
      name: exercise.name,
      sets: Array(exercise.sets || 3)
        .fill(null)
        .map(() => ({
          reps: exercise.reps || 10,
          weight: exercise.weight || 0,
          completed: false,
        })),
    }))

    setCurrentWorkout(workoutExercises)
    setActiveTab("workout")
    setIsWorkoutActive(true)
    setIsTimerRunning(true)
  }

  const updateWorkoutSet = (exerciseId: string, setIndex: number, field: "reps" | "weight", value: number) => {
    setCurrentWorkout((prev) =>
      prev.map((ex) =>
        ex.id === exerciseId
          ? {
              ...ex,
              sets: ex.sets.map((set, idx) => (idx === setIndex ? { ...set, [field]: value } : set)),
            }
          : ex,
      ),
    )
  }

  const toggleSetCompletion = async (exerciseId: string, setIndex: number) => {
    const exercise = currentWorkout.find((ex) => ex.id === exerciseId)
    const set = exercise?.sets[setIndex]

    if (!exercise || !set) return

    const newCompletedState = !set.completed

    setCurrentWorkout((prev) =>
      prev.map((ex) =>
        ex.id === exerciseId
          ? {
              ...ex,
              sets: ex.sets.map((set, idx) => (idx === setIndex ? { ...set, completed: newCompletedState } : set)),
            }
          : ex,
      ),
    )

    // Log to API if completing the set and Telegram WebApp is available
    if (newCompletedState && telegramWebApp?.initDataUnsafe?.user?.id) {
      const tgUserId = telegramWebApp.initDataUnsafe.user.id
      await logWorkoutSet(tgUserId, exercise.name, set.weight, set.reps, true)
    }
  }

  const finishWorkout = async () => {
    if (currentWorkout.length > 0) {
      // Finish workout session via API if available
      if (telegramWebApp?.initDataUnsafe?.user?.id) {
        const tgUserId = telegramWebApp.initDataUnsafe.user.id
        await finishWorkoutSession(tgUserId)

        // Reload history from API
        const updatedHistory = await loadWorkoutHistoryFromAPI(tgUserId)
        setWorkoutHistory(updatedHistory)
      } else {
        // Fallback to local storage
        const session: WorkoutSession = {
          id: Date.now().toString(),
          date: new Date().toLocaleDateString(),
          exercises: currentWorkout,
          duration: workoutTimer,
        }
        setWorkoutHistory((prev) => [session, ...prev])
      }

      setCurrentWorkout([])
      setIsWorkoutActive(false)
      setIsTimerRunning(false)
      setWorkoutTimer(0)
      localStorage.removeItem("currentWorkout")
      setActiveTab("history")
    }
  }

  const reorderExercises = (day: string, startIndex: number, endIndex: number) => {
    setWeeklyPlan((prev) => {
      const exercises = [...(prev[day] || [])]
      const [removed] = exercises.splice(startIndex, 1)
      exercises.splice(endIndex, 0, removed)
      return {
        ...prev,
        [day]: exercises,
      }
    })
  }

  const removeExerciseFromPlan = (day: string, exerciseId: string) => {
    setWeeklyPlan((prev) => ({
      ...prev,
      [day]: prev[day]?.filter((exercise) => exercise.id !== exerciseId) || [],
    }))
  }

  const getPreviousWeight = (exerciseName: string): number | null => {
    for (let i = workoutHistory.length - 1; i >= 0; i--) {
      const session = workoutHistory[i]
      const exercise = session.exercises.find((ex) => ex.name === exerciseName)
      if (exercise) {
        const completedSets = exercise.sets.filter((set) => set.completed && set.weight > 0)
        if (completedSets.length > 0) {
          return Math.max(...completedSets.map((set) => set.weight))
        }
      }
    }
    return null
  }

  return (
    <div
      className={`min-h-screen ${isDarkTheme ? "dark" : ""}`}
      style={{ backgroundColor: telegramWebApp?.themeParams.bg_color || undefined }}
    >
      {telegramWebApp?.initDataUnsafe.user && (
        <div className="bg-primary/10 p-2 text-center text-sm">
          {t(userLanguage, "welcome.greeting_name", { name: telegramWebApp.initDataUnsafe.user.first_name })}
          {userLanguage !== "en" && <span className="ml-2">{t(userLanguage, "welcome.language", { lang: userLanguage.toUpperCase() })}</span>}
          {isDevelopment && (
            <div className="mt-1">
              <span className="text-xs text-muted-foreground">{t(userLanguage, "welcome.dev_mode_user_id")} {devUserId}</span>
              <input
                type="number"
                value={devUserId}
                onChange={(e) => setDevUserId(Number(e.target.value))}
                className="ml-2 px-2 py-1 text-xs border rounded w-20"
                placeholder={t(userLanguage, "welcome.user_id_placeholder")}
              />
            </div>
          )}
        </div>
      )}

      {/* Main Content with Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col h-[calc(100vh-80px)]">
        {/* Content Area */}
        <div className="flex-1 px-0 pb-20 overflow-y-auto">
          <TabsContent value="plan" className="space-y-4 mt-0">
            <div className="flex items-center justify-between px-4">
              <h2 className="text-xl font-semibold">{t(userLanguage, "plan.title")}</h2>
            </div>

            <div className="grid grid-cols-7 gap-1 mb-4 px-4">
              {DAYS_OF_WEEK.map((day) => (
                <div
                  key={day}
                  className={`flex-shrink-0 p-2 border rounded-lg cursor-pointer transition-colors ${
                    selectedDay === day ? "border-primary bg-primary/5" : "border-border hover:bg-muted"
                  }`}
                  onClick={() => setSelectedDay(day)}
                >
                  <div className="font-medium mb-1 text-center">{day.slice(0, 3)}</div>

                  <div className="text-xs text-muted-foreground text-center">{weeklyPlan[day]?.length || 0}</div>
                </div>
              ))}
            </div>

            <Card className="relative rounded-none border-x-0">
              <CardHeader className="px-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-lg font-semibold">{selectedDay}</div>
                    <div className="text-sm text-muted-foreground font-normal">{dayAliases[selectedDay]}</div>
                  </div>

                  <Button
                    onClick={() => startWorkoutFromPlan(selectedDay)}
                    disabled={!weeklyPlan[selectedDay]?.length}
                    className="bg-primary text-primary-foreground"
                  >
                    {t(userLanguage, "plan.start_workout")}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4 px-4">
                {weeklyPlan[selectedDay] && weeklyPlan[selectedDay].length > 0 && (
                  <div className="grid grid-cols-[1fr_56px_72px_32px] gap-2 items-center pb-2 mb-2 border-b text-sm font-medium text-muted-foreground">
                    <div className="text-left">{t(userLanguage, "plan.exercise")}</div>
                    <div className="text-right">{t(userLanguage, "plan.sets")}</div>
                    <div className="text-right">{t(userLanguage, "plan.reps")}</div>
                    <div></div>
                  </div>
                )}

                {weeklyPlan[selectedDay]?.map((exercise, index) => (
                  <div
                    key={exercise.id}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData("text/plain", index.toString())
                      e.currentTarget.style.opacity = "0.5"
                    }}
                    onDragEnd={(e) => {
                      e.currentTarget.style.opacity = "1"
                    }}
                    onDragOver={(e) => {
                      e.preventDefault()
                    }}
                    onDrop={(e) => {
                      e.preventDefault()
                      const dragIndex = Number.parseInt(e.dataTransfer.getData("text/plain"))
                      const dropIndex = index
                      if (dragIndex !== dropIndex) {
                        reorderExercises(selectedDay, dragIndex, dropIndex)
                      }
                    }}
                    className="grid grid-cols-[1fr_56px_72px_32px] gap-2 items-center p-3 border border-border rounded-lg hover:bg-muted/50 transition-colors cursor-move"
                  >
                    <div className="flex items-center gap-2">
                      <div className="flex flex-col gap-0.5 text-muted-foreground mr-1">
                        <div className="w-1 h-1 bg-current rounded-full"></div>
                        <div className="w-1 h-1 bg-current rounded-full"></div>
                        <div className="w-1 h-1 bg-current rounded-full"></div>
                        <div className="w-1 h-1 bg-current rounded-full"></div>
                        <div className="w-1 h-1 bg-current rounded-full"></div>
                        <div className="w-1 h-1 bg-current rounded-full"></div>
                      </div>

                      <button
                        type="button"
                        className="font-medium text-left underline decoration-dotted hover:opacity-80 cursor-pointer"
                        onClick={async (e) => {
                          e.stopPropagation()
                          const details = await fetchExerciseDetailsByName(exercise.name)
                          setPlanExercisePreview(
                            details || {
                              name: exercise.name,
                              equipment: exercise.equipment,
                              category: exercise.category,
                              image: undefined,
                              instructions: [],
                            },
                          )
                        }}
                      >
                        {exercise.name}
                      </button>
                    </div>

                    <Input
                      type="text"
                      inputMode="numeric"
                      value={!exercise.sets || exercise.sets === 0 ? "" : exercise.sets}
                      onFocus={(e) => e.currentTarget.select()}
                      onChange={(e) =>
                        updatePlanExercise(
                          selectedDay,
                          exercise.id,
                          "sets",
                          Number.parseInt(e.target.value) || 0,
                        )
                      }
                      onContextMenu={(e) => e.preventDefault()}
                      className="text-right text-sm h-8"
                      placeholder="0"
                    />

                    <Input
                      type="text"
                      inputMode="numeric"
                      value={!exercise.reps || exercise.reps === 0 ? "" : String(exercise.reps)}
                      onFocus={(e) => e.currentTarget.select()}
                      onChange={(e) =>
                        updatePlanExercise(
                          selectedDay,
                          exercise.id,
                          "reps",
                          Number.parseInt(e.target.value.replace(/[^0-9]/g, "")) || 0,
                        )
                      }
                      onContextMenu={(e) => e.preventDefault()}
                      className="text-right text-sm h-8 w-[62px]"
                      placeholder="0"
                    />

                    <div className="flex justify-end">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeExerciseFromPlan(selectedDay, exercise.id)}
                        className="text-destructive hover:text-destructive hover:bg-destructive/10 h-6 w-6 p-0"
                        title={t(userLanguage, "exercise.remove_exercise_title")}
                      >
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                ))}

                {(!weeklyPlan[selectedDay] || weeklyPlan[selectedDay].length === 0) && (
                  <div className="text-center py-8 text-muted-foreground">
                    <div className="mb-2">{t(userLanguage, "plan.no_exercises_for_day", { day: selectedDay })}</div>
                    <div className="text-sm">{t(userLanguage, "plan.add_exercises_hint")}</div>
                  </div>
                )}

                <div className="space-y-2 pt-2 border-t">
                  <Button onClick={() => setShowExerciseSelector(true)} variant="outline" className="w-full">
                    <Plus className="w-4 h-4 mr-2" />
                    {t(userLanguage, "exercise.add_exercise")}
                  </Button>
                </div>
              </CardContent>

              {showExerciseSelector && (
                <ExerciseSelector
                  onSelectExercise={(exercise) => addExerciseToPlan(selectedDay, exercise)}
                  onClose={() => setShowExerciseSelector(false)}
                  userLanguage={userLanguage}
                />
              )}
            </Card>

            {isInitialized && (
              <AIWorkoutPlanner onPlanGenerated={handleAIPlanGenerated} weeklyPlan={weeklyPlan} telegramWebApp={telegramWebApp} devUserId={devUserId} userLanguage={userLanguage} />
            )}
          </TabsContent>

          <TabsContent value="workout" className="space-y-4 mt-0">
            <div className="flex items-center justify-between px-4">
              <h2 className="text-xl font-semibold">{t(userLanguage, "workout.title")}</h2>
              {isWorkoutActive && (
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2 bg-card border border-border rounded-lg px-3 py-2">
                    <Timer className="w-4 h-4" />
                    <span className="text-lg font-mono font-semibold">
                      {Math.floor(workoutTimer / 3600)}:
                      {Math.floor((workoutTimer % 3600) / 60)
                        .toString()
                        .padStart(2, "0")}
                      :{(workoutTimer % 60).toString().padStart(2, "0")}
                    </span>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={toggleWorkoutTimer} className="h-8 w-8 p-0">
                        {isTimerRunning ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={resetWorkoutTimer} className="h-8 w-8 p-0">
                        <Square className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {currentWorkout === null || currentWorkout.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-12 px-4">
                  <Dumbbell className="w-12 h-12 text-muted-foreground mb-4" />
                  <p className="text-muted-foreground text-center">{t(userLanguage, "workout.no_active")}</p>
                  <p className="text-sm text-muted-foreground text-center mt-2">{t(userLanguage, "workout.go_to_plan_hint")}</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {currentWorkout.map((exercise) => (
                  <Card key={exercise.id}>
                    <CardHeader className="px-4">
                      <CardTitle className="text-lg">
                        <button
                          type="button"
                          className="font-medium text-left underline decoration-dotted hover:opacity-80 cursor-pointer"
                          onClick={async (e) => {
                            e.stopPropagation()
                            const details = await fetchExerciseDetailsByName(exercise.name)
                            setPlanExercisePreview(
                              details || {
                                name: exercise.name,
                                equipment: undefined,
                                category: undefined,
                                image: undefined,
                                instructions: [],
                              },
                            )
                          }}
                        >
                          {exercise.name}
                        </button>
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 px-4">
                      <div className="grid grid-cols-5 gap-2 pb-2 border-b border-border text-sm font-medium text-muted-foreground">
                        <div className="text-left">{t(userLanguage, "workout.set")}</div>
                        <div className="text-right">{t(userLanguage, "workout.reps")}</div>
                        <div className="text-right">{t(userLanguage, "workout.weight_lbs")}</div>
                        <div className="text-right">{t(userLanguage, "workout.previous")}</div>
                        <div className="text-right">{t(userLanguage, "workout.done")}</div>
                      </div>
                      {exercise.sets.map((set, setIndex) => (
                        <div
                          key={setIndex}
                          className="grid grid-cols-5 gap-2 items-center p-2 border border-border rounded-lg"
                        >
                          <div className="flex justify-start">
                            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                              <span className="text-sm font-semibold text-primary">{setIndex + 1}</span>
                            </div>
                          </div>
                          <div className="flex justify-end">
                            <Input
                              type="text"
                              inputMode="numeric"
                              value={set.reps === 0 ? "" : set.reps}
                              onFocus={(e) => e.currentTarget.select()}
                              onChange={(e) =>
                                updateWorkoutSet(
                                  exercise.id,
                                  setIndex,
                                  "reps",
                                  Number.parseInt(e.target.value) || 0,
                                )
                              }
                              onContextMenu={(e) => e.preventDefault()}
                              className="w-20 text-right"
                              placeholder="0"
                            />
                          </div>
                          <div className="flex justify-end">
                            <Input
                              type="text"
                              inputMode="numeric"
                              value={set.weight === 0 ? "" : set.weight}
                              onFocus={(e) => e.currentTarget.select()}
                              onChange={(e) =>
                                updateWorkoutSet(
                                  exercise.id,
                                  setIndex,
                                  "weight",
                                  Number.parseInt(e.target.value) || 0,
                                )
                              }
                              onContextMenu={(e) => e.preventDefault()}
                              className={`w-16 text-right ${(() => {
                                const previousWeight = getPreviousWeight(exercise.name)
                                return previousWeight && set.weight >= previousWeight
                                  ? "border-green-500 bg-green-50"
                                  : ""
                              })()}`}
                              placeholder="0"
                            />
                          </div>
                          <div className="flex justify-end">
                            {(() => {
                              const previousWeight = getPreviousWeight(exercise.name)
                              return previousWeight ? (
                                <span className="text-sm text-muted-foreground">{previousWeight}</span>
                              ) : (
                                <span className="text-sm text-muted-foreground">-</span>
                              )
                            })()}
                          </div>
                          <div className="flex justify-end">
                            <Button
                              variant={set.completed ? "default" : "outline"}
                              size="sm"
                              onClick={() => toggleSetCompletion(exercise.id, setIndex)}
                              className={`w-8 h-8 p-0 ${set.completed ? "bg-primary text-primary-foreground" : ""}`}
                            >
                              ✓
                            </Button>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                ))}

                <div className="flex gap-3 px-4">
                  <Button
                  onClick={() => {
                    setCurrentWorkout([])
                    setActiveTab("plan")
                  }}
                  variant="outline"
                  className="flex-1"
                  size="lg"
                >
                  {t(userLanguage, "workout.cancel")}
                </Button>
                <Button onClick={finishWorkout} className="flex-1 bg-primary text-primary-foreground" size="lg">
                  {t(userLanguage, "workout.finish")}
                </Button>
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="history" className="space-y-4 mt-0">
            <div className="flex items-center justify-between px-4">
              <h2 className="text-xl font-semibold">{t(userLanguage, "history.title")}</h2>
              <div className="flex gap-2">
                <Button
                  variant={historyView === "sessions" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setHistoryView("sessions")}
                >
                  {t(userLanguage, "history.sessions")}
                </Button>
                <Button
                  variant={historyView === "stats" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setHistoryView("stats")}
                >
                  {t(userLanguage, "history.stats")}
                </Button>
              </div>
            </div>

            {workoutHistory.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-12">
                  <History className="w-12 h-12 text-muted-foreground mb-4" />
                  <p className="text-muted-foreground text-center">{t(userLanguage, "history.no_history")}</p>
                  <p className="text-sm text-muted-foreground text-center mt-2">{t(userLanguage, "history.complete_first_hint")}</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {historyView === "stats" &&
                  (() => {
                    const stats = calculateWorkoutStats(workoutHistory)
                    const prs = calculatePersonalRecords(workoutHistory)

                    if (!stats) return null

                    return (
                      <>
                        {/* Overview Stats */}
                        <div className="grid grid-cols-2 gap-4">
                          <StatCard title={t(userLanguage, "history.total_workouts")} value={stats.totalWorkouts} icon={Dumbbell} trend="up" />
                          <StatCard
                            title={t(userLanguage, "history.avg_duration")}
                            value={`${Math.floor(stats.avgDuration / 60)}:${(stats.avgDuration % 60).toString().padStart(2, "0")}`}
                            icon={Timer}
                          />
                          <StatCard
                            title={t(userLanguage, "history.total_volume")}
                            value={`${Math.round(stats.totalVolume / 1000)}k`}
                            subtitle={t(userLanguage, "history.lbs_lifted")}
                            icon={BarChart3}
                            trend="up"
                          />
                          <StatCard
                            title={t(userLanguage, "history.this_week")}
                            value={
                              workoutHistory.filter((session) => {
                                const sessionDate = new Date(session.date)
                                const weekAgo = new Date()
                                weekAgo.setDate(weekAgo.getDate() - 7)
                                return sessionDate >= weekAgo
                              }).length
                            }
                            subtitle={t(userLanguage, "history.workouts")}
                            icon={Target}
                          />
                        </div>

                        {/* Top Exercises */}
                        <Card>
                          <CardHeader>
                            <CardTitle className="text-lg flex items-center gap-2">
                              <TrendingUp className="w-5 h-5" />
                              {t(userLanguage, "history.most_frequent")}
                            </CardTitle>
                          </CardHeader>
                          <CardContent className="space-y-3 px-4">
                            {stats.topExercises.map(([exercise, count], index) => (
                              <div key={exercise} className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                                    <span className="text-sm font-semibold text-primary">#{index + 1}</span>
                                  </div>
                                  <span className="font-medium">{exercise}</span>
                                </div>
                                <Badge variant="secondary">{count} {t(userLanguage, "history.times")}</Badge>
                              </div>
                            ))}
                          </CardContent>
                        </Card>

                        {/* Personal Records */}
                        <Card>
                          <CardHeader>
                            <CardTitle className="text-lg flex items-center gap-2">
                              <Award className="w-5 h-5" />
                              {t(userLanguage, "history.personal_records")}
                            </CardTitle>
                          </CardHeader>
                          <CardContent className="space-y-3 px-4">
                            {prs.length === 0 ? (
                              <p className="text-muted-foreground text-center py-4">{t(userLanguage, "history.pr_more_needed")}</p>
                            ) : (
                              prs.map(([exercise, record]) => (
                                <div
                                  key={exercise}
                                  className="flex items-center justify-between p-3 border border-border rounded-lg"
                                >
                                  <div>
                                    <p className="font-medium">{exercise}</p>
                                    <p className="text-sm text-muted-foreground">{record.date}</p>
                                  </div>
                                  <div className="text-right">
                                    <p className="font-semibold">{record.weight} {t(userLanguage, "units.lbs")}</p>
                                    <p className="text-sm text-muted-foreground">{record.reps} {t(userLanguage, "units.reps")}</p>
                                  </div>
                                </div>
                              ))
                            )}
                          </CardContent>
                        </Card>

                        {/* Recent Progress for Top Exercise */}
                        {stats.topExercises.length > 0 &&
                          (() => {
                            const topExercise = stats.topExercises[0][0]
                            const progress = getRecentProgress(workoutHistory, topExercise)

                            return progress.length > 1 ? (
                              <Card>
                                <CardHeader>
                                  <CardTitle className="text-lg">{t(userLanguage, "history.recent_progress", { exercise: topExercise })}</CardTitle>
                                </CardHeader>
                                <CardContent className="px-4">
                                  <div className="space-y-2">
                                    {progress.map((session, index) => (
                                      <div
                                        key={index}
                                        className="flex items-center justify-between p-2 border border-border rounded"
                                      >
                                        <span className="text-sm text-muted-foreground">{session?.date}</span>
                                        <div className="flex items-center gap-2">
                                          <Badge variant="outline" className="text-xs">
                                            {session?.reps} × {session?.weight} {t(userLanguage, "units.lbs")}
                                          </Badge>
                                          {index < progress.length - 1 && (
                                            <div className="flex items-center">
                                              {session?.weight && progress[index + 1]?.weight && session.weight > (progress[index + 1]?.weight || 0) ? (
                                                <TrendingUp className="w-3 h-3 text-green-500" />
                                              ) : session?.weight && progress[index + 1]?.weight && session.weight < (progress[index + 1]?.weight || 0) ? (
                                                <TrendingUp className="w-3 h-3 text-red-500 rotate-180" />
                                              ) : (
                                                <div className="w-3 h-3" />
                                              )}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </CardContent>
                              </Card>
                            ) : null
                          })()}
                      </>
                    )
                  })()}

                {historyView === "sessions" && (
                  <>
                    {workoutHistory.map((session) => (
                      <Card key={session.id}>
                        <CardHeader>
                          <div className="flex items-center justify-between">
                            <CardTitle className="text-lg">{session.date}</CardTitle>
                            <div className="flex items-center gap-2">
                              <Badge variant="secondary">
                                {Math.floor(session.duration / 60)}:
                                {(session.duration % 60).toString().padStart(2, "0")}
                              </Badge>
                              <Badge variant="outline" className="text-xs">
                                {session.exercises.reduce(
                                  (total, ex) => total + ex.sets.filter((set) => set.completed).length,
                                  0,
                                )}{" "}
                                sets
                              </Badge>
                            </div>
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-3 px-4">
                          {session.exercises.map((exercise) => (
                            <div key={exercise.id} className="border-l-2 border-primary pl-4">
                              <p className="font-medium">{exercise.name}</p>
                              <div className="flex flex-wrap gap-2 mt-1">
                                {exercise.sets.map((set, idx) => (
                                  <Badge key={idx} variant={set.completed ? "default" : "outline"} className="text-xs">
                                    {set.reps} × {set.weight}lbs
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          ))}
                        </CardContent>
                      </Card>
                    ))}
                  </>
                )}
              </div>
            )}
          </TabsContent>
        </div>

        {/* Bottom Navigation */}
        <div
          className="fixed bottom-0 left-0 right-0 bg-card border-t border-border pb-safe"
          style={{ backgroundColor: telegramWebApp?.themeParams.secondary_bg_color || undefined }}
        >
          <TabsList className="grid w-full grid-cols-3 h-16 bg-transparent">
            <TabsTrigger
              value="plan"
              className="flex flex-col gap-1 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
              style={{
                backgroundColor: activeTab === "plan" ? telegramWebApp?.themeParams.button_color : undefined,
                color: activeTab === "plan" ? telegramWebApp?.themeParams.button_text_color : undefined,
              }}
            >
              <Calendar className="w-5 h-5" />
              <span className="text-xs">{t(userLanguage, "tabs.plan")}</span>
            </TabsTrigger>
            <TabsTrigger
              value="workout"
              className="flex flex-col gap-1 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
              style={{
                backgroundColor: activeTab === "workout" ? telegramWebApp?.themeParams.button_color : undefined,
                color: activeTab === "workout" ? telegramWebApp?.themeParams.button_text_color : undefined,
              }}
            >
              <Dumbbell className="w-5 h-5" />
              <span className="text-xs">{t(userLanguage, "tabs.workout")}</span>
            </TabsTrigger>
            <TabsTrigger
              value="history"
              className="flex flex-col gap-1 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
              style={{
                backgroundColor: activeTab === "history" ? telegramWebApp?.themeParams.button_color : undefined,
                color: activeTab === "history" ? telegramWebApp?.themeParams.button_text_color : undefined,
              }}
            >
              <History className="w-5 h-5" />
              <span className="text-xs">{t(userLanguage, "tabs.history")}</span>
            </TabsTrigger>
          </TabsList>
        </div>
      </Tabs>
      {/* Preview dialog for exercises already in the plan */}
      <ExercisePreviewDialog exercise={planExercisePreview} onClose={() => setPlanExercisePreview(null)} userLanguage={userLanguage} />
    </div>
  )
}
