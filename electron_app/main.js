// main.js — Processus principal Electron pour ASF Scheduler

const { app, BrowserWindow, dialog } = require("electron");
const path = require("path");
const { autoUpdater } = require("electron-updater");
const { launchStreamlit, waitForStreamlit } = require("./start-streamlit");

let splash = null;
let mainWindow = null;
let streamlitProcess = null;

const STREAMLIT_PORT = 8501;

// ----------------------------------------------------
// 1. Création du splash screen
// ----------------------------------------------------
function createSplash() {
  splash = new BrowserWindow({
    width: 480,
    height: 320,
    frame: false,
    alwaysOnTop: true,
    resizable: false,
    transparent: true,
    center: true,
    show: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js")
    }
  });

  splash.loadFile(path.join(__dirname, "splash.html"));
}

// ----------------------------------------------------
// 2. Fenêtre principale (Streamlit)
// ----------------------------------------------------
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js")
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  mainWindow.loadURL(`http://localhost:${STREAMLIT_PORT}`);

  mainWindow.once("ready-to-show", () => {
    if (splash) {
      splash.close();
      splash = null;
    }
    mainWindow.show();
  });
}

// ----------------------------------------------------
// 3. Cycle de vie de l'application
// ----------------------------------------------------
app.whenReady().then(async () => {
  console.log("🚀 ASF Scheduler – Electron prêt");

  createSplash();

  // Lancer Streamlit (dev ou packagé)
  streamlitProcess = launchStreamlit(STREAMLIT_PORT);

  // Attendre que Streamlit soit prêt
  try {
    await waitForStreamlit(STREAMLIT_PORT);
    console.log("✅ Streamlit répond, ouverture de la fenêtre principale");
    createMainWindow();
  } catch (err) {
    console.error("❌ Streamlit n'a pas démarré :", err);
    dialog.showErrorBox(
      "Erreur au démarrage",
      "Impossible de démarrer le serveur Streamlit.\n\nVérifie que Python et l'environnement sont correctement installés."
    );
    if (splash) splash.close();
    app.quit();
    return;
  }

  // Auto-update (ne fait rien si pas de release)
  autoUpdater.checkForUpdatesAndNotify();

  autoUpdater.on("update-downloaded", () => {
    dialog.showMessageBox({
      type: "info",
      title: "Mise à jour disponible",
      message:
        "Une nouvelle version d’ASF Scheduler a été téléchargée. Elle sera installée au prochain redémarrage.",
      buttons: ["OK"]
    });
  });
});

app.on("window-all-closed", () => {
  if (streamlitProcess) {
    try {
      streamlitProcess.kill();
    } catch (e) {
      console.warn("⚠️ Impossible de tuer le process Streamlit :", e);
    }
  }

  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0 && !mainWindow) {
    createMainWindow();
  }
});
