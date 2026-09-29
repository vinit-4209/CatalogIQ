/**
 * CatalogIQ - Frontend Application Script
 * Vanilla JavaScript implementation for CSV ingestion, live job polling,
 * product catalogue browsing, filtering, search, and manual review.
 */

const API_BASE = "/api";

// State
let currentPage = 1;
const pageSize = 20;
let currentCategory = "";
let currentSearch = "";
let totalProducts = 0;
let searchDebounceTimer = null;
let activePollingInterval = null;
let activeJobId = null;

// DOM Elements
const csvFileInput = document.getElementById("csvFileInput");
const fileNameDisplay = document.getElementById("fileNameDisplay");
const fileDropzone = document.getElementById("fileDropzone");
const uploadForm = document.getElementById("uploadForm");
const uploadBtn = document.getElementById("uploadBtn");
const uploadError = document.getElementById("uploadError");

const jobStatusCard = document.getElementById("jobStatusCard");
const jobEmptyState = document.getElementById("jobEmptyState");
const jobDetailsContent = document.getElementById("jobDetailsContent");
const jobIdDisplay = document.getElementById("jobId");
const jobStatusBadge = document.getElementById("jobStatusBadge");
const jobProgressText = document.getElementById("jobProgressText");
const jobProgressBar = document.getElementById("jobProgressBar");
const jobProgressAria = document.getElementById("jobProgressAria");
const jobTotal = document.getElementById("jobTotal");
const jobDone = document.getElementById("jobDone");
const jobFailed = document.getElementById("jobFailed");
const jobCacheHits = document.getElementById("jobCacheHits");

const searchInput = document.getElementById("searchInput");
const categoryFilter = document.getElementById("categoryFilter");
const refreshBtn = document.getElementById("refreshBtn");
const productsTableBody = document.getElementById("productsTableBody");
const totalProductsCount = document.getElementById("totalProductsCount");
const pageIndicator = document.getElementById("pageIndicator");
const prevPageBtn = document.getElementById("prevPageBtn");
const nextPageBtn = document.getElementById("nextPageBtn");

const editModal = document.getElementById("editModal");
const editForm = document.getElementById("editForm");
const editSku = document.getElementById("editSku");
const editRawTitle = document.getElementById("editRawTitle");
const editRawDescription = document.getElementById("editRawDescription");
const editCleanTitle = document.getElementById("editCleanTitle");
const editCategory = document.getElementById("editCategory");
const editTags = document.getElementById("editTags");
const modalCloseX = document.getElementById("modalCloseX");
const editCancelBtn = document.getElementById("editCancelBtn");
const modalError = document.getElementById("modalError");
const toast = document.getElementById("toast");

const healthProvider = document.getElementById("healthProvider");
const healthConcurrency = document.getElementById("healthConcurrency");

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
  fetchHealth();
  loadProducts();
  setupEventListeners();
});

// --- Health Check ---
async function fetchHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (res.ok) {
      const data = await res.json();
      if (healthProvider) healthProvider.textContent = data.provider || data.llm_provider || "mock";
      if (healthConcurrency) healthConcurrency.textContent = data.concurrency || data.llm_concurrency || "5";
    }
  } catch (err) {
    console.warn("Could not fetch system health:", err);
  }
}

// --- Event Listeners Setup ---
function setupEventListeners() {
  // File input change
  csvFileInput.addEventListener("change", handleFileSelected);

  // Drag and drop dropzone
  ["dragenter", "dragover"].forEach(name => {
    fileDropzone.addEventListener(name, (e) => {
      e.preventDefault();
      fileDropzone.classList.add("drag-over");
    });
  });
  ["dragleave", "drop"].forEach(name => {
    fileDropzone.addEventListener(name, (e) => {
      e.preventDefault();
      fileDropzone.classList.remove("drag-over");
    });
  });
  fileDropzone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      csvFileInput.files = e.dataTransfer.files;
      handleFileSelected();
    }
  });

  // Upload submission
  uploadForm.addEventListener("submit", handleUploadSubmit);

  // Search input (debounced by 300ms)
  searchInput.addEventListener("input", (e) => {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      currentSearch = e.target.value.trim();
      currentPage = 1;
      loadProducts();
    }, 300);
  });

  // Category filter
  categoryFilter.addEventListener("change", (e) => {
    currentCategory = e.target.value;
    currentPage = 1;
    loadProducts();
  });

  // Refresh button
  refreshBtn.addEventListener("click", () => {
    loadProducts();
    showToast("Catalogue refreshed");
  });

  // Pagination buttons
  prevPageBtn.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      loadProducts();
    }
  });

  nextPageBtn.addEventListener("click", () => {
    if (currentPage * pageSize < totalProducts) {
      currentPage++;
      loadProducts();
    }
  });

  // Modal controls
  modalCloseX.addEventListener("click", closeModal);
  editCancelBtn.addEventListener("click", closeModal);
  editForm.addEventListener("submit", handleProductSave);

  // Close modal on escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !editModal.classList.contains("hidden")) {
      closeModal();
    }
  });

  // Close modal when clicking outside modal card
  editModal.addEventListener("click", (e) => {
    if (e.target === editModal) {
      closeModal();
    }
  });
}

function handleFileSelected() {
  hideUploadError();
  const file = csvFileInput.files[0];
  if (file) {
    fileNameDisplay.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    uploadBtn.disabled = false;
  } else {
    fileNameDisplay.textContent = "No file chosen";
    uploadBtn.disabled = true;
  }
}

// --- CSV Parsing ---
/**
 * Parse RFC 4180 CSV entirely in browser.
 * Handles quoted fields, embedded commas, escaped quotes (""), and empty lines.
 */
function parseCSV(text) {
  const rows = [];
  let currentRow = [];
  let currentField = "";
  let inQuotes = false;
  let i = 0;

  while (i < text.length) {
    const char = text[i];
    const nextChar = text[i + 1];

    if (inQuotes) {
      if (char === '"') {
        if (nextChar === '"') {
          currentField += '"';
          i += 2;
          continue;
        } else {
          inQuotes = false;
          i++;
          continue;
        }
      } else {
        currentField += char;
        i++;
        continue;
      }
    } else {
      if (char === '"') {
        inQuotes = true;
        i++;
        continue;
      } else if (char === ",") {
        currentRow.push(currentField);
        currentField = "";
        i++;
        continue;
      } else if (char === "\r") {
        if (nextChar === "\n") i++;
        currentRow.push(currentField);
        currentField = "";
        if (currentRow.some((f) => f.trim() !== "")) {
          rows.push(currentRow);
        }
        currentRow = [];
        i++;
        continue;
      } else if (char === "\n") {
        currentRow.push(currentField);
        currentField = "";
        if (currentRow.some((f) => f.trim() !== "")) {
          rows.push(currentRow);
        }
        currentRow = [];
        i++;
        continue;
      } else {
        currentField += char;
        i++;
        continue;
      }
    }
  }

  if (currentField !== "" || currentRow.length > 0) {
    currentRow.push(currentField);
    if (currentRow.some((f) => f.trim() !== "")) {
      rows.push(currentRow);
    }
  }

  return rows;
}

// --- Upload & Job Submission ---
async function handleUploadSubmit(e) {
  e.preventDefault();
  hideUploadError();

  const file = csvFileInput.files[0];
  if (!file) {
    showUploadError("Please choose a CSV file to upload.");
    return;
  }

  try {
    const text = await file.text();
    if (!text || text.trim() === "") {
      showUploadError("The CSV file is empty.");
      return;
    }

    const rows = parseCSV(text);
    if (rows.length < 2) {
      showUploadError("The CSV file must contain a header row and at least one product row.");
      return;
    }

    // Match headers
    const headerRow = rows[0].map((h) => h.trim().toLowerCase());
    const skuIdx = headerRow.indexOf("sku");
    const rawTitleIdx = headerRow.indexOf("raw_title");
    const rawDescIdx = headerRow.indexOf("raw_description");

    if (skuIdx === -1) {
      showUploadError("Missing required 'sku' column in CSV header.");
      return;
    }
    if (rawTitleIdx === -1) {
      showUploadError("Missing required 'raw_title' column in CSV header.");
      return;
    }

    // Build products list with validation
    const products = [];
    for (let r = 1; r < rows.length; r++) {
      const row = rows[r];
      const rowNum = r + 1; // 1-indexed for user visibility

      const sku = (row[skuIdx] || "").trim();
      const rawTitle = (row[rawTitleIdx] || "").trim();
      const rawDesc = rawDescIdx !== -1 ? (row[rawDescIdx] || "").trim() : null;

      if (!sku) {
        showUploadError(`Row ${rowNum}: Product SKU cannot be empty.`);
        return;
      }
      if (!rawTitle) {
        showUploadError(`Row ${rowNum}: Product raw_title cannot be empty.`);
        return;
      }

      products.push({
        sku: sku,
        raw_title: rawTitle,
        raw_description: rawDesc || null,
      });
    }

    if (products.length === 0) {
      showUploadError("No valid product records found in CSV.");
      return;
    }

    // Submit batch job to backend
    uploadBtn.disabled = true;
    uploadBtn.textContent = "Submitting Job...";

    const res = await fetch(`${API_BASE}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ products }),
    });

    if (res.status === 202) {
      const job = await res.json();
      showToast(`Job submitted! (ID: ${job.id})`);
      displayJob(job);
      startPollingJob(job.id);
      // Reset file input
      uploadForm.reset();
      fileNameDisplay.textContent = "No file chosen";
    } else {
      const errData = await res.json().catch(() => ({}));
      showUploadError(errData.error || `Server error: HTTP ${res.status}`);
    }
  } catch (err) {
    showUploadError(`Failed to process CSV: ${err.message}`);
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.textContent = "Submit Enrichment Job";
  }
}

function showUploadError(msg) {
  uploadError.textContent = msg;
  uploadError.classList.remove("hidden");
}

function hideUploadError() {
  uploadError.textContent = "";
  uploadError.classList.add("hidden");
}

// --- Live Job Tracking ---
function displayJob(job) {
  jobEmptyState.classList.add("hidden");
  jobDetailsContent.classList.remove("hidden");

  jobIdDisplay.textContent = job.id;
  updateStatusBadge(jobStatusBadge, job.status);

  const done = job.done || 0;
  const failed = job.failed || 0;
  const total = job.total || 0;
  const cacheHits = job.cache_hits || 0;

  jobTotal.textContent = total;
  jobDone.textContent = done;
  jobFailed.textContent = failed;
  jobCacheHits.textContent = cacheHits;

  const processed = done + failed;
  jobProgressText.textContent = `${processed} / ${total}`;

  const pct = total > 0 ? Math.round((processed / total) * 100) : 0;
  jobProgressBar.style.width = `${pct}%`;
  jobProgressAria.setAttribute("aria-valuenow", pct);
}

function startPollingJob(jobId) {
  if (activePollingInterval) {
    clearInterval(activePollingInterval);
  }
  activeJobId = jobId;

  // Poll once per second (1000ms)
  activePollingInterval = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/jobs/${jobId}`);
      if (!res.ok) {
        clearInterval(activePollingInterval);
        return;
      }

      const job = await res.json();
      displayJob(job);

      if (job.status === "completed" || job.status === "failed") {
        clearInterval(activePollingInterval);
        activePollingInterval = null;
        showToast(`Job ${job.id} ${job.status}!`);
        // Refresh catalogue to show newly enriched products
        loadProducts();
      }
    } catch (err) {
      console.warn("Job polling error:", err);
    }
  }, 1000);
}

function updateStatusBadge(badgeElem, status) {
  badgeElem.textContent = status;
  badgeElem.className = "badge";
  switch (status) {
    case "enriched":
      badgeElem.classList.add("badge-enriched");
      break;
    case "approved":
      badgeElem.classList.add("badge-approved");
      break;
    case "failed":
      badgeElem.classList.add("badge-failed");
      break;
    case "running":
      badgeElem.classList.add("badge-running");
      break;
    case "queued":
      badgeElem.classList.add("badge-queued");
      break;
    default:
      badgeElem.classList.add("badge-idle");
  }
}

// --- Catalogue Loading & Rendering ---
async function loadProducts() {
  productsTableBody.innerHTML = `
    <tr class="empty-row"><td colspan="8">Loading catalogue...</td></tr>
  `;

  try {
    const params = new URLSearchParams({
      page: currentPage,
      page_size: pageSize,
    });
    if (currentCategory) params.append("category", currentCategory);
    if (currentSearch) params.append("q", currentSearch);

    const res = await fetch(`${API_BASE}/products?${params.toString()}`);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const data = await res.json();
    totalProducts = data.total || 0;
    renderProducts(data.items || []);
    renderPagination();
  } catch (err) {
    productsTableBody.innerHTML = `
      <tr class="empty-row"><td colspan="8" style="color: var(--color-danger);">Failed to load products: ${err.message}</td></tr>
    `;
  }
}

function renderProducts(items) {
  totalProductsCount.textContent = `${totalProducts} products`;

  if (!items || items.length === 0) {
    productsTableBody.innerHTML = `
      <tr class="empty-row"><td colspan="8">No products found matching the criteria.</td></tr>
    `;
    return;
  }

  productsTableBody.innerHTML = "";

  items.forEach((item) => {
    const tr = document.createElement("tr");
    if (item.status === "failed") {
      tr.classList.add("row-failed");
    }

    // SKU
    const tdSku = document.createElement("td");
    tdSku.innerHTML = `<span class="product-sku">${escapeHtml(item.sku)}</span>`;

    // Status
    const tdStatus = document.createElement("td");
    const statusBadge = document.createElement("span");
    updateStatusBadge(statusBadge, item.status);
    tdStatus.appendChild(statusBadge);

    // Title (Clean / Raw)
    const tdTitle = document.createElement("td");
    const cleanTitle = item.clean_title || `<em style="color: var(--color-text-light);">Not enriched</em>`;
    tdTitle.innerHTML = `
      <div class="title-cell">
        <span class="clean-title">${escapeHtml(cleanTitle)}</span>
        <span class="raw-title">${escapeHtml(item.raw_title)}</span>
      </div>
    `;

    // Category
    const tdCategory = document.createElement("td");
    tdCategory.textContent = item.category || "-";

    // Brand
    const tdBrand = document.createElement("td");
    tdBrand.textContent = item.brand || "-";

    // Tags
    const tdTags = document.createElement("td");
    const tagsDiv = document.createElement("div");
    tagsDiv.className = "tags-cell";
    if (Array.isArray(item.tags) && item.tags.length > 0) {
      item.tags.forEach((tag) => {
        const pill = document.createElement("span");
        pill.className = "tag-pill";
        pill.textContent = tag;
        tagsDiv.appendChild(pill);
      });
    } else {
      tagsDiv.innerHTML = `<span style="color: var(--color-text-light);">-</span>`;
    }
    tdTags.appendChild(tagsDiv);

    // Error
    const tdError = document.createElement("td");
    if (item.error) {
      tdError.innerHTML = `<span class="error-text" title="${escapeHtml(item.error)}">${escapeHtml(item.error)}</span>`;
    } else {
      tdError.innerHTML = `<span style="color: var(--color-text-light);">-</span>`;
    }

    // Action (Edit/Review button)
    const tdAction = document.createElement("td");
    tdAction.style.textAlign = "center";
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn btn-secondary btn-sm";
    editBtn.textContent = "Review";
    editBtn.setAttribute("aria-label", `Review product ${item.sku}`);
    editBtn.addEventListener("click", () => openEditModal(item));
    tdAction.appendChild(editBtn);

    tr.appendChild(tdSku);
    tr.appendChild(tdStatus);
    tr.appendChild(tdTitle);
    tr.appendChild(tdCategory);
    tr.appendChild(tdBrand);
    tr.appendChild(tdTags);
    tr.appendChild(tdError);
    tr.appendChild(tdAction);

    productsTableBody.appendChild(tr);
  });
}

function renderPagination() {
  const totalPages = Math.ceil(totalProducts / pageSize) || 1;
  pageIndicator.textContent = `Page ${currentPage} of ${totalPages}`;

  prevPageBtn.disabled = currentPage <= 1;
  nextPageBtn.disabled = currentPage >= totalPages;
}

// --- Product Review & Edit Modal ---
function openEditModal(product) {
  hideModalError();

  editSku.value = product.sku;
  editRawTitle.value = product.raw_title || "";
  editRawDescription.value = product.raw_description || "(None)";
  editCleanTitle.value = product.clean_title || product.raw_title || "";
  editCategory.value = product.category || "Other";

  if (Array.isArray(product.tags)) {
    editTags.value = product.tags.join(", ");
  } else {
    editTags.value = "";
  }

  editModal.classList.remove("hidden");
  editCleanTitle.focus();
}

function closeModal() {
  editModal.classList.add("hidden");
  hideModalError();
}

async function handleProductSave(e) {
  e.preventDefault();
  hideModalError();

  const sku = editSku.value;
  const cleanTitle = editCleanTitle.value.trim();
  const category = editCategory.value;
  const rawTags = editTags.value;

  if (!cleanTitle) {
    showModalError("Clean Title cannot be empty.");
    return;
  }

  // Parse tags into lowercase list
  const tagsList = rawTags
    .split(",")
    .map((t) => t.trim().toLowerCase())
    .filter((t) => t.length > 0)
    .slice(0, 5); // max 5

  const payload = {
    clean_title: cleanTitle,
    category: category,
    tags: tagsList,
  };

  const saveBtn = document.getElementById("editSaveBtn");
  saveBtn.disabled = true;
  saveBtn.textContent = "Saving...";

  try {
    const res = await fetch(`${API_BASE}/products/${encodeURIComponent(sku)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      closeModal();
      showToast(`Product ${sku} approved and updated!`);
      loadProducts();
    } else {
      const errData = await res.json().catch(() => ({}));
      showModalError(errData.error || `Failed to update product (HTTP ${res.status})`);
    }
  } catch (err) {
    showModalError(`Network error: ${err.message}`);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "Approve & Save";
  }
}

function showModalError(msg) {
  modalError.textContent = msg;
  modalError.classList.remove("hidden");
}

function hideModalError() {
  modalError.textContent = "";
  modalError.classList.add("hidden");
}

// --- Toast Notifications ---
let toastTimeout = null;
function showToast(message) {
  if (toastTimeout) clearTimeout(toastTimeout);
  toast.textContent = message;
  toast.classList.remove("hidden");
  toastTimeout = setTimeout(() => {
    toast.classList.add("hidden");
  }, 3500);
}

// --- Helpers ---
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
