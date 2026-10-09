const el = (id) => document.getElementById(id);

const BAND_ORDER = ["optimal", "good", "improve"];
const BAND_LABEL = { optimal: "Optimal", good: "Good", improve: "Needs work" };
/* DailyMetrics field, chart title and y axis unit for each wearable metric. */
const METRICS = [
  ["resting_hr_bpm", "Resting heart rate", "bpm"],
  ["steps", "Steps", "steps"],
  ["sleep_efficiency_pct", "Sleep efficiency", "%"],
];
/* --optimal and --good from styles.css, translucent, for the chart bands. */
const BAND_FILL = { optimal: "rgb(47 111 98 / 0.2)", good: "rgb(168 130 60 / 0.2)" };

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return body;
}

/* Draw timestamps and wearable days are both shown as a calendar date. Parsing
   the date part as local midnight keeps a date-only string from being read as
   UTC and shifting a day in western timezones. */
function formatDate(iso) {
  return new Date(`${iso.slice(0, 10)}T00:00`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/* The scale spans the full width of every band the marker defines. Bands are
   laid out in value order, not in optimal/good/improve order, so that the tick
   sits in a place that means something. */
function scaleFor(ranges) {
  const bands = BAND_ORDER.map((band) => ({
    band,
    min: ranges[band].min,
    max: ranges[band].max,
  })).sort((a, b) => a.min - b.min);

  const low = bands[0].min;
  const high = bands[bands.length - 1].max;
  const span = high - low || 1;

  return { bands, low, high, span };
}

/* The only chart code in the app. A line per dataset, gaps left open, unit on
   the y axis; hovering a date lists every dataset's value there. */
function lineChart(canvas, labels, datasets, unit) {
  return new Chart(canvas, {
    type: "line",
    data: { labels, datasets },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      spanGaps: false,
      interaction: { mode: "index", intersect: false },
      scales: { y: { title: { display: true, text: unit } } },
      plugins: { legend: { display: false } },
    },
  });
}

function renderMarker(result, points) {
  const { bands, low, high, span } = scaleFor(result.ranges);
  const offset = Math.min(100, Math.max(0, ((result.value - low) / span) * 100));

  const node = document.createElement("article");
  node.className = "marker";
  node.innerHTML = `
    <div class="marker-head">
      <span>
        <span class="marker-name"></span>
        <button type="button" class="quiet history-toggle" aria-expanded="false"></button>
      </span>
      <span>
        <span class="marker-value"></span><span class="marker-unit"></span>
        <span class="marker-status status-${result.status}"></span>
      </span>
    </div>
    <div class="scale-wrap">
      <div class="scale">
        ${bands
          .map(
            (b) =>
              `<div class="band band-${b.band}" style="width:${
                ((b.max - b.min) / span) * 100
              }%"></div>`
          )
          .join("")}
      </div>
      <div class="tick" style="left:${offset}%"></div>
    </div>
    <div class="scale-labels"><span class="low"></span><span class="high"></span></div>
  `;

  node.querySelector(".marker-name").textContent = result.name;
  node.querySelector(".marker-value").textContent = result.value;
  node.querySelector(".marker-unit").textContent = result.unit;
  node.querySelector(".marker-status").textContent =
    BAND_LABEL[result.status] ?? result.status;
  node.querySelector(".low").textContent = low;
  node.querySelector(".high").textContent = high;

  /* The chart is built on the first click and toggled after that. Bands are
     the optimal and good ranges recorded at each draw, held until the next
     draw, so a changed range shows as a step. */
  const toggle = node.querySelector(".history-toggle");
  toggle.textContent = `History (${points.length})`;
  let chart = null;
  toggle.addEventListener("click", () => {
    if (chart) {
      chart.hidden = !chart.hidden;
    } else {
      chart = document.createElement("div");
      chart.className = "chart";
      chart.innerHTML = "<canvas></canvas>";
      node.append(chart);
      const datasets = [
        { label: result.name, data: points.map((p) => p.value), borderColor: "#1b1f1d" },
      ];
      for (const band of ["optimal", "good"]) {
        for (const edge of ["max", "min"]) {
          datasets.push({
            label: `${BAND_LABEL[band]} ${edge}`,
            data: points.map((p) => p.ranges[band][edge]),
            stepped: "before",
            pointRadius: 0,
            borderWidth: 0,
            fill: edge === "max" ? "+1" : false,
            backgroundColor: BAND_FILL[band],
          });
        }
      }
      const labels = points.map((p) => formatDate(p.tested_at));
      lineChart(chart.firstChild, labels, datasets, result.unit);
    }
    toggle.setAttribute("aria-expanded", String(!chart.hidden));
  });
  return node;
}

function renderResults(results, history) {
  const root = el("results");
  root.replaceChildren();

  if (results.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No results yet. They appear here after your first draw.";
    root.append(empty);
    return;
  }

  let category = null;
  for (const result of results) {
    if (result.category !== category) {
      category = result.category;
      const heading = document.createElement("h2");
      heading.className = "category";
      heading.textContent = category;
      root.append(heading);
    }
    root.append(renderMarker(result, history[result.biomarker_id]));
  }
}

/* One chart per metric over the 30 days the server returned. A day without a
   value is a gap in the line. A metric with no value at all is a line of text:
   the provider sent data and never included it, or nothing arrived at all. */
function renderWearables(wearables) {
  const root = el("wearables");
  root.hidden = !wearables;
  root.replaceChildren();
  if (!wearables) return;

  const { provider, days } = wearables;
  const heading = document.createElement("h2");
  heading.className = "category";
  heading.textContent = "wearables";
  const lede = document.createElement("p");
  lede.className = "lede";
  lede.textContent = `From ${provider}, 30 days to ${formatDate(days.at(-1).date)}`;
  root.append(heading, lede);

  const labels = days.map((d) => formatDate(d.date));
  for (const [field, title, unit] of METRICS) {
    const block = document.createElement("article");
    block.className = "marker";
    block.innerHTML = `
      <div class="marker-head">
        <span class="marker-name"></span><span class="marker-unit"></span>
      </div>
    `;
    block.querySelector(".marker-name").textContent = title;
    block.querySelector(".marker-unit").textContent = unit;
    root.append(block);

    const values = days.map((d) => d[field]);
    if (values.every((v) => v === null)) {
      const empty = document.createElement("p");
      empty.className = "lede";
      empty.textContent = days.some((d) => d.upload_id)
        ? `Not reported by ${provider}`
        : "No data in this period";
      block.append(empty);
      continue;
    }
    const chart = document.createElement("div");
    chart.className = "chart";
    chart.innerHTML = "<canvas></canvas>";
    block.append(chart);
    const series = [{ label: title, data: values, borderColor: "#1b1f1d" }];
    lineChart(chart.firstChild, labels, series, unit);
  }
}

async function showDashboard(user) {
  el("signin").hidden = true;
  el("dashboard").hidden = false;
  el("whoami").textContent = user.name;

  const { data, meta } = await api("/api/home");
  renderResults(data.results, data.history);
  renderWearables(data.wearables);

  const latest = meta.tested_at || data.results[0]?.tested_at;
  el("drawn").textContent = latest ? `Drawn ${formatDate(latest)}` : "";
}

function showSignIn(message) {
  el("dashboard").hidden = true;
  el("signin").hidden = false;
  const error = el("signin-error");
  error.hidden = !message;
  error.textContent = message || "";
}

el("signin-button").addEventListener("click", async () => {
  const email = el("email").value.trim();
  if (!email) {
    showSignIn("Enter an email address to sign in.");
    return;
  }
  try {
    const { data } = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    await showDashboard(data.user);
  } catch (err) {
    showSignIn(err.message);
  }
});

el("email").addEventListener("keydown", (event) => {
  if (event.key === "Enter") el("signin-button").click();
});

el("signout-button").addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" });
  el("email").value = "";
  showSignIn();
});

(async function start() {
  try {
    const { data } = await api("/api/me");
    await showDashboard(data.user);
  } catch {
    showSignIn();
  }
})();
