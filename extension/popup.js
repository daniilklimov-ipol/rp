const DEFAULT_PORT = 8765;

const portInput = document.getElementById("port");
const enabledInput = document.getElementById("enabled");
const statusEl = document.getElementById("status");
const saveBtn = document.getElementById("save");

function setStatus(text, ok) {
  statusEl.textContent = text;
  statusEl.className = ok ? "ok" : "bad";
}

function checkHealth() {
  setStatus("Checking…", true);
  chrome.runtime.sendMessage({ type: "HEALTH" }, (health) => {
    if (!health || health.status !== "ok") {
      setStatus("Can't reach the desktop app. Is it running?", false);
      return;
    }
    const modelState = health.model_trained ? "ML model active" : "using heuristic (need more watch history)";
    const apiState = health.api_key_configured ? "API key set" : "no API key set";
    setStatus(`Connected. ${modelState}, ${apiState}.`, true);
  });
}

chrome.storage.local.get(["serverPort", "overlaysEnabled"], (res) => {
  portInput.value = res.serverPort || DEFAULT_PORT;
  enabledInput.checked = res.overlaysEnabled !== false;
  checkHealth();
});

saveBtn.addEventListener("click", () => {
  const port = parseInt(portInput.value, 10) || DEFAULT_PORT;
  const overlaysEnabled = enabledInput.checked;
  chrome.storage.local.set({ serverPort: port, overlaysEnabled }, checkHealth);
});
