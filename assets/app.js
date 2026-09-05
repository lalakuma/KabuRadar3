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

const STAR_TIER_LABELS = {
  5: "星5：超本命",
  4: "星4：優良・主戦場",
  3: "星3：中立・様子見",
  2: "星2：警戒・スルー推奨",
  1: "星1：危険・絶対見送り",
};

function starTierLabel(n) {
  const v = Math.max(1, Math.min(5, Number(n) || 3));
  return STAR_TIER_LABELS[v] || `星${v}`;
}

function confidenceLabel(value) {
  switch (value) {
    case "high":
      return "高";
    case "medium":
      return "中";
    case "low":
      return "低";
    default:
      return "—";
  }
}

function formatDividend(dividend) {
  if (!dividend || typeof dividend !== "object") return "";
  const parts = [];
  if (dividend.yield_pct != null) parts.push(`利回り ${dividend.yield_pct}%`);
  if (dividend.annual_yen != null) parts.push(`年間 ${fmt.format(dividend.annual_yen)}円/株`);
  if (dividend.ex_date) parts.push(`権利付き最終日 ${dividend.ex_date}`);
  if (dividend.payout_ratio_pct != null) parts.push(`配当性向 ${dividend.payout_ratio_pct}%`);
  return parts.join(" · ");
}

function formatEarnings(earnings) {
  if (!earnings || typeof earnings !== "object") return "";
  const parts = [];
  if (earnings.fiscal_month != null) parts.push(`${earnings.fiscal_month}月決算`);
  if (earnings.announcement_date) {
    let label = `次回決算発表 ${earnings.announcement_date}`;
    if (
      earnings.announcement_date_end &&
      earnings.announcement_date_end !== earnings.announcement_date
    ) {
      label += `〜${earnings.announcement_date_end}`;
    }
    if (earnings.is_estimate) label += "（予想）";
    parts.push(label);
  } else if (earnings.fiscal_year_end) {
    parts.push(`決算期 ${earnings.fiscal_year_end}`);
  }
  return parts.join(" · ");
}

function formatValuation(valuation) {
  if (!valuation || typeof valuation !== "object") return "";
  const parts = [];
  if (valuation.sector) {
    parts.push(valuation.industry ? `${valuation.sector} / ${valuation.industry}` : valuation.sector);
  }
  if (valuation.market_cap_oku != null) parts.push(`時価総額 約${fmt.format(valuation.market_cap_oku)}億円`);
  if (valuation.per != null) parts.push(`PER ${valuation.per}`);
  if (valuation.forward_per != null) parts.push(`予想PER ${valuation.forward_per}`);
  if (valuation.pbr != null) parts.push(`PBR ${valuation.pbr}`);
  if (valuation.revenue_growth_pct != null) parts.push(`売上成長 ${valuation.revenue_growth_pct}%`);
  if (valuation.earnings_growth_pct != null) parts.push(`利益成長 ${valuation.earnings_growth_pct}%`);
  if (valuation.profit_margin_pct != null) parts.push(`利益率 ${valuation.profit_margin_pct}%`);
  if (valuation.roe_pct != null) parts.push(`ROE ${valuation.roe_pct}%`);
  if (valuation.target_price_yen != null) {
    let label = `目標株価 ${fmt.format(valuation.target_price_yen)}円`;
    if (valuation.target_upside_pct != null) {
      label += ` (${valuation.target_upside_pct > 0 ? "+" : ""}${valuation.target_upside_pct}%)`;
    }
    parts.push(label);
  }
  return parts.join(" · ");
}

function valuationViewLabel(value) {
  switch (value) {
    case "cheap":
      return "割安寄り";
    case "fair":
      return "適正";
    case "expensive":
      return "割高寄り";
    default:
      return "";
  }
}

function renderAnalysisBlock(q) {
  const sections = [];
  if (q.background) {
    sections.push(
      `<section class="detail-section"><h4>下落背景</h4><p class="detail-text analysis-text">${escapeHtml(q.background)}</p></section>`,
    );
  }
  if (q.material_analysis) {
    sections.push(
      `<section class="detail-section"><h4>材料分析</h4><p class="detail-text analysis-text">${escapeHtml(q.material_analysis)}</p></section>`,
    );
  }
  if (q.fundamental_summary) {
    const valuationBadge = valuationViewLabel(q.valuation_view);
    const valuationText = formatValuation(q.valuation);
    sections.push(
      `<section class="detail-section"><h4>ファンダメンタル${
        valuationBadge
          ? `<span class="valuation-badge valuation-${escapeHtml(q.valuation_view)}">${escapeHtml(valuationBadge)}</span>`
          : ""
      }</h4><p class="detail-text analysis-text">${escapeHtml(q.fundamental_summary)}</p>${
        valuationText
          ? `<p class="detail-muted detail-metrics">${escapeHtml(valuationText)}</p>`
          : ""
      }</section>`,
    );
  } else {
    const valuationText = formatValuation(q.valuation);
    if (valuationText) {
      sections.push(
        `<section class="detail-section"><h4>指標</h4><p class="detail-text">${escapeHtml(valuationText)}</p></section>`,
      );
    }
  }
  if (q.technical_view) {
    sections.push(
      `<section class="detail-section"><h4>チャート所見</h4><p class="detail-text analysis-text">${escapeHtml(q.technical_view)}</p></section>`,
    );
  }
  return sections.join("");
}

function formatBenefitPreview(q) {
  const detail = q?.shareholder_benefit_detail;
  const summary = (q?.shareholder_benefit || detail?.summary || "").trim();
  if (!summary) return "";
  const firstTier = detail?.programs?.[0]?.tiers?.[0];
  if (firstTier?.content && summary !== "なし") {
    return `${summary} ${firstTier.shares}: ${firstTier.content}`.trim();
  }
  return summary;
}

function formatBenefitHtml(q) {
  const detail = q?.shareholder_benefit_detail;
  const summary = (q?.shareholder_benefit || detail?.summary || "").trim();
  if (!summary) {
    return `<p class="detail-muted">情報なし</p>`;
  }
  if (summary === "なし") {
    return `<p class="detail-text">なし</p>`;
  }

  const parts = [];
  const meta = [];
  if (detail?.min_shares) meta.push(`最低 ${detail.min_shares}株`);
  if (detail?.month) meta.push(`権利確定 ${detail.month}月`);
  if (detail?.yield_pct) meta.push(`優待利回り ${detail.yield_pct}%`);
  if (meta.length) {
    parts.push(`<p class="detail-text">${escapeHtml(meta.join(" · "))}</p>`);
  }
  parts.push(`<p class="detail-text"><strong>${escapeHtml(summary)}</strong></p>`);

  for (const program of detail?.programs || []) {
    const title = (program.title || "").trim();
    if (title) {
      parts.push(`<p class="detail-subtitle">${escapeHtml(title)}</p>`);
    }
    const tiers = program.tiers || [];
    if (tiers.length) {
      parts.push(
        `<ul class="detail-list benefit-tier-list">${tiers
          .map((tier) => {
            const note = (tier.note || "").trim();
            return `<li><strong>${escapeHtml(tier.shares || "")}</strong> ${escapeHtml(tier.content || "")}${
              note ? `<br><span class="detail-muted">${escapeHtml(note)}</span>` : ""
            }</li>`;
          })
          .join("")}</ul>`,
      );
    }
  }

  if (detail?.source && detail.source !== "none") {
    parts.push(
      `<p class="detail-muted">出典: ${escapeHtml(detail.source === "minkabu" ? "みんかぶ" : detail.source)}（参考）</p>`,
    );
  }
  return parts.join("");
}

function setupSignalModal() {
  const dialog = document.getElementById("signal-detail");
  const closeBtn = document.getElementById("signal-detail-close");
  if (!dialog || !closeBtn) return;

  closeBtn.addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) dialog.close();
  });
  dialog.addEventListener("cancel", (e) => {
    e.preventDefault();
    dialog.close();
  });
}

function renderQualityDetailBody(row) {
  const q = row.quality || {};
  const tech = [];
  if (row.close != null) tech.push(`終値 ¥${fmt.format(row.close)}`);
  if (row.rsi != null) tech.push(`RSI ${Number(row.rsi).toFixed(2)}`);
  if (row.rci != null) tech.push(`RCI ${Number(row.rci).toFixed(1)}`);
  if (row.rci_turn) tech.push("RCI 上向き");
  if (row.rsi_ok) tech.push("RSI条件 ✓");
  if (row.rci_ok) tech.push("RCI条件 ✓");
  if (row.pnl != null) tech.push(`損益 ${formatIncome(row.pnl)}`);

  const risks = (q.risk_factors || [])
    .map((r) => `<li>${escapeHtml(r)}</li>`)
    .join("");
  const watchPoints = (q.watch_points || [])
    .map((r) => `<li>${escapeHtml(r)}</li>`)
    .join("");
  const dividendText = formatDividend(q.dividend);
  const earningsText = formatEarnings(q.earnings);
  const benefitHtml = formatBenefitHtml(q);
  const analysisHtml = renderAnalysisBlock(q);
  const yahooUrl = row.code
    ? `https://finance.yahoo.co.jp/quote/${encodeURIComponent(String(row.code).replace(/\\.T$/, "") + ".T")}`
    : "";
  const sources = (q.sources || [])
    .filter(Boolean)
    .map(
      (url) =>
        `<li><a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a></li>`,
    )
    .join("");

  return `
    ${
      tech.length
        ? `<section class="detail-section"><h4>テクニカル</h4><p class="detail-text">${tech.map(escapeHtml).join(" · ")}</p></section>`
        : ""
    }
    ${
      analysisHtml
        ? analysisHtml
        : `<section class="detail-section"><h4>分析</h4><p class="detail-muted">評価テキストがありません</p></section>`
    }
    ${
      dividendText
        ? `<section class="detail-section"><h4>配当</h4><p class="detail-text">${escapeHtml(dividendText)}</p></section>`
        : ""
    }
    ${
      earningsText
        ? `<section class="detail-section"><h4>決算</h4><p class="detail-text">${escapeHtml(earningsText)}</p></section>`
        : `<section class="detail-section"><h4>決算</h4><p class="detail-muted">決算情報なし</p></section>`
    }
    <section class="detail-section"><h4>株主優待</h4>${benefitHtml}</section>
    ${
      risks
        ? `<section class="detail-section"><h4>リスク要因</h4><ul class="detail-list">${risks}</ul></section>`
        : ""
    }
    ${
      watchPoints
        ? `<section class="detail-section"><h4>注目ポイント</h4><ul class="detail-list">${watchPoints}</ul></section>`
        : ""
    }
    ${
      q.confidence
        ? `<section class="detail-section"><h4>信頼度</h4><p class="detail-text">${escapeHtml(confidenceLabel(q.confidence))}</p></section>`
        : ""
    }
    ${
      sources || yahooUrl
        ? `<section class="detail-section"><h4>リンク</h4><ul class="detail-links">${
            yahooUrl
              ? `<li><a href="${escapeHtml(yahooUrl)}" target="_blank" rel="noopener noreferrer">Yahoo!ファイナンス</a></li>`
              : ""
          }${sources}</ul></section>`
        : ""
    }
    <p class="detail-note">AI参考情報です。投資判断は自己責任でお願いします。</p>
  `;
}

function openSignalDetail(row) {
  const dialog = document.getElementById("signal-detail");
  const title = document.getElementById("signal-detail-title");
  const sub = document.getElementById("signal-detail-sub");
  const body = document.getElementById("signal-detail-body");
  if (!dialog || !title || !sub || !body) return;

  const q = row.quality || {};
  const stars = q.stars;
  const name = row.name || "";
  title.textContent = `${row.code} ${name}`.trim();
  sub.textContent =
    stars != null
      ? `${starsLabel(stars)}（${starTierLabel(stars)}）`
      : "AI評価なし";

  body.innerHTML = renderQualityDetailBody(row);

  if (typeof dialog.showModal === "function") {
    dialog.showModal();
    return;
  }
  dialog.setAttribute("open", "");
}

function renderSignalRows(container, rows, emptyText, options = {}) {
  const { clickable = false } = options;
  if (!rows?.length) {
    container.innerHTML = `<li class="signal-empty">${escapeHtml(emptyText)}</li>`;
    return;
  }
  container.innerHTML = rows
    .map((row, idx) => {
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
        ? `<span class="signal-quality">${starsLabel(q.stars)}</span>`
        : "";
      const hint = clickable
        ? `<span class="signal-hint" aria-hidden="true">詳細 ›</span>`
        : "";
      const itemClass = clickable ? "signal-item signal-item-clickable" : "signal-item";
      const attrs = clickable
        ? ` role="button" tabindex="0" data-signal-index="${idx}" aria-label="${escapeHtml(row.code)} ${escapeHtml(row.name)} の詳細"`
        : "";
      return `<li class="${itemClass}"${attrs}>
        <div class="signal-head">
          <span class="code">${escapeHtml(row.code)}</span>
          <span class="name">${escapeHtml(row.name)}</span>
          ${qualityHtml}
          ${close}
          ${pnl}
          ${hint}
        </div>
        ${flagHtml}
      </li>`;
    })
    .join("");

  if (clickable && rows?.length) {
    container.onclick = (e) => {
      const item = e.target.closest("[data-signal-index]");
      if (!item) return;
      openSignalDetail(rows[Number(item.dataset.signalIndex)]);
    };
    container.onkeydown = (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      const item = e.target.closest("[data-signal-index]");
      if (!item) return;
      e.preventDefault();
      openSignalDetail(rows[Number(item.dataset.signalIndex)]);
    };
  } else {
    container.onclick = null;
    container.onkeydown = null;
  }
}

function renderDailyBuyRow(row) {
  const q = row.quality || {};
  const close =
    row.close != null ? `<span class="signal-close">¥${fmt.format(row.close)}</span>` : "";
  const stars = q.stars != null ? `<span class="signal-quality">${starsLabel(q.stars)}</span>` : "";
  const benefit = formatBenefitPreview(q);
  const benefitLine = benefit
    ? `<p class="signal-benefit-preview"><strong>株主優待:</strong> ${escapeHtml(benefit)}</p>`
    : `<p class="signal-benefit-preview detail-muted">株主優待: 情報なし</p>`;

  return `<li class="signal-item signal-item-daily">
    <details class="signal-details">
      <summary class="signal-summary">
        <span class="signal-summary-main">
          <span class="code">${escapeHtml(row.code)}</span>
          <span class="name">${escapeHtml(row.name || "")}</span>
          ${stars}
          ${close}
        </span>
        ${benefitLine}
        <span class="signal-expand-hint">詳細を開く</span>
      </summary>
      <div class="signal-detail-inline">${renderQualityDetailBody(row)}</div>
    </details>
  </li>`;
}

function renderBuyTimeline(daily) {
  const timeline = document.getElementById("daily-buy-timeline");
  const meta = document.getElementById("daily-buy-meta");
  const buyDays = daily?.buy_days || (daily?.days || []).filter((d) => (d.new_buy_count ?? 0) > 0);
  const totalDays = daily?.days?.length ?? 0;

  if (!timeline || !meta) return;

  if (!buyDays.length) {
    meta.textContent = totalDays ? `直近 ${totalDays} 営業日 · 買いシグナルなし` : "データなし";
    timeline.innerHTML = `<li class="signal-empty">この期間に買い（新買）シグナルはありません</li>`;
    return;
  }

  const totalBuys = buyDays.reduce((n, d) => n + (d.new_buy_count ?? 0), 0);
  meta.textContent = `直近 ${totalDays} 営業日 · 買いあり ${buyDays.length} 日 · 計 ${totalBuys} 件`;

  timeline.innerHTML = buyDays
    .map(
      (day) => `<li class="daily-day-group">
        <div class="daily-day-header">
          <span class="daily-day-date">${escapeHtml(day.date)}</span>
          <span class="badge-count">${day.new_buy_count ?? 0} 件</span>
        </div>
        <ul class="signal-list">${(day.new_buy || []).map(renderDailyBuyRow).join("")}</ul>
      </li>`,
    )
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
  setupSignalModal();
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
  renderSignalRows(document.getElementById("today-buy"), today.new_buy, "本日の新買はありません", {
    clickable: true,
  });
  renderSignalRows(
    document.getElementById("today-sellback"),
    today.sellback,
    "本日の返売りはありません",
    { clickable: true },
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
