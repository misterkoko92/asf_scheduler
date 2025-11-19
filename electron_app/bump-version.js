// bump-version.js — incrémente la version, commit, tag, push

const fs = require("fs");
const { execSync } = require("child_process");
const path = require("path");

function run(cmd) {
  console.log("▶", cmd);
  return execSync(cmd, { stdio: "inherit" });
}

function bump() {
  const pkgPath = path.join(__dirname, "package.json");
  const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));

  const parts = pkg.version.split(".").map(n => parseInt(n, 10));
  parts[2] += 1; // patch++
  const newVersion = parts.join(".");

  pkg.version = newVersion;
  fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n", "utf8");

  console.log(`📦 Nouvelle version : ${newVersion}`);

  // Commit, tag, push
  run(`git add ${pkgPath}`);
  run(`git commit -m "bump version to ${newVersion}"`);
  run(`git tag v${newVersion}`);
  run("git push");
  run("git push --tags");
}

bump();
