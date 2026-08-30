const fmt = new Intl.NumberFormat("ja-JP");
const ACTIONS_BASE =
  "https://github.com/lalakuma/KabuRadar3/actions/workflows/daily-screening.yml";

function formatIncome(n) {
  const sign = n > 0 ? "+" : "";
  return `${sign}${fmt.format(n)}`;
}

function incomeClass(n) {
  if (n > 0) return "positive";
  if (n < 0) return "negative";
  return "zero";
}

function escapeHtml(text) {
  const d = document.createElement("div");
  d.textContent = text ?? "";
  return d.innerHTML;
}

function starsLabel(n) {
  const v = Math.max(1, Math.min(5, Number(n) || 3));
  return "★".repeat(v) + "☆".repeat(5 - v);
}

function renderSignalRows(container, rows, emptyText) {
  if (!rows?.length) {
    container.innerHTML = `<li class="signal-empty">${escapeHtml(emptyText)}</li>`;
    return;
  }
  container.innerHTML = rows
    .map((row) => {
      const close =
        row.close != null ? `<span class="signal-close">¥${fmt.format(row.close)}</span>` : "";
      const pnl =
        row.pnl != null
          ? `<span class="signal-pnl ${incomeClass(row.pnl)}">${formatIncome(row.pnl)}</span>`
          : "";
      const flags = [];
      if (row.rsi_ok) flags.push("RSI ✓");
      if (row.rci_ok) flags.push("RCI V ✓");
      const flagHtml = flags.length
        ? `<span class="signal-flags">${flags.map(escapeHtml).join(" · ")}</span>`
        : "";
      const q = row.quality;
      const qualityHtml = q
        ? `<span class="signal-quality" title="${escapeHtml(q.background || "")}">${starsLabel(q.stars)}</span>`
        : "";
      const bg = q?.background
        ? `<p class="signal-bg">${escapeHtml(q.background)}</p>`
        : "";
      return `<li class="signal-item">
        <div class="signal-head">
          <span class="code">${escapeHtml(row.code)}</span>
          <span class="name">${escapeHtml(row.name)}</span>
          ${qualityHtml}
          ${close}
          ${pnl}
        </div>
        ${flagHtml}
        ${bg}
      </li>`;
    })
    .join("");
}

function renderBuyTimeline(daily) {
  const timeline = document.getElementById("daily-buy-timeline");
  const meta = document.getElementById("daily-buy-meta");
  const buyDays = daily?.buy_days || (daily?.days || []).filter((d) => (d.new_buy_count ?? 0) > 0);
  const totalDays = daily?.days?.length ?? 0;

  if (!buyDays.length) {
    meta.textContent = totalDays ? `直近 ${totalDays} 営業日 · 買いシグナルなし` : "データなし";
    timeline.innerHTML = `<li class="signal-empty">この期間に買い（新買）シグナルはありません</li>`;
    return;
  }

  const totalBuys = buyDays.reduce((n, d) => n + (d.new_buy_count ?? 0), 0);
  meta.textContent = `直近 ${totalDays} 営業日 · 買いあり ${buyDays.length} 日 · 計 ${totalBuys} 件`;

  timeline.innerHTML = buyDays
    .map((day) => {
      const stocks = (day.new_buy || [])
        .map((row) => {
          const close =
            row.close != null ? `<span class="signal-close">¥${fmt.format(row.close)}</span>` : "";
          return `<li class="signal-item">
            <span class="code">${escapeHtml(row.code)}</span>
            <span class="name">${escapeHtml(row.name)}</span>
            ${close}
          </li>`;
        })
        .join("");
      return `<li class="daily-day-group">
        <div class="daily-day-header">
          <span class="daily-day-date">${escapeHtml(day.date)}</span>
          <span class="badge-count">${day.new_buy_count ?? 0} 件</span>
        </div>
        <ul class="signal-list">${stocks}</ul>
      </li>`;
    })
    .join("");
}

function renderDailyHistory(daily) {
  renderBuyTimeline(daily);

  const select = document.getElementById("daily-date");
  const days = daily?.days || [];
  if (!days.length) {
    select.innerHTML = `<option value="">データなし</option>`;
    document.getElementById("daily-summary").innerHTML = "";
    renderSignalRows(document.getElementById("daily-sellback"), [], "該当なし");
    document.getElementById("daily-sellback-count").textContent = "0";
    return;
  }

  select.innerHTML = days
    .map((day) => {
      const pnlLabel = day.pnl != null ? ` (${formatIncome(day.pnl)})` : "";
      return `<option value="${escapeHtml(day.date)}">${escapeHtml(day.date)}${pnlLabel}</option>`;
    })
    .join("");

  function showDay(date) {
    const day = days.find((d) => d.date === date) || days[0];
    const summaryEl = document.getElementById("daily-summary");
    summaryEl.innerHTML = `
      <div class="summary-card"><p class="label">日次損益</p><p class="value ${incomeClass(day.pnl ?? 0)}">${formatIncome(day.pnl ?? 0)}</p></div>
      <div class="summary-card"><p class="label">新買</p><p class="value">${day.new_buy_count ?? 0} 件</p></div>
      <div class="summary-card"><p class="label">返売り</p><p class="value">${day.sellback_count ?? 0} 件</p></div>
    `;
    document.getElementById("daily-sellback-count").textContent = String(day.sellback_count ?? 0);
    renderSignalRows(
      document.getElementById("daily-sellback"),
      day.sellback,
      "この日の返売りはありません",
    );
  }

  select.onchange = () => showDay(select.value);
  showDay(days[0].date);
}

function renderSpecial(special) {
  const el = document.getElementById("special-status");
  if (!special) {
    el.innerHTML = "<p>データなし</p>";
    return;
  }
  const stateLabel =
    special.state === "special_long"
      ? "特別買い中"
      : special.state === "idle"
        ? "待機"
        : special.state;
  const rsiLines = Object.entries(special.etf_rsi || {})
    .map(([code, val]) => `${code}: RSI ${val ?? "—"}`)
    .join(" · ");
  el.innerHTML = `
    <div class="summary-card"><p class="label">状態</p><p class="value">${escapeHtml(stateLabel)}</p></div>
    <div class="summary-card"><p class="label">新買件数</p><p class="value">${special.new_buy_count ?? "—"} / 閾値 ${special.min_new_buy_count ?? "—"}</p></div>
    <div class="summary-card"><p class="label">対象ETF</p><p class="value">${escapeHtml(special.etf || "—")}</p></div>
    <div class="summary-card"><p class="label">利確 RSI</p><p class="value">≥ ${special.exit_rsi ?? "—"}</p></div>
    <p class="panel-meta">${escapeHtml(rsiLines)}</p>
    ${special.signal ? `<p class="special-alert">シグナル: ${escapeHtml(special.signal)}</p>` : ""}
  `;
}

function renderRuntimeSettings(runtime) {
  const el = document.getElementById("runtime-settings");
  if (!runtime?.special_buy) {
    el.innerHTML = "<p>runtime 設定が未読込です</p>";
    return;
  }
  const sb = runtime.special_buy;
  const nt = runtime.notify || {};
  const gr = runtime.gemini_rating || {};
  const rows = [
    ["特別買い", sb.enabled ? "ON" : "OFF"],
    ["新買しきい値", `${sb.min_new_buy_count} 件以上`],
    ["既定 ETF", sb.etf_default],
    ["利確 RSI", `≥ ${sb.exit_rsi}`],
    ["Gemini 評価", gr.enabled ? "ON" : "OFF"],
    ["Gemini モデル", gr.model || "—"],
    ["LINE: 今日の買い", nt.today_buy ? "ON" : "OFF"],
    ["LINE: 返売り", nt.today_sellback ? "ON" : "OFF"],
    ["LINE: 特別買い", nt.special_buy_on ? "ON" : "OFF"],
    ["LINE: 特別売り", nt.special_exit ? "ON" : "OFF"],
  ];
  el.innerHTML = rows
    .map(
      ([k, v]) =>
        `<div class="settings-row"><span>${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></div>`,
    )
    .join("");
}

function renderSummary(summary) {
  const el = document.getElementById("summary");
  const cards = [
    ["勝率", summary.win_rate != null ? `${summary.win_rate}%` : "—"],
    ["全体 PF", summary.pf != null ? summary.pf : "—"],
    ["損益合計", summary.total_income != null ? fmt.format(summary.total_income) : "—"],
    ["銘柄数", summary.symbol_count ?? "—"],
    ["勝ち", summary.wins ?? "—"],
    ["負け", summary.losses ?? "—"],
  ];
  el.innerHTML = cards
    .map(
      ([label, value]) =>
        `<div class="summary-card"><p class="label">${label}</p><p class="value">${value}</p></div>`,
    )
    .join("");
}

function renderList(symbols) {
  const list = document.getElementById("list");
  list.innerHTML = symbols
    .map((s) => {
      const ic = incomeClass(s.incomes);
      return `<li class="item">
        <span class="code">${s.code}<span class="badge">${s.winlose}</span></span>
        <span class="income ${ic}">${formatIncome(s.incomes)}</span>
        <span class="name">${escapeHtml(s.name)}</span>
        <span class="meta">PF ${s.pf} · 勝率 ${s.win_per}%</span>
      </li>`;
    })
    .join("");
}

function sortSymbols(symbols, mode) {
  const copy = [...symbols];
  switch (mode) {
    case "incomes-asc":
      return copy.sort((a, b) => a.incomes - b.incomes);
    case "pf-desc":
      return copy.sort((a, b) => b.pf - a.pf);
    case "code-asc":
      return copy.sort((a, b) => a.code.localeCompare(b.code, "ja"));
    default:
      return copy.sort((a, b) => b.incomes - a.incomes);
  }
}

function filterSymbols(symbols, query) {
  const q = query.trim().toLowerCase();
  if (!q) return symbols;
  return symbols.filter(
    (s) =>
      s.code.toLowerCase().includes(q) ||
      (s.name && s.name.toLowerCase().includes(q)),
  );
}

function setupTabs() {
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".panel");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const id = tab.dataset.tab;
      tabs.forEach((t) => t.classList.toggle("active", t === tab));
      panels.forEach((p) => {
        const show = p.id === `panel-${id}`;
        p.hidden = !show;
        p.classList.toggle("active", show);
      });
    });
  });
}

function setupControls(controls) {
  const actionsUrl = controls?.actions_run_url || ACTIONS_BASE;
  const editUrl =
    controls?.runtime_edit_url ||
    "https://github.com/lalakuma/KabuRadar3/edit/master/config/runtime.json";
  document.getElementById("link-actions").href = actionsUrl;
  document.getElementById("btn-run-full").href = actionsUrl;
  document.getElementById("btn-run-publish").href = actionsUrl;
  document.getElementById("btn-edit-config").href = editUrl;
}

async function init() {
  const err = document.getElementById("error");
  setupTabs();
  let data;
  try {
    const res = await fetch("data.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`data.json (${res.status})`);
    data = await res.json();
  } catch (e) {
    err.hidden = false;
    err.textContent =
      "データを読み込めませんでした。Actions で screening を実行後に Pages を更新してください。";
    document.getElementById("updated").textContent = "";
    return;
  }

  const updated = document.getElementById("updated");
  const parts = [];
  if (data.generated_at) {
    parts.push(`更新: ${new Date(data.generated_at).toLocaleString("ja-JP")}`);
  }
  if (data.run?.source === "github-actions") {
    parts.push("クラウド実行");
    if (data.run.event === "schedule") parts.push("（自動）");
    else if (data.run.event === "workflow_dispatch") parts.push("（手動）");
  }
  updated.textContent = parts.join(" ");

  if (data.run?.workflow_url) {
    const linkActions = document.getElementById("link-actions");
    linkActions.href = data.run.workflow_url;
    linkActions.textContent = "今回の実行ログ";
  }

  const subtitle = document.querySelector(".subtitle");
  if (subtitle && data.mode) {
    const label = data.mode === "HI" ? "HI（RSI4反転）" : "LO（RSI4反転なし）";
    subtitle.textContent = `スクリーニング結果（${label}）`;
  }

  const today = data.today || {};
  document.getElementById("today-date").textContent = today.trade_date
    ? `対象日: ${today.trade_date}`
    : "対象日: —";
  document.getElementById("buy-count").textContent = String(
    today.new_buy?.length ?? today.new_buy_count ?? 0,
  );
  document.getElementById("sellback-count").textContent = String(today.sellback?.length ?? 0);
  renderSignalRows(document.getElementById("today-buy"), today.new_buy, "本日の新買はありません");
  renderSignalRows(
    document.getElementById("today-sellback"),
    today.sellback,
    "本日の返売りはありません",
  );

  renderSpecial(data.special);
  renderDailyHistory(data.daily);
  renderRuntimeSettings(data.runtime);
  setupControls(data.controls);

  const paidNote = document.getElementById("paid-note");
  paidNote.hidden = false;
  paidNote.textContent =
    "無料枠: GitHub Actions / Pages / LINE は個人運用で通常無料。Gemini 評価は API キー設定時のみ（参考情報・投資判断は自己責任）。";

  renderSummary(data.summary);
  let symbols = data.symbols || [];
  const search = document.getElementById("search");
  const sort = document.getElementById("sort");
  const count = document.getElementById("count");

  function refresh() {
    let rows = filterSymbols(symbols, search.value);
    rows = sortSymbols(rows, sort.value);
    renderList(rows);
    count.textContent = `${rows.length} / ${symbols.length} 銘柄`;
  }

  search.addEventListener("input", refresh);
  sort.addEventListener("change", refresh);
  refresh();
}

init();
