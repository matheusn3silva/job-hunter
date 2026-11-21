// JobHunter: interações do site (anexar currículo, buscar, prompts, detalhes).
// Sem frameworks: cada função chama uma rota /api/... do Flask.

const toastEl = document.getElementById("toast");
let toastTimer;

/** Mostra uma mensagem curta no rodapé. */
function toast(message, isError = false) {
  toastEl.textContent = message;
  toastEl.classList.toggle("error", isError);
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (toastEl.hidden = true), 5000);
}

/** Chama a API e devolve o JSON; mostra o erro do servidor se falhar. */
async function api(url, options = {}) {
  const response = await fetch(url, { method: "POST", ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Erro ${response.status}`);
  return data;
}

/** Desabilita o botão enquanto a ação roda e recarrega a página no fim. */
async function runAction(button, busyText, action) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = busyText;
  try {
    const message = await action();
    sessionStorage.setItem("jobhunter-toast", message);
    location.reload();
  } catch (error) {
    toast(error.message, true);
    button.disabled = false;
    button.textContent = original;
  }
}

function batchMessage(data) {
  const warnings = data.errors.length ? ` Avisos: ${data.errors.join(" | ")}` : "";
  return `${data.files.length} prompt(s) criado(s).${warnings}`;
}

// Mensagem guardada antes do reload (ex.: "Currículo salvo.").
const pending = sessionStorage.getItem("jobhunter-toast");
if (pending) {
  sessionStorage.removeItem("jobhunter-toast");
  toast(pending);
}

// --- Currículo -----------------------------------------------------------
document.getElementById("resume-input").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  try {
    const data = await api("/api/resume", { body: form });
    sessionStorage.setItem("jobhunter-toast", data.message);
    location.reload();
  } catch (error) {
    toast(error.message, true);
  }
});

// --- Busca ---------------------------------------------------------------
const searchBtn = document.getElementById("search-btn");
searchBtn.addEventListener("click", () =>
  runAction(searchBtn, "Buscando… (até 1 min)", async () => {
    const data = await api("/api/search");
    const warnings = data.errors.length ? ` (${data.errors.length} aviso(s) nas fontes)` : "";
    return `${data.collected} vagas coletadas, ${data.new} novas.${warnings}`;
  })
);

// --- Cliques nas listas (um único "ouvinte" para todos os botões) ---------
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action]");
  if (button) {
    event.stopPropagation();
    const { action, uid, name } = button.dataset;
    if (action === "prompt-top") {
      runAction(button, "Gerando…", async () => batchMessage(await api("/api/prompts/top")));
    } else if (action === "prompt-job") {
      runAction(button, "Gerando…", async () => batchMessage(await api(`/api/prompts/job/${uid}`)));
    } else if (action === "copy") {
      copyPrompt(name);
    }
    return;
  }
  if (event.target.closest("a")) return; // link "Ver vaga original"
  const card = event.target.closest(".job");
  if (card) openDetail(card.dataset.uid);
});

document.addEventListener("keydown", (event) => {
  const card = event.target.closest?.(".job");
  if (card && event.key === "Enter") openDetail(card.dataset.uid);
  if (event.key === "Escape") closeDetail();
});

/** Copia o texto de um prompt para a área de transferência. */
async function copyPrompt(name) {
  try {
    const response = await fetch(`/api/prompts/${encodeURIComponent(name)}`);
    if (!response.ok) throw new Error("Prompt não encontrado.");
    await navigator.clipboard.writeText(await response.text());
    toast("Prompt copiado! Cole numa conversa nova da IA.");
  } catch (error) {
    toast(error.message || "Não foi possível copiar.", true);
  }
}

// --- Painel de detalhes (estilo LinkedIn) ---------------------------------
const layout = document.querySelector(".layout");
const detail = document.getElementById("detail");
const detailBody = document.getElementById("detail-body");
document.getElementById("detail-close").addEventListener("click", closeDetail);

function closeDetail() {
  detail.hidden = true;
  layout.classList.remove("with-detail");
  document.querySelectorAll(".job.selected").forEach((el) => el.classList.remove("selected"));
}

/** Cria um elemento com texto (textContent evita injeção de HTML da vaga). */
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

async function openDetail(uid) {
  let job;
  try {
    const response = await fetch(`/api/jobs/${uid}`);
    job = await response.json();
    if (!response.ok) throw new Error(job.error);
  } catch (error) {
    toast(error.message || "Não foi possível abrir a vaga.", true);
    return;
  }
  document.querySelectorAll(".job.selected").forEach((e) => e.classList.remove("selected"));
  document.querySelector(`.job[data-uid="${uid}"]`)?.classList.add("selected");

  const head = el("div", null, "detail-head");
  const badge = el("span", job.source.initials, "badge");
  badge.style.background = job.source.color;
  head.append(badge, el("div", `${job.company || "Empresa não informada"} · via ${job.source.label}`, "muted"));

  const where = job.remote ? `Remota (${job.location || "sem restrição"})` : job.location || "Local não informado";
  const facts = el("p", [
    where,
    job.posted_at ? `publicada em ${job.posted_at}` : null,
    `nota ${job.score.toFixed(1)}`,
    job.rank ? `#${job.rank} ${job.in_top ? "(Top)" : ""}` : null,
  ].filter(Boolean).join(" · "), "facts muted");

  const tags = el("div", null, "tags");
  job.tags.forEach((t) => tags.append(el("span", t, "tag")));

  const buttons = el("div", null, "buttons");
  const original = el("a", "Ver vaga original ↗", "btn primary");
  original.href = job.url;
  original.target = "_blank";
  original.rel = "noopener";
  buttons.append(original);
  if (job.prompted) {
    buttons.append(el("span", "prompt criado", "pill ok"));
  } else {
    const make = el("button", "Gerar prompt desta vaga", "btn");
    make.dataset.action = "prompt-job";
    make.dataset.uid = job.uid;
    buttons.append(make);
  }

  detailBody.replaceChildren(
    head,
    el("h2", job.title),
    facts,
    tags,
    buttons,
    el("div", job.description || "Sem descrição; veja a vaga original.", "description")
  );
  detail.hidden = false;
  layout.classList.add("with-detail");
  detail.scrollTop = 0;
}
