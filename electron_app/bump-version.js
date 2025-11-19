const fs = require('fs');
const cp = require('child_process');

const pkgPath = './package.json';
const pkg = JSON.parse(fs.readFileSync(pkgPath));

const old = pkg.version.split('.').map(n => parseInt(n));
old[2] += 1;  // patch++
pkg.version = old.join('.');

fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2));

console.log(`📦 Nouvelle version : ${pkg.version}`);

cp.execSync(`git add ${pkgPath}`);
cp.execSync(`git commit -m "bump version to ${pkg.version}"`);
cp.execSync(`git tag v${pkg.version}`);
cp.execSync(`git push && git push --tags`);
