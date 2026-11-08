"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const iconPaths = {
  bag: '<path d="M5 8h14l-1 13H6L5 8Z"/><path d="M8 8V6a4 4 0 0 1 8 0v2"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  settings: '<path d="m9 3-1 3-3 1-2 3 2 3v4l3 1 2 3h4l2-3 3-1v-4l2-3-2-3-3-1-1-3H9Z"/><circle cx="12" cy="12" r="3"/>',
  sparkles: '<path d="m12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6L12 3ZM20 2v4M18 4h4M3 19v3M1.5 20.5h3"/>',
  home: '<path d="m3 10 9-7 9 7M5 9v12h14V9M9 21v-7h6v7"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  whatsapp: '<path d="m3 21 1.5-5A9 9 0 1 1 8 20L3 21Z"/><path d="M8 7c0 5 4 9 8 9l1-3-3-1-1 1-2-2 1-1-1-3H8Z"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  send: '<path d="m3 3 18 9-18 9 4-9-4-9ZM7 12h14"/>',
  "arrow-up-right": '<path d="M6 18 18 6M6 6h12v12"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 15v5h16v-5"/>',
  upload: '<path d="M12 16V4m-5 5 5-5 5 5M4 15v5h16v-5"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
  heart: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
  x: '<path d="m6 6 12 12M18 6 6 18"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
  edit: '<path d="m15 5 4 4M4 20l4-1L20 7a2.8 2.8 0 0 0-4-4L4 15v5Z"/>',
  archive: '<rect x="3" y="3" width="18" height="5" rx="1"/><path d="M5 8v13h14V8M9 12h6"/>',
  tag: '<path d="M3 3h8l10 10-8 8L3 11V3Z"/><circle cx="7.5" cy="7.5" r="1"/>',
};
function icon(name) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name] || iconPaths.tag}</svg>`;
}
$$('[data-icon]').forEach((node) => { node.innerHTML = icon(node.dataset.icon); });

let appState = { offers: [], settings: { channel_name: "Meu canal de ofertas" } };
let currentFilter = "all";
let editingId = null;
let reviewingId = null;
let loaded = false;
let refreshing = false;
const statusLabels = { ready: "Pronta", scheduled: "Agendada", draft: "Rascunho", sent: "Enviada", archived: "Arquivada" };
const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const dateTime = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

function textElement(tag, className, value) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (value !== undefined) element.textContent = value;
  return element;
}
function iconElement(name, className = "") {
  const element = textElement("span", className);
  element.innerHTML = icon(name);
  return element;
}
function actionButton(label, name, className, handler) {
  const button = textElement("button", className);
  button.type = "button";
  if (name) button.append(iconElement(name));
  if (label) button.append(document.createTextNode(label));
  button.addEventListener("click", handler);
  return button;
}
function toast(message, error = false) {
  const node = textElement("div", `toast${error ? " error" : ""}`, message);
  $("#toast-container").append(node);
  setTimeout(() => node.remove(), error ? 8000 : 5000);
}
function inlineError(id, message = "") {
  const node = $(id);
  node.textContent = message;
  node.hidden = !message;
}
function setBusy(button, busy, label = "Salvando…") {
  if (busy) {
    button.dataset.originalContent = button.innerHTML;
    button.textContent = label;
  } else if (button.dataset.originalContent) {
    button.innerHTML = button.dataset.originalContent;
    delete button.dataset.originalContent;
  }
  button.disabled = busy;
}
async function api(path, options = {}) {
  const method = options.method || "GET";
  let response;
  try {
    response = await fetch(path, {
      cache: "no-store",
      ...options,
      headers: method === "GET" ? {} : { "Content-Type": "application/json", "X-Achadinhos-Request": "1" },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new Error("O painel perdeu a conexão com o programa. Abra o aplicativo pelo atalho de início e tente novamente.");
  }
  let data;
  try { data = await response.json(); }
  catch { throw new Error("O aplicativo não respondeu como esperado. Verifique a janela do programa."); }
  if (!response.ok) throw new Error(data.error || "Não foi possível concluir esta ação.");
  return data;
}
function connectionStatus(online) {
  const node = $("#connection-status");
  node.classList.toggle("offline", !online);
  node.replaceChildren(textElement("span"), document.createTextNode(online ? "Rodando neste computador" : "Aplicativo desconectado"));
}
async function loadState(silent = false) {
  if (refreshing) return;
  refreshing = true;
  try {
    const next = await api("/api/state");
    if (!Array.isArray(next.offers) || !next.settings) throw new Error("Resposta inválida do aplicativo.");
    appState = next;
    loaded = true;
    connectionStatus(true);
    render();
  } catch (error) {
    connectionStatus(false);
    if (!loaded) renderConnectionError();
    if (!silent) toast("Não foi possível atualizar a fila. Mantenha a janela do programa aberta e tente novamente.", true);
  } finally { refreshing = false; }
}
function renderConnectionError() {
  const node = $("#offers-list");
  node.replaceChildren();
  const empty = textElement("div", "empty-state");
  empty.append(iconElement("info", "empty-illustration"), textElement("h3", "", "Vamos reconectar seu painel"), textElement("p", "", "Abra o programa pelo atalho de início e tente novamente. As ofertas salvas continuam neste computador."), actionButton("Tentar novamente", "plus", "button button-primary", () => loadState()));
  node.append(empty);
}
function render() {
  const offers = appState.offers;
  for (const status of ["ready", "scheduled", "sent"]) {
    $(`#count-${status}`).textContent = offers.filter((offer) => offer.status === status).length;
  }
  $("#total-count").textContent = offers.filter((offer) => offer.status !== "archived").length;
  $("#sidebar-count").textContent = offers.filter((offer) => ["ready", "scheduled", "draft"].includes(offer.status)).length;
  $("#sidebar-channel").textContent = appState.settings.channel_name;
  $("#sidebar-channel").title = appState.settings.channel_name;
  $$(".filter-tab").forEach((button) => {
    const selected = button.dataset.filter === currentFilter;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  renderOffers();
  if ($("#review-dialog").open && reviewingId) updateReview();
}
function searchable(text) { return String(text || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR"); }
function renderOffers() {
  const query = searchable($("#search").value.trim());
  const offers = appState.offers.filter((offer) => {
    const matchingStatus = currentFilter === "all" ? offer.status !== "archived" : offer.status === currentFilter;
    return matchingStatus && (!query || searchable([offer.title, offer.store, offer.category, offer.coupon].join(" ")).includes(query));
  }).sort((a, b) => {
    const priority = { ready: 0, scheduled: 1, draft: 2, sent: 3, archived: 4 };
    if (priority[a.status] !== priority[b.status]) return priority[a.status] - priority[b.status];
    if (a.status === "scheduled") return new Date(a.scheduled_at) - new Date(b.scheduled_at);
    return new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at);
  });
  const container = $("#offers-list");
  container.replaceChildren();
  if (!offers.length) {
    const isFirst = appState.offers.length === 0;
    const empty = textElement("div", "empty-state");
    let title = "Nada por aqui ainda";
    let description = "As ofertas desta etapa vão aparecer aqui. Você pode mudar o filtro ou cadastrar uma nova.";
    if (query) { title = "Nenhum achadinho encontrado"; description = "Tente outro nome, loja ou categoria para encontrar sua oferta."; }
    else if (isFirst) { title = "Todo bom negócio começa com um achadinho"; description = "Cadastre sua primeira oferta e transforme seu link de afiliado em uma mensagem pronta para compartilhar."; }
    else if (currentFilter === "ready") { title = "Sua próxima oferta está a caminho"; description = "As ofertas preparadas ficam aqui. Agende uma mensagem ou deixe uma oferta pronta agora."; }
    empty.append(iconElement(query ? "search" : "bag", "empty-illustration"), textElement("h3", "", title), textElement("p", "", description));
    if (!query) empty.append(actionButton(isFirst ? "Cadastrar primeira oferta" : "Nova oferta", "plus", "button button-primary", () => openOffer()));
    container.append(empty);
    return;
  }
  offers.forEach((offer) => container.append(offerCard(offer)));
}
function offerCard(offer) {
  const card = textElement("article", "offer-card");
  card.dataset.offerId = offer.id;
  const main = textElement("div", "offer-main");
  const meta = textElement("div", "offer-meta");
  meta.append(textElement("span", "store-badge", offer.store || "Outra loja"));
  if (offer.category) meta.append(textElement("span", "", offer.category));
  main.append(meta, textElement("h3", "offer-title", offer.title));
  const price = textElement("div", "offer-price-row");
  price.append(textElement("span", "offer-price", currency.format(Number(offer.price))));
  if (offer.original_price) price.append(textElement("span", "offer-previous", currency.format(Number(offer.original_price))));
  if (offer.scheduled_at && offer.status === "scheduled") {
    const when = textElement("span", "offer-date");
    when.append(iconElement("clock"), document.createTextNode(dateTime.format(new Date(offer.scheduled_at))));
    when.title = "Horário local deste computador";
    price.append(when);
  }
  main.append(price);
  const side = textElement("div", "offer-side");
  side.append(textElement("span", `status-tag ${offer.status}`, statusLabels[offer.status] || offer.status));
  const actions = textElement("div", "offer-actions");
  const review = actionButton("Revisar", "copy", "button button-secondary", () => openReview(offer.id));
  const edit = actionButton("", "edit", "icon-button", () => openOffer(offer));
  edit.title = "Editar oferta";
  edit.setAttribute("aria-label", `Editar ${offer.title}`);
  actions.append(review, edit);
  if (offer.status !== "archived") {
    const archive = actionButton("", "archive", "icon-button", () => archiveOffer(offer));
    archive.title = "Arquivar oferta";
    archive.setAttribute("aria-label", `Arquivar ${offer.title}`);
    actions.append(archive);
  }
  side.append(actions);
  card.append(iconElement("tag", "offer-thumb"), main, side);
  return card;
}
function setFilter(filter) { currentFilter = filter; if (loaded) render(); }
$$('[data-filter]').forEach((button) => button.addEventListener("click", () => setFilter(button.dataset.filter)));
$("#search").addEventListener("input", () => { if (loaded) renderOffers(); });
$("#nav-queue").addEventListener("click", () => { setFilter("all"); $("#queue-heading").scrollIntoView({ behavior: "smooth", block: "start" }); });
$("#new-offer").addEventListener("click", () => openOffer());

function localDateValue(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}
function openOffer(offer = null) {
  editingId = offer?.id || null;
  const form = $("#offer-form");
  form.reset();
  $$("option[data-temporary]", form).forEach((option) => option.remove());
  inlineError("#offer-error");
  $("#offer-dialog-title").textContent = offer ? "Editar achadinho" : "Novo achadinho";
  if (offer) {
    if (!$$('option', form.elements.store).some((option) => option.value === offer.store)) {
      const option = new Option(offer.store || "Outra", offer.store || "Outra");
      option.dataset.temporary = "true";
      form.elements.store.append(option);
    }
    if (["sent", "archived"].includes(offer.status)) {
      const option = new Option(offer.status === "sent" ? "Manter como enviada" : "Manter arquivada", offer.status);
      option.dataset.temporary = "true";
      form.elements.status.append(option);
    }
    for (const name of ["title", "url", "store", "category", "price", "original_price", "coupon", "notes", "status"]) {
      form.elements[name].value = offer[name] || "";
    }
    for (const name of ["price", "original_price"]) form.elements[name].value = String(offer[name] || "").replace(".", ",");
    form.elements.scheduled_at.value = localDateValue(offer.scheduled_at);
  } else {
    form.elements.status.value = "ready";
    form.elements.category.value = "Casa e dia a dia";
    const nextHour = new Date(Date.now() + 60 * 60 * 1000);
    form.elements.scheduled_at.value = localDateValue(nextHour.toISOString());
  }
  toggleSchedule();
  $("#offer-dialog").showModal();
}
function toggleSchedule() {
  const scheduled = $("#offer-status").value === "scheduled";
  $("#schedule-field").hidden = !scheduled;
  $("#scheduled-at").required = scheduled;
  try { $("#timezone-label").textContent = `Horário local deste computador (${Intl.DateTimeFormat().resolvedOptions().timeZone}).`; }
  catch { /* The browser still handles local dates without a timezone label. */ }
}
$("#offer-status").addEventListener("change", toggleSchedule);
function normalizePrice(value, optional = false) {
  const raw = value.trim();
  if (!raw && optional) return "";
  const cleaned = raw.includes(",") ? raw.replace(/\./g, "").replace(",", ".") : raw;
  if (!/^\d+(?:\.\d{1,2})?$/.test(cleaned) || Number(cleaned) <= 0) {
    throw new Error("Informe um preço maior que zero, com até duas casas decimais. Exemplo: 29,90.");
  }
  return cleaned;
}
$("#offer-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = $("#save-offer");
  if (button.disabled) return;
  inlineError("#offer-error");
  try {
    const fields = Object.fromEntries(new FormData(form));
    fields.price = normalizePrice(fields.price);
    fields.original_price = normalizePrice(fields.original_price, true);
    if (fields.status === "scheduled") {
      const scheduled = new Date(fields.scheduled_at);
      if (Number.isNaN(scheduled.getTime())) throw new Error("Escolha uma data e um horário para preparar a oferta.");
      fields.scheduled_at = scheduled.toISOString();
    } else { fields.scheduled_at = null; }
    setBusy(button, true);
    await api(editingId ? `/api/offers/${encodeURIComponent(editingId)}` : "/api/offers", { method: editingId ? "PATCH" : "POST", body: fields });
    $("#offer-dialog").close();
    toast(fields.status === "scheduled" ? "Oferta agendada. Ela ficará pronta para sua revisão no horário escolhido." : "Oferta salva neste computador.");
    await loadState();
  } catch (error) { inlineError("#offer-error", error.message); }
  finally { setBusy(button, false); }
});
async function archiveOffer(offer) {
  if (!confirm(`Arquivar “${offer.title}”? Você poderá encontrá-la na aba Arquivadas.`)) return;
  try {
    await api(`/api/offers/${encodeURIComponent(offer.id)}`, { method: "PATCH", body: { status: "archived" } });
    toast("Oferta arquivada.");
    await loadState();
  } catch (error) { toast(error.message, true); }
}

function openReview(id) {
  reviewingId = id;
  inlineError("#review-error");
  updateReview();
  $("#review-dialog").showModal();
}
function updateReview() {
  const offer = appState.offers.find((item) => item.id === reviewingId);
  if (!offer) { $("#review-dialog").close(); return; }
  const message = offer.message || "";
  const textarea = $("#message-preview");
  if (textarea.value !== message) textarea.value = message;
  $("#open-whatsapp").href = `https://wa.me/?text=${encodeURIComponent(message)}`;
  const button = $("#mark-sent");
  if (!button.dataset.originalContent) {
    button.disabled = offer.status === "sent";
    button.innerHTML = `${icon("check")} ${offer.status === "sent" ? "Já marcada como enviada" : "Marcar como enviada"}`;
  }
}
$("#copy-message").addEventListener("click", async () => {
  const textarea = $("#message-preview");
  try {
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(textarea.value);
    else {
      textarea.focus();
      textarea.select();
      if (!document.execCommand("copy")) throw new Error("Selecione a mensagem e copie com Ctrl+C (ou ⌘C).");
    }
    toast("Mensagem copiada. Agora você pode colar no WhatsApp.");
  } catch { toast("Não foi possível copiar automaticamente. Selecione a mensagem e use Ctrl+C (ou ⌘C).", true); }
});
$("#open-whatsapp").addEventListener("click", () => toast("Escolha o destino no WhatsApp e confirme o envio por lá."));
$("#mark-sent").addEventListener("click", async () => {
  const offer = appState.offers.find((item) => item.id === reviewingId);
  if (!offer || offer.status === "sent") return;
  if (!confirm("Você já enviou esta oferta? Esta ação apenas registra o envio no painel.")) return;
  const button = $("#mark-sent");
  inlineError("#review-error");
  setBusy(button, true, "Registrando…");
  try {
    await api(`/api/offers/${encodeURIComponent(offer.id)}`, { method: "PATCH", body: { status: "sent" } });
    $("#review-dialog").close();
    toast("Oferta marcada como enviada.");
    await loadState();
  } catch (error) { inlineError("#review-error", error.message); }
  finally { setBusy(button, false); }
});

$("#settings-button").addEventListener("click", () => {
  $("#channel-name").value = appState.settings.channel_name;
  inlineError("#settings-error");
  $("#settings-dialog").showModal();
});
$("#settings-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#save-settings");
  if (button.disabled) return;
  inlineError("#settings-error");
  setBusy(button, true);
  try {
    await api("/api/settings", { method: "POST", body: { channel_name: $("#channel-name").value.trim() } });
    $("#settings-dialog").close();
    toast("Nome do seu espaço atualizado.");
    await loadState();
  } catch (error) { inlineError("#settings-error", error.message); }
  finally { setBusy(button, false); }
});
$("#import-button").addEventListener("click", () => $("#import-file").click());
$("#import-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  event.target.value = "";
  if (!file) return;
  const button = $("#import-button");
  try {
    if (file.size > 128 * 1024 * 1024) throw new Error("O backup deve ter no máximo 128 MB.");
    let backup;
    try { backup = JSON.parse(await file.text()); }
    catch { throw new Error("Este arquivo não é um backup JSON válido."); }
    if (backup.version !== 1 || !Array.isArray(backup.offers)) throw new Error("Escolha um backup criado por este aplicativo.");
    if (!confirm(`Importar as ${backup.offers.length} ofertas deste backup? As ofertas já existentes serão mantidas, sem substituição.`)) return;
    button.disabled = true;
    const result = await api("/api/restore", { method: "POST", body: backup });
    toast(`${result.imported} oferta(s) importada(s). ${result.skipped} já existente(s) preservada(s).`);
    await loadState();
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
});
$$('[data-close]').forEach((button) => button.addEventListener("click", () => document.getElementById(button.dataset.close).close()));
loadState();
setInterval(() => { if (!document.hidden) loadState(true); }, 15000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) loadState(true); });

// O laboratório mantém os dados e segredos fora do armazenamento do navegador.
let automationState = null;
let lastAnalysis = null;
let evaluatingCandidates = false;
let savingIntegrations = false;

function integrationStateFrom(response) {
  return response?.config ? response : response?.state?.config ? response.state : null;
}
function updateAutomationStatus() {
  const config = automationState?.config;
  const usage = automationState?.usage;
  $("#lab-provider-label").textContent = config ? `OpenAI · ${config.model}` : "Configuração da IA indisponível";
  $("#lab-provider-note").textContent = config?.ai_key_configured
    ? `Chave disponível. ${usage?.used_today ?? 0} de ${usage?.daily_limit ?? config.daily_limit} chamadas diárias usadas. Os filtros continuam gratuitos, sem IA.`
    : "Os filtros funcionam sem chave. Configure a API da OpenAI para analisar com IA de verdade.";
  $("#lab-test-ai").disabled = evaluatingCandidates || !config?.ai_key_configured;
  $("#lab-test-rules").disabled = evaluatingCandidates;
  const sources = { environment: "fornecida pelo ambiente", saved: "lembrada neste computador", session: "disponível somente nesta sessão" };
  $("#ai-key-status").textContent = config?.ai_key_configured
    ? `Chave configurada: ${sources[config.ai_key_source] || "disponível no programa"}.`
    : "Nenhuma chave de IA configurada.";
  $("#meta-token-status").textContent = config?.meta_token_configured
    ? "Token configurado. Use o diagnóstico para verificar o acesso ao número."
    : "Nenhum token da Meta configurado.";
}
async function loadAutomationState(showError = false) {
  try {
    const next = integrationStateFrom(await api("/api/automation/state"));
    if (!next) throw new Error("Não foi possível ler a configuração das integrações.");
    automationState = next;
    updateAutomationStatus();
    return next;
  } catch (error) {
    updateAutomationStatus();
    if (showError) toast(error.message, true);
    return null;
  }
}
async function openLab() {
  inlineError("#lab-error");
  if (!$("#lab-dialog").open) $("#lab-dialog").showModal();
  const state = await loadAutomationState();
  if (!lastAnalysis && state?.runs?.length) renderAnalysis(state.runs[0]);
}
$("#lab-button").addEventListener("click", openLab);
$("#open-lab").addEventListener("click", openLab);

function fictitiousCandidates() {
  const now = new Date().toISOString();
  const base = {
    store: "Loja fictícia", category: "Casa e dia a dia", original_price: "", coupon: "", notes: "Dados fictícios: apenas teste, não compartilhar.",
    available: true, observed_at: now, expires_at: null, is_demo: true,
  };
  return [
    { ...base, candidate_id: "EX1", product_id: "P1", title: "[FICTÍCIO] Organizador de cozinha", url: "https://example.com/organizador", price: "29.90", original_price: "49.90" },
    { ...base, candidate_id: "EX2", product_id: "P1", title: "[FICTÍCIO] O mesmo organizador, repetido", url: "https://example.com/organizador?repetido=1", price: "29.90", original_price: "49.90" },
    { ...base, candidate_id: "EX3", product_id: "P2", title: "[FICTÍCIO] Promoção encerrada", url: "https://example.com/encerrada", price: "19.90", expires_at: new Date(Date.now() - 3600000).toISOString() },
    { ...base, candidate_id: "EX4", product_id: "P3", title: "[FICTÍCIO] Produto sem preço válido", url: "https://example.com/invalida", price: "0", available: false },
    { ...base, candidate_id: "EX5", product_id: "P4", title: "[FICTÍCIO] Suporte para esponja", url: "https://example.com/suporte", price: "12.90" },
  ];
}
function candidateArray(raw) {
  let parsed;
  try { parsed = JSON.parse(raw); }
  catch { throw new Error("Não foi possível ler o lote. Carregue os exemplos ou importe um JSON válido."); }
  const candidates = Array.isArray(parsed) ? parsed : parsed?.candidates;
  if (!Array.isArray(candidates) || !candidates.length || candidates.length > 20) {
    throw new Error("O lote deve conter uma lista de 1 a 20 candidatos. Use os exemplos para conferir o formato.");
  }
  return candidates;
}
function isDemoCandidate(candidate) {
  if (candidate?.is_demo === true || /\[fict[ií]cio\]/i.test(candidate?.title || "")) return true;
  try { const host = new URL(candidate?.url).hostname.toLowerCase(); return host === "example.com" || host.endsWith(".example.com"); }
  catch { return false; }
}
function updateCandidateSource(label = "Lote editado") {
  try {
    const candidates = candidateArray($("#lab-candidates").value);
    const demo = candidates.some(isDemoCandidate);
    $("#lab-source-status").textContent = `${label}: ${candidates.length} candidato(s).${demo ? " Contém exemplos fictícios, que não podem virar ofertas reais." : " Confira a origem e o horário dos dados antes de analisar."}`;
    $("#lab-source-status").classList.toggle("is-demo", demo);
  } catch {
    $("#lab-source-status").textContent = "Carregue os exemplos ou um lote JSON válido para começar.";
    $("#lab-source-status").classList.remove("is-demo");
  }
}
$("#lab-examples").addEventListener("click", () => {
  if ($("#lab-candidates").value.trim() && !confirm("Substituir o lote atual pelos exemplos fictícios? O resultado anterior continuará visível.")) return;
  $("#lab-candidates").value = JSON.stringify(fictitiousCandidates(), null, 2);
  updateCandidateSource("Exemplos fictícios carregados");
  inlineError("#lab-error");
});
$("#lab-candidates").addEventListener("change", () => updateCandidateSource());
$("#lab-panel-offers").addEventListener("click", () => {
  inlineError("#lab-error");
  const activeOffers = appState.offers.filter((offer) => ["draft", "ready", "scheduled"].includes(offer.status));
  const selectedOffers = activeOffers.slice(0, 20);
  if (!selectedOffers.length) {
    inlineError("#lab-error", "Cadastre uma oferta no painel primeiro. Rascunhos, ofertas prontas e agendadas podem ser usados neste teste.");
    return;
  }
  const notice = activeOffers.length > 20 ? " Serão usadas as primeiras 20 ofertas ativas do painel." : "";
  const replace = $("#lab-candidates").value.trim() ? " O lote atual será substituído." : "";
  if (!confirm(`Você conferiu agora preço, cupom e disponibilidade dessas ${selectedOffers.length} ofertas nas lojas? Isso registra sua conferência; o aplicativo não consultará as lojas.${notice}${replace}`)) return;
  const observedAt = new Date().toISOString();
  const candidates = selectedOffers.map((offer) => ({
    candidate_id: `PAINEL_${String(offer.id).replace(/-/g, "")}`,
    product_id: "", title: offer.title, url: offer.url, store: offer.store || "", category: offer.category || "",
    price: offer.price, original_price: offer.original_price || "", coupon: offer.coupon || "", notes: offer.notes || "",
    available: true, observed_at: observedAt, expires_at: null, is_demo: isDemoCandidate(offer),
  }));
  $("#lab-candidates").value = JSON.stringify(candidates, null, 2);
  updateCandidateSource("Ofertas do painel — conferência declarada por você agora");
});
$("#lab-import").addEventListener("click", () => $("#lab-file").click());
$("#lab-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  event.target.value = "";
  if (!file) return;
  inlineError("#lab-error");
  try {
    if (file.size > 1024 * 1024) throw new Error("O arquivo do lote deve ter até 1 MB e no máximo 20 candidatos.");
    const candidates = candidateArray(await file.text());
    if ($("#lab-candidates").value.trim() && !confirm("Substituir os dados do lote atual pelo arquivo escolhido?")) return;
    $("#lab-candidates").value = JSON.stringify(candidates, null, 2);
    updateCandidateSource("Arquivo carregado");
  } catch (error) { inlineError("#lab-error", error.message); }
});
async function evaluateCandidates(mode) {
  if (evaluatingCandidates) return;
  inlineError("#lab-error");
  const activeButton = mode === "live" ? $("#lab-test-ai") : $("#lab-test-rules");
  try {
    const candidates = candidateArray($("#lab-candidates").value);
    const niche = $("#lab-niche").value.trim();
    if (!niche) throw new Error("Informe o nicho desejado para orientar a seleção.");
    if (mode === "live" && !automationState?.config?.ai_key_configured) throw new Error("Configure uma chave de API em Integrações para usar a IA.");
    evaluatingCandidates = true;
    $("#lab-progress").textContent = mode === "live" ? "Analisando o lote. A chamada de IA pode levar alguns segundos…" : "Aplicando filtros de validade, preço e duplicidade…";
    $("#lab-progress").hidden = false;
    setBusy(activeButton, true, mode === "live" ? "Analisando com IA…" : "Testando filtros…");
    updateAutomationStatus();
    const run = await api("/api/automation/evaluate", { method: "POST", body: { mode, niche, max_results: Number($("#lab-max-results").value), candidates } });
    renderAnalysis(run);
    await loadAutomationState();
    $("#lab-results").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) { inlineError("#lab-error", error.message); }
  finally {
    evaluatingCandidates = false;
    setBusy(activeButton, false);
    $("#lab-progress").hidden = true;
    updateAutomationStatus();
  }
}
$("#lab-test-rules").addEventListener("click", () => evaluateCandidates("rules"));
$("#lab-test-ai").addEventListener("click", () => evaluateCandidates("live"));
function renderAnalysis(run) {
  if (!run || !Array.isArray(run.selected) || !Array.isArray(run.rejected)) return;
  lastAnalysis = run;
  $("#lab-results").hidden = false;
  const usedAI = run.engine === "openai";
  $("#lab-engine").textContent = usedAI ? (run.cached ? "IA · resultado em cache" : "IA · OpenAI") : "Filtros · sem IA";
  $("#lab-engine").className = `status-tag ${usedAI ? "ready" : "scheduled"}`;
  const time = run.created_at ? dateTime.format(new Date(run.created_at)) : "agora";
  const explanation = usedAI ? (run.cached ? "Resultado anterior reutilizado, sem nova chamada." : `Modelo: ${run.model || automationState?.config?.model || "OpenAI"}.`) : "Não houve chamada de IA nem cobrança de API neste teste.";
  $("#lab-run-summary").textContent = `${run.selected.length} selecionada(s), ${run.rejected.length} descartada(s) · ${time}. ${explanation} Os fatos ainda dependem da fonte e da sua conferência.`;
  const selected = $("#lab-selected");
  selected.replaceChildren();
  if (!run.selected.length) selected.append(textElement("p", "lab-empty", "Nenhum candidato adequado foi selecionado neste lote."));
  run.selected.forEach((item) => {
    const candidate = item.candidate || {};
    const demo = isDemoCandidate(candidate);
    const card = textElement("article", "lab-result-card");
    const top = textElement("div", "lab-result-top");
    const title = textElement("div");
    title.append(textElement("h4", "", candidate.title || item.candidate_id));
    const numericPrice = Number(candidate.price);
    title.append(textElement("p", "lab-result-price", Number.isFinite(numericPrice) ? currency.format(numericPrice) : "Confira o preço na fonte"));
    top.append(title, textElement("span", "status-tag ready", demo ? "Teste fictício" : "Selecionada"));
    card.append(top, textElement("p", "lab-result-reason", item.reason || "Selecionada para revisão."));
    const message = textElement("details", "lab-message");
    message.append(textElement("summary", "", "Ver mensagem preparada"));
    const messageLabel = textElement("label", "field", "Prévia da mensagem");
    const textarea = textElement("textarea");
    textarea.readOnly = true;
    textarea.rows = 7;
    textarea.value = item.message || "";
    messageLabel.append(textarea);
    message.append(messageLabel);
    card.append(message);
    const approve = actionButton(demo ? "Exemplo fictício: só para testar" : "Adicionar como rascunho", demo ? "info" : "plus", "button button-secondary", async () => {
      if (demo || approve.disabled) return;
      inlineError("#lab-error");
      try {
        setBusy(approve, true, "Adicionando…");
        const result = await api("/api/automation/approve", { method: "POST", body: { run_id: run.id, candidate_id: item.candidate_id } });
        setBusy(approve, false);
        approve.textContent = result.created ? "Rascunho adicionado" : "Esta oferta já está no painel";
        approve.disabled = true;
        toast(result.created ? "Oferta adicionada como rascunho. Revise antes de compartilhar." : "A oferta já estava no painel. Nenhum rascunho duplicado foi criado.");
        await loadState();
      } catch (error) { setBusy(approve, false); inlineError("#lab-error", error.message); }
    });
    approve.disabled = demo;
    if (demo) approve.dataset.demo = "true";
    card.append(approve);
    selected.append(card);
  });
  const rejected = $("#lab-rejected-list");
  rejected.replaceChildren();
  run.rejected.forEach((item) => {
    const row = textElement("li");
    row.append(textElement("strong", "", item.title || item.candidate_id), textElement("span", "", item.reason || "Não selecionada."));
    rejected.append(row);
  });
  $("#lab-rejected-section").hidden = !run.rejected.length;
  $("#lab-rejected-summary").textContent = `Ver ${run.rejected.length} candidato(s) descartado(s) e motivos`;
}

async function openIntegrations() {
  inlineError("#integrations-error");
  $("#meta-test-result").hidden = true;
  $("#integration-ai-key").value = "";
  $("#integration-meta-token").value = "";
  $("#remember-ai-key").checked = false;
  $("#remember-meta-token").checked = false;
  if (!$("#integrations-dialog").open) $("#integrations-dialog").showModal();
  const state = await loadAutomationState();
  if (!state) {
    inlineError("#integrations-error", "Não foi possível carregar as integrações. Verifique se você abriu a versão atualizada do programa.");
    return;
  }
  $("#integration-model").value = state.config.model || "gpt-4.1-mini";
  $("#integration-daily-limit").value = state.config.daily_limit || 20;
  $("#integration-phone-id").value = state.config.phone_number_id || "";
  $("#integration-api-version").value = state.config.api_version || "v23.0";
}
$("#integrations-button").addEventListener("click", openIntegrations);
$("#lab-configure").addEventListener("click", openIntegrations);
function integrationPayload() {
  if (!$("#integrations-form").reportValidity()) throw new Error("Confira os campos das integrações.");
  return {
    model: $("#integration-model").value.trim(), daily_limit: Number($("#integration-daily-limit").value),
    ai_key: $("#integration-ai-key").value.trim(), remember_key: $("#remember-ai-key").checked,
    meta_token: $("#integration-meta-token").value.trim(), remember_meta_token: $("#remember-meta-token").checked,
    phone_number_id: $("#integration-phone-id").value.trim(), api_version: $("#integration-api-version").value.trim(),
  };
}
async function saveIntegrationConfig() {
  const response = await api("/api/automation/config", { method: "POST", body: integrationPayload() });
  $("#integration-ai-key").value = "";
  $("#integration-meta-token").value = "";
  $("#remember-ai-key").checked = false;
  $("#remember-meta-token").checked = false;
  automationState = integrationStateFrom(response) || await loadAutomationState();
  updateAutomationStatus();
}
function setIntegrationBusy(busy, testing = false) {
  savingIntegrations = busy;
  $("#save-integrations").disabled = busy;
  $("#test-meta-connection").disabled = busy;
  $("#clear-ai-key").disabled = busy;
  $("#clear-meta-token").disabled = busy;
  $("#save-integrations").textContent = busy && !testing ? "Salvando…" : "Salvar integrações";
  $("#test-meta-connection").textContent = busy && testing ? "Testando conexão…" : "Salvar e testar conexão Meta";
}
$("#integrations-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (savingIntegrations) return;
  inlineError("#integrations-error");
  setIntegrationBusy(true);
  try {
    await saveIntegrationConfig();
    toast("Configurações salvas. Use os botões de teste para verificar as integrações.");
  } catch (error) { inlineError("#integrations-error", error.message); }
  finally { setIntegrationBusy(false); }
});
$("#test-meta-connection").addEventListener("click", async () => {
  if (savingIntegrations) return;
  inlineError("#integrations-error");
  $("#meta-test-result").hidden = true;
  setIntegrationBusy(true, true);
  try {
    await saveIntegrationConfig();
    const result = await api("/api/automation/meta/test", { method: "POST", body: {} });
    const node = $("#meta-test-result");
    node.replaceChildren();
    node.append(textElement("strong", "", result.connected ? "Conexão com a API confirmada" : "Confira a configuração da Meta"));
    const phone = result.phone || {};
    if (phone.verified_name || phone.display_phone_number) node.append(textElement("p", "", [phone.verified_name, phone.display_phone_number].filter(Boolean).join(" · ")));
    node.append(textElement("p", "", result.message || "Este teste não confirma suporte a grupos ou comunidades e não envia mensagens."));
    node.hidden = false;
  } catch (error) { inlineError("#integrations-error", error.message); }
  finally { setIntegrationBusy(false); }
});
async function clearLocalSecret(kind) {
  if (savingIntegrations || !confirm("Remover este segredo salvo localmente? Valores fornecidos pelo ambiente continuarão disponíveis.")) return;
  inlineError("#integrations-error");
  setIntegrationBusy(true);
  try {
    const field = kind === "ai" ? "clear_ai_key" : "clear_meta_token";
    const response = await api("/api/automation/config", { method: "POST", body: { [field]: true } });
    automationState = integrationStateFrom(response) || await loadAutomationState();
    $(kind === "ai" ? "#integration-ai-key" : "#integration-meta-token").value = "";
    updateAutomationStatus();
    toast("Segredo local removido. Valores fornecidos pelo ambiente não são alterados.");
  } catch (error) { inlineError("#integrations-error", error.message); }
  finally { setIntegrationBusy(false); }
}
$("#clear-ai-key").addEventListener("click", () => clearLocalSecret("ai"));
$("#clear-meta-token").addEventListener("click", () => clearLocalSecret("meta"));
$("#integrations-dialog").addEventListener("close", () => {
  $("#integration-ai-key").value = "";
  $("#integration-meta-token").value = "";
  if ($("#lab-dialog").open) loadAutomationState();
});
