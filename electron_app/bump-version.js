const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const packagePath = path.join(__dirname, "package.json");

// Lire package.json
const pkg = JSON.parse(fs.readFileSync(packagePath));

// extraire la version
let [major, minor, patch] = pkg.version.split(".").map(Number);

// incrémenter
patch += 1;

const newVersion = `${major}.${minor}.${patch}`;
pkg.version = newVersion;

// écrire
fs.writeFileSync(packagePath, JSON.stringify(pkg, null, 2));

console.log("📦 Nouvelle version :", newVersion);

// commit + tag
execSync("git add .");
execSync(`git commit -m "Auto bump to v${newVersion}"`);
execSync(`git tag v${newVersion}`);
execSync("git push --follow-tags");

console.log("🚀 Tag envoyé : v" + newVersion);
