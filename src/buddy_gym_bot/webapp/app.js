const tg = window.Telegram.WebApp;

const form = document.getElementById("log-form");
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = {
    tg_user_id: tg?.initDataUnsafe?.user?.id,
    exercise: form.exercise.value,
    sets: Number(form.sets.value),
    reps: Number(form.reps.value),
    weight: Number(form.weight.value),
    rpe: Number(form.rpe.value) || 0,
  };
  try {
    await fetch("/webapp/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    tg.close();
  } catch (err) {
    alert("Failed to log set");
  }
});
