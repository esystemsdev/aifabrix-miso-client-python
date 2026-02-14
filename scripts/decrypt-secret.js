const fs = require('fs');
const path = require('path');
const scriptDir = path.resolve(__dirname, process.argv[2]);
const secretsModule = path.join(scriptDir, 'lib/utils/secrets-encryption.js');
const m = require(secretsModule);
const enc = fs.readFileSync(process.argv[3], 'utf8').trim();
const key = fs.readFileSync(process.argv[4], 'utf8').trim();
console.log(m.decryptSecret(enc, key));
