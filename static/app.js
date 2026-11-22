const token = localStorage.getItem("kendo_token");

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Erro na operação");
  return data;
}

async function loadProfile() {
  if (!token) return null;
  try {
    return await api("/api/me");
  } catch (error) {
    localStorage.removeItem("kendo_token");
    return null;
  }
}

async function initDashboard() {
  const profile = await loadProfile();
  if (!profile) {
    document.getElementById("hero-name").textContent = "VISITANTE";
    document.getElementById("level").textContent = "01";
    document.getElementById("xp-label").textContent = "0 XP";
    document.getElementById("next-mission").textContent = "Crie uma conta para começar.";
    return;
  }

  document.getElementById("hero-name").textContent = profile.username.toUpperCase();
  document.getElementById("level").textContent = String(profile.level).padStart(2, "0");
  document.getElementById("xp-label").textContent = `${profile.xp} XP`;
  const levelRanges = [0, 250, 500, 750, 1000, 1250];
  const levelIndex = Math.min(profile.level - 1, levelRanges.length - 1);
  const currentLevelXp = levelRanges[levelIndex];
  const nextLevelXp = levelRanges[levelIndex + 1] || currentLevelXp + 100;
  const progress = nextLevelXp === currentLevelXp
    ? 100
    : ((profile.xp - currentLevelXp) / (nextLevelXp - currentLevelXp)) * 100;
  document.getElementById("xp-bar").style.width = `${Math.max(0, Math.min(100, progress))}%`;

  const missions = await api("/api/missions");
  const next = missions.find((mission) => !mission.completed && !mission.locked);
  document.getElementById("next-mission").textContent = next ? next.title : "Todas as missões disponíveis concluídas.";
}

async function initMissions() {
  if (!token) {
    document.getElementById("mission-list").innerHTML = '<p class="muted">Entre no sistema para visualizar as missões.</p><a class="button" href="/auth">ACESSAR</a>';
    return;
  }

  try {
    const [missions, profile] = await Promise.all([api("/api/missions"), loadProfile()]);
    const playerLevel = profile ? profile.level : 0;
    const maximumLevel = Math.max(...missions.map((mission) => mission.level_required));
    const levelTabs = document.getElementById("level-tabs");

    levelTabs.innerHTML = Array.from({ length: maximumLevel }, (_, index) => {
      const level = index + 1;
      return `<button type="button" class="level-tab ${level === 1 ? "active" : ""}" data-level="${level}">NÍVEL ${String(level).padStart(2, "0")}</button>`;
    }).join("");

    document.getElementById("mission-count").textContent = `${missions.filter((mission) => !mission.completed).length} ATIVAS`;

    const renderLevel = (level) => {
      const levelMissions = missions.filter((mission) => mission.level_required === level);
      document.getElementById("mission-list").innerHTML = levelMissions.map((mission) => {
        const inaccessible = mission.level_required > playerLevel;
        return `
          <article class="mission ${mission.completed ? "completed" : ""} ${inaccessible ? "locked" : ""}">
            <div>
              ${mission.image ? `<img class="mission-image" src="${mission.image}" alt="${mission.title}">` : ""}
              <span class="mission-meta">${mission.category} / NÍVEL ${String(mission.level_required).padStart(2, "0")}</span>
              <h2>${mission.title}</h2>
              <p>${mission.objective}</p>
              <details>
                <summary>INSTRUÇÕES</summary>
                <p>${mission.description}</p>
                <p><strong>Complemento:</strong> ${mission.strength_complement}</p>
              </details>
            </div>
            <div>
              <span class="mission-meta">+${mission.xp} XP</span>
              ${mission.completed ? '<button disabled>CONCLUÍDA</button>' : inaccessible ? '<button disabled>BLOQUEADA</button>' : `<button data-complete="${mission.id}">CONCLUIR</button>`}
            </div>
          </article>
        `;
      }).join("") || '<p class="muted">Nenhuma missão neste nível.</p>';

      document.querySelectorAll("[data-complete]").forEach((button) => {
        button.addEventListener("click", async () => {
          button.disabled = true;
          try {
            await api(`/api/missions/${button.dataset.complete}/complete`, { method: "POST", body: "{}" });
            location.reload();
          } catch (error) {
            alert(error.message);
            button.disabled = false;
          }
        });
      });
    };

    levelTabs.querySelectorAll("[data-level]").forEach((tab) => {
      tab.addEventListener("click", () => {
        levelTabs.querySelectorAll("[data-level]").forEach((item) => item.classList.remove("active"));
        tab.classList.add("active");
        renderLevel(Number(tab.dataset.level));
      });
    });

    renderLevel(1);
  } catch (error) {
    document.getElementById("mission-list").innerHTML = `<p class="muted">${error.message}</p>`;
  }
}

async function initRank() {
  const profile = await loadProfile();
  if (profile) {
    document.getElementById("rank-name").textContent = profile.username.toUpperCase();
    document.getElementById("rank-xp").textContent = `${profile.xp} XP / NÍVEL ${String(profile.level).padStart(2, "0")}`;
  }
}

async function submitAuth(mode) {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const message = document.getElementById("auth-message");
  message.textContent = "PROCESSANDO...";

  try {
    const data = await api(`/api/${mode}`, {
      method: "POST",
      body: JSON.stringify({ username, password })
    });
    localStorage.setItem("kendo_token", data.token);
    location.href = "/";
  } catch (error) {
    message.textContent = error.message.toUpperCase();
  }
}

function initAuth() {
  const form = document.getElementById("auth-form");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitAuth("login");
  });
  document.getElementById("register-button").addEventListener("click", () => {
    submitAuth("register");
  });
}

if (token) {
  const authLink = document.getElementById("auth-link");
  if (authLink) {
    authLink.textContent = "SAIR";
    authLink.href = "/auth";
    authLink.addEventListener("click", (event) => {
      event.preventDefault();
      localStorage.removeItem("kendo_token");
      location.href = "/";
    });
  }
}

if (document.getElementById("level")) initDashboard();
if (document.getElementById("mission-list")) initMissions();
if (document.getElementById("rank-name")) initRank();
if (document.getElementById("auth-form")) initAuth();
