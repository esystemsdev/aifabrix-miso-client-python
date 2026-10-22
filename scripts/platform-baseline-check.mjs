#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const CHECKER_DIRECTORY = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_ROOT = path.resolve(CHECKER_DIRECTORY, '..');
const DEFAULT_BASELINE = 'platform-baseline.yaml';

function fail(message) {
  throw new Error(message);
}

async function loadYaml(source, label) {
  let yaml;
  try {
    yaml = await import('js-yaml');
  } catch {
    fail(`${label}: js-yaml is required; install the repository's development dependencies`);
  }
  try {
    return yaml.load(source);
  } catch (error) {
    fail(`${label}: invalid YAML (${error.message})`);
  }
}

async function loadPnpmLock(source, label, baseline) {
  let yaml;
  try {
    yaml = await import('js-yaml');
  } catch {
    fail(`${label}: js-yaml is required; install the repository's development dependencies`);
  }
  const documents = [];
  try {
    yaml.loadAll(source, (document) => documents.push(document));
  } catch (error) {
    fail(`${label}: invalid pnpm lock YAML (${error.message})`);
  }
  if (documents.length < 1 || documents.length > 2) {
    fail(`${label}: pnpm 12 lock must contain a project document with an optional leading environment document`);
  }
  const environment = documents.length === 2 ? documents[0] : undefined;
  const project = documents.at(-1);
  const expectedLock = baseline.platform.lockfileVersion;
  const expectedPnpm = baseline.platform.pnpmVersion;
  if (String(project?.lockfileVersion) !== expectedLock) {
    fail(`${label}: project lockfileVersion must be ${expectedLock}`);
  }
  if (environment) {
    if (String(environment?.lockfileVersion) !== expectedLock) {
      fail(`${label}: environment lockfileVersion must be ${expectedLock}`);
    }
    const manager = environment?.importers?.['.']?.packageManagerDependencies?.pnpm;
    if (manager?.specifier !== expectedPnpm || manager?.version !== expectedPnpm) {
      fail(`${label}: environment document must pin pnpm ${expectedPnpm}`);
    }
  }
  if (!project?.settings || typeof project.settings !== 'object' || !project?.importers || typeof project.importers !== 'object') {
    fail(`${label}: final project document must declare settings and importers`);
  }
  return project;
}

async function loadToml(source, label) {
  let toml;
  try {
    toml = await import('smol-toml');
  } catch {
    fail(`${label}: smol-toml is required; install the repository's development dependencies`);
  }
  try {
    return toml.parse(source);
  } catch (error) {
    fail(`${label}: invalid TOML (${error.message})`);
  }
}

function readRequired(file, label) {
  if (!fs.existsSync(file)) fail(`${label}: required file is missing`);
  return fs.readFileSync(file, 'utf8');
}

function propertyPath(value) {
  if (Array.isArray(value)) return value;
  if (typeof value !== 'string' || value.length === 0) fail('check path must be a string or array');
  return value.split('.').flatMap((part) => {
    const result = [];
    const matcher = /([^\[\]]+)|\[(\d+)\]/g;
    for (const match of part.matchAll(matcher)) result.push(match[1] ?? Number(match[2]));
    return result;
  });
}

function getAtPath(document, requestedPath, label) {
  let current = document;
  for (const key of propertyPath(requestedPath)) {
    if (current === null || current === undefined || !Object.hasOwn(current, key)) {
      fail(`${label}: missing property ${propertyPath(requestedPath).join('.')}`);
    }
    current = current[key];
  }
  return current;
}

function hasAtPath(document, requestedPath) {
  let current = document;
  for (const key of propertyPath(requestedPath)) {
    if (current === null || current === undefined || !Object.hasOwn(current, key)) return false;
    current = current[key];
  }
  return true;
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stable(value[key])]));
  }
  return value;
}

function same(left, right) {
  return JSON.stringify(stable(left)) === JSON.stringify(stable(right));
}

function display(value) {
  return typeof value === 'string' ? JSON.stringify(value) : JSON.stringify(value);
}

function expectedValue(check, baseline, label) {
  if (Object.hasOwn(check, 'expected')) return check.expected;
  if (check.expectedFrom) return getAtPath(baseline, check.expectedFrom, `${label} expectedFrom`);
  fail(`${label}: check requires expected or expectedFrom`);
}

function assertValue(actual, check, baseline, label) {
  const operator = check.operator ?? 'equals';
  const expected = expectedValue(check, baseline, label);
  if (operator === 'equals' && !same(actual, expected)) {
    fail(`${label}: expected ${display(expected)}, received ${display(actual)}`);
  }
  if (operator === 'includes') {
    const matched =
      (typeof actual === 'string' || Array.isArray(actual)) && actual.includes(expected);
    if (!matched) fail(`${label}: expected file content to include ${display(expected)}`);
  }
  if (operator === 'containsAll') {
    if (!Array.isArray(actual) || !Array.isArray(expected)) {
      fail(`${label}: containsAll requires array values`);
    }
    const missing = expected.filter(
      (expectedEntry) => !actual.some((actualEntry) => same(actualEntry, expectedEntry))
    );
    if (missing.length > 0) fail(`${label}: missing ${display(missing)}`);
  }
  if (operator === 'matches') {
    if (typeof actual !== 'string' || !new RegExp(expected, check.flags ?? '').test(actual)) {
      fail(`${label}: value does not match /${expected}/${check.flags ?? ''}`);
    }
  }
  if (operator === 'noneMatch') {
    if (!Array.isArray(actual)) fail(`${label}: noneMatch requires an array value`);
    const matched = actual.find(
      (entry) => typeof entry === 'string' && new RegExp(expected, check.flags ?? '').test(entry)
    );
    if (matched !== undefined) fail(`${label}: unexpected matching entry ${display(matched)}`);
  }
  if (operator === 'everyEquals') {
    if (!Array.isArray(actual)) fail(`${label}: everyEquals requires an array value`);
    const memberPath = propertyPath(check.memberPath);
    const mismatched = actual.find((entry) => {
      try {
        return !same(getAtPath(entry, memberPath, label), expected);
      } catch {
        return true;
      }
    });
    if (mismatched !== undefined) {
      fail(`${label}: every ${memberPath.join('.')} must equal ${display(expected)}`);
    }
  }
  if (operator === 'versionFloor' || operator === 'sameMajorFloor') {
    const declaration = (value) => {
      const match = String(value)
        .trim()
        .match(/^(\^|~|>=)?\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?$/);
      if (!match) {
        fail(
          `${label}: unsupported version declaration ${display(value)}; use exact, caret, tilde or >= syntax`
        );
      }
      return {
        operator: match[1] ?? 'exact',
        version: match.slice(2).map((part) => Number(part ?? 0))
      };
    };
    const leftDeclaration = declaration(actual);
    const rightDeclaration = declaration(expected);
    const left = leftDeclaration.version;
    const right = rightDeclaration.version;
    const comparison = left[0] - right[0] || left[1] - right[1] || left[2] - right[2];
    if (operator === 'sameMajorFloor') {
      if (!['^', '~', 'exact'].includes(leftDeclaration.operator)) {
        fail(`${label}: same-major declaration must use exact, caret or tilde syntax`);
      }
      if (left[0] !== right[0]) {
        fail(`${label}: expected major ${right[0]}, received ${display(actual)}`);
      }
    }
    if (comparison < 0) fail(`${label}: expected at least ${display(expected)}, received ${display(actual)}`);
  }
  if (
    ![
      'equals',
      'includes',
      'containsAll',
      'matches',
      'noneMatch',
      'everyEquals',
      'versionFloor',
      'sameMajorFloor'
    ].includes(operator)
  ) {
    fail(`${label}: unsupported operator ${operator}`);
  }
}

async function parseDocument(source, format, label, baseline) {
  if (format === 'json') {
    try {
      return JSON.parse(source);
    } catch (error) {
      fail(`${label}: invalid JSON (${error.message})`);
    }
  }
  if (format === 'yaml') return loadYaml(source, label);
  if (format === 'pnpmLock') return loadPnpmLock(source, label, baseline);
  if (format === 'toml') return loadToml(source, label);
  if (['text', 'python', 'dockerfile', 'globText'].includes(format)) return source;
  fail(`${label}: unsupported format ${format}`);
}

async function executeCheck(root, check, baseline, index) {
  const label = `${check.id ?? `check-${index + 1}`} (${check.file})`;
  const file = path.resolve(root, check.file);
  let source;
  if (check.format === 'globText') {
    if (!fs.existsSync(file) || !fs.statSync(file).isDirectory()) {
      fail(`${label}: required directory is missing`);
    }
    const files = fs
      .readdirSync(file)
      .filter((entry) => /\.ya?ml$/.test(entry))
      .sort();
    if (files.length === 0) fail(`${label}: no YAML files found`);
    source = files.map((entry) => fs.readFileSync(path.join(file, entry), 'utf8')).join('\n');
  } else {
    source = readRequired(file, label);
  }
  const document = await parseDocument(source, check.format, label, baseline);
  if (check.operator === 'absent') {
    if (!check.path) fail(`${label}: absent requires path`);
    if (hasAtPath(document, check.path)) fail(`${label}: property ${propertyPath(check.path).join('.')} must be absent`);
    return label;
  }
  if (check.operator === 'exists') {
    if (!check.path) fail(`${label}: exists requires path`);
    if (!hasAtPath(document, check.path)) fail(`${label}: property ${propertyPath(check.path).join('.')} is required`);
    return label;
  }
  const actual = check.path ? getAtPath(document, check.path, label) : document;
  assertValue(actual, check, baseline, label);
  return label;
}

function resolveProfile(baseline, profileName) {
  if (!baseline || baseline.schemaVersion !== 1) fail('platform baseline schemaVersion must be 1');
  if (!baseline.profiles || typeof baseline.profiles !== 'object') {
    fail('platform baseline must declare profiles');
  }
  const profile = baseline.profiles[profileName];
  if (!profile) fail(`unknown platform baseline profile ${profileName}`);
  if (!Array.isArray(profile.checks) || profile.checks.length === 0) {
    fail(`profile ${profileName} must declare at least one check`);
  }
  return profile;
}

function parseArguments(argv) {
  const options = { root: DEFAULT_ROOT, baseline: DEFAULT_BASELINE };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (
      ![
        '--root',
        '--baseline',
        '--profile',
        '--canonical-baseline',
        '--canonical-checker'
      ].includes(argument)
    ) {
      fail(`unknown argument ${argument}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) fail(`${argument} requires a value`);
    options[argument.slice(2).replaceAll('-', '_')] = value;
    index += 1;
  }
  if (!options.profile) fail('--profile is required');
  options.root = path.resolve(options.root);
  options.baseline = path.resolve(options.root, options.baseline);
  if (options.canonical_baseline) {
    options.canonical_baseline = path.resolve(options.root, options.canonical_baseline);
  }
  if (options.canonical_checker) {
    options.canonical_checker = path.resolve(options.root, options.canonical_checker);
  }
  return options;
}

export async function checkPlatformBaseline(options) {
  const baselineSource = readRequired(options.baseline, 'platform baseline');
  const baseline = await loadYaml(baselineSource, options.baseline);
  const profile = resolveProfile(baseline, options.profile);
  const canonicalRoot = profile.canonicalSiblingRoot
    ? path.resolve(options.root, profile.canonicalSiblingRoot)
    : undefined;
  const canonicalBaseline =
    options.canonical_baseline ??
    (canonicalRoot ? path.join(canonicalRoot, DEFAULT_BASELINE) : undefined);
  const canonicalChecker =
    options.canonical_checker ??
    (canonicalRoot ? path.join(canonicalRoot, 'scripts/platform-baseline-check.mjs') : undefined);
  const passed = [];
  const failures = [];
  for (const requiredFile of profile.requiredFiles ?? []) {
    if (!fs.existsSync(path.resolve(options.root, requiredFile))) {
      failures.push(`profile ${options.profile}: required file ${requiredFile} is missing`);
    }
  }
  for (const forbiddenFile of profile.forbiddenFiles ?? []) {
    if (fs.existsSync(path.resolve(options.root, forbiddenFile))) {
      failures.push(`profile ${options.profile}: forbidden file ${forbiddenFile} is present`);
    }
  }
  for (const [index, check] of profile.checks.entries()) {
    try {
      passed.push(await executeCheck(options.root, check, baseline, index));
    } catch (error) {
      failures.push(error.message);
    }
  }
  if (failures.length > 0) fail(failures.join('\n'));

  let baselineParity = 'not-requested';
  if (canonicalBaseline) {
    if (!fs.existsSync(canonicalBaseline)) {
      baselineParity = 'skipped-missing-canonical-sibling';
    } else {
      const canonicalSource = fs.readFileSync(canonicalBaseline);
      if (!Buffer.from(baselineSource).equals(canonicalSource)) {
        fail('local platform baseline differs byte-for-byte from the canonical copy');
      }
      baselineParity = 'passed';
    }
  }

  let checkerParity = 'not-requested';
  if (canonicalChecker) {
    if (!fs.existsSync(canonicalChecker)) {
      checkerParity = 'skipped-missing-canonical-sibling';
    } else {
      const localChecker = fs.readFileSync(fileURLToPath(import.meta.url));
      const canonicalCheckerSource = fs.readFileSync(canonicalChecker);
      if (!localChecker.equals(canonicalCheckerSource)) {
        fail('local platform baseline checker differs byte-for-byte from the canonical copy');
      }
      checkerParity = 'passed';
    }
  }
  return { profile: options.profile, passed, baselineParity, checkerParity };
}

async function main() {
  const result = await checkPlatformBaseline(parseArguments(process.argv.slice(2)));
  for (const label of result.passed) console.log(`PASS ${label}`);
  if (result.baselineParity === 'skipped-missing-canonical-sibling') {
    console.log('SKIP canonical baseline parity: sibling copy is not present');
  } else if (result.baselineParity === 'passed') {
    console.log('PASS canonical baseline parity');
  }
  if (result.checkerParity === 'skipped-missing-canonical-sibling') {
    console.log('SKIP canonical checker parity: sibling copy is not present');
  } else if (result.checkerParity === 'passed') {
    console.log('PASS canonical checker byte parity');
  }
  console.log(`Platform baseline profile ${result.profile} passed`);
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(`Platform baseline check failed: ${error.message}`);
    process.exitCode = 1;
  });
}
