import React, { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

declare global {
  interface Window { Telegram: any }
}

function tgUser() {
  try {
    return window.Telegram?.WebApp?.initDataUnsafe?.user;
  } catch { return null; }
}

export default function App() {
  const { t, i18n } = useTranslation();
  const user = useMemo(() => tgUser(), []);
  const [exercise, setExercise] = useState("");
  const [weight, setWeight] = useState("60");
  const [reps, setReps] = useState("5");
  const [suggestions, setSuggestions] = useState<any[]>([]);

  useEffect(() => {
    const lc = user?.language_code?.slice(0,2) || "en";
    i18n.changeLanguage(lc);
    try { window.Telegram?.WebApp?.expand?.(); } catch {}
  }, [user]);

  async function queryExercises(q: string) {
    if (!q) return setSuggestions([]);
    console.log("Querying exercises:", q);
    const resp = await fetch(`/api/v1/exercises/search?q=${encodeURIComponent(q)}`);
    console.log("Exercise search response:", resp);
    const data = await resp.json();
    setSuggestions(data.items || []);
  }

  async function addSet() {
    const body = {
      tg_id: user?.id || 0,
      exercise,
      weight_kg: parseFloat(weight),
      reps: parseInt(reps, 10),
    };
    console.log("Sending set:", body);
    const resp = await fetch("/api/v1/track/set", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    console.log("Add set response:", resp);
    const data = await resp.json();
    console.log("Add set response data:", data);
    if (data.ok) {
      try { window.Telegram?.WebApp?.showPopup({ title: "Saved ✅", message: t("saved") }); } catch {}
      setExercise("");
    } else {
      alert("Error");
    }
  }

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: 12, color: "#e7e7e7", background: "#101214", minHeight: "100vh" }}>
      <h2 style={{ margin: 0, marginBottom: 8 }}>{t("title")}</h2>
      <label>{t("exercise")}</label>
      <input list="exlist" value={exercise} onChange={e => { setExercise(e.target.value); queryExercises(e.target.value); }} placeholder="Bench Press" style={inp}/>
      <datalist id="exlist">
        {suggestions.map((s) => <option key={s.id} value={s.name} />)}
      </datalist>

      <div style={{ display: "flex", gap: 8 }}>
        <div style={{ flex: 1 }}>
          <label>{t("weight")}</label>
          <input value={weight} onChange={e=>setWeight(e.target.value)} style={inp} />
        </div>
        <div style={{ width: 100 }}>
          <label>{t("reps")}</label>
          <input value={reps} onChange={e=>setReps(e.target.value)} style={inp} />
        </div>
      </div>

      <button onClick={addSet} style={btn}>{t("add_set")}</button>
    </div>
  )
}

const inp: React.CSSProperties = { width: "100%", padding: 10, borderRadius: 10, border: "1px solid #333", background: "#1b1f24", color: "#e7e7e7", marginBottom: 12 };
const btn: React.CSSProperties = { width: "100%", padding: 12, borderRadius: 12, border: "1px solid #2b2b2b", background: "#0a84ff", color: "white", fontWeight: 600 };
