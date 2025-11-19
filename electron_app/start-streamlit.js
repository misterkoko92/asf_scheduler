// start-streamlit.js — Lancement de Streamlit (dev & app packagée)

const path = require("path");
const { spawn } = require("child_process");
const waitOn = require("wait-on");
const { app } = require("electron");

function getPythonAndScript(port) {
  const isDev = !app.isPackaged;

  if (isDev) {
    // Mode développement : on utilise le venv local
    const projectRoot = path.resolve(__dirname, "..");
    const pythonPath = path.join(projectRoot, "venv", "bin", "python3");
    const scriptPath = path.join(projectRoot, "app.py");
    return { pythonPath, scriptPath };
  }

  // Mode packagé : ressources à l'intérieur de l'app
  const resources = process.resourcesPath;
  const pythonPath = path.join(resources, "venv", "bin", "python3");
  const scriptPath = path.join(resources, "app.py");
  return { pythonPath, scriptPath };
}

function launchStreamlit(port = 8501) {
  const { pythonPath, scriptPath } = getPythonAndScript(port);

  console.log("➡️ Lancement Streamlit");
  console.log("   Python :", pythonPath);
  console.log("   Script :", scriptPath);

  const args = [
    "-m",
    "streamlit",
    "run",
    scriptPath,
    "--server.port",
    String(port),
    "--server.headless",
    "true",
    "--browser.serverAddress",
    "localhost"
  ];

  const child = spawn(pythonPath, args, {
    env: {
      ...process.env,
      PYTHONUNBUFFERED: "1"
    },
    cwd: path.dirname(scriptPath)
  });

  child.stdout.on("data", data => {
    console.log("[Streamlit]", data.toString());
  });

  child.stderr.on("data", data => {
    console.error("[Streamlit ERR]", data.toString());
  });

  child.on("close", code => {
    console.log("ℹ️ Streamlit quitté avec le code :", code);
  });

  return child;
}

function waitForStreamlit(port = 8501) {
  return new Promise((resolve, reject) => {
    console.log("⏳ Attente de http://localhost:" + port);

    waitOn(
      {
        resources: [`http://localhost:${port}`],
        timeout: 30000,
        interval: 500
      },
      err => {
        if (err) {
          return reject(err);
        }
        resolve();
      }
    );
  });
}

module.exports = {
  launchStreamlit,
  waitForStreamlit
};
