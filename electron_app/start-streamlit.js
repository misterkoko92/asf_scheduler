const { spawn } = require('child_process');
const path = require('path');

const streamlit = spawn('python3', [
  '-m',
  'streamlit',
  'run',
  path.join(__dirname, '..', 'app.py'),
  '--server.headless=true'
]);

streamlit.stdout.on('data', (d) => console.log(`[Streamlit] ${d}`));
streamlit.stderr.on('data', (d) => console.error(`[Streamlit ERROR] ${d}`));

