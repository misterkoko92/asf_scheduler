const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const waitOn = require("wait-on");
const { autoUpdater } = require("electron-updater");

let splash = null;
let mainWindow = null;
let streamlitProcess = null;

const STREAMLIT_PORT = 8501;

const PYTHON_EXEC = process.platform === "win32"
  ? path.join(process.resourcesPath, "python", "venv", "Scripts", "python.exe")
  : path.join(process.resourcesPath, "python", "venv", "bin", "python3");

const STREAMLIT_SCRIPT = path.join(process.resourcesPath, "python", "app.py");

// ----------------------------------------------------------------------
// 1. Splash Screen avec barre de progression
// ----------------------------------------------------------------------
function createSplash() {
  splash = new BrowserWindow({
    width: 480,
    height: 320,
    frame: false,
    alwaysOnTop: true,
    transparent: true,
    center: true,
    resizable: false,
    show: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    }
  });

  splash.loadFile(path.join(__dirname, "splash.html"));
}

// ----------------------------------------------------------------------
// 2. Fenêtre principale (Streamlit)
// ----------------------------------------------------------------------
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1350,
    height: 900,
    icon: path.join(process.resourcesPath, "icon.png"),
    webPreferences: {
      devTools: true,
    },
    show: false,
  });

  mainWindow.loadURL("http://localhost:" + STREAMLIT_PORT + "/");

  mainWindow.once("ready-to-show", () => {
    if (splash) splash.close();
    mainWindow.show();
  });
}

// ----------------------------------------------------------------------
// 3. Démarrer Streamlit
// ----------------------------------------------------------------------
function startStreamlit() {
  streamlitProcess = spawn(
    PYTHON_EXEC,
    [
      "-m", "streamlit",
      "run", STREAMLIT_SCRIPT,
      "--server.headless", "true",
      "--server.port", String(STREAMLIT_PORT),
      "--browser.serverAddress", "localhost"
    ],
    {
      env: { ...process.env, PYTHONUNBUFFERED: "1" }
    }
  );

  streamlitProcess.stdout.on("data", (data) => console.log("[Streamlit]", data.toString()));
  streamlitProcess.stderr.on("data", (data) => console.error("[Streamlit ERR]", data.toString()));
}

// ----------------------------------------------------------------------
// 4. Attente de Streamlit + Progression visuelle
// ----------------------------------------------------------------------
async function waitForStreamlit() {
  let progress = 0;

  // simulation de progression pendant boot Python + Streamlit
  const timer = setInterval(() => {
    if (progress < 80) {
      progress += 3;
      if (splash) splash.webContents.send("progress", progress);
    }
  }, 300);

  try {
    await waitOn({
      resources: ["http://localhost:" + STREAMLIT_PORT],
      timeout: 30000,
      interval: 500,
    });

    clearInterval(timer);

    // remplir jusqu'à 100%
    let finalProgress = 80;
    const finalize = setInterval(() => {
      finalProgress += 5;
      splash.webContents.send("progress", finalProgress);
      if (finalProgress >= 100) clearInterval(finalize);
    }, 80);

    createMainWindow();

  } catch (e) {
    console.error("❌ Streamlit n'a pas répondu :", e);
  }
}

// ----------------------------------------------------------------------
// Auto-update
// ----------------------------------------------------------------------
autoUpdater.on("update-downloaded", () => {
  autoUpdater.quitAndInstall();
});

// ----------------------------------------------------------------------
// Cycle Electron
// ----------------------------------------------------------------------
app.whenReady().then(async () => {
  createSplash();
  startStreamlit();
  waitForStreamlit();
  autoUpdater.checkForUpdatesAndNotify();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
  if (streamlitProcess) streamlitProcess.kill();
});
