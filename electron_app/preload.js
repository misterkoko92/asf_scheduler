// preload.js — pont entre le renderer et le main process (si besoin plus tard)

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("asfAPI", {
  // Exemple : plus tard, tu pourras exposer des fonctions ici
  ping: () => "pong"
});
