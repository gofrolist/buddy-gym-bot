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
  const [sets, setSets] = useState<{ weight: string; reps: string; done: boolean; }[]>([
    { weight: "20", reps: "5", done: false }
  ]);
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

  async function saveSet(index: number) {
    const s = sets[index];
    const body = {
      tg_id: user?.id || 0,
      exercise,
      weight_kg: parseFloat(s.weight),
      reps: parseInt(s.reps, 10),
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
      setSets(prev => prev.map((p, i) => i === index ? { ...p, done: true } : p));
    } else {
      alert("Error");
    }
  }

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: 12, color: "#e7e7e7", background: "#101214", minHeight: "100vh" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <h2 style={{ margin: 0 }}>{t("title")}</h2>
        <button style={finishBtn}>{t("finish")}</button>
      </div>

      <label>{t("exercise")}</label>
      <input
        list="exlist"
        value={exercise}
        onChange={e => { setExercise(e.target.value); queryExercises(e.target.value); }}
        placeholder="Bench Press"
        style={inp}
      />
      <datalist id="exlist">
        {suggestions.map((s: any) => <option key={s.id} value={s.name} />)}
      </datalist>

      {exercise && (
        <>
          <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 12 }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}>#</th>
                <th style={{ textAlign: "left" }}>{t("weight")}</th>
                <th style={{ textAlign: "left" }}>{t("reps")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sets.map((s, i) => (
                <tr key={i}>
                  <td style={{ paddingRight: 8 }}>{i + 1}</td>
                  <td style={{ paddingRight: 8 }}>
                    <input
                      value={s.weight}
                      disabled={s.done}
                      onChange={e => setSets(prev => prev.map((p, idx) => idx === i ? { ...p, weight: e.target.value } : p))}
                      style={inpSmall}
                    />
                  </td>
                  <td style={{ paddingRight: 8 }}>
                    <input
                      value={s.reps}
                      disabled={s.done}
                      onChange={e => setSets(prev => prev.map((p, idx) => idx === i ? { ...p, reps: e.target.value } : p))}
                      style={inpSmall}
                    />
                  </td>
                  <td>{s.done ? "✅" : <button onClick={() => saveSet(i)} style={smallBtn}>✓</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <button
            onClick={() => setSets(prev => [...prev, { weight: prev[prev.length - 1]?.weight || "", reps: prev[prev.length - 1]?.reps || "", done: false }])}
            style={btn}
          >
            {t("add_set")}
          </button>
        </>
      )}
    </div>
  );
}

const inp: React.CSSProperties = { width: "100%", padding: 10, borderRadius: 10, border: "1px solid #333", background: "#1b1f24", color: "#e7e7e7", marginBottom: 12 };
const inpSmall: React.CSSProperties = { width: "100%", padding: 8, borderRadius: 8, border: "1px solid #333", background: "#1b1f24", color: "#e7e7e7" };
const btn: React.CSSProperties = { width: "100%", padding: 12, borderRadius: 12, border: "1px solid #2b2b2b", background: "#0a84ff", color: "white", fontWeight: 600, marginTop: 8 };
const smallBtn: React.CSSProperties = { padding: 8, borderRadius: 8, border: "1px solid #2b2b2b", background: "#0a84ff", color: "white", fontWeight: 600 };
const finishBtn: React.CSSProperties = { padding: 8, borderRadius: 8, border: "1px solid #2b2b2b", background: "#0a84ff", color: "white", fontWeight: 600 };
