import fs from 'node:fs';
import path from 'node:path';
import { parse } from '@babel/parser';

const root = path.resolve('src');
const files = [];

function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(fullPath);
    else if (/\.(jsx?|mjs|cjs)$/.test(entry.name)) files.push(fullPath);
  }
}

walk(root);
const errors = [];

for (const file of files) {
  try {
    parse(fs.readFileSync(file, 'utf8'), {
      sourceType: 'module',
      plugins: ['jsx', 'classProperties', 'optionalChaining', 'nullishCoalescingOperator', 'topLevelAwait'],
    });
  } catch (error) {
    errors.push(`${path.relative(process.cwd(), file)}: ${error.message}`);
  }
}

if (errors.length) {
  console.error('Frontend syntax check failed:');
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(`Frontend syntax check passed: ${files.length} JS/JSX files.`);
