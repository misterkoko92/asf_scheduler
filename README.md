# ✈️ ASF Scheduler  
Gestion automatisée du planning Messagerie Médicale & Fret Humanitaire  
*Aviation Sans Frontières – Desktop App (macOS & Windows)*

![GitHub Release](https://img.shields.io/github/v/release/misterkoko92/asf_scheduler)
![Build CI](https://img.shields.io/github/actions/workflow/status/misterkoko92/asf_scheduler/build.yml)
![Auto Update](https://img.shields.io/badge/auto--update-enabled-brightgreen)
![Platforms](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-orange)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## 🚀 Présentation

ASF Scheduler permet :

- 📦 Planification automatique des expéditions (BE)
- ✈️ Gestion des vols, capacités, bénévoles
- 📄 Génération des PDFs & Excel
- 📬 Génération des emails (destinations / ASF / expéditeurs)
- 💬 WhatsApp / Outlook Mac / Outlook Windows
- 📊 Interface Streamlit en mode Desktop (via Electron)

L’application fonctionne **offline**, en gardant une interface moderne.

---

## 📥 Installation

### 🔹 macOS

Télécharger le `.dmg` ou `.zip` depuis :  
👉 https://github.com/misterkoko92/asf_scheduler/releases

Étapes :

1. Ouvrir le `.dmg`
2. Glisser *ASF Scheduler.app* dans *Applications*
3. Lancer l’application

### 🔹 Windows

Télécharger le `.exe` depuis :  
👉 https://github.com/misterkoko92/asf_scheduler/releases

Suivre l’installation classique.

---

## 🔄 Auto-update

Les versions Windows `.exe` et macOS `.zip` se mettent à jour automatiquement :  

- Le système vérifie les mises à jour via GitHub Releases  
- Télécharge la nouvelle version  
- Installe au prochain démarrage  
- Aucun téléchargement manuel nécessaire  

---

## 🛠 Technologies utilisées

**Backend :**

- Python 3.11/3.13
- Streamlit
- Pandas, OpenPyXL

**Frontend :**

- Electron 31
- Electron-Updater
- Splash Screen + Preload

**Build :**

- Electron-Builder
- GitHub Actions (macOS + Windows)
- Publication automatique en Releases

---

## 📦 Structure du projet

