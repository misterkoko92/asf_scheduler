const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const path = require("path");
const { autoUpdater } = require("electron-updater");
const { spawn } = require("child_process");
const waitOn = require("wait-on");

let mainWindow;
let splashWindow;
let streamlitProcess = null;

function createSplash() {
  splashWindow = new BrowserWindow({
    width: 500,
    height: 300,
    frame: false,
    transparent: false,
    alwaysOnTop: true,
    resizable: false,
    show: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js")
    }
  });

  splashWindow.loadFile(path.join(__dirname, "splash.html"));
}

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
}

function startStreamlit() {
  const pythonPath = path.join(process.resourcesPath, "venv/bin/python3");
  const scriptPath = path.join(process.resourcesPath, "app.py");

  console.log("➡️ Python =", pythonPath);
  console.log("➡️ Script Streamlit =", scriptPath);

  streamlitProcess = spawn(pythonPath, ["-m", "streamlit", "run", scriptPath, "--server.port=8501"], {
    cwd: process.resourcesPath
  });

  streamlitProcess.stdout.on("data", data => {
    console.log("[Streamlit]", data.toString());
  });

  streamlitProcess.stderr.on("data", data => {
    console.error("[Streamlit ERROR]", data.toString());
    if (splashWindow) {
      splashWindow.webContents.send("log", data.toString());
    }
  });

  streamlitProcess.on("close", code => {
    console.error("❌ Streamlit exited with code", code);
    app.quit();
  });
}

function monitorStreamlit() {
  waitOn(
    {
      resources: ["http://localhost:8501"],
      timeout: 30000
    },
    err => {
      if (err) {
        console.error("❌ Streamlit not responding:", err);
        return;
      }
      console.log("🚀 Streamlit READY!");
      
      if (mainWindow) {
        mainWindow.loadURL("http://localhost:8501");
        mainWindow.show();
      }
      if (splashWindow) {
        splashWindow.close();
      }
    }
  );
}

app.whenReady().then(() => {
  createSplash();
  createMainWindow();
  startStreamlit();
  monitorStreamlit();

  // 🔄 Auto-update
  autoUpdater.checkForUpdatesAndNotify();

  autoUpdater.on("update-downloaded", () => {
    dialog.showMessageBox({
      title: "Mise à jour prête",
      message:
        "Une nouvelle version d’ASF Scheduler a été téléchargée. Elle sera installée au prochain redémarrage."
    });
  });
});

app.on("window-all-closed", () => {
  if (streamlitProcess) {
    streamlitProcess.kill();
  }
  if (process.platform !== "darwin") {
    app.quit();
  }
});

ipcMain.on("log", (_, msg) => {
  if (splashWindow) {
    splashWindow.webContents.send("log", msg);
  }
});
