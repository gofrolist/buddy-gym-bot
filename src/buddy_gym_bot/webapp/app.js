const tg = window.Telegram.WebApp;

const form = document.getElementById("log-form");
const workoutList = document.getElementById("workout-list");
const totalWeightEl = document.getElementById("total-weight");
const totalRepsEl = document.getElementById("total-reps");
const avgWeightEl = document.getElementById("avg-weight");
const toggleBtn = document.getElementById("toggle-btn");
const finishBtn = document.getElementById("finish-btn");
const resetBtn = document.getElementById("reset-btn");

let workout = [];
let isRunning = false;

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = {
    tg_user_id: tg?.initDataUnsafe?.user?.id,
    exercise: form.exercise.value,
    reps: Number(form.reps.value),
    weight: Number(form.weight.value),
  };
  try {
    await fetch("/webapp/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...data, sets: 1, rpe: 0 }),
    });
    workout.push(data);
    renderWorkout();
    form.reps.value = "";
    form.weight.value = "";
  } catch (err) {
    alert("Failed to log set");
  }
});

function renderWorkout() {
  workoutList.innerHTML = "";
  workout.forEach((set) => {
    const div = document.createElement("div");
    div.className = "set-item";
    div.textContent = `${set.exercise}: ${set.weight} kg × ${set.reps} reps`;
    workoutList.appendChild(div);
  });

  const totalWeight = workout.reduce((acc, cur) => acc + cur.weight * cur.reps, 0);
  const totalReps = workout.reduce((acc, cur) => acc + cur.reps, 0);
  const avgWeight = totalReps ? (totalWeight / totalReps).toFixed(1) : 0;

  totalWeightEl.textContent = (totalWeight / 1000).toFixed(2) + " ton";
  totalRepsEl.textContent = totalReps;
  avgWeightEl.textContent = avgWeight + " kg";
}

toggleBtn.addEventListener("click", () => {
  isRunning = !isRunning;
  toggleBtn.textContent = isRunning ? "Pause" : "Start";
});

finishBtn.addEventListener("click", () => tg.close());

resetBtn.addEventListener("click", () => {
  workout = [];
  renderWorkout();
});
