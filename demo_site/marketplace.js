const STATUS_MEANINGS = {
    200: { tone: "good", text: "Request completed successfully." },
    201: { tone: "good", text: "Order accepted and created." },
    400: { tone: "warn", text: "Request payload or field range is invalid." },
    401: { tone: "bad", text: "Missing API key header." },
    402: { tone: "warn", text: "Insufficient buyer balance or credit limit reached." },
    403: { tone: "bad", text: "API key invalid, inactive, or node mismatch." },
    404: { tone: "warn", text: "Target trade/order not found or already completed." },
    422: { tone: "warn", text: "Schema validation failed for request body." },
    500: { tone: "bad", text: "Internal server error in marketplace service." }
};

const POLL_MS = 15000;

let latestLive = {
    stats: null,
    orders: null,
    trades: null,
    lastUpdated: null
};

let parsedA = { lines: [], counts: {} };
let parsedB = { lines: [], summary: {} };

function byId(id) {
    return document.getElementById(id);
}

function nowStamp() {
    return new Date().toLocaleTimeString();
}

function setText(id, text) {
    byId(id).textContent = text;
}

function number(value, digits = 2) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return "--";
    }
    return Number(value).toFixed(digits);
}

function setApiStatus(message, level) {
    const status = byId("apiStatus");
    status.textContent = message;
    status.className = `api-status ${level || "neutral"}`;
}

async function fetchJSON(baseUrl, path) {
    const endpoint = `${baseUrl.replace(/\/$/, "")}${path}`;
    const response = await fetch(endpoint, { method: "GET" });

    if (!response.ok) {
        const text = await response.text();
        throw new Error(`${response.status} ${response.statusText} ${text}`.trim());
    }

    return response.json();
}

function renderStats(stats) {
    setText("kpiTrades", stats?.total_trades ?? "--");
    setText("kpiVolume", `${number(stats?.total_volume_kwh)} kWh`);
    setText("kpiPrice", `Rs ${number(stats?.average_price_per_kwh)}`);
    setText("kpiPending", stats?.total_pending_orders ?? "--");
}

function renderTrades(trades) {
    const tbody = byId("tradesTableBody");
    if (!Array.isArray(trades) || trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="muted">No recent trades found.</td></tr>';
        return;
    }

    tbody.innerHTML = trades.slice(0, 12).map((trade) => {
        return `
            <tr>
                <td>${trade.id}</td>
                <td>${trade.buyer_node_id}</td>
                <td>${trade.seller_node_id}</td>
                <td>${number(trade.quantity_kwh, 3)}</td>
                <td>${number(trade.price_per_kwh, 2)}</td>
                <td>${number(trade.total_cost, 2)}</td>
            </tr>
        `;
    }).join("");
}

function renderOrderBook(snapshot) {
    const buyBook = byId("buyBook");
    const sellBook = byId("sellBook");

    const buys = snapshot?.pending_buy_orders || [];
    const sells = snapshot?.pending_sell_orders || [];

    buyBook.innerHTML = buys.length ? buys.slice(0, 8).map((o) => {
        return `<li>${o.node_id} | ${number(o.remaining_kwh, 3)} kWh @ Rs ${number(o.price_per_kwh, 2)}</li>`;
    }).join("") : '<li class="muted">No pending buy orders.</li>';

    sellBook.innerHTML = sells.length ? sells.slice(0, 8).map((o) => {
        return `<li>${o.node_id} | ${number(o.remaining_kwh, 3)} kWh @ Rs ${number(o.price_per_kwh, 2)}</li>`;
    }).join("") : '<li class="muted">No pending sell orders.</li>';

    setText("bookSpread", `Spread: ${snapshot?.spread === null || snapshot?.spread === undefined ? "--" : `Rs ${number(snapshot.spread, 2)}`}`);
    setText("bookVolume", `Total Buy/Sell Volume: ${number(snapshot?.total_buy_volume_kwh, 2)} / ${number(snapshot?.total_sell_volume_kwh, 2)} kWh`);
}

function renderInsights(targetId, items) {
    const target = byId(targetId);
    if (!items.length) {
        target.innerHTML = '<li class="muted">No interpreted events yet.</li>';
        return;
    }

    target.innerHTML = items.map((item) => {
        const tone = item.tone || "live";
        return `<li class="${tone}">${item.text}</li>`;
    }).join("");
}

function parseTerminalA(raw) {
    const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const insights = [];
    const counts = {};

    for (const line of lines) {
        const uvicornPattern = line.match(/"(GET|POST|PUT|PATCH|DELETE)\s+([^\s]+)\s+HTTP\/[0-9.]+"\s+(\d{3})/i);
        const genericPattern = line.match(/\b(GET|POST|PUT|PATCH|DELETE)\b\s+([^\s]+).*?\b(\d{3})\b/i);
        const statusOnlyPattern = line.match(/\b(\d{3})\b/);

        let method = null;
        let path = null;
        let code = null;

        if (uvicornPattern) {
            method = uvicornPattern[1].toUpperCase();
            path = uvicornPattern[2];
            code = Number(uvicornPattern[3]);
        } else if (genericPattern) {
            method = genericPattern[1].toUpperCase();
            path = genericPattern[2];
            code = Number(genericPattern[3]);
        } else if (statusOnlyPattern) {
            code = Number(statusOnlyPattern[1]);
        }

        if (!code) {
            continue;
        }

        counts[code] = (counts[code] || 0) + 1;
        const meaning = STATUS_MEANINGS[code] || { tone: "warn", text: "Unknown status code; inspect backend logs." };

        const prefix = method && path ? `${method} ${path}` : "Request event";
        insights.push({
            tone: meaning.tone,
            text: `${prefix} -> ${code}: ${meaning.text}`
        });
    }

    if (!insights.length && raw.trim()) {
        insights.push({ tone: "warn", text: "No HTTP status pattern detected. Paste raw FastAPI/Uvicorn request lines." });
    }

    return { lines: insights, counts };
}

function parsePilotSummary(raw) {
    const text = raw || "";

    function pick(label) {
        const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const regex = new RegExp(`${escaped}\\s*:\\s*([0-9.]+)`, "i");
        const match = text.match(regex);
        return match ? Number(match[1]) : null;
    }

    const summary = {
        nodes: pick("Nodes in pilot"),
        rounds: pick("Rounds per node"),
        ordersPlaced: pick("Orders placed"),
        orderFailures: pick("Order placement failures"),
        ordersMatched: pick("Orders matched"),
        tradesGenerated: pick("Trades generated"),
        totalTradesMarket: pick("Total trades in market"),
        totalVolume: pick("Total volume (kWh)"),
        totalValue: pick("Total value (INR)"),
        avgPrice: pick("Average price (INR/kWh)")
    };

    const lines = [];

    if (summary.nodes !== null && summary.rounds !== null) {
        lines.push({ tone: "good", text: `Pilot scale: ${summary.nodes} nodes across ${summary.rounds} rounds.` });
    }

    if (summary.ordersPlaced !== null) {
        lines.push({ tone: "live", text: `Order attempts observed: ${summary.ordersPlaced}.` });
    }

    if (summary.orderFailures !== null) {
        const tone = summary.orderFailures > 0 ? "warn" : "good";
        lines.push({ tone, text: `Order placement failures: ${summary.orderFailures}.` });
    }

    if (summary.ordersMatched !== null && summary.tradesGenerated !== null) {
        lines.push({ tone: "good", text: `Matching outcome: ${summary.ordersMatched} orders matched, producing ${summary.tradesGenerated} trades.` });
    }

    if (summary.totalVolume !== null && summary.totalValue !== null) {
        lines.push({ tone: "live", text: `Executed market value: ${number(summary.totalVolume, 2)} kWh for Rs ${number(summary.totalValue, 2)}.` });
    }

    if (summary.avgPrice !== null) {
        lines.push({ tone: "live", text: `Average clearing price from pilot report: Rs ${number(summary.avgPrice, 2)} per kWh.` });
    }

    if (!lines.length && raw.trim()) {
        lines.push({ tone: "warn", text: "Pilot summary format not recognized. Paste output from marketplace.pilot_runner summary block." });
    }

    return { lines, summary };
}

function buildCombinedSummary() {
    const items = [];

    if (latestLive.stats) {
        items.push({
            tone: "live",
            text: `[LIVE] Market has ${latestLive.stats.total_trades} trades, ${number(latestLive.stats.total_volume_kwh)} kWh volume, average Rs ${number(latestLive.stats.average_price_per_kwh)} per kWh.`
        });
        items.push({
            tone: "live",
            text: `[LIVE] Pending orders: ${latestLive.stats.total_pending_orders}, active nodes: ${latestLive.stats.active_nodes}.`
        });
    }

    const statusSummary = Object.keys(parsedA.counts).sort().map((code) => `${code}x${parsedA.counts[code]}`).join(", ");
    if (statusSummary) {
        items.push({ tone: "live", text: `[TERMINAL A] Status distribution: ${statusSummary}.` });
    }

    if (parsedB.summary.ordersPlaced !== null || parsedB.summary.totalValue !== null) {
        const orders = parsedB.summary.ordersPlaced !== null ? parsedB.summary.ordersPlaced : "--";
        const failures = parsedB.summary.orderFailures !== null ? parsedB.summary.orderFailures : "--";
        const value = parsedB.summary.totalValue !== null ? `Rs ${number(parsedB.summary.totalValue, 2)}` : "--";
        items.push({
            tone: "live",
            text: `[TERMINAL B] Pilot attempted ${orders} orders with ${failures} failures and reported executed value ${value}.`
        });
    }

    if (!items.length) {
        items.push({ tone: "warn", text: "Waiting for data. Poll live APIs and paste terminal outputs to generate combined summary." });
    }

    renderInsights("combinedSummary", items);
    setText("combinedStamp", `updated ${nowStamp()}`);
}

async function refreshLive() {
    if (!demoData || !demoData.marketplace_snapshots) {
        setApiStatus("Waiting for demo data load...", "neutral");
        return;
    }

    try {
        const snapshots = demoData.marketplace_snapshots;
        const elapsed = (Date.now() - startTime) / 1000;
        
        // Cycle through snapshots every 15 seconds
        const snapIndex = Math.floor((elapsed / 15) % snapshots.length);
        const snap = snapshots[snapIndex];

        latestLive = {
            stats: snap.stats,
            orders: snap.orders,
            trades: snap.trades,
            lastUpdated: new Date()
        };

        renderStats(snap.stats);
        renderOrderBook(snap.orders);
        renderTrades(snap.trades);

        setText("lastTradesStamp", `Demo Snap #${snapIndex + 1} @ ${nowStamp()}`);
        setText("lastOrdersStamp", `Demo Snap #${snapIndex + 1} @ ${nowStamp()}`);
        setApiStatus(`Demo Mode Active [Looping ${snapshots.length} frames]`, "ok");
        buildCombinedSummary();
    } catch (error) {
        console.error(error);
        setApiStatus(`Demo playback error: ${error.message}`, "error");
    }
}

function wireEvents() {
    byId("refreshNow").addEventListener("click", refreshLive);

    byId("parseA").addEventListener("click", () => {
        parsedA = parseTerminalA(byId("terminalALog").value);
        renderInsights("terminalAInsights", parsedA.lines);
        buildCombinedSummary();
    });

    byId("parseB").addEventListener("click", () => {
        parsedB = parsePilotSummary(byId("terminalBLog").value);
        renderInsights("terminalBInsights", parsedB.lines);
        buildCombinedSummary();
    });
}
let demoData = null;
let startTime = Date.now();

async function initDemo() {
    try {
        const response = await fetch('demo_data.json');
        demoData = await response.json();
        console.log("Marketplace Demo data loaded:", demoData);
        refreshLive();
    } catch (err) {
        console.error("Failed to load demo data:", err);
        setApiStatus("Data file missing.", "error");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    wireEvents();
    initDemo(); // Load demo data
    setInterval(refreshLive, 5000); // UI Refresh every 5s
});
